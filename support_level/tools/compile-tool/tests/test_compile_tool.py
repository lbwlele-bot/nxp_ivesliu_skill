from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import importlib.machinery
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest

import yaml


TOOL_PATH = Path(__file__).resolve().parents[1] / "compile-tool"
LOADER = importlib.machinery.SourceFileLoader("compile_tool", str(TOOL_PATH))
SPEC = importlib.util.spec_from_loader(LOADER.name, LOADER)
assert SPEC is not None
compile_tool = importlib.util.module_from_spec(SPEC)
LOADER.exec_module(compile_tool)


def request_data(cwd: Path) -> dict:
    return {
        "schema_version": 1,
        "case": "test-case",
        "parameters": {
            "experimental_lane": {
                "value": "candidate-a",
                "source": "assumption",
            }
        },
        "compile": {
            "target": "linux",
            "steps": [
                {
                    "name": "test-step",
                    "cwd": str(cwd),
                    "env": {},
                    "command": "printf success",
                }
            ],
        },
    }


def write_request(path: Path, data: dict) -> None:
    path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


class CompileToolTests(unittest.TestCase):
    def test_valid_request_has_parameters_and_raw_command_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            request = compile_tool.normalize_request(request_data(root))
            report = compile_tool.render_report(request)

            self.assertIn("[编译前置声明]", report)
            self.assertIn("experimental_lane：candidate-a", report)
            self.assertIn("$ printf success", report)
            self.assertNotIn("Plan hash", report)

    def test_unconstrained_request_does_not_require_board_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data = request_data(Path(temp_dir))
            data["parameters"] = {}
            request = compile_tool.normalize_request(data)
            self.assertEqual(request["parameters"], {})

    def test_parameter_source_must_be_explicit_and_supported(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data = request_data(Path(temp_dir))
            data["parameters"]["experimental_lane"]["source"] = "guessed-by-ai"
            with self.assertRaisesRegex(
                compile_tool.RequestError, "source must be one of"
            ):
                compile_tool.normalize_request(data)

    def test_invalid_cwd_env_and_empty_command_are_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            data = request_data(root)
            data["compile"]["steps"][0]["cwd"] = "relative/path"
            with self.assertRaisesRegex(compile_tool.RequestError, "absolute path"):
                compile_tool.normalize_request(data)

            data = request_data(root)
            data["compile"]["steps"][0]["env"] = {"BAD-NAME": "value"}
            with self.assertRaisesRegex(compile_tool.RequestError, "invalid variable"):
                compile_tool.normalize_request(data)

            data = request_data(root)
            data["compile"]["steps"][0]["command"] = " "
            with self.assertRaisesRegex(compile_tool.RequestError, "must not be empty"):
                compile_tool.normalize_request(data)

    def test_run_executes_current_valid_request_without_plan_hash(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = root / "request.yaml"
            marker = root / "current-request-ran"
            data = request_data(root)
            data["compile"]["steps"][0]["command"] = f"touch {marker}"
            write_request(path, data)
            with redirect_stdout(io.StringIO()):
                result = compile_tool.main(["run", str(path)])

            self.assertEqual(result, 0)
            self.assertTrue(marker.exists())

    def test_run_uses_declared_cwd_env_and_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = root / "request.yaml"
            data = request_data(root)
            data["compile"]["steps"][0]["env"] = {"TEST_VALUE": "bound-value"}
            data["compile"]["steps"][0]["command"] = (
                'printf "%s" "$TEST_VALUE" > result.txt'
            )
            write_request(path, data)
            with redirect_stdout(io.StringIO()):
                result = compile_tool.main(["run", str(path)])

            self.assertEqual(result, 0)
            self.assertEqual((root / "result.txt").read_text(), "bound-value")

    def test_failed_step_stops_following_steps(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            request = request_data(root)
            marker = root / "second-step-ran"
            request["compile"]["steps"] = [
                {
                    "name": "fail-first",
                    "cwd": str(root),
                    "env": {},
                    "command": "exit 7",
                },
                {
                    "name": "must-not-run",
                    "cwd": str(root),
                    "env": {},
                    "command": f"touch {marker}",
                },
            ]
            normalized = compile_tool.normalize_request(request)

            with redirect_stderr(io.StringIO()), redirect_stdout(io.StringIO()):
                result = compile_tool.execute_request(normalized)

            self.assertEqual(result, 7)
            self.assertFalse(marker.exists())


if __name__ == "__main__":
    unittest.main()

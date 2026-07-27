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
        "identity": {
            "soc": "i.MX95",
            "silicon_revision": "B0",
            "chip_package": "19x19",
            "board": "imx95evk19",
            "ddr": "LPDDR5",
            "software_release": "RTE-3.3",
        },
        "identity_notes": {},
        "identity_effects": {
            "soc": "SOC=iMX95",
            "silicon_revision": "REV=B0",
            "chip_package": "mx95lp5 input",
            "board": "i.MX95 19x19 EVK config",
            "ddr": "LPDDR_TYPE=lpddr5",
            "software_release": "RTE 3.3 aligned inputs",
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
    def test_valid_request_has_stable_hash_and_raw_command_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            request = compile_tool.normalize_request(request_data(root))

            first_hash = compile_tool.request_hash(request)
            second_hash = compile_tool.request_hash(request)
            report = compile_tool.render_report(request)

            self.assertEqual(first_hash, second_hash)
            self.assertRegex(first_hash, r"^sha256:[0-9a-f]{64}$")
            self.assertIn("[编译前置声明]", report)
            self.assertIn("Silicon revision：B0", report)
            self.assertIn("$ printf success", report)
            self.assertIn(f"Plan hash：{first_hash}", report)

    def test_missing_unknown_and_empty_identity_values_are_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            for field, value in (
                ("soc", None),
                ("silicon_revision", "unknown"),
                ("chip_package", "TBD"),
                ("board", "TODO"),
                ("ddr", "?"),
                ("software_release", ""),
            ):
                with self.subTest(field=field, value=value):
                    data = request_data(root)
                    if value is None:
                        del data["identity"][field]
                    else:
                        data["identity"][field] = value
                    with self.assertRaises(compile_tool.RequestError):
                        compile_tool.normalize_request(data)

    def test_na_requires_a_reason(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data = request_data(root)
            data["identity"]["ddr"] = "N/A"
            with self.assertRaisesRegex(
                compile_tool.RequestError, r"identity_notes\.ddr"
            ):
                compile_tool.normalize_request(data)

            data["identity_notes"]["ddr"] = "host-only build"
            request = compile_tool.normalize_request(data)
            self.assertEqual(request["identity"]["ddr"], "N/A")

    def test_every_identity_field_requires_an_effect(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data = request_data(Path(temp_dir))
            del data["identity_effects"]["silicon_revision"]
            with self.assertRaisesRegex(
                compile_tool.RequestError, r"identity_effects\.silicon_revision"
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

    def test_changed_request_is_rejected_before_execution(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = root / "request.yaml"
            marker = root / "must-not-exist"
            data = request_data(root)
            write_request(path, data)
            plan_hash = compile_tool.request_hash(compile_tool.load_request(path))

            data["compile"]["steps"][0]["command"] = f"touch {marker}"
            write_request(path, data)
            with redirect_stderr(io.StringIO()), redirect_stdout(io.StringIO()):
                result = compile_tool.main(
                    ["run", str(path), "--plan-hash", plan_hash]
                )

            self.assertEqual(result, 2)
            self.assertFalse(marker.exists())

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
            request = compile_tool.load_request(path)

            with redirect_stdout(io.StringIO()):
                result = compile_tool.main(
                    [
                        "run",
                        str(path),
                        "--plan-hash",
                        compile_tool.request_hash(request),
                    ]
                )

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

from __future__ import annotations

from contextlib import redirect_stdout
import io
from pathlib import Path
import subprocess
import tempfile
import unittest

import yaml

from compile_tool.cli import main
from compile_tool.common import ToolError
from compile_tool.manifest import load_manifest
from compile_tool.planner import assess
from compile_tool.profiles import load_compile_profile, render_project_manifest
from compile_tool.request import load_request


TOOL_DIR = Path(__file__).resolve().parents[1]


def write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def run_git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    return result.stdout.strip()


class ProjectProfileInitTests(unittest.TestCase):
    def test_init_materializes_oei_profile_and_project_policy(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            case_root = Path(temp_dir) / "profile-case"
            case_root.mkdir()
            with redirect_stdout(io.StringIO()):
                result = main(
                    [
                        "init",
                        "imx-oei",
                        "--case-root",
                        str(case_root),
                        "--ref",
                        "lf-6.18.2-1.0.0",
                        "--set",
                        "silicon_revision=B0",
                        "--set",
                        "board=mx95lp5",
                    ]
                )
            self.assertEqual(result, 0)
            path = case_root / "records" / "compile" / "imx-oei" / "manifest.yaml"
            manifest = load_manifest(path)
            self.assertEqual(manifest["target"], "imx-oei")
            self.assertEqual(
                manifest["guards"][0]["policy_path"],
                "code_assets/projects/imx-oei/COMPILE_POLICY.yaml",
            )
            self.assertEqual(
                manifest["exports"]["oei_ddr"]["identity"]["silicon_revision"],
                "B0",
            )
            self.assertEqual(
                manifest["components"]["imx-oei"]["configuration"]["values"][
                    "compile_profile.parameter.board.value"
                ],
                "mx95lp5",
            )

    def test_project_command_guards_and_mkimage_isolation_are_active(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            case_root = Path(temp_dir) / "guard-case"
            case_root.mkdir()
            with redirect_stdout(io.StringIO()):
                self.assertEqual(
                    main(
                        [
                            "init",
                            "imx-oei",
                            "--case-root",
                            str(case_root),
                            "--ref",
                            "lf-6.18.2-1.0.0",
                            "--set",
                            "silicon_revision=B0",
                            "--set",
                            "board=mx95lp5",
                        ]
                    ),
                    0,
                )
            manifest_path = (
                case_root / "records" / "compile" / "imx-oei" / "manifest.yaml"
            )
            manifest = load_manifest(manifest_path)
            build = Path(
                manifest["components"]["imx-oei"]["execution"]["workspace"]
            )
            request_path = manifest_path.parent / "request.yaml"
            request = {
                "schema_version": 2,
                "case": case_root.name,
                "assessment": {
                    "manifest": str(manifest_path),
                    "hash": "sha256:" + "1" * 64,
                },
                "decision": {
                    "scope": ["imx-oei"],
                    "reason": "fixture",
                    "destructive": {},
                },
                "compile": {
                    "target": "imx-oei",
                    "units": [
                        {
                            "component": "imx-oei",
                            "action": "rebuild",
                            "steps": [
                                {
                                    "name": "build-oei",
                                    "cwd": str(build),
                                    "env": {},
                                    "command": "make board=mx95lp5 oei=ddr",
                                }
                            ],
                        }
                    ],
                },
            }
            write_yaml(request_path, request)
            with self.assertRaisesRegex(ToolError, "explicit REV=B0"):
                load_request(request_path, allow_project_checklist_request=True)
            request["compile"]["units"][0]["steps"][0]["command"] = (
                "make board=mx95lp5 oei=ddr REV=B0"
            )
            write_yaml(request_path, request)
            self.assertEqual(
                load_request(
                    request_path,
                    allow_project_checklist_request=True,
                )["compile"]["target"],
                "imx-oei",
            )

        with tempfile.TemporaryDirectory() as temp_dir:
            case_root = Path(temp_dir) / "isolation-case"
            case_root.mkdir()
            with redirect_stdout(io.StringIO()):
                self.assertEqual(
                    main(
                        [
                            "init",
                            "imx-mkimage",
                            "--case-root",
                            str(case_root),
                            "--ref",
                            "lf-6.18.2-1.0.0",
                            "--set",
                            "silicon_revision=B0",
                            "--set",
                            "soc=iMX95",
                            "--set",
                            "recipe=flash_all",
                            "--set",
                            "lpddr_type=lpddr5",
                        ]
                    ),
                    0,
                )
            manifest_path = (
                case_root
                / "records"
                / "compile"
                / "imx-mkimage"
                / "manifest.yaml"
            )
            manifest = load_manifest(manifest_path)
            workspace = manifest["components"]["imx-mkimage"]["execution"]["workspace"]
            (case_root / "build").mkdir()
            request_path = manifest_path.parent / "request.yaml"
            request = {
                "schema_version": 2,
                "case": case_root.name,
                "assessment": {
                    "manifest": str(manifest_path),
                    "hash": "sha256:" + "1" * 64,
                },
                "decision": {
                    "scope": ["imx-mkimage"],
                    "reason": "fixture",
                    "destructive": {},
                },
                "compile": {
                    "target": "imx-mkimage",
                    "units": [
                        {
                            "component": "imx-mkimage",
                            "action": "repack",
                            "steps": [
                                {
                                    "name": "package",
                                    "cwd": str(case_root / "build"),
                                    "env": {},
                                    "command": "make SOC=iMX95 REV=B0 flash_all",
                                }
                            ],
                        }
                    ],
                },
            }
            write_yaml(request_path, request)
            with self.assertRaisesRegex(ToolError, "requires isolated_git"):
                load_request(request_path, allow_project_checklist_request=True)
            request["compile"]["units"][0]["steps"][0]["cwd"] = workspace
            write_yaml(request_path, request)
            self.assertEqual(
                load_request(
                    request_path,
                    allow_project_checklist_request=True,
                )["compile"]["target"],
                "imx-mkimage",
            )

    def test_required_values_profile_hash_and_required_slot_are_enforced(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            case_root = Path(temp_dir) / "draft-case"
            case_root.mkdir()
            with redirect_stdout(io.StringIO()):
                self.assertEqual(
                    main(["init", "imx-oei", "--case-root", str(case_root)]),
                    0,
                )
            path = case_root / "records" / "compile" / "imx-oei" / "manifest.yaml"
            with self.assertRaisesRegex(ToolError, "ask the user|must be resolved"):
                load_manifest(path)

        with tempfile.TemporaryDirectory() as temp_dir:
            case_root = Path(temp_dir) / "hash-case"
            case_root.mkdir()
            with redirect_stdout(io.StringIO()):
                self.assertEqual(
                    main(
                        [
                            "init",
                            "imx-oei",
                            "--case-root",
                            str(case_root),
                            "--ref",
                            "lf-6.18.2-1.0.0",
                            "--set",
                            "silicon_revision=B0",
                            "--set",
                            "board=mx95lp5",
                        ]
                    ),
                    0,
                )
            path = case_root / "records" / "compile" / "imx-oei" / "manifest.yaml"
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            data["project_profile"]["hash"] = "sha256:" + "0" * 64
            write_yaml(path, data)
            with self.assertRaisesRegex(ToolError, "profile hash mismatch"):
                load_manifest(path)

        with tempfile.TemporaryDirectory() as temp_dir:
            case_root = Path(temp_dir) / "slot-case"
            case_root.mkdir()
            with redirect_stdout(io.StringIO()):
                self.assertEqual(
                    main(
                        [
                            "init",
                            "imx-mkimage",
                            "--case-root",
                            str(case_root),
                            "--ref",
                            "lf-6.18.2-1.0.0",
                            "--set",
                            "silicon_revision=B0",
                            "--set",
                            "soc=iMX95",
                            "--set",
                            "recipe=flash_all",
                            "--set",
                            "lpddr_type=lpddr5",
                            "--set",
                            "oei_enabled=YES",
                        ]
                    ),
                    0,
                )
            path = (
                case_root
                / "records"
                / "compile"
                / "imx-mkimage"
                / "manifest.yaml"
            )
            with self.assertRaisesRegex(ToolError, "slot oei is required"):
                load_manifest(path)


class ArtifactFixture:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.support = root / "support_level"
        self.case_root = self.support / "work" / "artifact-case"
        self.case_root.mkdir(parents=True)
        self.tool = self.support / "tools" / "fixture-compiler"
        self.tool.parent.mkdir(parents=True)
        self.tool.write_text("#!/bin/sh\nprintf 'fixture compiler 1.0\\n'\n")
        self.tool.chmod(0o755)
        self.producer_path, self.producer_output = self._make_project(
            "producer",
            output_type="fixture.binary",
            artifact_inputs={},
        )
        self.consumer_path, self.consumer_output = self._make_project(
            "consumer",
            output_type="fixture.container",
            artifact_inputs={
                "producer": {
                    "type": "fixture.binary",
                    "multiple": False,
                    "parameter_matches": {
                        "silicon_revision": "silicon_revision"
                    },
                }
            },
        )

    def _make_project(
        self,
        project: str,
        *,
        output_type: str,
        artifact_inputs: dict,
    ) -> tuple[Path, Path]:
        project_root = self.support / "code_assets" / "projects" / project
        source = project_root / "source"
        source.mkdir(parents=True)
        run_git(source, "init")
        run_git(source, "config", "user.email", "fixture@example.com")
        run_git(source, "config", "user.name", "Fixture")
        (source / "source.txt").write_text(f"{project}-source-v1\n")
        run_git(source, "add", "source.txt")
        run_git(source, "commit", "-m", "initial")
        run_git(source, "tag", "release-v1")
        run_git(
            source,
            "remote",
            "add",
            "origin",
            f"https://fixture.invalid/{project}",
        )
        output = self.case_root / "artifacts" / project / "output.bin"
        profile_data = {
            "schema_version": 1,
            "id": project,
            "type": "project_compile",
            "target": project,
            "component": project,
            "source": {
                "id": project,
                "path": "source",
                "case_path": f"sources/{project}",
                "ref_kind": "tag",
                "remote": "origin",
                "remote_url": f"https://fixture.invalid/{project}",
                "update": "if_missing",
            },
            "parameters": {
                "silicon_revision": {"source": "user", "required": True}
            },
            "configuration_parameters": ["silicon_revision"],
            "tools": [
                {
                    "name": "compiler",
                    "path": "tools/fixture-compiler",
                    "version_args": [],
                }
            ],
            "watched_inputs": [],
            "outputs": {
                "image": {
                    "type": output_type,
                    "path": f"artifacts/{project}/output.bin",
                    "identity_parameters": ["silicon_revision"],
                }
            },
            "artifact_inputs": artifact_inputs,
        }
        profile_path = project_root / "COMPILE_PROFILE.yaml"
        write_yaml(profile_path, profile_data)
        profile = load_compile_profile(profile_path)
        manifest_path, manifest_data = render_project_manifest(
            profile,
            self.case_root,
            ref="release-v1",
            parameter_values=["silicon_revision=B0"],
        )
        write_yaml(manifest_path, manifest_data)
        case_source = self.case_root / "sources" / project
        case_source.parent.mkdir(parents=True, exist_ok=True)
        run_git(self.root, "clone", str(source), str(case_source))
        run_git(case_source, "checkout", "--detach", "release-v1")
        return manifest_path, output

    def connect_consumer(self, *, revision: str = "B0") -> None:
        data = yaml.safe_load(self.consumer_path.read_text(encoding="utf-8"))
        data["parameters"]["silicon_revision"]["value"] = revision
        data["artifact_inputs"] = {
            "producer_image": {
                "slot": "producer",
                "manifest": str(self.producer_path),
                "artifact": "image",
            }
        }
        write_yaml(self.consumer_path, data)

    def run_target(self, manifest_path: Path, output: Path, command: str) -> None:
        manifest = load_manifest(manifest_path)
        result = assess(manifest)
        component = manifest["component_order"][0]
        build = self.case_root / "build" / manifest["target"]
        build.mkdir(parents=True, exist_ok=True)
        output.parent.mkdir(parents=True, exist_ok=True)
        request_path = manifest_path.parent / "request.yaml"
        request = {
            "schema_version": 2,
            "case": self.case_root.name,
            "assessment": {
                "manifest": str(manifest_path),
                "hash": result["assessment_hash"],
            },
            "decision": {
                "scope": [component],
                "reason": "fixture project build",
                "destructive": {},
            },
            "compile": {
                "target": manifest["target"],
                "units": [
                    {
                        "component": component,
                        "action": "rebuild",
                        "steps": [
                            {
                                "name": f"build-{component}",
                                "cwd": str(build),
                                "env": {},
                                "command": command,
                            }
                        ],
                    }
                ],
            },
        }
        write_yaml(request_path, request)
        with redirect_stdout(io.StringIO()):
            self.assert_result(main(["run", str(request_path)]), output)

    @staticmethod
    def assert_result(result: int, output: Path) -> None:
        if result != 0 or not output.is_file():
            raise AssertionError(
                f"project build failed: result={result}, output={output}"
            )


class CrossManifestArtifactTests(unittest.TestCase):
    def test_artifact_requires_successful_producer_and_tracks_producer_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = ArtifactFixture(Path(temp_dir))
            fixture.connect_consumer()
            with self.assertRaisesRegex(ToolError, "no successful software state"):
                assess(load_manifest(fixture.consumer_path))

            fixture.run_target(
                fixture.producer_path,
                fixture.producer_output,
                f"printf 'producer-v1' > {fixture.producer_output}",
            )
            consumer = load_manifest(fixture.consumer_path)
            first = assess(consumer)
            self.assertEqual(
                first["observed_units"],
                [{"component": "consumer", "action": "rebuild"}],
            )
            artifact = first["snapshots"]["consumer"]["artifact_inputs"][
                "producer_image"
            ]
            self.assertEqual(artifact["producer_target"], "producer")
            self.assertEqual(artifact["identity"]["silicon_revision"], "B0")

            fixture.run_target(
                fixture.consumer_path,
                fixture.consumer_output,
                f"cp {fixture.producer_output} {fixture.consumer_output}",
            )
            self.assertEqual(assess(load_manifest(fixture.consumer_path))["state_summary"], "MATCHED")

            producer_source = fixture.case_root / "sources" / "producer" / "source.txt"
            producer_source.write_text("producer-source-v2\n")
            fixture.run_target(
                fixture.producer_path,
                fixture.producer_output,
                f"printf 'producer-v2' > {fixture.producer_output}",
            )
            propagated = assess(load_manifest(fixture.consumer_path))
            self.assertEqual(
                propagated["observed_units"],
                [{"component": "consumer", "action": "rebuild"}],
            )
            self.assertIn(
                "跨项目输入产物或生产者状态变化",
                propagated["observations"]["consumer"]["reasons"],
            )

            fixture.producer_output.write_text("tampered\n")
            with self.assertRaisesRegex(ToolError, "differs from its producer"):
                assess(load_manifest(fixture.consumer_path))

    def test_artifact_identity_mismatch_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = ArtifactFixture(Path(temp_dir))
            fixture.run_target(
                fixture.producer_path,
                fixture.producer_output,
                f"printf 'producer-v1' > {fixture.producer_output}",
            )
            fixture.connect_consumer(revision="A0")
            with self.assertRaisesRegex(ToolError, "identity mismatch"):
                assess(load_manifest(fixture.consumer_path))


if __name__ == "__main__":
    unittest.main()

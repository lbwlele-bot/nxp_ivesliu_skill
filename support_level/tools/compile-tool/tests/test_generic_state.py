from __future__ import annotations

import io
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from unittest import mock
import zipfile

import yaml

from compile_tool.common import ToolError, hash_data
from compile_tool.manifest import load_manifest
from compile_tool.planner import assess
from compile_tool.request import load_request
from compile_tool.sources import execute_acquisition
from compile_tool.state import load_state, write_state


TOOL_PATH = Path(__file__).resolve().parents[1] / "compile-tool"


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


class GenericFixture:
    def __init__(self, root: Path, target: str = "linux") -> None:
        self.root = root
        self.target = target
        self.case_root = root / "support_level" / "work" / "generic-case"
        self.records = self.case_root / "records" / "compile" / target
        self.build = self.case_root / "build" / target
        self.inputs = self.case_root / "sources" / target
        self.records.mkdir(parents=True)
        self.build.mkdir(parents=True)
        self.inputs.mkdir(parents=True)
        self.source = self.inputs / "source.c"
        self.source.write_text("source-v1\n")
        self.tool = self.case_root / f"{target}-compiler"
        self.tool.write_text("#!/bin/sh\nprintf 'fixture compiler 1.0\\n'\n")
        self.tool.chmod(0o755)
        self.outputs = {
            "image": self.build / "Image",
            "dtb": self.build / "board.dtb",
        }
        self.manifest_data = {
            "schema_version": 2,
            "case": self.case_root.name,
            "case_root": str(self.case_root),
            "target": target,
            "parameters": {},
            "sources": {
                "tree": {
                    "kind": "local_files",
                    "paths": [str(self.source)],
                }
            },
            "components": {
                component: self.component(component)
                for component in self.outputs
            },
        }
        self.manifest_path = self.records / "manifest.yaml"
        self.write_manifest()

    def component(self, component: str) -> dict:
        return {
            "sources": ["tree"],
            "configuration": {
                "values": {"target": component},
                "files": [],
            },
            "tools": [
                {
                    "name": "compiler",
                    "executable": str(self.tool),
                    "version_args": [],
                }
            ],
            "watched_inputs": [],
            "outputs": [str(self.outputs[component])],
            "depends_on": [],
        }

    def write_manifest(self) -> None:
        write_yaml(self.manifest_path, self.manifest_data)

    def manifest(self) -> dict:
        return load_manifest(self.manifest_path)

    def use_managed_git_source(self) -> Path:
        canonical = (
            self.root
            / "support_level"
            / "code_assets"
            / "projects"
            / self.target
            / "source"
        )
        canonical.mkdir(parents=True)
        run_git(canonical, "init")
        run_git(canonical, "config", "user.email", "fixture@example.com")
        run_git(canonical, "config", "user.name", "Fixture")
        (canonical / "source.c").write_text("managed-source-v1\n")
        run_git(canonical, "add", "source.c")
        run_git(canonical, "commit", "-m", "initial")
        remote_url = f"https://fixture.invalid/{self.target}"
        run_git(canonical, "remote", "add", "origin", remote_url)
        case_source = self.case_root / "sources" / f"{self.target}-managed"
        run_git(canonical, "worktree", "add", "--detach", str(case_source), "HEAD")
        self.manifest_data["sources"]["tree"] = {
            "kind": "managed_git",
            "canonical_path": str(canonical),
            "case_path": str(case_source),
            "ref_kind": "commit",
            "ref": run_git(canonical, "rev-parse", "HEAD"),
            "remote": "origin",
            "remote_url": remote_url,
            "update": "if_missing",
        }
        self.write_manifest()
        return case_source

    def request(
        self,
        assessment: dict,
        commands: dict[str, str] | None = None,
        *,
        scope: list[str] | None = None,
        unit_components: list[str] | None = None,
        destructive: dict[str, str] | None = None,
        cwd_overrides: dict[str, Path] | None = None,
    ) -> Path:
        commands = commands or {}
        cwd_overrides = cwd_overrides or {}
        observed_actions = {
            item["component"]: item["action"]
            for item in assessment["observed_units"]
        }
        if unit_components is None:
            unit_components = list(observed_actions)
        if scope is None:
            scope = list(unit_components)
        units = []
        for component in unit_components:
            command = commands.get(
                component,
                f"printf '{component}-output' > {self.outputs[component]}",
            )
            units.append(
                {
                    "component": component,
                    "action": observed_actions.get(component, "rebuild"),
                    "steps": [
                        {
                            "name": f"build-{component}",
                            "cwd": str(cwd_overrides.get(component, self.build)),
                            "env": {},
                            "command": command,
                        }
                    ],
                }
            )
        request = {
            "schema_version": 2,
            "case": self.case_root.name,
            "assessment": {
                "manifest": str(self.manifest_path),
                "hash": assessment["assessment_hash"],
            },
            "decision": {
                "scope": scope,
                "reason": "fixture engineering decision",
                "destructive": destructive or {},
            },
            "compile": {"target": self.target, "units": units},
        }
        path = self.records / "request.yaml"
        write_yaml(path, request)
        return path

    def run(
        self,
        assessment: dict,
        commands: dict[str, str] | None = None,
        **request_options: object,
    ) -> subprocess.CompletedProcess[str]:
        path = self.request(assessment, commands, **request_options)
        return subprocess.run(
            [
                str(TOOL_PATH),
                "run",
                str(path),
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )


class GenericStateTests(unittest.TestCase):
    def test_managed_git_build_cwd_requires_external_or_isolated_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = GenericFixture(Path(temp_dir), target="custom-os")
            fixture.manifest_data["components"] = {
                "image": fixture.component("image")
            }
            case_source = fixture.use_managed_git_source()
            assessment = assess(fixture.manifest())
            request_path = fixture.request(
                assessment,
                cwd_overrides={"image": case_source},
            )
            with self.assertRaisesRegex(ToolError, "without an isolated_git"):
                load_request(request_path)

            request_path = fixture.request(assessment)
            self.assertEqual(
                load_request(request_path)["compile"]["units"][0]["steps"][0][
                    "cwd"
                ],
                str(fixture.build),
            )

    def test_arbitrary_target_and_missing_dtb_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = GenericFixture(Path(temp_dir), target="custom-os")
            first = assess(fixture.manifest())
            self.assertEqual(
                first["observed_units"],
                [
                    {"component": "image", "action": "rebuild"},
                    {"component": "dtb", "action": "rebuild"},
                ],
            )
            result = fixture.run(first)
            self.assertEqual(result.returncode, 0, result.stderr)
            fixture.outputs["dtb"].unlink()
            changed = assess(fixture.manifest())
            self.assertEqual(
                changed["observed_units"],
                [{"component": "dtb", "action": "rebuild"}],
            )

    def test_requirements_has_no_extra_rules_for_unprofiled_generic_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = GenericFixture(Path(temp_dir), target="custom-os")
            result = subprocess.run(
                [str(TOOL_PATH), "requirements", str(fixture.manifest_path)],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("无额外硬规则", result.stdout)

    def test_llm_can_rebuild_when_state_is_matched_and_command_is_audit_only(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = GenericFixture(Path(temp_dir))
            fixture.manifest_data["components"] = {
                "image": fixture.component("image")
            }
            fixture.write_manifest()
            first = assess(fixture.manifest())
            self.assertEqual(fixture.run(first).returncode, 0)
            matched = assess(fixture.manifest())
            self.assertEqual(matched["state_summary"], "MATCHED")

            changed_command = (
                f"printf image-output > {fixture.outputs['image']} # another recipe"
            )
            result = fixture.run(
                matched,
                {"image": changed_command},
                scope=["image"],
                unit_components=["image"],
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            state = load_state(fixture.manifest())
            self.assertNotIn("command_hash", state["components"]["image"])
            self.assertEqual(
                assess(fixture.manifest())["state_summary"],
                "MATCHED",
            )

    def test_observed_changes_do_not_force_every_component_to_execute(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = GenericFixture(Path(temp_dir))
            assessment = assess(fixture.manifest())
            self.assertEqual(len(assessment["observed_units"]), 2)
            result = fixture.run(
                assessment,
                scope=["dtb"],
                unit_components=["dtb"],
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            current = assess(fixture.manifest())
            self.assertEqual(current["observations"]["dtb"]["action"], "reuse")
            self.assertEqual(current["observations"]["image"]["action"], "rebuild")

    def test_scope_allows_explicit_downstream_only_in_topological_order(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = GenericFixture(Path(temp_dir))
            fixture.manifest_data["components"]["dtb"]["depends_on"] = ["image"]
            fixture.write_manifest()
            assessment = assess(fixture.manifest())
            valid = fixture.run(
                assessment,
                scope=["image"],
                unit_components=["image", "dtb"],
            )
            self.assertEqual(valid.returncode, 0, valid.stderr)

        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = GenericFixture(Path(temp_dir))
            fixture.manifest_data["components"]["dtb"]["depends_on"] = ["image"]
            fixture.write_manifest()
            assessment = assess(fixture.manifest())
            path = fixture.request(
                assessment,
                scope=["image"],
                unit_components=["dtb", "image"],
            )
            with self.assertRaisesRegex(ToolError, "dependency order"):
                load_request(path)

    def test_destructive_commands_require_an_explicit_component_reason(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = GenericFixture(Path(temp_dir))
            fixture.manifest_data["components"] = {
                "image": fixture.component("image")
            }
            fixture.write_manifest()
            assessment = assess(fixture.manifest())
            commands = {
                "clean": "make -f /dev/null --eval='clean: ; @:' clean",
                "distclean": (
                    "make -f /dev/null --eval='distclean: ; @:' distclean"
                ),
                "mrproper": (
                    "make -f /dev/null --eval='mrproper: ; @:' mrproper"
                ),
                "really-clean": (
                    "make -f /dev/null --eval='really-clean: ; @:' really-clean"
                ),
                "rm-rf": f"rm -rf {fixture.build / 'throwaway'}",
            }
            for name, destructive_command in commands.items():
                with self.subTest(name=name):
                    blocked = fixture.run(
                        assessment,
                        {
                            "image": (
                                destructive_command
                                + " && "
                                + f"printf image-output > {fixture.outputs['image']}"
                            )
                        },
                        scope=["image"],
                        unit_components=["image"],
                    )
                    self.assertEqual(blocked.returncode, 2)
                    self.assertIn("decision.destructive", blocked.stderr)

            command = (
                commands["clean"]
                + " && "
                + f"printf image-output > {fixture.outputs['image']}"
            )
            allowed = fixture.run(
                assessment,
                {"image": command},
                scope=["image"],
                unit_components=["image"],
                destructive={"image": "configuration requires a clean rebuild"},
            )
            self.assertEqual(allowed.returncode, 0, allowed.stderr)

    def test_multiple_targets_share_one_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            linux = GenericFixture(root, target="linux")
            self.assertEqual(linux.run(assess(linux.manifest())).returncode, 0)
            zephyr = GenericFixture(root, target="zephyr")
            self.assertEqual(zephyr.run(assess(zephyr.manifest())).returncode, 0)
            state = yaml.safe_load(
                (linux.case_root / "state" / "software-state.yaml").read_text()
            )
            self.assertEqual(set(state["targets"]), {"linux", "zephyr"})

    def test_legacy_state_is_migrated_when_generic_target_is_written(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = GenericFixture(Path(temp_dir), target="linux")
            legacy = {
                "schema_version": 1,
                "generated_by": "compile-tool 2.0",
                "case": fixture.case_root.name,
                "target": "flashbin",
                "profile_hash": "sha256:" + "1" * 64,
                "manifest_hash": "sha256:" + "2" * 64,
                "components": {},
            }
            legacy["integrity_hash"] = hash_data(legacy)
            state_path = fixture.case_root / "state" / "software-state.yaml"
            write_yaml(state_path, legacy)
            manifest = fixture.manifest()
            state = load_state(manifest)
            state["components"] = {}
            write_state(manifest, state)
            migrated = yaml.safe_load(state_path.read_text())
            self.assertEqual(migrated["schema_version"], 2)
            self.assertEqual(set(migrated["targets"]), {"flashbin", "linux"})

    def test_watched_input_change_and_unchanged_output_are_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = GenericFixture(Path(temp_dir))
            watched = fixture.inputs / "project"
            watched.mkdir()
            watched_file = watched / "main.c"
            watched_file.write_text("v1\n")
            fixture.manifest_data["components"] = {
                "image": fixture.component("image")
            }
            fixture.manifest_data["components"]["image"]["watched_inputs"] = [
                str(watched)
            ]
            fixture.write_manifest()
            first = assess(fixture.manifest())
            self.assertEqual(fixture.run(first).returncode, 0)
            watched_file.write_text("v2\n")
            changed = assess(fixture.manifest())
            result = fixture.run(changed, {"image": "true"})
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                assess(fixture.manifest())["state_summary"],
                "MATCHED",
            )

    def test_changed_output_must_be_repaired(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = GenericFixture(Path(temp_dir))
            fixture.manifest_data["components"] = {
                "image": fixture.component("image")
            }
            fixture.write_manifest()
            self.assertEqual(
                fixture.run(assess(fixture.manifest())).returncode,
                0,
            )
            fixture.outputs["image"].write_text("tampered\n")
            changed = assess(fixture.manifest())
            result = fixture.run(changed, {"image": "true"})
            self.assertEqual(result.returncode, 2)
            self.assertIn("did not repair changed outputs", result.stderr)

    def test_explicit_dependency_propagates_only_when_declared(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = GenericFixture(Path(temp_dir))
            fixture.manifest_data["components"]["dtb"]["depends_on"] = ["image"]
            fixture.write_manifest()
            self.assertEqual(
                fixture.run(assess(fixture.manifest())).returncode,
                0,
            )
            fixture.outputs["image"].unlink()
            changed = assess(fixture.manifest())
            self.assertEqual(
                changed["observed_units"],
                [
                    {"component": "image", "action": "rebuild"},
                    {"component": "dtb", "action": "rebuild"},
                ],
            )

    def test_failed_downstream_remains_required_after_upstream_is_recorded(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = GenericFixture(Path(temp_dir))
            watched = fixture.inputs / "project"
            watched.mkdir()
            watched_file = watched / "main.c"
            watched_file.write_text("v1\n")
            fixture.manifest_data["components"]["image"]["watched_inputs"] = [
                str(watched)
            ]
            fixture.manifest_data["components"]["dtb"]["depends_on"] = ["image"]
            fixture.write_manifest()
            self.assertEqual(
                fixture.run(assess(fixture.manifest())).returncode,
                0,
            )

            watched_file.write_text("v2\n")
            changed = assess(fixture.manifest())
            failed = fixture.run(
                changed,
                {
                    "image": (
                        f"printf image-v2 > {fixture.outputs['image']}"
                    ),
                    "dtb": "false",
                },
            )
            self.assertEqual(failed.returncode, 1)

            resumed = assess(fixture.manifest())
            self.assertEqual(
                resumed["observed_units"],
                [{"component": "dtb", "action": "rebuild"}],
            )

    def test_west_command_is_preserved_as_raw_text(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = GenericFixture(Path(temp_dir), target="zephyr")
            fixture.manifest_data["components"] = {
                "image": fixture.component("image")
            }
            fixture.write_manifest()
            assessment = assess(fixture.manifest())
            command = (
                "west build -p always -b imx93_evk/mimx9352/a55 "
                "samples/hello_world && printf image > "
                f"{fixture.outputs['image']}"
            )
            path = fixture.request(assessment, {"image": command})
            prepared = subprocess.run(
                [str(TOOL_PATH), "prepare", str(path)],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(prepared.returncode, 0, prepared.stderr)
            self.assertIn(command, prepared.stdout)

    def test_dxl_sdk_29_rejects_wrong_compiler(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = GenericFixture(Path(temp_dir), target="m_freertos_sdk")
            fixture.manifest_data["parameters"]["software_release"] = {
                "value": "SDK_2_9_0_EVK-MIMX8DXL",
                "source": "project",
            }
            fixture.tool.write_text("#!/bin/sh\nprintf 'arm-none-eabi-gcc 14.3\\n'\n")
            fixture.write_manifest()
            with self.assertRaisesRegex(ToolError, "requires GCC ARM Embedded 9.2.1"):
                assess(fixture.manifest())


class GenericAcquisitionTests(unittest.TestCase):
    def _git_source(self, root: Path, name: str) -> tuple[Path, str]:
        canonical = (
            root
            / "support_level"
            / "code_assets"
            / "workspaces"
            / name
        )
        canonical.mkdir(parents=True)
        run_git(canonical, "init", "-q")
        run_git(canonical, "config", "user.name", "fixture")
        run_git(canonical, "config", "user.email", "fixture@example.com")
        (canonical / "source.txt").write_text(name)
        run_git(canonical, "add", "source.txt")
        run_git(canonical, "commit", "-qm", "initial")
        run_git(canonical, "remote", "add", "origin", str(canonical))
        return canonical, run_git(canonical, "rev-parse", "HEAD")

    def test_managed_git_set_uses_local_worktrees(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fixture = GenericFixture(root, target="a55_rtos")
            repositories = []
            for name in ("hmc", "zephyr"):
                canonical, commit = self._git_source(root, name)
                repositories.append(
                    {
                        "name": name,
                        "canonical_path": str(canonical),
                        "case_path": str(fixture.inputs / name),
                        "ref_kind": "commit",
                        "ref": commit,
                        "remote": "origin",
                        "remote_url": str(canonical),
                        "update": "if_missing",
                    }
                )
            fixture.source.unlink()
            fixture.manifest_data["sources"] = {
                "workspace": {
                    "kind": "managed_git_set",
                    "repositories": repositories,
                }
            }
            fixture.manifest_data["components"] = {
                "image": {
                    **fixture.component("image"),
                    "sources": ["workspace"],
                }
            }
            fixture.write_manifest()
            manifest = fixture.manifest()
            acquisition = assess(manifest)
            self.assertEqual(acquisition["status"], "ACQUIRE_REQUIRED")
            result = execute_acquisition(
                manifest, acquisition["source"]["plan_hash"]
            )
            self.assertEqual(result, 0)
            self.assertTrue((fixture.inputs / "hmc" / ".git").exists())
            self.assertTrue((fixture.inputs / "zephyr" / ".git").exists())

    def _archive_fixture(self, root: Path, *, unsafe: bool = False) -> GenericFixture:
        fixture = GenericFixture(root, target="sdk_fixture")
        archive = root / "SDK_fixture.tar.gz"
        with tarfile.open(archive, "w:gz") as handle:
            data = b"fixture source\n"
            member = tarfile.TarInfo(
                "../escape.txt" if unsafe else "sdk/project/main.c"
            )
            member.size = len(data)
            handle.addfile(member, io.BytesIO(data))
        fixture.source.unlink()
        sdk_root = fixture.inputs / "sdk-package"
        fixture.manifest_data["sources"] = {
            "sdk": {
                "kind": "release_archive",
                "archive_path": str(archive),
                "case_path": str(sdk_root),
            }
        }
        fixture.manifest_data["components"] = {
            "image": {
                **fixture.component("image"),
                "sources": ["sdk"],
                "watched_inputs": [str(sdk_root / "sdk" / "project")],
            }
        }
        fixture.write_manifest()
        return fixture

    def test_release_archive_is_extracted_locally(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = self._archive_fixture(Path(temp_dir))
            manifest = fixture.manifest()
            acquisition = assess(manifest)
            self.assertEqual(acquisition["status"], "ACQUIRE_REQUIRED")
            self.assertEqual(
                execute_acquisition(
                    manifest, acquisition["source"]["plan_hash"]
                ),
                0,
            )
            ready = assess(fixture.manifest())
            self.assertEqual(ready["status"], "READY")
            self.assertTrue(
                (fixture.inputs / "sdk-package" / "sdk" / "project" / "main.c").is_file()
            )
            with mock.patch(
                "compile_tool.sources.hash_file",
                side_effect=AssertionError("archive content was rehashed"),
            ):
                self.assertEqual(assess(fixture.manifest())["status"], "READY")

    def test_release_archive_path_traversal_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = self._archive_fixture(Path(temp_dir), unsafe=True)
            with self.assertRaisesRegex(ToolError, "unsafe archive path"):
                assess(fixture.manifest())

    def test_release_zip_is_extracted_and_traversal_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fixture = GenericFixture(root, target="m_freertos_sdk")
            fixture.source.unlink()
            archive = root / "SDK_fixture.zip"
            with zipfile.ZipFile(archive, "w") as handle:
                handle.writestr("sdk/project/main.c", "fixture source\n")
            sdk_root = fixture.inputs / "sdk-package"
            fixture.manifest_data["sources"] = {
                "sdk": {
                    "kind": "release_archive",
                    "archive_path": str(archive),
                    "case_path": str(sdk_root),
                }
            }
            fixture.manifest_data["components"] = {
                "image": {
                    **fixture.component("image"),
                    "sources": ["sdk"],
                    "watched_inputs": [str(sdk_root / "sdk" / "project")],
                }
            }
            fixture.write_manifest()
            manifest = fixture.manifest()
            acquisition = assess(manifest)
            self.assertEqual(
                execute_acquisition(
                    manifest, acquisition["source"]["plan_hash"]
                ),
                0,
            )
            self.assertTrue((sdk_root / "sdk" / "project" / "main.c").is_file())

            unsafe = root / "unsafe.zip"
            with zipfile.ZipFile(unsafe, "w") as handle:
                handle.writestr("../escape.txt", "escape\n")
            fixture.manifest_data["sources"]["sdk"]["archive_path"] = str(unsafe)
            fixture.manifest_data["sources"]["sdk"]["case_path"] = str(
                fixture.inputs / "unsafe-package"
            )
            fixture.write_manifest()
            with self.assertRaisesRegex(ToolError, "unsafe archive path"):
                assess(fixture.manifest())

    def test_cli_assess_acquire_prepare_run_smoke(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = self._archive_fixture(Path(temp_dir))
            manifest = fixture.manifest()
            source_plan = assess(manifest)["source"]["plan_hash"]

            first_assess = subprocess.run(
                [str(TOOL_PATH), "assess", str(fixture.manifest_path)],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(first_assess.returncode, 3, first_assess.stderr)
            self.assertIn("ACQUIRE_REQUIRED", first_assess.stdout)

            acquired = subprocess.run(
                [
                    str(TOOL_PATH),
                    "acquire",
                    str(fixture.manifest_path),
                    "--plan-hash",
                    source_plan,
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(acquired.returncode, 0, acquired.stderr)

            ready_assess = subprocess.run(
                [str(TOOL_PATH), "assess", str(fixture.manifest_path)],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(ready_assess.returncode, 0, ready_assess.stderr)
            self.assertIn("Decision：READY", ready_assess.stdout)

            assessment = assess(fixture.manifest())
            request_path = fixture.request(assessment)
            prepared = subprocess.run(
                [str(TOOL_PATH), "prepare", str(request_path)],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(prepared.returncode, 0, prepared.stderr)
            self.assertIn("Decision：READY", prepared.stdout)
            executed = subprocess.run(
                [
                    str(TOOL_PATH),
                    "run",
                    str(request_path),
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(executed.returncode, 0, executed.stderr)
            self.assertEqual(
                assess(fixture.manifest())["state_summary"],
                "MATCHED",
            )


if __name__ == "__main__":
    unittest.main()

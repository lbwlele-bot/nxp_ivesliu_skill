from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
import io
from pathlib import Path
import subprocess
import tempfile
import unittest

import yaml

from compile_tool.cli import main
from compile_tool.common import ToolError, case_lock
from compile_tool.manifest import load_manifest
from compile_tool import manifest as manifest_module
from compile_tool.planner import assess
from compile_tool.request import load_request, verify_assessment
from compile_tool.sources import assess_sources, execute_acquisition
from compile_tool.state import load_state, state_path


PARAMETERS = {
    "silicon_revision": {
        "value": "B0",
        "source": "user",
    },
    "smfw_config": {
        "value": "fixture",
        "source": "project",
    },
}
PROFILE_COMPONENTS = (
    "atf",
    "smfw",
    "uboot",
    "optee",
    "oei",
    "m_payload",
    "firmware",
    "scfw",
    "ahab",
    "flashbin",
)
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


class FlashbinFixture:
    def __init__(self, root: Path, enabled_builds: tuple[str, ...]) -> None:
        self.root = root
        self.case_root = root / "support_level" / "work" / "test-case"
        self.records = self.case_root / "records"
        self.build = self.case_root / "build"
        self.artifacts = self.case_root / "artifacts"
        self.inputs = self.case_root / "inputs"
        for directory in (
            self.records,
            self.build,
            self.artifacts,
            self.inputs,
        ):
            directory.mkdir(parents=True, exist_ok=True)
        self.toolchain = self.case_root / "toolchain-version"
        self.toolchain.write_text("#!/bin/sh\nprintf 'fixture-toolchain 1.0\\n'\n")
        self.toolchain.chmod(0o755)

        self.sources: dict[str, Path] = {}
        self.outputs: dict[str, Path] = {}
        components: dict[str, dict] = {
            component: {
                "status": "not_applicable",
                "reason": f"{component} is outside this fixture",
            }
            for component in PROFILE_COMPONENTS
        }
        for component in enabled_builds:
            source = self.case_root / "sources" / f"{component}.txt"
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_text(f"{component}-source-v1\n")
            output = self.artifacts / f"{component}.bin"
            self.sources[component] = source
            self.outputs[component] = output
            components[component] = self._local_component(source, output)

        self.fixed_input = self.inputs / "firmware.bin"
        self.fixed_input.write_bytes(b"firmware-v1")
        components["firmware"] = {
            "status": "enabled",
            "inputs": [str(self.fixed_input)],
        }
        self.flash_source = self.case_root / "sources" / "mkimage.txt"
        self.flash_source.parent.mkdir(parents=True, exist_ok=True)
        self.flash_source.write_text("mkimage-source-v1\n")
        self.flash_output = self.artifacts / "flash.bin"
        self.sources["flashbin"] = self.flash_source
        self.outputs["flashbin"] = self.flash_output
        components["flashbin"] = self._local_component(
            self.flash_source, self.flash_output
        )
        self.manifest_data = {
            "schema_version": 1,
            "case": self.case_root.name,
            "case_root": str(self.case_root),
            "target": "flashbin",
            "parameters": deepcopy(PARAMETERS),
            "components": components,
        }
        self.manifest_path = self.records / "compile-manifest.yaml"
        write_yaml(self.manifest_path, self.manifest_data)

    def _local_component(self, source: Path, output: Path) -> dict:
        return {
            "status": "enabled",
            "source": {"kind": "local_files", "paths": [str(source)]},
            "configuration": {"values": {"fixture": "1"}, "files": []},
            "toolchains": [
                {"executable": str(self.toolchain), "version_args": []}
            ],
            "outputs": [str(output)],
        }

    def use_managed_git_flash_source(self) -> tuple[Path, Path]:
        canonical = (
            self.root
            / "support_level"
            / "code_assets"
            / "projects"
            / "imx-mkimage"
            / "imx-mkimage"
        )
        canonical.mkdir(parents=True)
        run_git(canonical, "init")
        run_git(canonical, "config", "user.email", "fixture@example.com")
        run_git(canonical, "config", "user.name", "Fixture")
        (canonical / "tracked.txt").write_text("tracked-v1\n")
        run_git(canonical, "add", "tracked.txt")
        run_git(canonical, "commit", "-m", "initial")
        remote_url = "https://fixture.invalid/imx-mkimage"
        run_git(canonical, "remote", "add", "origin", remote_url)

        case_source = self.case_root / "sources" / "imx-mkimage"
        run_git(canonical, "worktree", "add", "--detach", str(case_source), "HEAD")
        self.manifest_data["components"]["flashbin"]["source"] = {
            "kind": "managed_git",
            "canonical_path": str(canonical),
            "case_path": str(case_source),
            "ref_kind": "commit",
            "ref": run_git(canonical, "rev-parse", "HEAD"),
            "remote": "origin",
            "remote_url": remote_url,
            "update": "if_missing",
        }
        write_yaml(self.manifest_path, self.manifest_data)
        workspace = (
            self.case_root
            / "build"
            / ".compile-tool"
            / "flashbin"
            / "flashbin"
            / "source"
        )
        return case_source, workspace

    def manifest(self) -> dict:
        return load_manifest(self.manifest_path)

    def request(
        self,
        assessment: dict,
        *,
        failing_component: str | None = None,
        scope: list[str] | None = None,
        unit_components: list[str] | None = None,
        commands: dict[str, str] | None = None,
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
            scope = [
                component
                for component in unit_components
                if component != "flashbin"
            ] or ["flashbin"]
        units = []
        for component in unit_components:
            output = self.outputs[component]
            if component == failing_component:
                command = "exit 7"
            elif component == "flashbin":
                inputs = [
                    str(self.outputs[item])
                    for item in self.outputs
                    if item != "flashbin"
                ]
                inputs.append(str(self.fixed_input))
                command = "cat " + " ".join(inputs) + f" > {output}"
            elif component == "smfw":
                command = (
                    "rm -rf configs/fixture && "
                    "make -f /dev/null --eval='really-clean: ; @:' "
                    "really-clean && "
                    "make config=fixture -f /dev/null "
                    "--eval='cfg: ; @:' cfg && "
                    "make config=fixture -f /dev/null "
                    "--eval='all: ; @:' all && "
                    f"printf '{component}-artifact' > {output}"
                )
            else:
                command = f"printf '{component}-artifact' > {output}"
            command = commands.get(component, command)
            if component in {"oei", "flashbin"}:
                revision = self.manifest_data["parameters"]["silicon_revision"][
                    "value"
                ]
                command = (
                    f"make REV={revision} -f /dev/null "
                    "--eval='guard: ; @:' guard && " + command
                )
            units.append(
                {
                    "component": component,
                    "action": observed_actions.get(
                        component,
                        "repack" if component == "flashbin" else "rebuild",
                    ),
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
        data = {
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
            "compile": {"target": "flashbin", "units": units},
        }
        path = self.records / "compile-request.yaml"
        write_yaml(path, data)
        return path


class StateWorkflowTests(unittest.TestCase):
    def test_isolated_git_materializes_dirty_source_and_contains_build_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = FlashbinFixture(Path(temp_dir), enabled_builds=())
            case_source, workspace = fixture.use_managed_git_flash_source()
            (case_source / "tracked.txt").write_text("tracked-patched\n")
            (case_source / "new-source.txt").write_text("new-source\n")
            (case_source / "source-link").symlink_to("new-source.txt")
            source_status = run_git(
                case_source, "status", "--short", "--untracked-files=all"
            )

            manifest = fixture.manifest()
            assessment = assess(manifest)
            request_path = fixture.request(
                assessment,
                commands={
                    "flashbin": (
                        f"printf flash > {fixture.flash_output} && "
                        "printf generated > generated.tmp"
                    )
                },
                cwd_overrides={"flashbin": workspace},
            )
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["run", str(request_path)]), 0)

            self.assertEqual(
                run_git(case_source, "status", "--short", "--untracked-files=all"),
                source_status,
            )
            self.assertEqual(
                (workspace / "tracked.txt").read_text(), "tracked-patched\n"
            )
            self.assertEqual(
                (workspace / "new-source.txt").read_text(), "new-source\n"
            )
            self.assertTrue((workspace / "source-link").is_symlink())
            self.assertEqual(
                (workspace / "generated.tmp").read_text(), "generated"
            )
            state = load_state(manifest)
            self.assertEqual(
                state["components"]["flashbin"]["execution"]["mode"],
                "isolated_git",
            )

            (workspace / "stale-from-previous-run").write_text("stale\n")
            matched = assess(manifest)
            second_request = fixture.request(
                matched,
                scope=["flashbin"],
                unit_components=["flashbin"],
                commands={"flashbin": f"printf flash > {fixture.flash_output}"},
                cwd_overrides={"flashbin": workspace},
            )
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["run", str(second_request)]), 0)
            self.assertFalse((workspace / "stale-from-previous-run").exists())

    def test_isolated_git_rejects_legacy_source_or_external_cwd(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = FlashbinFixture(Path(temp_dir), enabled_builds=())
            fixture.use_managed_git_flash_source()
            request_path = fixture.request(assess(fixture.manifest()))
            with self.assertRaisesRegex(ToolError, "requires isolated_git"):
                load_request(request_path)

    def test_isolated_git_still_blocks_original_source_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = FlashbinFixture(Path(temp_dir), enabled_builds=())
            case_source, workspace = fixture.use_managed_git_flash_source()
            manifest = fixture.manifest()
            request_path = fixture.request(
                assess(manifest),
                commands={
                    "flashbin": (
                        f"printf hacked >> {case_source / 'tracked.txt'} && "
                        f"printf flash > {fixture.flash_output}"
                    )
                },
                cwd_overrides={"flashbin": workspace},
            )
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                self.assertEqual(main(["run", str(request_path)]), 2)
            self.assertNotIn("flashbin", load_state(manifest)["components"])

    def test_isolated_git_refuses_to_claim_unowned_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = FlashbinFixture(Path(temp_dir), enabled_builds=())
            _, workspace = fixture.use_managed_git_flash_source()
            workspace.parent.mkdir(parents=True)
            unrelated = workspace.parent / "user-file"
            unrelated.write_text("keep\n")
            manifest = fixture.manifest()
            request_path = fixture.request(
                assess(manifest),
                cwd_overrides={"flashbin": workspace},
            )
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                self.assertEqual(main(["run", str(request_path)]), 2)
            self.assertEqual(unrelated.read_text(), "keep\n")

    def test_minimal_rebuild_and_fixed_input_propagation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = FlashbinFixture(
                Path(temp_dir), enabled_builds=("atf", "smfw", "uboot")
            )
            manifest = fixture.manifest()
            first = assess(manifest)
            self.assertEqual(
                first["observed_units"],
                [
                    {"component": "atf", "action": "rebuild"},
                    {"component": "smfw", "action": "rebuild"},
                    {"component": "uboot", "action": "rebuild"},
                    {"component": "flashbin", "action": "repack"},
                ],
            )
            request_path = fixture.request(first)
            prepared = subprocess.run(
                [str(TOOL_PATH), "prepare", str(request_path)],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(prepared.returncode, 0, prepared.stderr)
            self.assertIn("smfw -> REBUILD", prepared.stdout)
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
            self.assertTrue(state_path(manifest).is_file())
            self.assertEqual(assess(manifest)["state_summary"], "MATCHED")

            fixture.sources["smfw"].write_text("smfw-source-v2\n")
            changed = assess(manifest)
            self.assertEqual(
                changed["observed_units"],
                [
                    {"component": "smfw", "action": "rebuild"},
                    {"component": "flashbin", "action": "repack"},
                ],
            )
            self.assertEqual(changed["observations"]["atf"]["action"], "reuse")
            self.assertEqual(changed["observations"]["uboot"]["action"], "reuse")

            fixture.sources["smfw"].write_text("smfw-source-v1\n")
            self.assertEqual(assess(manifest)["state_summary"], "MATCHED")
            fixture.fixed_input.write_bytes(b"firmware-v2")
            fixed_changed = assess(manifest)
            self.assertEqual(
                fixed_changed["observed_units"],
                [{"component": "flashbin", "action": "repack"}],
            )

    def test_request_scope_blocks_unrelated_sibling_rebuild(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = FlashbinFixture(
                Path(temp_dir), enabled_builds=("atf", "smfw")
            )
            manifest = fixture.manifest()
            result = assess(manifest)
            request_path = fixture.request(
                result,
                scope=["smfw"],
                unit_components=["atf", "smfw", "flashbin"],
            )
            with self.assertRaisesRegex(ToolError, "exceed the declared decision scope"):
                load_request(request_path)

    def test_flashbin_upstream_scope_requires_final_repack(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = FlashbinFixture(Path(temp_dir), enabled_builds=("smfw",))
            request_path = fixture.request(
                assess(fixture.manifest()),
                scope=["smfw"],
                unit_components=["smfw"],
            )
            with self.assertRaisesRegex(ToolError, "requires a final flashbin repack"):
                load_request(request_path)

    def test_request_without_llm_decision_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = FlashbinFixture(Path(temp_dir), enabled_builds=("atf",))
            request_path = fixture.request(assess(fixture.manifest()))
            data = yaml.safe_load(request_path.read_text())
            del data["decision"]
            write_yaml(request_path, data)
            with self.assertRaisesRegex(ToolError, "decision"):
                load_request(request_path)

    def test_fixed_input_scope_executes_only_flashbin_repack(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = FlashbinFixture(Path(temp_dir), enabled_builds=("atf",))
            manifest = fixture.manifest()
            self.assertEqual(main(["run", str(fixture.request(assess(manifest)))]), 0)
            fixture.fixed_input.write_bytes(b"firmware-v2")
            changed = assess(manifest)
            request_path = fixture.request(
                changed,
                scope=["firmware"],
                unit_components=["flashbin"],
            )
            request = load_request(request_path)
            self.assertEqual(
                [
                    (unit["component"], unit["action"])
                    for unit in request["compile"]["units"]
                ],
                [("flashbin", "repack")],
            )
            self.assertEqual(main(["run", str(request_path)]), 0)

    def test_flashbin_state_records_input_artifact_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = FlashbinFixture(
                Path(temp_dir), enabled_builds=("atf", "smfw")
            )
            manifest = fixture.manifest()
            request_path = fixture.request(assess(manifest))
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["run", str(request_path)]), 0)
            state = load_state(manifest)
            package = state["components"]["flashbin"]
            self.assertEqual(
                set(package["input_artifacts"]),
                {"atf", "smfw", "firmware"},
            )
            for entries in package["input_artifacts"].values():
                self.assertTrue(entries)
                self.assertTrue(all(entry["sha256"].startswith("sha256:") for entry in entries))
            self.assertTrue(package["outputs"][0]["sha256"].startswith("sha256:"))

    def test_smfw_policy_requires_safe_generated_config_refresh(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = FlashbinFixture(Path(temp_dir), enabled_builds=("smfw",))
            assessment = assess(fixture.manifest())
            output = fixture.outputs["smfw"]
            base = (
                "make -f /dev/null --eval='really-clean: ; @:' really-clean && "
                "make config=fixture -f /dev/null --eval='cfg: ; @:' cfg && "
                "make config=fixture -f /dev/null --eval='all: ; @:' all && "
                f"printf smfw > {output}"
            )
            missing_remove = fixture.request(
                assessment,
                scope=["smfw"],
                unit_components=["smfw", "flashbin"],
                commands={"smfw": base},
            )
            with self.assertRaisesRegex(ToolError, "remove-generated-config"):
                load_request(missing_remove)

            deletes_source = fixture.request(
                assessment,
                scope=["smfw"],
                unit_components=["smfw", "flashbin"],
                commands={"smfw": "rm -rf configs/fixture.cfg && " + base},
            )
            with self.assertRaisesRegex(ToolError, "source .cfg files"):
                load_request(deletes_source)

            deletes_source_without_recursive_force = fixture.request(
                assessment,
                scope=["smfw"],
                unit_components=["smfw", "flashbin"],
                commands={"smfw": "rm -f configs/fixture.cfg && " + base},
            )
            with self.assertRaisesRegex(ToolError, "source .cfg files"):
                load_request(deletes_source_without_recursive_force)

            wrong_order = fixture.request(
                assessment,
                scope=["smfw"],
                unit_components=["smfw", "flashbin"],
                commands={
                    "smfw": (
                        "make -f /dev/null --eval='really-clean: ; @:' "
                        "really-clean && rm -rf configs/fixture && "
                        "make config=fixture -f /dev/null "
                        "--eval='cfg: ; @:' cfg && "
                        "make config=fixture -f /dev/null "
                        "--eval='all: ; @:' all && "
                        f"printf smfw > {output}"
                    )
                },
            )
            with self.assertRaisesRegex(ToolError, "requires order"):
                load_request(wrong_order)

            valid = fixture.request(
                assessment,
                scope=["smfw"],
                unit_components=["smfw", "flashbin"],
            )
            self.assertEqual(load_request(valid)["decision"]["scope"], ["smfw"])

            fixture.manifest_data["parameters"]["smfw_config"]["value"] = "../fixture"
            write_yaml(fixture.manifest_path, fixture.manifest_data)
            with self.assertRaisesRegex(ToolError, "safe relative"):
                fixture.manifest()

    def test_stale_assessment_blocks_prepare(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = FlashbinFixture(Path(temp_dir), enabled_builds=("smfw",))
            result = assess(fixture.manifest())
            request_path = fixture.request(result)
            fixture.sources["smfw"].write_text("changed-after-assess\n")
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                exit_code = main(["prepare", str(request_path)])
            self.assertEqual(exit_code, 2)

    def test_successful_unit_is_kept_when_later_unit_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = FlashbinFixture(Path(temp_dir), enabled_builds=("atf",))
            manifest = fixture.manifest()
            result = assess(manifest)
            request_path = fixture.request(result, failing_component="flashbin")
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                exit_code = main(["run", str(request_path)])
            self.assertEqual(exit_code, 7)
            next_result = assess(manifest)
            self.assertEqual(next_result["observations"]["atf"]["action"], "reuse")
            self.assertEqual(
                next_result["observed_units"],
                [{"component": "flashbin", "action": "repack"}],
            )

    def test_state_integrity_failure_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = FlashbinFixture(Path(temp_dir), enabled_builds=("atf",))
            manifest = fixture.manifest()
            result = assess(manifest)
            request_path = fixture.request(result)
            with redirect_stdout(io.StringIO()):
                self.assertEqual(
                    main(["run", str(request_path)]),
                    0,
                )
            state = yaml.safe_load(state_path(manifest).read_text())
            state["targets"]["flashbin"]["components"]["atf"]["kind"] = "tampered"
            write_yaml(state_path(manifest), state)
            with self.assertRaisesRegex(ToolError, "integrity"):
                load_state(manifest)

    def test_config_toolchain_and_artifact_changes_invalidate_component(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = FlashbinFixture(Path(temp_dir), enabled_builds=("smfw",))
            manifest = fixture.manifest()
            initial = assess(manifest)
            request_path = fixture.request(initial)
            with redirect_stdout(io.StringIO()):
                self.assertEqual(
                    main(["run", str(request_path)]),
                    0,
                )

            fixture.toolchain.write_text(
                "#!/bin/sh\nprintf 'fixture-toolchain 2.0\\n'\n"
            )
            fixture.toolchain.chmod(0o755)
            changed = assess(manifest)
            self.assertEqual(changed["observations"]["smfw"]["action"], "rebuild")

            fixture.toolchain.write_text(
                "#!/bin/sh\nprintf 'fixture-toolchain 1.0\\n'\n"
            )
            fixture.toolchain.chmod(0o755)
            fixture.manifest_data["components"]["smfw"]["configuration"]["values"][
                "fixture"
            ] = "2"
            write_yaml(fixture.manifest_path, fixture.manifest_data)
            config_changed = assess(fixture.manifest())
            self.assertEqual(
                config_changed["observed_units"],
                [
                    {"component": "smfw", "action": "rebuild"},
                    {"component": "flashbin", "action": "repack"},
                ],
            )

            fixture.manifest_data["components"]["smfw"]["configuration"]["values"][
                "fixture"
            ] = "1"
            write_yaml(fixture.manifest_path, fixture.manifest_data)
            fixture.outputs["smfw"].write_bytes(b"externally-replaced")
            artifact_changed = assess(fixture.manifest())
            self.assertEqual(
                artifact_changed["observations"]["smfw"]["action"], "rebuild"
            )

    def test_touching_unchanged_artifact_reuses_cached_content_hash(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = FlashbinFixture(Path(temp_dir), enabled_builds=("atf",))
            manifest = fixture.manifest()
            initial = assess(manifest)
            request_path = fixture.request(initial)
            with redirect_stdout(io.StringIO()):
                self.assertEqual(
                    main(["run", str(request_path)]),
                    0,
                )
            fixture.outputs["atf"].touch()
            self.assertEqual(assess(manifest)["state_summary"], "MATCHED")

    def test_rebuild_command_must_refresh_declared_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = FlashbinFixture(Path(temp_dir), enabled_builds=("smfw",))
            manifest = fixture.manifest()
            first = assess(manifest)
            first_request_path = fixture.request(first)
            with redirect_stdout(io.StringIO()):
                self.assertEqual(
                    main(["run", str(first_request_path)]),
                    0,
                )
            fixture.sources["smfw"].write_text("changed-source\n")
            changed = assess(manifest)
            request_path = fixture.request(changed)
            data = yaml.safe_load(request_path.read_text())
            data["compile"]["units"][0]["steps"][0]["command"] = "true"
            write_yaml(request_path, data)
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                exit_code = main(["run", str(request_path)])
            self.assertEqual(exit_code, 2)
            self.assertEqual(
                assess(manifest)["observations"]["smfw"]["action"], "rebuild"
            )

    def test_manifest_requires_complete_components_and_safe_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = FlashbinFixture(Path(temp_dir), enabled_builds=("atf",))
            del fixture.manifest_data["components"]["ahab"]
            write_yaml(fixture.manifest_path, fixture.manifest_data)
            with self.assertRaisesRegex(ToolError, "missing: ahab"):
                fixture.manifest()

        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = FlashbinFixture(Path(temp_dir), enabled_builds=("atf",))
            fixture.manifest_data["components"]["optee"] = {
                "status": "not_applicable"
            }
            write_yaml(fixture.manifest_path, fixture.manifest_data)
            with self.assertRaisesRegex(ToolError, "reason"):
                fixture.manifest()

        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = FlashbinFixture(Path(temp_dir), enabled_builds=("atf",))
            fixture.manifest_data["components"]["atf"]["outputs"] = [
                str(Path(temp_dir) / "outside.bin")
            ]
            write_yaml(fixture.manifest_path, fixture.manifest_data)
            with self.assertRaisesRegex(ToolError, "must be inside"):
                fixture.manifest()

    def test_parameter_guards_require_user_revision_and_command_binding(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = FlashbinFixture(Path(temp_dir), enabled_builds=())
            fixture.manifest_data["parameters"] = {}
            write_yaml(fixture.manifest_path, fixture.manifest_data)
            with self.assertRaisesRegex(ToolError, "ask the user"):
                fixture.manifest()

        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = FlashbinFixture(Path(temp_dir), enabled_builds=())
            fixture.manifest_data["parameters"]["silicon_revision"][
                "source"
            ] = "assumption"
            write_yaml(fixture.manifest_path, fixture.manifest_data)
            with self.assertRaisesRegex(ToolError, "source=user"):
                fixture.manifest()

        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = FlashbinFixture(Path(temp_dir), enabled_builds=())
            result = assess(fixture.manifest())
            request_path = fixture.request(result)
            data = yaml.safe_load(request_path.read_text())
            data["compile"]["units"][0]["steps"][0]["command"] = (
                "make -f /dev/null --eval='guard: ; @:' guard && "
                f"printf flash > {fixture.flash_output}"
            )
            write_yaml(request_path, data)
            with self.assertRaisesRegex(ToolError, "requires explicit REV=B0"):
                load_request(request_path)

            data["compile"]["units"][0]["steps"][0]["command"] = (
                "REV=B0 make -f /dev/null --eval='guard: ; @:' guard && "
                f"printf flash > {fixture.flash_output}"
            )
            write_yaml(request_path, data)
            with self.assertRaisesRegex(ToolError, "requires explicit REV=B0"):
                load_request(request_path)

        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = FlashbinFixture(Path(temp_dir), enabled_builds=("oei",))
            result = assess(fixture.manifest())
            request_path = fixture.request(result)
            data = yaml.safe_load(request_path.read_text())
            oei_unit = next(
                unit
                for unit in data["compile"]["units"]
                if unit["component"] == "oei"
            )
            oei_unit["steps"][0]["command"] = (
                f"printf oei > {fixture.outputs['oei']}"
            )
            write_yaml(request_path, data)
            with self.assertRaisesRegex(ToolError, "flashbin-oei-silicon-revision"):
                load_request(request_path)

            oei_unit["steps"][0]["command"] = (
                "make REV=B0 R=A1 -f /dev/null "
                "--eval='guard: ; @:' guard && "
                f"printf oei > {fixture.outputs['oei']}"
            )
            write_yaml(request_path, data)
            with self.assertRaisesRegex(ToolError, "requires explicit REV/R/r=B0"):
                load_request(request_path)

    def test_requirements_lists_guarded_parameters_before_values_are_known(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = FlashbinFixture(Path(temp_dir), enabled_builds=())
            fixture.manifest_data["parameters"] = {}
            write_yaml(fixture.manifest_path, fixture.manifest_data)
            with redirect_stdout(io.StringIO()) as captured:
                result = main(["requirements", str(fixture.manifest_path)])

            self.assertEqual(result, 0)
            output = captured.getvalue()
            self.assertIn("flashbin", output)
            self.assertIn("silicon_revision", output)
            self.assertIn("source=user", output)
            self.assertIn("COMPILE_POLICY.yaml", output)

        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = FlashbinFixture(Path(temp_dir), enabled_builds=("smfw",))
            fixture.manifest_data["parameters"] = {}
            write_yaml(fixture.manifest_path, fixture.manifest_data)
            with redirect_stdout(io.StringIO()) as captured:
                result = main(["requirements", str(fixture.manifest_path)])
            self.assertEqual(result, 0)
            output = captured.getvalue()
            self.assertIn("smfw_config", output)
            self.assertIn("really-clean", output)

    def test_revision_change_only_invalidates_guarded_components(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = FlashbinFixture(
                Path(temp_dir), enabled_builds=("atf", "oei")
            )
            manifest = fixture.manifest()
            first = assess(manifest)
            request_path = fixture.request(first)
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["run", str(request_path)]), 0)

            fixture.manifest_data["parameters"]["silicon_revision"][
                "value"
            ] = "A1"
            write_yaml(fixture.manifest_path, fixture.manifest_data)
            changed = assess(fixture.manifest())
            self.assertEqual(changed["observations"]["atf"]["action"], "reuse")
            self.assertEqual(
                changed["observed_units"],
                [
                    {"component": "oei", "action": "rebuild"},
                    {"component": "flashbin", "action": "repack"},
                ],
            )

    def test_dependency_profile_cycle_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "cycle.yaml"
            write_yaml(
                path,
                {
                    "schema_version": 1,
                    "target": "flashbin",
                    "components": {
                        "a": {"kind": "build", "depends_on": ["b"]},
                        "b": {"kind": "package", "depends_on": ["a"]},
                    },
                },
            )
            original = manifest_module.PROFILE_PATHS["flashbin"]
            manifest_module.PROFILE_PATHS["flashbin"] = path
            try:
                with self.assertRaisesRegex(ToolError, "cycle"):
                    manifest_module.load_profile("flashbin")
            finally:
                manifest_module.PROFILE_PATHS["flashbin"] = original

    def test_v2_cwd_outside_case_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = FlashbinFixture(Path(temp_dir), enabled_builds=("atf",))
            result = assess(fixture.manifest())
            request_path = fixture.request(result)
            data = yaml.safe_load(request_path.read_text())
            data["compile"]["units"][0]["steps"][0]["cwd"] = temp_dir
            write_yaml(request_path, data)
            with self.assertRaisesRegex(ToolError, "must be inside"):
                load_request(request_path)

    def test_case_lock_rejects_concurrent_state_owner(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = FlashbinFixture(Path(temp_dir), enabled_builds=("atf",))
            with case_lock(fixture.case_root):
                with self.assertRaisesRegex(ToolError, "locked"):
                    with case_lock(fixture.case_root):
                        pass


class SourceAcquisitionTests(unittest.TestCase):
    def _managed_fixture(
        self,
        root: Path,
        *,
        ref_kind: str = "branch",
        ref: str = "main",
    ) -> tuple[FlashbinFixture, Path, Path]:
        remote = root / "remote.git"
        seed = root / "seed"
        canonical = (
            root
            / "support_level"
            / "code_assets"
            / "projects"
            / "imx-atf"
            / "imx-atf"
        )
        run_git(root, "init", "--bare", str(remote))
        run_git(root, "init", "--initial-branch=main", str(seed))
        run_git(seed, "config", "user.email", "fixture@example.com")
        run_git(seed, "config", "user.name", "Fixture")
        (seed / "source.c").write_text("v1\n")
        run_git(seed, "add", "source.c")
        run_git(seed, "commit", "-m", "initial")
        run_git(seed, "remote", "add", "origin", str(remote))
        run_git(seed, "push", "-u", "origin", "main")
        canonical.parent.mkdir(parents=True, exist_ok=True)
        run_git(root, "clone", "--branch", "main", str(remote), str(canonical))

        fixture = FlashbinFixture(root, enabled_builds=())
        case_checkout = fixture.build / "imx-atf"
        fixture.manifest_data["components"]["atf"] = {
            "status": "enabled",
            "source": {
                "kind": "managed_git",
                "canonical_path": str(canonical),
                "case_path": str(case_checkout),
                "ref_kind": ref_kind,
                "ref": ref,
                "remote": "origin",
                "remote_url": str(remote),
                "update": "if_missing",
            },
            "configuration": {"values": {}, "files": []},
            "toolchains": [
                {"executable": str(fixture.toolchain), "version_args": []}
            ],
            "outputs": [str(fixture.artifacts / "atf.bin")],
        }
        fixture.outputs["atf"] = fixture.artifacts / "atf.bin"
        write_yaml(fixture.manifest_path, fixture.manifest_data)
        return fixture, canonical, remote

    def test_local_ref_creates_worktree_without_fetch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture, _, _ = self._managed_fixture(Path(temp_dir))
            manifest = fixture.manifest()
            result = assess_sources(manifest)
            self.assertEqual(result["status"], "ACQUIRE_REQUIRED")
            self.assertEqual(len(result["operations"]), 1)
            self.assertEqual(result["operations"][0]["argv"][1:3], ["worktree", "add"])
            assessed = subprocess.run(
                [str(TOOL_PATH), "assess", str(fixture.manifest_path)],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(assessed.returncode, 3, assessed.stderr)
            self.assertIn("git worktree add --detach", assessed.stdout)
            acquired = subprocess.run(
                [
                    str(TOOL_PATH),
                    "acquire",
                    str(fixture.manifest_path),
                    "--plan-hash",
                    result["plan_hash"],
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(acquired.returncode, 0, acquired.stderr)
            ready = assess_sources(manifest)
            self.assertEqual(ready["status"], "READY")
            git_marker = fixture.build / "imx-atf" / ".git"
            self.assertTrue(git_marker.is_file())

    def test_missing_tag_uses_targeted_fetch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fixture, _, remote = self._managed_fixture(
                root, ref_kind="tag", ref="release-v1"
            )
            tagger = root / "tagger"
            run_git(root, "clone", "--branch", "main", str(remote), str(tagger))
            run_git(tagger, "config", "user.email", "fixture@example.com")
            run_git(tagger, "config", "user.name", "Fixture")
            run_git(tagger, "tag", "release-v1")
            run_git(tagger, "push", "origin", "release-v1")
            manifest = fixture.manifest()
            result = assess_sources(manifest)
            self.assertEqual(result["operations"][0]["argv"][1:4], ["fetch", "origin", "tag"])
            with redirect_stdout(io.StringIO()):
                self.assertEqual(
                    execute_acquisition(manifest, result["plan_hash"]),
                    0,
                )
            self.assertEqual(assess_sources(manifest)["status"], "READY")

    def test_dirty_canonical_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture, canonical, _ = self._managed_fixture(Path(temp_dir))
            (canonical / "source.c").write_text("dirty\n")
            with self.assertRaisesRegex(ToolError, "not clean"):
                assess_sources(fixture.manifest())

    def test_unsafe_ref_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture, _, _ = self._managed_fixture(Path(temp_dir))
            fixture.manifest_data["components"]["atf"]["source"]["ref"] = "--all"
            write_yaml(fixture.manifest_path, fixture.manifest_data)
            with self.assertRaisesRegex(ToolError, "unsafe"):
                fixture.manifest()

    def test_pull_ff_only_is_bound_and_non_fast_forward_stops(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fixture, canonical, remote = self._managed_fixture(root)
            source = fixture.manifest_data["components"]["atf"]["source"]
            source["update"] = "pull_ff_only"
            write_yaml(fixture.manifest_path, fixture.manifest_data)

            run_git(canonical, "config", "user.email", "fixture@example.com")
            run_git(canonical, "config", "user.name", "Fixture")
            (canonical / "local.txt").write_text("local\n")
            run_git(canonical, "add", "local.txt")
            run_git(canonical, "commit", "-m", "local divergence")

            remote_writer = root / "remote-writer"
            run_git(root, "clone", "--branch", "main", str(remote), str(remote_writer))
            run_git(remote_writer, "config", "user.email", "fixture@example.com")
            run_git(remote_writer, "config", "user.name", "Fixture")
            (remote_writer / "remote.txt").write_text("remote\n")
            run_git(remote_writer, "add", "remote.txt")
            run_git(remote_writer, "commit", "-m", "remote divergence")
            run_git(remote_writer, "push", "origin", "main")

            manifest = fixture.manifest()
            result = assess_sources(manifest)
            self.assertEqual(result["operations"][0]["argv"][1:3], ["pull", "--ff-only"])
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                self.assertNotEqual(
                    execute_acquisition(manifest, result["plan_hash"]),
                    0,
                )
            self.assertFalse((fixture.build / "imx-atf").exists())


if __name__ == "__main__":
    unittest.main()

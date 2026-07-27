from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
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
from compile_tool.request import load_request, request_hash, verify_assessment
from compile_tool.sources import assess_sources, execute_acquisition
from compile_tool.state import load_state, state_path


IDENTITY = {
    "soc": "i.MX8DXL",
    "silicon_revision": "B0",
    "chip_package": "N/A",
    "board": "imx8dxlevk",
    "ddr": "LPDDR4",
    "software_release": "lf-6.18.2-1.0.0",
}
EFFECTS = {
    "soc": "SOC=iMX8DXL",
    "silicon_revision": "REV=B0",
    "chip_package": "package does not select this test recipe",
    "board": "imx8dxlevk config",
    "ddr": "LPDDR4 inputs",
    "software_release": "aligned source refs",
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
            "identity": IDENTITY,
            "identity_notes": {
                "chip_package": "package does not select this test recipe"
            },
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

    def manifest(self) -> dict:
        return load_manifest(self.manifest_path)

    def request(
        self,
        assessment: dict,
        *,
        failing_component: str | None = None,
    ) -> Path:
        units = []
        for required in assessment["required_units"]:
            component = required["component"]
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
            else:
                command = f"printf '{component}-artifact' > {output}"
            units.append(
                {
                    "component": component,
                    "action": required["action"],
                    "steps": [
                        {
                            "name": f"build-{component}",
                            "cwd": str(self.build),
                            "env": {},
                            "command": command,
                        }
                    ],
                }
            )
        data = {
            "schema_version": 2,
            "case": self.case_root.name,
            "identity": IDENTITY,
            "identity_notes": {
                "chip_package": "package does not select this test recipe"
            },
            "identity_effects": EFFECTS,
            "assessment": {
                "manifest": str(self.manifest_path),
                "hash": assessment["assessment_hash"],
            },
            "compile": {"target": "flashbin", "units": units},
        }
        path = self.records / "compile-request.yaml"
        write_yaml(path, data)
        return path


class StateWorkflowTests(unittest.TestCase):
    def test_minimal_rebuild_and_fixed_input_propagation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = FlashbinFixture(
                Path(temp_dir), enabled_builds=("atf", "smfw", "uboot")
            )
            manifest = fixture.manifest()
            first = assess(manifest)
            self.assertEqual(
                first["required_units"],
                [
                    {"component": "atf", "action": "rebuild"},
                    {"component": "smfw", "action": "rebuild"},
                    {"component": "uboot", "action": "rebuild"},
                    {"component": "flashbin", "action": "repack"},
                ],
            )
            request_path = fixture.request(first)
            request = load_request(request_path)
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
                    "--plan-hash",
                    request_hash(request),
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(executed.returncode, 0, executed.stderr)
            self.assertTrue(state_path(manifest).is_file())
            self.assertEqual(assess(manifest)["status"], "REUSE_ONLY")

            fixture.sources["smfw"].write_text("smfw-source-v2\n")
            changed = assess(manifest)
            self.assertEqual(
                changed["required_units"],
                [
                    {"component": "smfw", "action": "rebuild"},
                    {"component": "flashbin", "action": "repack"},
                ],
            )
            self.assertEqual(changed["decisions"]["atf"]["action"], "reuse")
            self.assertEqual(changed["decisions"]["uboot"]["action"], "reuse")

            fixture.sources["smfw"].write_text("smfw-source-v1\n")
            self.assertEqual(assess(manifest)["status"], "REUSE_ONLY")
            fixture.fixed_input.write_bytes(b"firmware-v2")
            fixed_changed = assess(manifest)
            self.assertEqual(
                fixed_changed["required_units"],
                [{"component": "flashbin", "action": "repack"}],
            )

    def test_request_must_exactly_match_assessment(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = FlashbinFixture(Path(temp_dir), enabled_builds=("smfw",))
            manifest = fixture.manifest()
            result = assess(manifest)
            request_path = fixture.request(result)
            request_data = yaml.safe_load(request_path.read_text())
            request_data["compile"]["units"].pop()
            write_yaml(request_path, request_data)
            request = load_request(request_path)
            with self.assertRaisesRegex(ToolError, "exactly match"):
                verify_assessment(request, result)

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
            request = load_request(request_path)
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                exit_code = main(
                    [
                        "run",
                        str(request_path),
                        "--plan-hash",
                        request_hash(request),
                    ]
                )
            self.assertEqual(exit_code, 7)
            next_result = assess(manifest)
            self.assertEqual(next_result["decisions"]["atf"]["action"], "reuse")
            self.assertEqual(
                next_result["required_units"],
                [{"component": "flashbin", "action": "repack"}],
            )

    def test_state_integrity_failure_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = FlashbinFixture(Path(temp_dir), enabled_builds=("atf",))
            manifest = fixture.manifest()
            result = assess(manifest)
            request_path = fixture.request(result)
            request = load_request(request_path)
            with redirect_stdout(io.StringIO()):
                self.assertEqual(
                    main(
                        [
                            "run",
                            str(request_path),
                            "--plan-hash",
                            request_hash(request),
                        ]
                    ),
                    0,
                )
            state = yaml.safe_load(state_path(manifest).read_text())
            state["components"]["atf"]["command_hash"] = "tampered"
            write_yaml(state_path(manifest), state)
            with self.assertRaisesRegex(ToolError, "integrity"):
                load_state(manifest)

    def test_config_toolchain_and_artifact_changes_invalidate_component(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = FlashbinFixture(Path(temp_dir), enabled_builds=("smfw",))
            manifest = fixture.manifest()
            initial = assess(manifest)
            request_path = fixture.request(initial)
            request = load_request(request_path)
            with redirect_stdout(io.StringIO()):
                self.assertEqual(
                    main(
                        [
                            "run",
                            str(request_path),
                            "--plan-hash",
                            request_hash(request),
                        ]
                    ),
                    0,
                )

            fixture.toolchain.write_text(
                "#!/bin/sh\nprintf 'fixture-toolchain 2.0\\n'\n"
            )
            fixture.toolchain.chmod(0o755)
            changed = assess(manifest)
            self.assertEqual(changed["decisions"]["smfw"]["action"], "rebuild")

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
                config_changed["required_units"],
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
                artifact_changed["decisions"]["smfw"]["action"], "rebuild"
            )

    def test_touching_unchanged_artifact_reuses_cached_content_hash(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = FlashbinFixture(Path(temp_dir), enabled_builds=("atf",))
            manifest = fixture.manifest()
            initial = assess(manifest)
            request_path = fixture.request(initial)
            request = load_request(request_path)
            with redirect_stdout(io.StringIO()):
                self.assertEqual(
                    main(
                        [
                            "run",
                            str(request_path),
                            "--plan-hash",
                            request_hash(request),
                        ]
                    ),
                    0,
                )
            fixture.outputs["atf"].touch()
            self.assertEqual(assess(manifest)["status"], "REUSE_ONLY")

    def test_rebuild_command_must_refresh_declared_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = FlashbinFixture(Path(temp_dir), enabled_builds=("smfw",))
            manifest = fixture.manifest()
            first = assess(manifest)
            first_request_path = fixture.request(first)
            first_request = load_request(first_request_path)
            with redirect_stdout(io.StringIO()):
                self.assertEqual(
                    main(
                        [
                            "run",
                            str(first_request_path),
                            "--plan-hash",
                            request_hash(first_request),
                        ]
                    ),
                    0,
                )
            fixture.sources["smfw"].write_text("changed-source\n")
            changed = assess(manifest)
            request_path = fixture.request(changed)
            data = yaml.safe_load(request_path.read_text())
            data["compile"]["units"][0]["steps"][0]["command"] = "true"
            write_yaml(request_path, data)
            request = load_request(request_path)
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                exit_code = main(
                    [
                        "run",
                        str(request_path),
                        "--plan-hash",
                        request_hash(request),
                    ]
                )
            self.assertEqual(exit_code, 2)
            self.assertEqual(
                assess(manifest)["decisions"]["smfw"]["action"], "rebuild"
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

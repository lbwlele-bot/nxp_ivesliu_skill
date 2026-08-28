from __future__ import annotations

from contextlib import redirect_stdout
import io
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import yaml

from compile_tool import m_sdk
from compile_tool.artifacts import resolve_artifact_inputs
from compile_tool.common import ToolError, hash_file
from compile_tool.manifest import load_manifest
from compile_tool.planner import assess
from compile_tool.public_checklists import (
    materialize_public_manifest,
    normalize_public_checklist,
)
from compile_tool.state import load_state
from tests.test_checklists import ChecklistFixture


class MSdkChecklistTests(unittest.TestCase):
    def _compiler(self, root: Path, version: str = "14.3") -> Path:
        compiler = root / "toolchain" / "bin" / "arm-none-eabi-gcc"
        compiler.parent.mkdir(parents=True)
        compiler.write_text(f"#!/bin/sh\nprintf 'arm-none-eabi-gcc {version}\\n'\n")
        compiler.chmod(0o755)
        return compiler

    def _legacy_archive(self, root: Path, *, second_core: bool = False) -> Path:
        source = root / "archive-source"
        cores = ["cm7", "cm7b"] if second_core else ["cm7"]
        for core in cores:
            project = source / "boards" / "fixture" / "demo_apps" / "hello_world" / core / "armgcc"
            project.mkdir(parents=True)
            (project / "CMakeLists.txt").write_text(
                f"set(MCUX_SDK_PROJECT_NAME hello_world_{core}.elf)\n"
                "ADD_CUSTOM_COMMAND(TARGET demo POST_BUILD COMMAND tool "
                "${EXECUTABLE_OUTPUT_PATH}/hello_world.bin)\n"
            )
            (project / "build_release.sh").write_text(
                "#!/bin/sh\n"
                "mkdir -p release\n"
                f"printf '\\177ELF{core}' > release/hello_world_{core}.elf\n"
                f"printf '{core}-bin' > release/hello_world.bin\n"
            )
        prebuilt = source / "boards" / "fixture" / "demo_apps" / "hello_world"
        (prebuilt / "hello_world.bin").write_bytes(b"vendor-default-bin")
        archive = root / "SDK_25_09_00_FIXTURE.tar.gz"
        with tarfile.open(archive, "w:gz") as handle:
            for path in sorted(source.rglob("*")):
                handle.add(path, arcname=path.relative_to(source))
        return archive

    def _west_archive(self, root: Path, release: str = "25.12.00") -> Path:
        archive = root / f"SDK_{release.replace('.', '_')}_FIXTURE.zip"
        example = {
            "hello_world": {
                "boards": {"fixture@cm7": ["+armgcc@debug", "+armgcc@release"]}
            }
        }
        with zipfile.ZipFile(archive, "w") as handle:
            handle.writestr(".west/config", "[manifest]\npath = manifests\nfile = west.yml\n")
            handle.writestr("manifests/west.yml", "manifest:\n  projects: []\n")
            handle.writestr("mcuxsdk/scripts/west_commands/build.py", "# fixture\n")
            handle.writestr(
                "mcuxsdk/scripts/west_commands.yml",
                "west-commands:\n  - file: scripts/west_commands/build.py\n",
            )
            handle.writestr(
                "mcuxsdk/examples/demo_apps/hello_world/example.yml",
                yaml.safe_dump(example, sort_keys=False),
            )
            handle.writestr(
                "mcuxsdk/examples/demo_apps/hello_world/CMakeLists.txt",
                "project(hello_world LANGUAGES C ASM)\n",
            )
        return archive

    def _catalog(
        self,
        root: Path,
        archive: Path,
        *,
        release: str = "25.09.00",
        cores: dict[str, str] | None = None,
        compiler_constraint: str | None = None,
    ) -> Path:
        catalog = root / "packages" / "PACKAGES.yaml"
        catalog.parent.mkdir(parents=True)
        copied = catalog.parent / archive.name
        copied.write_bytes(archive.read_bytes())
        package = {
            "archive": copied.name,
            "sha256": hash_file(copied),
            "sdk_release": release,
            "soc": "imxfixture",
            "boards": {
                "fixture": {"core_roles": cores or {"cm7": "m7"}}
            },
        }
        if compiler_constraint:
            package["compiler_version_contains"] = compiler_constraint
        catalog.write_text(
            yaml.safe_dump(
                {
                    "schema_version": 1,
                    "kind": "m_freertos_sdk_package_catalog",
                    "packages": {"SDK_FIXTURE": package},
                },
                sort_keys=False,
            )
        )
        return catalog

    def _case(self, root: Path) -> Path:
        case = root / "support_level" / "work" / "m-sdk-case"
        (case / "records" / "compile" / "m_freertos_sdk").mkdir(parents=True)
        return case

    def _checklist(
        self,
        case: Path,
        compiler: Path,
        jobs: dict,
        *,
        scope: list[str] | None = None,
        sdk: dict | None = None,
    ) -> Path:
        path = case / "records" / "compile" / "m_freertos_sdk" / "compile.yaml"
        path.write_text(
            yaml.safe_dump(
                {
                    "schema_version": 1,
                    "kind": "m_freertos_sdk_compile_checklist",
                    "target": "m_freertos_sdk",
                    "case_root": str(case),
                    "sdk": sdk or {"package": "SDK_FIXTURE", "compiler": str(compiler)},
                    "jobs": jobs,
                    "intent": {
                        "scope": list(jobs) if scope is None else scope,
                        "reason": "fixture M SDK producer validation",
                    },
                },
                sort_keys=False,
            )
        )
        return path

    @staticmethod
    def _source_job(core: str = "cm7", role: str = "m7") -> dict:
        return {
            "mode": "source_build",
            "soc": "imxfixture",
            "board": "fixture",
            "core": core,
            "core_role": role,
            "application": "demo_apps/hello_world",
            "build_configuration": "release",
        }

    def test_backend_cutoff_is_exact(self) -> None:
        self.assertEqual(m_sdk.select_backend("2.9.0"), "legacy")
        self.assertEqual(m_sdk.select_backend("25.09.00"), "legacy")
        self.assertEqual(m_sdk.select_backend("25.12.00"), "west")
        self.assertEqual(m_sdk.select_backend("26.06.00"), "west")
        with self.assertRaisesRegex(ToolError, "2510/2511"):
            m_sdk.select_backend("25.10.00")
        with self.assertRaisesRegex(ToolError, "unsupported M SDK release format"):
            m_sdk.select_backend("release-latest")

    def test_missing_selected_package_requests_user_input(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            archive = self._legacy_archive(root)
            catalog = self._catalog(root, archive)
            catalog_archive = catalog.parent / archive.name
            catalog_archive.unlink()
            compiler = self._compiler(root)
            case = self._case(root)
            checklist = self._checklist(case, compiler, {"m7": self._source_job()})
            with patch.object(m_sdk, "CATALOG_PATH", catalog):
                with self.assertRaisesRegex(ToolError, "STATUS: USER_INPUT_REQUIRED"):
                    m_sdk.normalize_m_sdk_checklist(checklist)

    def test_unrelated_missing_catalog_package_does_not_block_selected_package(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            archive = self._legacy_archive(root)
            catalog = self._catalog(root, archive)
            raw = yaml.safe_load(catalog.read_text())
            raw["packages"]["SDK_MISSING_UNUSED"] = {
                **raw["packages"]["SDK_FIXTURE"],
                "archive": "missing-unused.zip",
            }
            catalog.write_text(yaml.safe_dump(raw, sort_keys=False))
            compiler = self._compiler(root)
            case = self._case(root)
            checklist = self._checklist(case, compiler, {"m7": self._source_job()})
            with patch.object(m_sdk, "CATALOG_PATH", catalog):
                normalized = m_sdk.normalize_m_sdk_checklist(checklist)
            self.assertEqual(normalized["package"]["id"], "SDK_FIXTURE")

    def test_user_provided_unregistered_sdk_builds_without_catalog_edit(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            archive = self._legacy_archive(root)
            catalog = self._catalog(root, archive)
            compiler = self._compiler(root)
            case = self._case(root)
            supplied = case / "inputs" / "sdk" / "customer-sdk.tar.gz"
            supplied.parent.mkdir(parents=True)
            supplied.write_bytes(archive.read_bytes())
            checklist = self._checklist(
                case,
                compiler,
                {"m7": self._source_job()},
                sdk={
                    "package": "CUSTOMER_SDK_25_09",
                    "archive": str(supplied.relative_to(case)),
                    "sdk_release": "25.09.00",
                    "trust_reason": "user downloaded this package from NXP",
                    "compiler": str(compiler),
                },
            )
            with patch.object(m_sdk, "CATALOG_PATH", catalog):
                with redirect_stdout(io.StringIO()):
                    self.assertEqual(m_sdk.prepare_m_sdk_checklist(checklist), 0)
                    self.assertEqual(m_sdk.run_m_sdk_checklist(checklist), 0)
                normalized = m_sdk.normalize_m_sdk_checklist(checklist)
                manifest = m_sdk.materialize_m_sdk_manifest(normalized)
                state = load_state(manifest)["components"]["m7"]
            self.assertEqual(normalized["package"]["assurance"], "user_attested")
            self.assertEqual(
                state["origin"]["details"]["package_assurance"], "user_attested"
            )

    def test_legacy_source_build_exports_sibling_elf_and_bin(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            archive = self._legacy_archive(root)
            catalog = self._catalog(root, archive)
            compiler = self._compiler(root)
            case = self._case(root)
            checklist_path = self._checklist(case, compiler, {"m7": self._source_job()})
            with patch.object(m_sdk, "CATALOG_PATH", catalog):
                prepared_output = io.StringIO()
                with redirect_stdout(prepared_output):
                    self.assertEqual(m_sdk.prepare_m_sdk_checklist(checklist_path), 0)
                self.assertIn("受控 backend：legacy", prepared_output.getvalue())
                self.assertIn("软件状态：PENDING_SOURCE_ACQUISITION", prepared_output.getvalue())
                self.assertIn("build_release.sh", prepared_output.getvalue())
                with redirect_stdout(io.StringIO()):
                    self.assertEqual(m_sdk.run_m_sdk_checklist(checklist_path), 0)
                manifest = m_sdk.materialize_m_sdk_manifest(
                    m_sdk.normalize_m_sdk_checklist(checklist_path)
                )
                self.assertEqual(assess(manifest)["state_summary"], "MATCHED")
                self.assertTrue((case / "artifacts/m_freertos_sdk/m7/m7.elf").is_file())
                self.assertTrue((case / "artifacts/m_freertos_sdk/m7/m7.bin").is_file())
                state = load_state(manifest)["components"]["m7"]
                self.assertEqual(state["origin"]["mode"], "source_build")
                self.assertEqual(state["origin"]["assurance"], "locally_built")

    def test_vendor_prebuilt_bin_is_imported_without_fake_build(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            archive = self._legacy_archive(root)
            catalog = self._catalog(root, archive, compiler_constraint="14.3")
            compiler = self._compiler(root)
            case = self._case(root)
            job = self._source_job()
            job["mode"] = "prebuilt_import"
            job["provenance"] = {
                "kind": "vendor_package",
                "artifacts": {
                    "bin": {
                        "member": "boards/fixture/demo_apps/hello_world/hello_world.bin"
                    }
                },
            }
            checklist_path = self._checklist(case, compiler, {"default_m7": job})
            with patch.object(m_sdk, "CATALOG_PATH", catalog):
                with redirect_stdout(io.StringIO()):
                    m_sdk.prepare_m_sdk_checklist(checklist_path)
                    m_sdk.run_m_sdk_checklist(checklist_path)
                normalized = m_sdk.normalize_m_sdk_checklist(checklist_path)
                manifest = m_sdk.materialize_m_sdk_manifest(normalized)
                state = load_state(manifest)["components"]["default_m7"]
                self.assertEqual(state["kind"], "import")
                self.assertEqual(state["origin"]["mode"], "prebuilt_import")
                self.assertEqual(state["origin"]["assurance"], "catalog_verified")
                request = yaml.safe_load(
                    (checklist_path.parent / ".compile-tool-request.yaml").read_text()
                )
                self.assertEqual(len(request["compile"]["units"]), 1)
                self.assertEqual(request["compile"]["units"][0]["action"], "import")
                self.assertEqual(request["compile"]["units"][0]["steps"][0]["env"], {})
                self.assertTrue(
                    request["compile"]["units"][0]["steps"][0]["command"].startswith(
                        "/usr/bin/install -D -m 0644 "
                    )
                )
                self.assertEqual(
                    (case / "artifacts/m_freertos_sdk/default_m7/default_m7.bin").read_bytes(),
                    b"vendor-default-bin",
                )
                self.assertNotIn("default_m7.elf", manifest["exports"])

    def test_user_supplied_requires_hash_and_records_attestation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            archive = self._legacy_archive(root)
            catalog = self._catalog(root, archive)
            compiler = self._compiler(root)
            case = self._case(root)
            supplied = case / "inputs" / "trusted.bin"
            supplied.parent.mkdir(parents=True)
            supplied.write_bytes(b"user-trusted-bin")
            job = self._source_job()
            job["mode"] = "prebuilt_import"
            job["provenance"] = {
                "kind": "user_supplied",
                "trust_reason": "user selected a known matching payload",
                "artifacts": {
                    "bin": {"path": str(supplied), "sha256": hash_file(supplied)}
                },
            }
            checklist_path = self._checklist(case, compiler, {"trusted": job})
            with patch.object(m_sdk, "CATALOG_PATH", catalog):
                with redirect_stdout(io.StringIO()):
                    m_sdk.prepare_m_sdk_checklist(checklist_path)
                    m_sdk.run_m_sdk_checklist(checklist_path)
                manifest = m_sdk.materialize_m_sdk_manifest(
                    m_sdk.normalize_m_sdk_checklist(checklist_path)
                )
                origin = load_state(manifest)["components"]["trusted"]["origin"]
                self.assertEqual(origin["assurance"], "user_attested")
                supplied.write_bytes(b"changed")
                with self.assertRaisesRegex(ToolError, "hash mismatch"):
                    m_sdk.normalize_m_sdk_checklist(checklist_path)

    def test_west_layout_generates_controlled_command_and_rejects_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            archive = self._west_archive(root)
            catalog = self._catalog(root, archive, release="25.12.00")
            compiler = self._compiler(root)
            case = self._case(root)
            checklist_path = self._checklist(case, compiler, {"m7": self._source_job()})
            with patch.object(m_sdk, "CATALOG_PATH", catalog), patch(
                "compile_tool.m_sdk.shutil.which", return_value="/usr/bin/west"
            ):
                output = io.StringIO()
                with redirect_stdout(output):
                    m_sdk.prepare_m_sdk_checklist(checklist_path)
                rendered = output.getvalue()
                self.assertIn("受控 backend：west", rendered)
                self.assertIn("west build -b fixture", rendered)
                self.assertIn("-p always", rendered)
                self.assertIn("--config release", rendered)
                self.assertIn("-Dcore_id=cm7", rendered)
                self.assertIn("hello_world_cm7.elf", rendered)

            bad_catalog = self._catalog(root / "bad", archive, release="25.09.00")
            with patch.object(m_sdk, "CATALOG_PATH", bad_catalog):
                with self.assertRaisesRegex(ToolError, "legacy backend.*West layout"):
                    m_sdk.normalize_m_sdk_checklist(checklist_path)

    def test_jobs_outside_scope_must_have_reusable_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            archive = self._legacy_archive(root, second_core=True)
            catalog = self._catalog(
                root, archive, cores={"cm7": "m70", "cm7b": "m71"}
            )
            compiler = self._compiler(root)
            case = self._case(root)
            jobs = {
                "m70": self._source_job("cm7", "m70"),
                "m71": self._source_job("cm7b", "m71"),
            }
            checklist_path = self._checklist(case, compiler, jobs, scope=["m70"])
            with patch.object(m_sdk, "CATALOG_PATH", catalog):
                with self.assertRaisesRegex(ToolError, "every package-backed job"):
                    m_sdk.prepare_m_sdk_checklist(checklist_path)

    def test_jobs_keep_independent_state_and_execution_scope(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            archive = self._legacy_archive(root)
            catalog = self._catalog(root, archive, cores={"cm7": "m70"})
            compiler = self._compiler(root)
            case = self._case(root)

            def vendor_job() -> dict:
                job = self._source_job("cm7", "m70")
                job["mode"] = "prebuilt_import"
                job["provenance"] = {
                    "kind": "vendor_package",
                    "artifacts": {
                        "bin": {
                            "member": "boards/fixture/demo_apps/hello_world/hello_world.bin"
                        }
                    },
                }
                return job

            jobs = {"m70_a": vendor_job(), "m70_b": vendor_job()}
            checklist_path = self._checklist(case, compiler, jobs)
            with patch.object(m_sdk, "CATALOG_PATH", catalog):
                with redirect_stdout(io.StringIO()):
                    m_sdk.prepare_m_sdk_checklist(checklist_path)
                    m_sdk.run_m_sdk_checklist(checklist_path)
                manifest = materialize_public_manifest(
                    normalize_public_checklist(checklist_path)
                )
                first_state = load_state(manifest)["components"]
                untouched_hash = first_state["m70_b"]["outputs"][0]["sha256"]
                (case / "artifacts/m_freertos_sdk/m70_a/m70_a.bin").write_bytes(
                    b"tampered"
                )
                checklist_path = self._checklist(
                    case, compiler, jobs, scope=["m70_a"]
                )
                with redirect_stdout(io.StringIO()):
                    m_sdk.prepare_m_sdk_checklist(checklist_path)
                request = yaml.safe_load(
                    (checklist_path.parent / ".compile-tool-request.yaml").read_text()
                )
                self.assertEqual(
                    [unit["component"] for unit in request["compile"]["units"]],
                    ["m70_a"],
                )
                with redirect_stdout(io.StringIO()):
                    m_sdk.run_m_sdk_checklist(checklist_path)
                final_state = load_state(
                    materialize_public_manifest(normalize_public_checklist(checklist_path))
                )["components"]
                self.assertEqual(
                    final_state["m70_b"]["outputs"][0]["sha256"], untouched_hash
                )

    def test_raw_fields_bad_catalog_hash_and_non_elf_import_are_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            archive = self._legacy_archive(root)
            catalog = self._catalog(root, archive)
            compiler = self._compiler(root)
            case = self._case(root)
            checklist_path = self._checklist(case, compiler, {"m7": self._source_job()})
            raw = yaml.safe_load(checklist_path.read_text())
            raw["jobs"]["m7"]["command"] = "make arbitrary"
            checklist_path.write_text(yaml.safe_dump(raw, sort_keys=False))
            with patch.object(m_sdk, "CATALOG_PATH", catalog):
                with self.assertRaisesRegex(ToolError, "unsupported fields: command"):
                    m_sdk.normalize_m_sdk_checklist(checklist_path)

            checklist_path = self._checklist(case, compiler, {"m7": self._source_job()})
            catalog_raw = yaml.safe_load(catalog.read_text())
            catalog_raw["packages"]["SDK_FIXTURE"]["sha256"] = "sha256:" + "0" * 64
            catalog.write_text(yaml.safe_dump(catalog_raw, sort_keys=False))
            with patch.object(m_sdk, "CATALOG_PATH", catalog):
                with self.assertRaisesRegex(ToolError, "package hash mismatch"):
                    m_sdk.normalize_m_sdk_checklist(checklist_path)

            catalog = self._catalog(root / "restored", archive)
            bogus_elf = case / "inputs" / "bogus.elf"
            bogus_elf.parent.mkdir(parents=True, exist_ok=True)
            bogus_elf.write_bytes(b"not-an-elf")
            job = self._source_job()
            job["mode"] = "prebuilt_import"
            job["provenance"] = {
                "kind": "user_supplied",
                "trust_reason": "negative type validation fixture",
                "artifacts": {
                    "elf": {"path": str(bogus_elf), "sha256": hash_file(bogus_elf)}
                },
            }
            checklist_path = self._checklist(case, compiler, {"bogus": job})
            with patch.object(m_sdk, "CATALOG_PATH", catalog):
                with redirect_stdout(io.StringIO()):
                    m_sdk.prepare_m_sdk_checklist(checklist_path)
                with self.assertRaisesRegex(ToolError, "invalid ELF magic"):
                    with redirect_stdout(io.StringIO()):
                        m_sdk.run_m_sdk_checklist(checklist_path)

    def test_public_m_producer_artifact_resolves_for_downstream_consumer(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            archive = self._legacy_archive(root)
            catalog = self._catalog(root, archive)
            compiler = self._compiler(root)
            case = self._case(root)
            job = self._source_job()
            job["mode"] = "prebuilt_import"
            job["provenance"] = {
                "kind": "vendor_package",
                "artifacts": {
                    "bin": {
                        "member": "boards/fixture/demo_apps/hello_world/hello_world.bin"
                    }
                },
            }
            checklist_path = self._checklist(case, compiler, {"default_m7": job})
            with patch.object(m_sdk, "CATALOG_PATH", catalog):
                with redirect_stdout(io.StringIO()):
                    m_sdk.prepare_m_sdk_checklist(checklist_path)
                    m_sdk.run_m_sdk_checklist(checklist_path)
                producer = materialize_public_manifest(
                    normalize_public_checklist(checklist_path)
                )
                consumer = {
                    "case": producer["case"],
                    "case_root": producer["case_root"],
                    "target": "imx-mkimage-fixture",
                    "profile": {"hash": "sha256:consumer-fixture"},
                    "hash": "sha256:consumer-manifest-fixture",
                    "parameters": {
                        "soc": {"value": "imxfixture"},
                        "m_role": {"value": "m7"},
                    },
                    "project_profile": {
                        "artifact_inputs": {
                            "m_payload": {
                                "type": "nxp.mcore.bin",
                                "parameter_matches": {
                                    "soc": "soc",
                                    "core_role": "m_role",
                                },
                            }
                        }
                    },
                    "artifact_inputs": {
                        "m_payload": {
                            "slot": "m_payload",
                            "manifest": producer["path"],
                            "artifact": "default_m7.bin",
                        }
                    },
                }
                resolved = resolve_artifact_inputs(consumer)["m_payload"]
                self.assertEqual(resolved["type"], "nxp.mcore.bin")
                self.assertEqual(resolved["identity"]["core_role"], "m7")
                self.assertEqual(
                    resolved["producer_origin"]["assurance"], "catalog_verified"
                )
                Path(resolved["path"]).write_bytes(b"replaced")
                with self.assertRaisesRegex(ToolError, "content differs"):
                    resolve_artifact_inputs(consumer)

    def test_mkimage_prepare_resolves_public_m_producer(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fixture = ChecklistFixture(root)
            archive = self._legacy_archive(root / "m-sdk")
            catalog = self._catalog(root / "m-sdk", archive)
            compiler = self._compiler(root / "m-sdk")

            profile_path = fixture.projects / "imx-mkimage" / "COMPILE_PROFILE.yaml"
            profile = yaml.safe_load(profile_path.read_text())
            profile["artifact_inputs"]["m_payload"] = {
                "type": "nxp.mcore.bin",
                "multiple": True,
                "parameter_matches": {},
            }
            profile["file_inputs"].pop("m_payload")
            profile_path.write_text(yaml.safe_dump(profile, sort_keys=False))

            m_checklist = (
                fixture.case_root
                / "records"
                / "compile"
                / "m_freertos_sdk"
                / "compile.yaml"
            )
            m_checklist.parent.mkdir(parents=True)
            m_job = self._source_job()
            m_job["mode"] = "prebuilt_import"
            m_job["provenance"] = {
                "kind": "vendor_package",
                "artifacts": {
                    "bin": {
                        "member": "boards/fixture/demo_apps/hello_world/hello_world.bin"
                    }
                },
            }
            m_checklist.write_text(
                yaml.safe_dump(
                    {
                        "schema_version": 1,
                        "kind": "m_freertos_sdk_compile_checklist",
                        "target": "m_freertos_sdk",
                        "case_root": str(fixture.case_root),
                        "sdk": {
                            "package": "SDK_FIXTURE",
                            "compiler": str(compiler),
                        },
                        "jobs": {"default_m7": m_job},
                        "intent": {
                            "scope": ["default_m7"],
                            "reason": "mkimage dependency resolution fixture",
                        },
                    },
                    sort_keys=False,
                )
            )

            first_patch, second_patch = fixture.patches()
            with first_patch, second_patch, patch.object(m_sdk, "CATALOG_PATH", catalog):
                oei = fixture.oei_checklist()
                with redirect_stdout(io.StringIO()):
                    m_sdk.prepare_m_sdk_checklist(m_checklist)
                    m_sdk.run_m_sdk_checklist(m_checklist)
                    from compile_tool.checklists import prepare_checklist, run_checklist

                    prepare_checklist(oei)
                    run_checklist(oei)

                mkimage = fixture.mkimage_checklist()
                mk_data = yaml.safe_load(mkimage.read_text())
                mk_data["inputs"]["artifacts"].append(
                    {
                        "name": "m7",
                        "slot": "m_payload",
                        "checklist": str(m_checklist.relative_to(fixture.case_root)),
                        "artifact": "default_m7.bin",
                        "stage_to": "inputs/m7.bin",
                    }
                )
                mkimage.write_text(yaml.safe_dump(mk_data, sort_keys=False))
                prepared = io.StringIO()
                with redirect_stdout(prepared):
                    self.assertEqual(prepare_checklist(mkimage), 0)
                self.assertIn("stage-m7", prepared.getvalue())
                consumer_manifest = load_manifest(mkimage.parent / "manifest.yaml")
                self.assertEqual(
                    resolve_artifact_inputs(consumer_manifest)["m7"]["type"],
                    "nxp.mcore.bin",
                )


if __name__ == "__main__":
    unittest.main()

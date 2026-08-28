from __future__ import annotations

from contextlib import redirect_stdout
import io
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import yaml

from compile_tool import checklists, composition, profiles
from compile_tool.cli import main
from compile_tool.common import ToolError
from compile_tool.state import load_state
from compile_tool.manifest import load_manifest


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


class ChecklistFixture:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.support = root / "support_level"
        self.projects = self.support / "code_assets" / "projects"
        self.case_root = self.support / "work" / "checklist-case"
        self.case_root.mkdir(parents=True)
        self.compiler = self.support / "tools" / "arm-none-eabi-gcc"
        self.compiler.parent.mkdir(parents=True)
        self.compiler.write_text("#!/bin/sh\nprintf 'fixture compiler 1.0\\n'\n")
        self.compiler.chmod(0o755)
        self.fixed = self.case_root / "inputs" / "fixed.bin"
        self.fixed.parent.mkdir(parents=True)
        self.fixed.write_text("fixed-v1\n")
        self._create_oei_project()
        self._create_mkimage_project()

    def patches(self):
        return (
            patch.object(profiles, "PROJECTS_ROOT", self.projects),
            patch.object(checklists, "PROJECTS_ROOT", self.projects),
        )

    def _source_repo(self, project: str, makefile: str) -> Path:
        source = self.projects / project / "source"
        source.mkdir(parents=True)
        run_git(source, "init")
        run_git(source, "config", "user.email", "fixture@example.com")
        run_git(source, "config", "user.name", "Fixture")
        (source / "Makefile").write_text(makefile)
        run_git(source, "add", "Makefile")
        run_git(source, "commit", "-m", "initial")
        run_git(source, "tag", "release-v1")
        run_git(source, "remote", "add", "origin", f"https://fixture.invalid/{project}")
        return source

    @staticmethod
    def _profile(project: str, *, action: str, output_type: str, output_path: str) -> dict:
        return {
            "schema_version": 1,
            "id": project,
            "type": "project_compile",
            "target": project,
            "component": project,
            "action": action,
            "source": {
                "id": project,
                "path": "source",
                "case_path": f"sources/{project}",
                "ref_kind": "tag",
                "remote": "origin",
                "remote_url": f"https://fixture.invalid/{project}",
                "update": "if_missing",
            },
            "parameters": {},
            "configuration_parameters": [],
            "tools": [
                {
                    "name": "make",
                    "path": "/usr/bin/make",
                    "version_args": ["--version"],
                },
                {
                    "name": "compiler",
                    "path": "tools/arm-none-eabi-gcc",
                    "version_args": [],
                }
            ],
            "watched_inputs": [],
            "outputs": {
                "oei_ddr" if project == "imx-oei" else "flashbin": {
                    "type": output_type,
                    "path": output_path,
                    "identity_parameters": ["silicon_revision"],
                }
            },
            "artifact_inputs": {},
            "file_inputs": {},
        }

    def _create_oei_project(self) -> None:
        self._source_repo(
            "imx-oei",
            "all:\n\tmkdir -p build/$(board)/$(oei)\n"
            "\tprintf 'oei-%s-%s\\n' '$(REV)' '$(board)' > "
            "build/$(board)/$(oei)/oei-m33-ddr.bin\n",
        )
        profile = self._profile(
            "imx-oei",
            action="rebuild",
            output_type="nxp.oei.ddr-image",
            output_path="artifacts/imx-oei/oei-m33-ddr.bin",
        )
        profile["parameters"] = {
            "silicon_revision": {"source": "user", "required": True},
            "board": {"source": "user", "required": True},
            "oei_type": {"source": "project", "default": "ddr"},
        }
        profile["configuration_parameters"] = ["silicon_revision", "board", "oei_type"]
        profile["checklist_build"] = {
            "mode": "isolated_git",
            "env": {"OEI_CROSS_COMPILE": "${tool_prefix.compiler}"},
            "steps": [
                {
                    "name": "build-imx-oei",
                    "command": [
                        "${tools.make}",
                        "REV=${parameters.silicon_revision}",
                        "R=${parameters.silicon_revision}",
                        "board=${parameters.board}",
                        "oei=${parameters.oei_type}",
                    ],
                }
            ],
        }
        template = {
            "schema_version": 1,
            "kind": "project_compile_checklist",
            "project": "imx-oei",
            "case_root": "TBD",
            "source": {"ref": "TBD"},
            "parameters": {"silicon_revision": "TBD", "board": "TBD", "oei_type": "ddr"},
            "inputs": {"artifacts": [], "files": []},
            "toolchain": {"make": "/usr/bin/make", "compiler": "tools/arm-none-eabi-gcc"},
            "intent": {"action": "rebuild", "reason": "TBD"},
            "build": {"mode": "isolated_git"},
            "outputs": {
                "oei_ddr": {
                    "type": "nxp.oei.ddr-image",
                    "collect_from": "build/${parameters.board}/${parameters.oei_type}/oei-m33-ddr.bin",
                    "publish_to": "artifacts/imx-oei/oei-m33-ddr.bin",
                }
            },
        }
        write_yaml(self.projects / "imx-oei" / "COMPILE_PROFILE.yaml", profile)
        write_yaml(self.projects / "imx-oei" / "COMPILE_CHECKLIST.yaml", template)

    def _create_mkimage_project(self) -> None:
        self._source_repo(
            "imx-mkimage",
            "all:\n\tmkdir -p $(SOC)\n"
            "\tcat inputs/oei.bin inputs/fixed.bin > $(SOC)/flash.bin\n",
        )
        profile = self._profile(
            "imx-mkimage",
            action="repack",
            output_type="nxp.boot.flashbin",
            output_path="artifacts/imx-mkimage/flash.bin",
        )
        profile["parameters"] = {
            "silicon_revision": {"source": "user", "required": True},
            "soc": {"source": "user", "required": True},
            "recipe": {"source": "user", "required": True},
            "lpddr_type": {"source": "user", "required": True},
            "oei_enabled": {"source": "project", "default": "NO"},
        }
        profile["configuration_parameters"] = list(profile["parameters"])
        profile["artifact_inputs"] = {
            "oei": {
                "type": "nxp.oei.ddr-image",
                "multiple": False,
                "required_when": {"parameter": "oei_enabled", "equals": "YES"},
                "parameter_matches": {"silicon_revision": "silicon_revision"},
            }
        }
        profile["file_inputs"] = {
            "firmware": {"multiple": True},
            "m_payload": {"multiple": True},
        }
        profile["checklist_build"] = {
            "mode": "isolated_git",
            "env": {},
            "steps": [
                {
                    "name": "build-imx-mkimage",
                    "command": [
                        "${tools.make}",
                        "SOC=${parameters.soc}",
                        "REV=${parameters.silicon_revision}",
                        "OEI=${parameters.oei_enabled}",
                        "LPDDR_TYPE=${parameters.lpddr_type}",
                        "${parameters.recipe}",
                    ],
                }
            ],
        }
        template = {
            "schema_version": 1,
            "kind": "project_compile_checklist",
            "project": "imx-mkimage",
            "case_root": "TBD",
            "source": {"ref": "TBD"},
            "parameters": {
                "silicon_revision": "TBD",
                "soc": "TBD",
                "recipe": "TBD",
                "lpddr_type": "TBD",
                "oei_enabled": "TBD",
            },
            "inputs": {"artifacts": [], "files": []},
            "toolchain": {"make": "/usr/bin/make", "compiler": "tools/arm-none-eabi-gcc"},
            "intent": {"action": "repack", "reason": "TBD"},
            "build": {"mode": "isolated_git"},
            "outputs": {
                "flashbin": {
                    "type": "nxp.boot.flashbin",
                    "collect_from": "${parameters.soc}/flash.bin",
                    "publish_to": "artifacts/imx-mkimage/flash.bin",
                }
            },
        }
        write_yaml(self.projects / "imx-mkimage" / "COMPILE_PROFILE.yaml", profile)
        write_yaml(self.projects / "imx-mkimage" / "COMPILE_CHECKLIST.yaml", template)

    def oei_checklist(self, *, action: str = "rebuild") -> Path:
        data = yaml.safe_load((self.projects / "imx-oei" / "COMPILE_CHECKLIST.yaml").read_text())
        data["case_root"] = str(self.case_root)
        data["source"]["ref"] = "release-v1"
        data["parameters"].update({"silicon_revision": "B0", "board": "mx95lp5"})
        data["intent"] = {"action": action, "reason": "fixture OEI build"}
        path = self.case_root / "records" / "compile" / "imx-oei" / "compile.yaml"
        write_yaml(path, data)
        return path

    def mkimage_checklist(self, *, payload: Path | None = None) -> Path:
        data = yaml.safe_load((self.projects / "imx-mkimage" / "COMPILE_CHECKLIST.yaml").read_text())
        data["case_root"] = str(self.case_root)
        data["source"]["ref"] = "release-v1"
        data["parameters"].update(
            {
                "silicon_revision": "B0",
                "soc": "fixture-soc",
                "recipe": "all",
                "lpddr_type": "lpddr5",
                "oei_enabled": "YES",
            }
        )
        data["inputs"] = {
            "artifacts": [
                {
                    "name": "oei",
                    "slot": "oei",
                    "checklist": "records/compile/imx-oei/compile.yaml",
                    "artifact": "oei_ddr",
                    "stage_to": "inputs/oei.bin",
                }
            ],
            "files": [
                {
                    "name": "fixed",
                    "slot": "firmware",
                    "path": "inputs/fixed.bin",
                    "stage_to": "inputs/fixed.bin",
                }
            ],
        }
        if payload is not None:
            data["inputs"]["files"].append(
                {
                    "name": "m7",
                    "slot": "m_payload",
                    "path": str(payload.relative_to(self.case_root)),
                    "stage_to": "inputs/m7.bin",
                }
            )
        data["intent"] = {"action": "repack", "reason": "fixture mkimage pack"}
        path = self.case_root / "records" / "compile" / "imx-mkimage" / "compile.yaml"
        write_yaml(path, data)
        return path


class ChecklistWorkflowTests(unittest.TestCase):
    def test_oei_single_checklist_prepare_run_and_reuse(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = ChecklistFixture(Path(temp_dir))
            first_patch, second_patch = fixture.patches()
            with first_patch, second_patch:
                checklist = fixture.oei_checklist()
                prepared = io.StringIO()
                with redirect_stdout(prepared):
                    self.assertEqual(main(["prepare", str(checklist)]), 0)
                self.assertIn("ACQUIRE_REQUIRED", prepared.getvalue())
                with redirect_stdout(io.StringIO()):
                    self.assertEqual(main(["run", str(checklist)]), 0)
                output = fixture.case_root / "artifacts" / "imx-oei" / "oei-m33-ddr.bin"
                self.assertEqual(output.read_text(), "oei-B0-mx95lp5\n")
                self.assertEqual(
                    main(["prepare", str(checklist.parent / ".compile-tool-request.yaml")]),
                    2,
                )

                checklist = fixture.oei_checklist(action="reuse")
                with redirect_stdout(io.StringIO()):
                    self.assertEqual(main(["prepare", str(checklist)]), 0)
                    self.assertEqual(main(["run", str(checklist)]), 0)
                manifest = load_manifest(checklist.parent / "manifest.yaml")
                self.assertIn("imx-oei", load_state(manifest)["_root_state"]["targets"])

    def test_command_mismatch_and_mkimage_artifact_flow(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = ChecklistFixture(Path(temp_dir))
            first_patch, second_patch = fixture.patches()
            with first_patch, second_patch:
                bad = fixture.oei_checklist()
                data = yaml.safe_load(bad.read_text())
                data["build"]["command"] = "make REV=A0"
                write_yaml(bad, data)
                with self.assertRaisesRegex(ToolError, "build.*exactly match"):
                    checklists.normalize_checklist(bad)

                oei = fixture.oei_checklist()
                with redirect_stdout(io.StringIO()):
                    self.assertEqual(main(["prepare", str(oei)]), 0)
                    self.assertEqual(main(["run", str(oei)]), 0)
                mkimage = fixture.mkimage_checklist()
                prepared = io.StringIO()
                with redirect_stdout(prepared):
                    self.assertEqual(main(["prepare", str(mkimage)]), 0)
                self.assertIn("stage-oei", prepared.getvalue())
                self.assertIn("stage-fixed", prepared.getvalue())
                with redirect_stdout(io.StringIO()):
                    self.assertEqual(main(["run", str(mkimage)]), 0)
                flashbin = fixture.case_root / "artifacts" / "imx-mkimage" / "flash.bin"
                self.assertEqual(flashbin.read_text(), "oei-B0-mx95lp5\nfixed-v1\n")

                payload = fixture.case_root / "inputs" / "m7.bin"
                payload.write_text("m7-v1\n")
                mkimage = fixture.mkimage_checklist(payload=payload)
                payload_plan = io.StringIO()
                with redirect_stdout(payload_plan):
                    self.assertEqual(main(["prepare", str(mkimage)]), 0)
                self.assertIn("stage-m7", payload_plan.getvalue())
                self.assertIn("CHANGES_OBSERVED", payload_plan.getvalue())
                with redirect_stdout(io.StringIO()):
                    self.assertEqual(main(["run", str(mkimage)]), 0)

                (fixture.case_root / "artifacts" / "imx-oei" / "oei-m33-ddr.bin").write_text("tampered\n")
                with self.assertRaisesRegex(ToolError, "differs from its producer"):
                    checklists.prepare_checklist(mkimage)


class RealProjectChecklistContractTests(unittest.TestCase):
    def test_soc_mak_parser_discovers_m_payloads_beyond_imx94_imx95(self) -> None:
        source = profiles.PROJECTS_ROOT / "imx-mkimage" / "imx-mkimage"
        cases = {
            ("iMX94", "flash_all"): [
                "m33_image.bin",
                "m33s_image.bin",
                "m70_image.bin",
                "m71_image.bin",
            ],
            ("iMX95", "flash_all"): ["m33_image.bin", "m7_image.bin"],
            ("iMX8DXL", "flash_linux_m4"): ["m4_image.bin"],
            ("iMX8QM", "flash_linux_m4"): ["m4_1_image.bin", "m4_image.bin"],
        }
        for (soc, recipe), expected in cases.items():
            text = (source / soc / "soc.mak").read_text(encoding="utf-8")
            self.assertEqual(composition.make_recipe_m_images(text, recipe), expected)

    def _prepare(
        self,
        case_root: Path,
        project: str,
        parameters: dict[str, str],
    ) -> str:
        template_path = profiles.PROJECTS_ROOT / project / "COMPILE_CHECKLIST.yaml"
        data = yaml.safe_load(template_path.read_text(encoding="utf-8"))
        data["case_root"] = str(case_root)
        data["source"]["ref"] = "lf-6.18.2-1.0.0"
        data["parameters"].update(parameters)
        data["intent"]["reason"] = f"verify {project} checklist contract"
        path = case_root / "records" / "compile" / project / "compile.yaml"
        write_yaml(path, data)
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(["prepare", str(path)]), 0)
        return output.getvalue()

    def test_atf_uboot_optee_and_smfw_commands_are_profile_generated(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            atf_case = root / "atf-case"
            atf_case.mkdir()
            atf = self._prepare(
                atf_case,
                "imx-atf",
                {"platform": "imx95", "spd": "opteed"},
            )
            self.assertIn("PLAT=imx95 SPD=opteed bl31", atf)
            self.assertIn("-u LDFLAGS -u AS", atf)

            uboot_case = root / "uboot-case"
            uboot_case.mkdir()
            uboot = self._prepare(
                uboot_case,
                "uboot-imx",
                {"defconfig": "imx95_19x19_evk_defconfig"},
            )
            self.assertIn("configure-uboot-imx", uboot)
            self.assertIn("O=build imx95_19x19_evk_defconfig", uboot)
            self.assertIn("build-uboot-imx", uboot)
            self.assertIn("-j8", uboot)

            optee_case = root / "optee-case"
            optee_case.mkdir()
            optee = self._prepare(
                optee_case,
                "imx-optee-os",
                {"platform_flavor": "mx95evk"},
            )
            self.assertIn("PLATFORM=imx PLATFORM_FLAVOR=mx95evk", optee)
            self.assertIn("CROSS_COMPILE64=", optee)

            smfw_case = root / "smfw-case"
            smfw_case.mkdir()
            smfw = self._prepare(
                smfw_case,
                "imx-sm",
                {"config": "other/mx95rte"},
            )
            self.assertIn("/usr/bin/rm -rf configs/other/mx95rte", smfw)
            self.assertLess(smfw.index("remove-generated-smfw-config"), smfw.index("really-clean-imx-sm"))
            self.assertLess(smfw.index("really-clean-imx-sm"), smfw.index("configure-imx-sm"))
            self.assertLess(smfw.index("configure-imx-sm"), smfw.index("build-imx-sm"))

    def test_profile_parameter_allowlist_blocks_invalid_platform(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            case_root = Path(temp_dir) / "bad-atf-case"
            case_root.mkdir()
            template_path = profiles.PROJECTS_ROOT / "imx-atf" / "COMPILE_CHECKLIST.yaml"
            data = yaml.safe_load(template_path.read_text(encoding="utf-8"))
            data["case_root"] = str(case_root)
            data["source"]["ref"] = "lf-6.18.2-1.0.0"
            data["parameters"].update({"platform": "imx93", "spd": "none"})
            data["intent"]["reason"] = "verify invalid platform is blocked"
            path = case_root / "records" / "compile" / "imx-atf" / "compile.yaml"
            write_yaml(path, data)
            with self.assertRaisesRegex(ToolError, "must be one of"):
                checklists.prepare_checklist(path)

    def _mkimage_draft(self, case_root: Path, recipe: str = "flash_a55") -> Path:
        template = profiles.PROJECTS_ROOT / "imx-mkimage" / "COMPILE_CHECKLIST.yaml"
        data = yaml.safe_load(template.read_text(encoding="utf-8"))
        data["case_root"] = str(case_root)
        data["source"]["ref"] = "lf-6.18.2-1.0.0"
        data["parameters"].update(
            {
                "silicon_revision": "B0",
                "soc": "iMX95",
                "recipe": recipe,
                "lpddr_type": "lpddr5",
                "oei_enabled": "NO",
            }
        )
        data["intent"]["reason"] = "verify recipe input contract"
        path = case_root / "records" / "compile" / "imx-mkimage" / "compile.yaml"
        write_yaml(path, data)
        return path

    def test_mkimage_recipe_contract_blocks_missing_roles_and_unknown_recipe(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            case_root = Path(temp_dir) / "mkimage-contract-case"
            case_root.mkdir()
            path = self._mkimage_draft(case_root)
            with self.assertRaisesRegex(ToolError, "requires role atf"):
                checklists.normalize_checklist(path)

            path = self._mkimage_draft(case_root, recipe="flash_kernel")
            with self.assertRaisesRegex(ToolError, "unsupported project input combination"):
                checklists.normalize_checklist(path)

    def _producer_stub(
        self,
        case_root: Path,
        project: str,
        parameters: dict[str, str],
    ) -> Path:
        path = case_root / "records" / "compile" / project / "compile.yaml"
        write_yaml(
            path,
            {
                "schema_version": 1,
                "kind": "project_compile_checklist",
                "project": project,
                "parameters": parameters,
            },
        )
        return path

    def test_mkimage_recipe_contract_accepts_complete_roles_and_binds_optee_to_atf(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            case_root = Path(temp_dir) / "mkimage-complete-contract-case"
            case_root.mkdir()
            path = self._mkimage_draft(case_root)
            atf = self._producer_stub(
                case_root,
                "imx-atf",
                {"platform": "imx95", "spd": "none"},
            )
            uboot = self._producer_stub(
                case_root,
                "uboot-imx",
                {"defconfig": "imx95_19x19_evk_defconfig", "jobs": "8"},
            )
            smfw = self._producer_stub(
                case_root,
                "imx-sm",
                {"config": "other/mx95rte"},
            )
            ahab = case_root / "inputs" / "mx95b0-ahab-container.img"
            ahab.parent.mkdir()
            shutil.copyfile(
                profiles.SUPPORT_LEVEL
                / "firmware/imx95/firmware-ele-imx-2.0.3-286c884/mx95b0-ahab-container.img",
                ahab,
            )
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            data["inputs"] = {
                "artifacts": [
                    {
                        "name": "atf",
                        "slot": "atf",
                        "checklist": str(atf.relative_to(case_root)),
                        "artifact": "bl31",
                        "stage_to": "iMX95/bl31.bin",
                    },
                    {
                        "name": "uboot_bin",
                        "slot": "uboot_bin",
                        "checklist": str(uboot.relative_to(case_root)),
                        "artifact": "uboot_bin",
                        "stage_to": "iMX95/u-boot.bin",
                    },
                    {
                        "name": "uboot_spl",
                        "slot": "uboot_spl",
                        "checklist": str(uboot.relative_to(case_root)),
                        "artifact": "uboot_spl",
                        "stage_to": "iMX95/u-boot-spl.bin",
                    },
                    {
                        "name": "smfw",
                        "slot": "smfw",
                        "checklist": str(smfw.relative_to(case_root)),
                        "artifact": "smfw",
                        "stage_to": "iMX95/m33_image.bin",
                    },
                ],
                "files": [
                    {
                        "name": "ahab",
                        "slot": "ahab",
                        "path": str(ahab.relative_to(case_root)),
                        "stage_to": "iMX95/mx95b0-ahab-container.img",
                    }
                ],
            }
            write_yaml(path, data)
            normalized = checklists.normalize_checklist(path)
            self.assertEqual(normalized["project"], "imx-mkimage")
            self.assertEqual(normalized["make_recipe"]["source"], "iMX95/soc.mak")
            self.assertEqual(
                list(normalized["make_recipe"]["required_m_payloads"].values()),
                [],
            )

            optee = self._producer_stub(
                case_root,
                "imx-optee-os",
                {"platform": "imx", "platform_flavor": "mx95evk"},
            )
            data["inputs"]["artifacts"].append(
                {
                    "name": "optee",
                    "slot": "optee",
                    "checklist": str(optee.relative_to(case_root)),
                    "artifact": "tee",
                    "stage_to": "iMX95/tee.bin",
                }
            )
            write_yaml(path, data)
            with self.assertRaisesRegex(ToolError, "requires atf producer parameter spd=opteed"):
                checklists.normalize_checklist(path)

            atf_data = yaml.safe_load(atf.read_text(encoding="utf-8"))
            atf_data["parameters"]["spd"] = "opteed"
            write_yaml(atf, atf_data)
            self.assertEqual(checklists.normalize_checklist(path)["project"], "imx-mkimage")

            ahab.write_bytes(b"wrong fixed asset\n")
            with self.assertRaisesRegex(ToolError, "content hash does not match"):
                checklists.normalize_checklist(path)

    def test_mkimage_flash_all_requires_mcore_bin_producer_roles(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            case_root = Path(temp_dir) / "mkimage-mcore-contract-case"
            case_root.mkdir()
            path = self._mkimage_draft(case_root, recipe="flash_all")
            atf = self._producer_stub(
                case_root, "imx-atf", {"platform": "imx95", "spd": "none"}
            )
            uboot = self._producer_stub(
                case_root,
                "uboot-imx",
                {"defconfig": "imx95_19x19_evk_defconfig", "jobs": "8"},
            )
            smfw = self._producer_stub(
                case_root, "imx-sm", {"config": "other/mx95rte"}
            )
            m_sdk = case_root / "records/compile/m_freertos_sdk/compile.yaml"
            write_yaml(
                m_sdk,
                {
                    "schema_version": 1,
                    "kind": "m_freertos_sdk_compile_checklist",
                    "target": "m_freertos_sdk",
                    "jobs": {
                        "m7": {
                            "mode": "source_build",
                            "soc": "imx95",
                            "board": "imx95lpd5evk19",
                            "core": "cm7",
                            "core_role": "m7",
                            "application": "demo_apps/hello_world",
                            "build_configuration": "release",
                        }
                    },
                },
            )
            ahab = case_root / "inputs/mx95b0-ahab-container.img"
            ahab.parent.mkdir()
            shutil.copyfile(
                profiles.SUPPORT_LEVEL
                / "firmware/imx95/firmware-ele-imx-2.0.3-286c884/mx95b0-ahab-container.img",
                ahab,
            )
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            data["inputs"] = {
                "artifacts": [
                    {"name": "atf", "slot": "atf", "checklist": str(atf.relative_to(case_root)), "artifact": "bl31", "stage_to": "iMX95/bl31.bin"},
                    {"name": "uboot_bin", "slot": "uboot_bin", "checklist": str(uboot.relative_to(case_root)), "artifact": "uboot_bin", "stage_to": "iMX95/u-boot.bin"},
                    {"name": "uboot_spl", "slot": "uboot_spl", "checklist": str(uboot.relative_to(case_root)), "artifact": "uboot_spl", "stage_to": "iMX95/u-boot-spl.bin"},
                    {"name": "smfw", "slot": "smfw", "checklist": str(smfw.relative_to(case_root)), "artifact": "smfw", "stage_to": "iMX95/m33_image.bin"},
                    {"name": "m7", "slot": "m_payload", "checklist": str(m_sdk.relative_to(case_root)), "artifact": "m7.bin", "stage_to": "iMX95/m7_image.bin"},
                ],
                "files": [
                    {"name": "ahab", "slot": "ahab", "path": str(ahab.relative_to(case_root)), "stage_to": "iMX95/mx95b0-ahab-container.img"}
                ],
            }
            write_yaml(path, data)
            normalized = checklists.normalize_checklist(path)
            self.assertEqual(normalized["project"], "imx-mkimage")
            self.assertEqual(normalized["make_recipe"]["source"], "iMX95/soc.mak")
            self.assertEqual(
                list(normalized["make_recipe"]["required_m_payloads"].values()),
                ["m7_image.bin"],
            )

            without_m = yaml.safe_load(path.read_text(encoding="utf-8"))
            without_m["inputs"]["artifacts"] = [
                entry
                for entry in without_m["inputs"]["artifacts"]
                if entry["slot"] != "m_payload"
            ]
            write_yaml(path, without_m)
            with self.assertRaisesRegex(
                ToolError, "soc.mak recipe iMX95/flash_all requires M payloads"
            ):
                checklists.normalize_checklist(path)
            write_yaml(path, data)

            m_data = yaml.safe_load(m_sdk.read_text(encoding="utf-8"))
            m_data["jobs"]["m7"]["core_role"] = "m70"
            write_yaml(m_sdk, m_data)
            with self.assertRaisesRegex(ToolError, "requires producer parameter core_role=m7"):
                checklists.normalize_checklist(path)

            data["inputs"]["artifacts"] = [
                entry for entry in data["inputs"]["artifacts"] if entry["name"] != "m7"
            ]
            data["inputs"]["files"].append(
                {"name": "raw_m7", "slot": "m_payload", "path": str(ahab.relative_to(case_root)), "stage_to": "iMX95/m7_image.bin"}
            )
            write_yaml(path, data)
            with self.assertRaisesRegex(ToolError, "unknown slots: m_payload"):
                checklists.normalize_checklist(path)

    def test_mkimage_fixed_asset_catalog_requires_exact_oei_firmware_set(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            ele = profiles.SUPPORT_LEVEL / "firmware/imx95/firmware-ele-imx-2.0.3-286c884"
            ddr = (
                profiles.SUPPORT_LEVEL
                / "firmware/imx95/firmware-imx-8.29-8741a3b/firmware/ddr/synopsys"
            )
            sources = {
                "ahab": ele / "mx95b0-ahab-container.img",
                "lpddr_imem": ddr / "lpddr5_imem_v202409.bin",
                "lpddr_dmem": ddr / "lpddr5_dmem_v202409.bin",
                "lpddr_imem_qb": ddr / "lpddr5_imem_qb_v202409.bin",
                "lpddr_dmem_qb": ddr / "lpddr5_dmem_qb_v202409.bin",
            }
            files = []
            for name, source in sources.items():
                destination = root / source.name
                shutil.copyfile(source, destination)
                files.append(
                    {
                        "name": name,
                        "slot": "ahab" if name == "ahab" else "firmware",
                        "path": str(destination),
                        "stage_to": f"iMX95/{source.name}",
                    }
                )
            profile = profiles.load_compile_profile("imx-mkimage")
            parameters = {
                "soc": "iMX95",
                "silicon_revision": "B0",
                "lpddr_type": "lpddr5",
                "oei_enabled": "YES",
            }
            composition.validate_fixed_asset_contract(
                profile["fixed_asset_contract"],
                parameters,
                {"artifacts": [], "files": files},
            )
            with self.assertRaisesRegex(ToolError, "requires roles: lpddr_dmem_qb"):
                composition.validate_fixed_asset_contract(
                    profile["fixed_asset_contract"],
                    parameters,
                    {"artifacts": [], "files": files[:-1]},
                )


if __name__ == "__main__":
    unittest.main()

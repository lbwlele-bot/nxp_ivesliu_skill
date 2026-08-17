#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest


MODULE_PATH = Path(__file__).with_name("validate_release.py")
SPEC = importlib.util.spec_from_file_location("validate_release", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
validate_release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validate_release)


class ReleaseValidatorTests(unittest.TestCase):
    def test_minimal_customer_integration_package_passes(self) -> None:
        with tempfile.TemporaryDirectory() as value:
            root = Path(value)
            (root / "README_CN.md").write_text(
                "# Demo\n\n整体设计\n为什么\n各组件修改\n移植\n已验证范围\n限制\n",
                encoding="utf-8",
            )
            (root / "RELEASE.yaml").write_text(
                "schema_version: 1\nname: demo\naudience: customer_integration\n",
                encoding="utf-8",
            )
            checksum_lines = []
            for relative in (Path("README_CN.md"), Path("RELEASE.yaml")):
                checksum_lines.append(f"{validate_release.sha256(root / relative)}  {relative}\n")
            (root / "SHA256SUMS").write_text("".join(checksum_lines), encoding="utf-8")
            request = {
                "schema_version": 1,
                "audience": "customer_integration",
                "required_files": ["README_CN.md", "RELEASE.yaml", "SHA256SUMS"],
                "allowed_top_level": ["README_CN.md", "RELEASE.yaml", "SHA256SUMS"],
                "readme": {
                    "path": "README_CN.md",
                    "required_phrases": ["整体设计", "为什么", "各组件修改", "移植", "已验证范围", "限制"],
                },
                "patches": [],
                "scripts": [],
            }
            validate_release.validate(root, request, layout_only=False)

    def test_rejects_internal_docs_directory(self) -> None:
        with tempfile.TemporaryDirectory() as value:
            root = Path(value)
            (root / "README_CN.md").write_text("ok\n", encoding="utf-8")
            (root / "SHA256SUMS").write_text("placeholder\n", encoding="utf-8")
            (root / "docs").mkdir()
            with self.assertRaisesRegex(validate_release.ValidationError, "internal directory"):
                validate_release.verify_layout(
                    root,
                    {"README_CN.md", "SHA256SUMS", "docs"},
                    ["README_CN.md", "SHA256SUMS"],
                )

    def test_bash_syntax_is_not_enough_when_dry_run_is_wrong(self) -> None:
        with tempfile.TemporaryDirectory() as value:
            root = Path(value)
            scripts = root / "scripts"
            scripts.mkdir()
            script = scripts / "build.sh"
            script.write_text(
                "#!/usr/bin/env bash\n"
                "set -euo pipefail\n"
                "if [[ ${1:-} == --dry-run ]]; then\n"
                "  echo 'make + SOC=iMX8DXL flash_linux_m4'\n"
                "  exit 0\n"
                "fi\n"
                "exit 2\n",
                encoding="utf-8",
            )
            script.chmod(0o755)
            entry = {
                "path": "scripts/build.sh",
                "syntax": "bash",
                "checks": [
                    {
                        "argv": ["--dry-run"],
                        "must_contain": ["make"],
                        "must_not_contain": [" + "],
                    }
                ],
            }
            with self.assertRaisesRegex(validate_release.ValidationError, "contains forbidden"):
                validate_release.verify_script(root, entry)

    def test_script_requires_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as value:
            root = Path(value)
            scripts = root / "scripts"
            scripts.mkdir()
            script = scripts / "help-only.sh"
            script.write_text("#!/usr/bin/env bash\necho help\n", encoding="utf-8")
            script.chmod(0o755)
            entry = {
                "path": "scripts/help-only.sh",
                "syntax": "bash",
                "checks": [{"argv": ["--help"], "must_contain": ["help"]}],
            }
            with self.assertRaisesRegex(validate_release.ValidationError, "requires a --dry-run"):
                validate_release.verify_script(root, entry)

    def test_patch_is_checked_against_declared_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as value:
            root = Path(value)
            baseline = root / "baseline"
            patches = root / "patches"
            baseline.mkdir()
            patches.mkdir()
            (baseline / "value.txt").write_text("old\n", encoding="utf-8")
            patch = patches / "change.patch"
            patch.write_text(
                "diff --git a/value.txt b/value.txt\n"
                "--- a/value.txt\n"
                "+++ b/value.txt\n"
                "@@ -1 +1 @@\n"
                "-old\n"
                "+new\n",
                encoding="utf-8",
            )
            validate_release.verify_patch(
                root,
                {
                    "path": "patches/change.patch",
                    "baseline": str(baseline),
                    "method": "git",
                    "strip": 1,
                },
            )


if __name__ == "__main__":
    unittest.main()

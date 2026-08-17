#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path, PurePosixPath
import shlex
import subprocess
import sys
import tarfile
import tempfile
from typing import Any

import yaml


DEFAULT_ALLOWED = {
    "README_CN.md",
    "RELEASE.yaml",
    "BUILD_IDENTITY.yaml",
    "SHA256SUMS",
    "patches",
    "binaries",
    "reference",
    "licenses",
}
FORBIDDEN_DIRS = {"build", "configs", "docs", "logs", "records", "state", "templates"}
TEXT_SUFFIXES = {".c", ".h", ".md", ".patch", ".py", ".sh", ".txt", ".yaml", ".yml"}
LEAK_MARKERS = ("/home/", "support_level/work/", "\\home\\")


class ValidationError(RuntimeError):
    pass


def load_yaml(path: Path) -> dict[str, Any]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise ValidationError(f"cannot read YAML {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValidationError(f"YAML root must be a mapping: {path}")
    return value


def ensure_relative(value: str, label: str) -> Path:
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or value in {"", "."}:
        raise ValidationError(f"{label} must be a safe relative path: {value!r}")
    return Path(*path.parts)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def extract_archive(path: Path, destination: Path) -> Path:
    try:
        archive = tarfile.open(path, "r:*")
    except (OSError, tarfile.TarError) as exc:
        raise ValidationError(f"cannot open archive {path}: {exc}") from exc
    with archive:
        members = archive.getmembers()
        if not members:
            raise ValidationError("archive is empty")
        roots: set[str] = set()
        for member in members:
            member_path = PurePosixPath(member.name)
            if member_path.is_absolute() or ".." in member_path.parts:
                raise ValidationError(f"unsafe archive member: {member.name}")
            if member.issym() or member.islnk() or member.isdev() or member.isfifo():
                raise ValidationError(f"unsupported archive member type: {member.name}")
            if member_path.parts:
                roots.add(member_path.parts[0])
        if len(roots) != 1:
            raise ValidationError(f"archive must contain one top-level directory: {sorted(roots)}")
        archive.extractall(destination)
    root = destination / next(iter(roots))
    if not root.is_dir():
        raise ValidationError("archive top-level entry is not a directory")
    return root


def verify_layout(root: Path, allowed: set[str], required: list[str]) -> None:
    if not root.is_dir():
        raise ValidationError(f"release root is not a directory: {root}")
    actual = {item.name for item in root.iterdir()}
    unexpected = sorted(actual - allowed)
    if unexpected:
        raise ValidationError(f"unexpected top-level entries: {', '.join(unexpected)}")
    for value in required:
        path = root / ensure_relative(value, "required_files entry")
        if not path.is_file() or path.stat().st_size == 0:
            raise ValidationError(f"required file missing or empty: {value}")
    for directory in FORBIDDEN_DIRS:
        if (root / directory).exists():
            raise ValidationError(f"internal directory is forbidden: {directory}")
    markdown = [
        path.relative_to(root)
        for path in root.rglob("*.md")
        if path.relative_to(root) != Path("README_CN.md")
        and not path.relative_to(root).parts[0] == "licenses"
    ]
    if markdown:
        raise ValidationError(
            "customer_integration allows one customer Markdown document; extra files: "
            + ", ".join(str(path) for path in markdown)
        )


def verify_no_leaks(root: Path) -> None:
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            raise ValidationError(f"cannot inspect {path}: {exc}") from exc
        for marker in (*LEAK_MARKERS, "REPLACE_WITH_", "[必须替换"):
            if marker in content:
                raise ValidationError(f"forbidden marker {marker!r} found in {path.relative_to(root)}")


def verify_checksums(root: Path) -> None:
    manifest = root / "SHA256SUMS"
    if not manifest.is_file():
        raise ValidationError("SHA256SUMS is missing")
    seen: set[Path] = set()
    for line_number, raw in enumerate(manifest.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        parts = raw.split(maxsplit=1)
        if len(parts) != 2 or len(parts[0]) != 64:
            raise ValidationError(f"invalid SHA256SUMS line {line_number}: {raw!r}")
        expected, name = parts
        name = name.lstrip(" *")
        relative = ensure_relative(name, f"SHA256SUMS line {line_number}")
        path = root / relative
        if relative == Path("SHA256SUMS"):
            raise ValidationError("SHA256SUMS must not checksum itself")
        if not path.is_file():
            raise ValidationError(f"checksummed file is missing: {relative}")
        actual = sha256(path)
        if actual != expected.lower():
            raise ValidationError(f"checksum mismatch: {relative}")
        seen.add(relative)
    expected_files = {
        path.relative_to(root)
        for path in root.rglob("*")
        if path.is_file() and path.relative_to(root) != Path("SHA256SUMS")
    }
    missing = sorted(expected_files - seen)
    extra = sorted(seen - expected_files)
    if missing or extra:
        details = []
        if missing:
            details.append("not listed: " + ", ".join(str(path) for path in missing))
        if extra:
            details.append("unexpected: " + ", ".join(str(path) for path in extra))
        raise ValidationError("SHA256SUMS coverage error: " + "; ".join(details))


def verify_readme(root: Path, spec: dict[str, Any]) -> None:
    readme = spec.get("readme", {})
    if not isinstance(readme, dict):
        raise ValidationError("readme must be a mapping")
    relative = ensure_relative(str(readme.get("path", "README_CN.md")), "readme.path")
    path = root / relative
    if not path.is_file():
        raise ValidationError(f"README is missing: {relative}")
    content = path.read_text(encoding="utf-8", errors="replace")
    placeholder_markers = ("[必须替换", "REPLACE_WITH_")
    for marker in placeholder_markers:
        if marker in content:
            raise ValidationError(f"README contains unresolved placeholder: {marker}")
    phrases = readme.get("required_phrases", [])
    if not isinstance(phrases, list) or not all(isinstance(item, str) and item for item in phrases):
        raise ValidationError("readme.required_phrases must be a list of non-empty strings")
    missing = [phrase for phrase in phrases if phrase not in content]
    if missing:
        raise ValidationError("README is missing required concepts: " + ", ".join(missing))


def verify_patch(root: Path, entry: dict[str, Any]) -> None:
    relative = ensure_relative(str(entry.get("path", "")), "patch.path")
    patch_path = root / relative
    if not patch_path.is_file() or patch_path.stat().st_size == 0:
        raise ValidationError(f"patch missing or empty: {relative}")
    baseline = Path(str(entry.get("baseline", ""))).resolve()
    if not baseline.is_dir():
        raise ValidationError(f"patch baseline is not a directory: {baseline}")
    method = entry.get("method", "git")
    strip = entry.get("strip", 1)
    if not isinstance(strip, int) or strip < 0:
        raise ValidationError(f"invalid patch strip for {relative}: {strip!r}")
    if method == "git":
        command = ["git", "-C", str(baseline), "apply", "--check", f"-p{strip}", str(patch_path)]
    elif method == "patch":
        command = ["patch", "--dry-run", f"-p{strip}", "-d", str(baseline), "-i", str(patch_path)]
    else:
        raise ValidationError(f"unsupported patch method for {relative}: {method!r}")
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if result.returncode != 0:
        raise ValidationError(
            f"patch semantic check failed for {relative}: {shlex.join(command)}\n{result.stdout.strip()}"
        )


def verify_script(root: Path, entry: dict[str, Any]) -> None:
    relative = ensure_relative(str(entry.get("path", "")), "script.path")
    script = root / relative
    if not script.is_file() or script.stat().st_size == 0:
        raise ValidationError(f"script missing or empty: {relative}")
    syntax = entry.get("syntax")
    if syntax == "bash":
        result = subprocess.run(["bash", "-n", str(script)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        if result.returncode != 0:
            raise ValidationError(f"bash syntax check failed for {relative}: {result.stdout.strip()}")
    elif syntax not in {None, "none"}:
        raise ValidationError(f"unsupported script syntax for {relative}: {syntax!r}")
    checks = entry.get("checks", [])
    if not isinstance(checks, list) or not checks:
        raise ValidationError(f"script requires at least one semantic check: {relative}")
    if not any("--dry-run" in check.get("argv", []) for check in checks if isinstance(check, dict)):
        raise ValidationError(f"script requires a --dry-run semantic check: {relative}")
    for index, check in enumerate(checks):
        if not isinstance(check, dict):
            raise ValidationError(f"script check must be a mapping: {relative}[{index}]")
        argv = check.get("argv", [])
        if not isinstance(argv, list) or not all(isinstance(item, str) for item in argv):
            raise ValidationError(f"script check argv must be a string list: {relative}[{index}]")
        timeout = check.get("timeout_seconds", 30)
        if not isinstance(timeout, int) or timeout < 1 or timeout > 120:
            raise ValidationError(f"invalid timeout for {relative}[{index}]")
        command = [str(script), *argv]
        env = os.environ.copy()
        env["CUSTOMER_RELEASE_VALIDATE"] = "1"
        try:
            result = subprocess.run(
                command,
                cwd=root,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=timeout,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ValidationError(f"script semantic check could not run: {shlex.join(command)}: {exc}") from exc
        if result.returncode != 0:
            raise ValidationError(
                f"script semantic check failed ({result.returncode}): {shlex.join(command)}\n{result.stdout.strip()}"
            )
        must_contain = check.get("must_contain", [])
        must_not_contain = check.get("must_not_contain", [])
        if "--dry-run" in argv and (
            not isinstance(must_contain, list)
            or not all(isinstance(item, str) and item for item in must_contain)
            or not must_contain
        ):
            raise ValidationError(
                f"--dry-run must inspect at least one expected output phrase: {relative}[{index}]"
            )
        if not isinstance(must_not_contain, list) or not all(
            isinstance(item, str) and item for item in must_not_contain
        ):
            raise ValidationError(f"must_not_contain must be a string list: {relative}[{index}]")
        for phrase in must_contain:
            if phrase not in result.stdout:
                raise ValidationError(f"script output missing {phrase!r}: {relative}[{index}]")
        for phrase in must_not_contain:
            if phrase in result.stdout:
                raise ValidationError(f"script output contains forbidden {phrase!r}: {relative}[{index}]")


def validate(root: Path, spec: dict[str, Any] | None, layout_only: bool) -> None:
    if layout_only:
        allowed = DEFAULT_ALLOWED
        required = ["README_CN.md", "SHA256SUMS"]
    else:
        if spec is None:
            raise ValidationError("--spec is required unless --layout-only is used")
        if spec.get("schema_version") != 1:
            raise ValidationError("spec schema_version must be 1")
        if spec.get("audience") != "customer_integration":
            raise ValidationError("this validator currently requires audience: customer_integration")
        allowed_values = spec.get("allowed_top_level", [])
        required = spec.get("required_files", [])
        if not isinstance(allowed_values, list) or not all(isinstance(item, str) for item in allowed_values):
            raise ValidationError("allowed_top_level must be a string list")
        if not isinstance(required, list) or not all(isinstance(item, str) for item in required):
            raise ValidationError("required_files must be a string list")
        allowed = set(allowed_values)
    verify_layout(root, allowed, required)
    verify_no_leaks(root)
    verify_checksums(root)
    if not layout_only and spec is not None:
        verify_readme(root, spec)
        patches = spec.get("patches", [])
        scripts = spec.get("scripts", [])
        if not isinstance(patches, list) or not all(isinstance(item, dict) for item in patches):
            raise ValidationError("patches must be a list of mappings")
        if not isinstance(scripts, list) or not all(isinstance(item, dict) for item in scripts):
            raise ValidationError("scripts must be a list of mappings")
        for entry in patches:
            verify_patch(root, entry)
        declared_patches = {
            ensure_relative(str(entry.get("path", "")), "patch.path")
            for entry in patches
        }
        packaged_patches = {
            path.relative_to(root)
            for path in (root / "patches").rglob("*")
            if (root / "patches").is_dir() and path.is_file()
        }
        if packaged_patches != declared_patches:
            raise ValidationError(
                "packaged patches must exactly match patches declared in spec: "
                f"packaged={sorted(map(str, packaged_patches))}, "
                f"declared={sorted(map(str, declared_patches))}"
            )
        declared_scripts = {ensure_relative(str(entry.get("path", "")), "script.path") for entry in scripts}
        packaged_scripts = {
            path.relative_to(root)
            for path in (root / "scripts").rglob("*")
            if (root / "scripts").is_dir() and path.is_file()
        }
        if packaged_scripts != declared_scripts:
            raise ValidationError(
                "packaged scripts must exactly match scripts declared in spec: "
                f"packaged={sorted(map(str, packaged_scripts))}, declared={sorted(map(str, declared_scripts))}"
            )
        for entry in scripts:
            verify_script(root, entry)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate a customer integration release directory or tar archive")
    parser.add_argument("package", type=Path)
    parser.add_argument("--spec", type=Path, help="case-local customer release request YAML")
    parser.add_argument("--layout-only", action="store_true", help="check historical package layout/checksums without patch or script semantics")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.layout_only and args.spec is not None:
        print("validate-release: BLOCKED: --layout-only and --spec are mutually exclusive", file=sys.stderr)
        return 2
    try:
        spec = load_yaml(args.spec.resolve()) if args.spec is not None else None
        package = args.package.resolve()
        if package.is_dir():
            validate(package, spec, args.layout_only)
            checked = package
        elif package.is_file():
            with tempfile.TemporaryDirectory(prefix="customer-release-") as temp:
                root = extract_archive(package, Path(temp))
                validate(root, spec, args.layout_only)
                checked = package
        else:
            raise ValidationError(f"package does not exist: {package}")
    except ValidationError as exc:
        print(f"validate-release: BLOCKED: {exc}", file=sys.stderr)
        return 2
    mode = "layout-only" if args.layout_only else "full"
    print(f"Customer release: VALID ({mode})")
    print(f"Checked: {checked}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

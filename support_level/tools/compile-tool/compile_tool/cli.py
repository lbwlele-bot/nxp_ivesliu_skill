from __future__ import annotations

import argparse
from pathlib import Path
import sys

from . import __version__
from .common import ToolError, case_lock
from .guards import render_requirements
from .manifest import load_manifest
from .planner import assess, render_assessment
from .request import (
    execute_v1,
    execute_v2,
    load_request,
    render_report,
    verify_assessment,
)
from .sources import execute_acquisition, render_acquisition


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Observe software state, validate an explicit LLM build scope, and "
            "execute raw compile commands"
        )
    )
    parser.add_argument(
        "--version", action="version", version=f"compile-tool {__version__}"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    assess_parser = subparsers.add_parser(
        "assess",
        help="observe local source, configuration, tool, and artifact state",
    )
    assess_parser.add_argument("manifest", type=Path)

    acquire = subparsers.add_parser(
        "acquire",
        help="execute a previously displayed and hash-bound local source plan",
    )
    acquire.add_argument("manifest", type=Path)
    acquire.add_argument("--plan-hash", required=True)

    requirements = subparsers.add_parser(
        "requirements",
        help="display component parameter requirements selected by a manifest",
    )
    requirements.add_argument("manifest", type=Path)

    prepare = subparsers.add_parser(
        "prepare", help="validate and display a compile request without executing it"
    )
    prepare.add_argument("request", type=Path)

    run = subparsers.add_parser(
        "run", help="validate and execute a compile request"
    )
    run.add_argument("request", type=Path)
    return parser


def _assess_command(manifest_path: Path) -> int:
    manifest = load_manifest(manifest_path)
    with case_lock(Path(manifest["case_root"])):
        result = assess(manifest)
        print(render_assessment(manifest, result))
        if result["status"] == "ACQUIRE_REQUIRED":
            print()
            print(render_acquisition(manifest, result["source"]))
            return 3
        return 0


def _acquire_command(manifest_path: Path, plan_hash: str) -> int:
    manifest = load_manifest(manifest_path)
    with case_lock(Path(manifest["case_root"])):
        return execute_acquisition(manifest, plan_hash)


def _requirements_command(manifest_path: Path) -> int:
    manifest = load_manifest(manifest_path, validate_guards=False)
    print(render_requirements(manifest))
    return 0


def _prepare_or_run(
    request_path: Path,
    *,
    execute: bool,
) -> int:
    request = load_request(request_path)
    if request["schema_version"] == 1:
        print(render_report(request), flush=True)
        if not execute:
            return 0
        print("\nExecution：STARTING", flush=True)
        return execute_v1(request)

    manifest = request["_manifest"]
    with case_lock(Path(manifest["case_root"])):
        assessment = assess(manifest)
        verify_assessment(request, assessment)
        print(render_report(request, assessment), flush=True)
        if not execute:
            return 0
        print("\nExecution：STARTING", flush=True)
        return execute_v2(request, assessment)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "assess":
            return _assess_command(args.manifest)
        if args.command == "acquire":
            return _acquire_command(args.manifest, args.plan_hash)
        if args.command == "requirements":
            return _requirements_command(args.manifest)
        return _prepare_or_run(
            args.request,
            execute=args.command == "run",
        )
    except ToolError as exc:
        print(f"compile-tool: BLOCKED: {exc}", file=sys.stderr)
        return 2

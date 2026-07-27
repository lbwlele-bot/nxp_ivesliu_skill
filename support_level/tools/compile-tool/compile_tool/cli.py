from __future__ import annotations

import argparse
from pathlib import Path
import sys

from . import __version__
from .common import ToolError, case_lock, normalize_hash
from .manifest import load_manifest
from .planner import assess, render_assessment
from .request import (
    execute_v1,
    execute_v2,
    load_request,
    render_report,
    request_hash,
    verify_assessment,
)
from .sources import execute_acquisition, render_acquisition


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Assess software state, bind explicit compile commands, and execute "
            "the minimal authorized build"
        )
    )
    parser.add_argument(
        "--version", action="version", version=f"compile-tool {__version__}"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    assess_parser = subparsers.add_parser(
        "assess",
        help="assess local sources and the minimal rebuild/repack action set",
    )
    assess_parser.add_argument("manifest", type=Path)

    acquire = subparsers.add_parser(
        "acquire",
        help="execute a previously displayed and hash-bound local source plan",
    )
    acquire.add_argument("manifest", type=Path)
    acquire.add_argument("--plan-hash", required=True)

    prepare = subparsers.add_parser(
        "prepare", help="validate and display a compile request without executing it"
    )
    prepare.add_argument("request", type=Path)

    run = subparsers.add_parser(
        "run", help="execute a previously displayed and hash-bound compile request"
    )
    run.add_argument("request", type=Path)
    run.add_argument("--plan-hash", required=True)
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


def _prepare_or_run(
    request_path: Path,
    *,
    execute: bool,
    supplied_plan_hash: str | None,
) -> int:
    request = load_request(request_path)
    if request["schema_version"] == 1:
        if execute:
            assert supplied_plan_hash is not None
            if normalize_hash(supplied_plan_hash, "plan hash") != request_hash(request):
                raise ToolError(
                    "plan hash mismatch; run prepare again and show the updated command"
                )
        print(render_report(request), flush=True)
        if not execute:
            return 0
        print("\nExecution：STARTING", flush=True)
        return execute_v1(request)

    manifest = request["_manifest"]
    with case_lock(Path(manifest["case_root"])):
        assessment = assess(manifest)
        verify_assessment(request, assessment)
        if execute:
            assert supplied_plan_hash is not None
            if normalize_hash(supplied_plan_hash, "plan hash") != request_hash(request):
                raise ToolError(
                    "plan hash mismatch; run prepare again and show the updated command"
                )
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
        return _prepare_or_run(
            args.request,
            execute=args.command == "run",
            supplied_plan_hash=getattr(args, "plan_hash", None),
        )
    except ToolError as exc:
        print(f"compile-tool: BLOCKED: {exc}", file=sys.stderr)
        return 2

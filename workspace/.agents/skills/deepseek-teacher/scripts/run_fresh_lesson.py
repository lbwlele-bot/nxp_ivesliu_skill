#!/usr/bin/env python3
"""Run one no-session DeepSeek lesson and preserve its raw JSON events."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


PATCHES = ("readonly", "supervised-workspace", "supervised-compile")


def events_from(text: str) -> list[dict]:
    events: list[dict] = []
    for line in text.splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            events.append(value)
    return events


def captured_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run a fresh DeepSeek session against an explicitly selected workspace.",
        epilog=(
            "The selected workspace must sit beside support_level/. Launchers and "
            "patches are resolved from that environment, never the teacher's install. "
            "Relative input paths are relative to the caller's current directory. "
            "Output is buffered until completion or timeout; this is not a live monitor."
        ),
    )
    parser.add_argument(
        "--workspace", type=Path, required=True,
        help="Student working directory, with sibling support_level/; no implicit default.",
    )
    parser.add_argument("--prompt-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--patch", choices=sorted(PATCHES), default="readonly")
    parser.add_argument(
        "--board-mcp",
        action="store_true",
        help="Load the fixed board-task MCP. Off by default for offline lessons.",
    )
    parser.add_argument("--timeout", type=int, default=600)
    args = parser.parse_args(argv)

    workspace = args.workspace.expanduser().resolve()
    if not workspace.is_dir():
        print(f"WORKSPACE_MISSING: {workspace}", file=sys.stderr)
        return 2
    harness_dir = workspace.parent / "support_level/tools/deepseek-harness"
    launcher = workspace / "dsh" if args.board_mcp else harness_dir / "dsh"
    patch = harness_dir / f"{args.patch}.patch.yml"
    if not launcher.is_file() or not os.access(launcher, os.X_OK):
        print(f"LAUNCHER_NOT_EXECUTABLE: {launcher}", file=sys.stderr)
        return 2
    if not patch.is_file():
        print(f"PATCH_MISSING: {patch}", file=sys.stderr)
        return 2

    prompt_file = args.prompt_file.expanduser().resolve()
    output = args.output.expanduser().resolve()
    if not prompt_file.is_file():
        print(f"PROMPT_MISSING: {prompt_file}", file=sys.stderr)
        return 2
    if output.exists():
        print(f"REFUSE_OVERWRITE: {output}", file=sys.stderr)
        return 2
    if not output.parent.is_dir():
        print(f"OUTPUT_PARENT_MISSING: {output.parent}", file=sys.stderr)
        return 2
    prompt = prompt_file.read_text(encoding="utf-8").strip()
    if not prompt:
        print("PROMPT_EMPTY", file=sys.stderr)
        return 2

    command = [
        str(launcher),
        "--profile",
        "headless",
        "--patch",
        str(patch),
        "--json",
        prompt,
    ]
    try:
        completed = subprocess.run(
            command,
            cwd=workspace,
            text=True,
            capture_output=True,
            timeout=args.timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = captured_text(exc.stdout)
        stderr = captured_text(exc.stderr)
        output.write_text(stdout, encoding="utf-8")
        if stderr:
            output.with_suffix(output.suffix + ".stderr").write_text(
                stderr, encoding="utf-8"
            )
        print(f"TIMEOUT: {args.timeout}s", file=sys.stderr)
        return 124

    output.write_text(completed.stdout, encoding="utf-8")
    if completed.stderr:
        output.with_suffix(output.suffix + ".stderr").write_text(
            completed.stderr, encoding="utf-8"
        )

    events = events_from(completed.stdout)
    session_ids = [
        event.get("sessionId")
        for event in events
        if event.get("type") == "session" and event.get("sessionId")
    ]
    completed_turn = any(
        event.get("type") == "status"
        and event.get("phase") == "turn_end"
        and event.get("reason", {}).get("kind") == "completed"
        for event in events
    )
    final_seen = any(event.get("type") == "final" for event in events)

    print(f"SESSION: {session_ids[-1] if session_ids else 'UNKNOWN'}")
    print(f"DSH_EXIT: {completed.returncode}")
    print(f"TURN_COMPLETED: {str(completed_turn).lower()}")
    print(f"FINAL_SEEN: {str(final_seen).lower()}")
    print(f"OUTPUT: {output}")

    if completed.returncode != 0 or not completed_turn or not final_seen:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

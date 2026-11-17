#!/usr/bin/env python3
"""Run one no-session DeepSeek lesson and preserve its raw JSON events."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


DS_ROOT = Path("/home/ives/桌面/NXP_ds_v1")
WORKSPACE = DS_ROOT / "workspace"
DSH_BASE = DS_ROOT / "support_level/tools/deepseek-harness/dsh"
DSH_WITH_BOARD_MCP = WORKSPACE / "dsh"
PATCHES = {
    "readonly": DS_ROOT / "support_level/tools/deepseek-harness/readonly.patch.yml",
    "supervised-workspace": DS_ROOT
    / "support_level/tools/deepseek-harness/supervised-workspace.patch.yml",
    "supervised-compile": DS_ROOT
    / "support_level/tools/deepseek-harness/supervised-compile.patch.yml",
}


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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--patch", choices=sorted(PATCHES), default="readonly")
    parser.add_argument(
        "--board-mcp",
        action="store_true",
        help="Load the fixed board-task MCP. Off by default for offline lessons.",
    )
    parser.add_argument("--timeout", type=int, default=600)
    args = parser.parse_args()

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
        str(DSH_WITH_BOARD_MCP if args.board_mcp else DSH_BASE),
        "--profile",
        "headless",
        "--patch",
        str(PATCHES[args.patch]),
        "--json",
        prompt,
    ]
    try:
        completed = subprocess.run(
            command,
            cwd=WORKSPACE,
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

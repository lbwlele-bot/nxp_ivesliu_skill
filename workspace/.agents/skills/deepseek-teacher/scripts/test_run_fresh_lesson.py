"""Offline runner checks: temporary student trees, no model API or board access."""

import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


RUNNER = Path(__file__).with_name("run_fresh_lesson.py")
spec = importlib.util.spec_from_file_location("lesson_runner", RUNNER)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
EVENTS = "\n".join(json.dumps(e) for e in [
    {"type": "session", "sessionId": "fixture-session"},
    {"type": "status", "phase": "turn_end", "reason": {"kind": "completed"}},
    {"type": "final", "text": "fixture complete"},
]) + "\n"


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="lesson-runner-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.workspace = self.root / "学生 environment" / "work area"
        self.harness = self.workspace.parent / "support_level/tools/deepseek-harness"
        self.workspace.mkdir(parents=True)
        self.harness.mkdir(parents=True)
        # Local fake launcher only prints fixture JSON; it cannot call a model or board.
        for launcher in [self.workspace / "dsh", self.harness / "dsh"]:
            launcher.write_text("#!/bin/sh\nprintf '%s' '" + EVENTS + "'\n")
            launcher.chmod(0o700)
        for name in runner.PATCHES:
            (self.harness / f"{name}.patch.yml").write_text("{}\n")
        self.prompt = self.root / "task.txt"
        self.prompt.write_text("A normal fixture task")
        self.output = self.root / "events.jsonl"

    def args(self, *extra):
        return ["--workspace", str(self.workspace), "--prompt-file", str(self.prompt),
                "--output", str(self.output), *extra]

    def invoke(self, args=None):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return runner.main(self.args() if args is None else args)

    def test_relocated_environment_real_subprocess(self):
        self.assertEqual(self.invoke(), 0)
        self.assertEqual(self.output.read_text(), EVENTS)

    def test_all_patch_choices_and_launcher_modes(self):
        for name in runner.PATCHES:
            for board in (False, True):
                with self.subTest(patch=name, board=board):
                    self.output = self.root / f"{name}-{board}.jsonl"
                    args = self.args("--patch", name, *(["--board-mcp"] if board else []))
                    with patch.object(runner.subprocess, "run", return_value=
                                      subprocess.CompletedProcess([], 0, EVENTS, "")) as run:
                        self.assertEqual(self.invoke(args), 0)
                    command = run.call_args.args[0]
                    expected = self.workspace / "dsh" if board else self.harness / "dsh"
                    self.assertEqual(command[0], str(expected))
                    self.assertEqual(command[command.index("--patch") + 1],
                                     str(self.harness / f"{name}.patch.yml"))
                    self.assertEqual(run.call_args.kwargs["cwd"], self.workspace)
                    self.assertNotIn("--session-id", command)

    def test_relative_workspace_from_unrelated_cwd(self):
        caller = self.root / "caller"
        caller.mkdir()
        original = Path.cwd()
        try:
            os.chdir(caller)
            args = self.args()
            args[1] = os.path.relpath(self.workspace, caller)
            self.assertEqual(self.invoke(args), 0)
        finally:
            os.chdir(original)

    def test_workspace_required_no_fallback(self):
        with patch.object(runner.subprocess, "run") as run:
            with self.assertRaises(SystemExit) as error:
                self.invoke(self.args()[2:])
            self.assertEqual(error.exception.code, 2)
            run.assert_not_called()

    def test_missing_inputs_never_launch(self):
        for label,change in [
            ("workspace", lambda a: a.__setitem__(1, str(self.root / "absent"))),
            ("prompt", lambda a: a.__setitem__(3, str(self.root / "absent.txt"))),
            ("output-parent", lambda a: a.__setitem__(5, str(self.root / "absent/out.jsonl"))),
        ]:
            with self.subTest(label=label), patch.object(runner.subprocess, "run") as run:
                args = self.args()
                change(args)
                self.assertEqual(self.invoke(args), 2)
                run.assert_not_called()

    def test_launcher_and_patch_must_exist(self):
        for target in [self.harness / "dsh", self.harness / "readonly.patch.yml",
                       self.workspace / "dsh"]:
            saved = target.with_name(target.name + ".saved")
            target.rename(saved)
            try:
                args = self.args(*(["--board-mcp"] if target.parent == self.workspace else []))
                with patch.object(runner.subprocess, "run") as run:
                    self.assertEqual(self.invoke(args), 2)
                    run.assert_not_called()
            finally:
                saved.rename(target)

    def test_non_executable_launcher(self):
        (self.harness / "dsh").chmod(0o600)
        with patch.object(runner.subprocess, "run") as run:
            self.assertEqual(self.invoke(), 2)
            run.assert_not_called()

    def test_preserve_existing_output(self):
        self.output.write_text("existing evidence")
        with patch.object(runner.subprocess, "run") as run:
            self.assertEqual(self.invoke(), 2)
            run.assert_not_called()
        self.assertEqual(self.output.read_text(), "existing evidence")

    def test_empty_prompt(self):
        self.prompt.write_text(" \n")
        with patch.object(runner.subprocess, "run") as run:
            self.assertEqual(self.invoke(), 2)
            run.assert_not_called()

    def test_nonzero_or_incomplete_turn_is_not_success(self):
        for code,output in [(1, EVENTS), (0, '{"type":"final","text":"alone"}\n')]:
            self.output = self.root / f"failure-{code}.jsonl"
            with patch.object(runner.subprocess, "run", return_value=
                              subprocess.CompletedProcess([], code, output, "fixture stderr")):
                self.assertEqual(self.invoke(), 1)
            self.assertEqual(self.output.read_text(), output)

    def test_timeout_preserves_partial_output(self):
        with patch.object(runner.subprocess, "run", side_effect=
                          subprocess.TimeoutExpired("fixture", 1, output=b"partial", stderr=b"error")):
            self.assertEqual(self.invoke(), 124)
        self.assertEqual(self.output.read_text(), "partial")
        self.assertEqual(self.output.with_suffix(".jsonl.stderr").read_text(), "error")


if __name__ == "__main__":
    unittest.main()

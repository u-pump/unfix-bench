# SPDX-License-Identifier: MIT
# Copyright (c) 2026 U-Pump
"""A failed Claude Code run is explained in a short fixed vocabulary, never with raw output."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import collect_agent_run as collect
import verify_cases

SCRIPTS = Path(__file__).resolve().parent
KEY = "sk-ant-api03-" + "A" * 40
INIT = {"type": "system", "subtype": "init", "model": "claude-opus-5-5", "session_id": "s"}


def api_error(text: str, status: int | None, kind: str = "unknown") -> list[dict[str, object]]:
    return [
        INIT,
        {"type": "assistant", "error": kind, "isApiErrorMessage": True,
         "message": {"model": "<synthetic>", "content": [{"type": "text", "text": text}]}},
        {"type": "result", "subtype": "success", "is_error": True, "api_error_status": status, "result": text},
    ]


class DiagnoseTest(unittest.TestCase):
    def test_credit_balance_is_named_and_the_model_gave_no_response(self) -> None:
        text = "Credit balance is too low to access the Anthropic API"
        diagnosis = collect.diagnose_failure(api_error(text, 400))
        line = collect.describe_failure(diagnosis, 1)
        self.assertIn("credit balance too low", line)
        self.assertIn("HTTP 400", line)
        self.assertIn("the model gave no response", line)
        self.assertEqual(diagnosis["model_responses"], 0)
        self.assertTrue(diagnosis["started_session"])

    def test_each_api_problem_has_its_own_short_text(self) -> None:
        cases = {
            "Invalid API key": ("invalid, disabled, deleted", 401),
            "This request would exceed your rate limit": ("rate limit", 429),
            "model: claude-x does not exist": ("model is not available", 404),
            "Overloaded": ("temporarily unavailable", 529),
        }
        for text, (expected, status) in cases.items():
            with self.subTest(text):
                line = collect.describe_failure(collect.diagnose_failure(api_error(text, status)), 1)
                self.assertIn(expected, line)

    def test_status_alone_classifies_when_the_text_is_unfamiliar(self) -> None:
        events = api_error("something unexpected", 401, "unknown")
        self.assertIn("invalid, disabled, deleted", collect.diagnose_failure(events)["problem"])

    def test_a_run_that_worked_before_failing_reports_its_responses(self) -> None:
        events = [
            INIT,
            {"type": "assistant", "message": {"model": "claude-opus-5-5", "content": [{"type": "text", "text": "hi"}]}},
            {"type": "result", "subtype": "error_during_execution", "is_error": True},
        ]
        diagnosis = collect.diagnose_failure(events)
        self.assertEqual(diagnosis["model_responses"], 1)
        self.assertIn("unclassified", diagnosis["problem"])
        self.assertIn("the model had given 1 responses", collect.describe_failure(diagnosis, 1))

    def test_an_empty_transcript_is_handled(self) -> None:
        diagnosis = collect.diagnose_failure([], "")
        self.assertFalse(diagnosis["started_session"])
        self.assertEqual(diagnosis["model_responses"], 0)

    def test_every_description_is_publishable_as_an_error_reason(self) -> None:
        for text, status in (("Credit balance is too low", 400), ("Invalid API key", 401),
                             ("rate limit", 429), ("model not found", 404), ("Overloaded", 529), ("x", None)):
            line = collect.describe_failure(collect.diagnose_failure(api_error(text, status)), 1)
            self.assertEqual(verify_cases.summary_reason(line, ""), line, line)

    def test_cli_prints_one_line_and_never_the_key_or_the_raw_message(self) -> None:
        raw = f"Credit balance is too low. key={KEY} secret-task-text"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            transcript = root / "transcript.jsonl"
            transcript.write_text("\n".join(json.dumps(e) for e in api_error(raw, 400)), encoding="utf-8")
            stderr = root / "stderr.log"
            stderr.write_text(f"boom {KEY}", encoding="utf-8")
            done = subprocess.run(
                [sys.executable, str(SCRIPTS / "collect_agent_run.py"), "diagnose", "--transcript", str(transcript),
                 "--stderr", str(stderr), "--exit-code", "1"],
                capture_output=True, text=True, check=True, env={"ANTHROPIC_API_KEY": KEY, "PATH": ""},
            )
        out = done.stdout + done.stderr
        self.assertEqual(len(done.stdout.strip().splitlines()), 1)
        self.assertIn("credit balance too low", out)
        self.assertNotIn(KEY, out)
        self.assertNotIn("secret-task-text", out)
        self.assertNotIn("sk-ant", out)

    def test_cli_without_files_still_gives_the_exit_code(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            done = subprocess.run(
                [sys.executable, str(SCRIPTS / "collect_agent_run.py"), "diagnose",
                 "--transcript", str(Path(directory) / "none"), "--stderr", str(Path(directory) / "none2"),
                 "--exit-code", "1"],
                capture_output=True, text=True, check=True,
            )
        self.assertIn("exited with code 1", done.stdout)
        self.assertIn("the model gave no response", done.stdout)


class RunnerUsesDiagnosisTest(unittest.TestCase):
    def test_a_failed_agent_publishes_the_classified_reason_and_prints_no_transcript(self) -> None:
        script = (SCRIPTS / "run_claude_case.sh").read_text(encoding="utf-8")
        self.assertIn("collect_agent_run.py\" diagnose", script)
        self.assertIn('fail "$reason"', script)
        self.assertRegex(script, r'--transcript "\$PRIV/transcript\.jsonl"\s*\\\s*\n\s*--stderr "\$PRIV/agent-stderr\.log"')


if __name__ == "__main__":
    unittest.main()

# SPDX-License-Identifier: MIT
# Copyright (c) 2026 U-Pump
"""NO_PATCH: the agent finished its attempt without changing any file."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import verify_cases

AGENT = {
    "name": "Claude Code", "version": "2.1.323 (Claude Code)", "model": "claude-opus-5-5",
    "invocation": "claude -p", "date_utc": "2026-11-20T10:00:00Z", "environment": "container",
    "patch_sha256": None, "attempt_note": "First completed attempt; changed nothing.",
    "outcome": "NO_PATCH",
}


class NoPatchTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        folder = self.root / "cases" / "demo-1" / "agents" / "claude-code"
        folder.mkdir(parents=True)
        (folder / "agent-fix.patch").write_bytes(b"")
        self.meta = folder / "agent.yaml"
        self.meta.write_text(json.dumps(AGENT), encoding="utf-8")
        (self.root / "cases" / "demo-1" / "case.yaml").write_text("{}", encoding="utf-8")
        self.patcher = patch.object(verify_cases, "ROOT", self.root)
        self.patcher.start()

    def tearDown(self) -> None:
        self.patcher.stop()
        self.tmp.cleanup()

    def test_completed_empty_attempt_is_no_patch_not_pending(self) -> None:
        verdict, gates, seconds, reason = verify_cases.run_case("demo-1", "claude-code")
        self.assertEqual((verdict, gates, seconds), ("NO_PATCH", {}, None))
        self.assertIn("without changing any file", str(reason))

    def test_unrun_agent_stays_pending(self) -> None:
        self.meta.write_text(json.dumps({**AGENT, "outcome": None, "model": None}), encoding="utf-8")
        verdict, *_ = verify_cases.run_case("demo-1", "claude-code")
        self.assertEqual(verdict, "PENDING")

    def test_no_patch_is_selected_until_its_report_exists(self) -> None:
        with patch.dict("os.environ", {"BEFORE_SHA": "", "HEAD_SHA": "", "SELECT_CASE": "", "SELECT_AGENT": ""}):
            self.assertEqual(verify_cases.selected_pairs(), [("demo-1", "claude-code")])
            report = self.root / "results" / "demo-1" / "claude-code.md"
            report.parent.mkdir(parents=True)
            report.write_text(
                verify_cases.render("demo-1", "NO_PATCH", {}, None, "Claude Code", "2.1.323",
                                    "2026-11-20 10:00:00 UTC", "reason"), encoding="utf-8")
            self.assertEqual(verify_cases.selected_pairs(), [])

    def test_report_names_the_verdict_and_an_empty_patch(self) -> None:
        text = verify_cases.render("demo-1", "NO_PATCH", {}, None, "Claude Code", "2.1.323",
                                   "2026-11-20 10:00:00 UTC", "the agent finished without changes")
        self.assertIn("Verdict: **NO_PATCH**", text)
        self.assertIn("Patch: none (empty)", text)
        self.assertIn("| anti_cheat | SKIPPED |", text)


if __name__ == "__main__":
    unittest.main()

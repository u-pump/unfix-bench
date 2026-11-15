# SPDX-License-Identifier: MIT
# Copyright (c) 2026 U-Pump
"""Policy for .github/workflows/mine-candidates.yml: it builds other people's code, so it must stay small and unprivileged."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEXT = (ROOT / ".github" / "workflows" / "mine-candidates.yml").read_text(encoding="utf-8")


class MineWorkflowPolicyTest(unittest.TestCase):
    def test_only_triggered_by_hand(self) -> None:
        on = TEXT[TEXT.index("\non:"): TEXT.index("\npermissions:")]
        self.assertIn("workflow_dispatch:", on)
        for trigger in ("pull_request", "push:", "schedule:", "workflow_run", "pull_request_target"):
            self.assertNotIn(trigger, on)

    def test_read_only_and_no_secrets(self) -> None:
        self.assertRegex(TEXT, r"(?m)^permissions:\n  contents: read\n")
        self.assertNotIn("write", TEXT.replace("workflow_dispatch", ""))  # no write permission anywhere (yet)
        self.assertNotIn("secrets.", TEXT)
        self.assertNotIn("persist-credentials: true", TEXT)
        self.assertEqual(TEXT.count("persist-credentials: false"), TEXT.count("actions/checkout@"))

    def test_actions_are_pinned_to_commits(self) -> None:
        uses = re.findall(r"(?m)^\s*- uses: (\S+)", TEXT)
        self.assertTrue(uses)
        for ref in uses:
            self.assertRegex(ref, r"@[0-9a-f]{40}$")

    def test_inputs_reach_the_shell_only_through_env(self) -> None:
        for block in re.findall(r"(?ms)^\s*run: \|\n(.*?)(?=^\s*- |\Z)", TEXT):
            self.assertNotIn("${{", block)

    def test_only_the_owner_runs_it_and_jobs_have_time_limits(self) -> None:
        self.assertIn("github.actor == 'u-pump'", TEXT)
        self.assertEqual(TEXT.count("timeout-minutes:"), TEXT.count("runs-on:"))

    def test_verify_lints_and_watches_the_workflow(self) -> None:
        verify = (ROOT / ".github" / "workflows" / "verify.yml").read_text(encoding="utf-8")
        self.assertGreaterEqual(verify.count("mine-candidates.yml"), 2)


if __name__ == "__main__":
    unittest.main()

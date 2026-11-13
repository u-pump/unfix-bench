# SPDX-License-Identifier: MIT
# Copyright (c) 2026 U-Pump
"""Static checks that the Claude Code run publishes only what the owner approved."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN_SCRIPT = (ROOT / "scripts" / "run_claude_case.sh").read_text(encoding="utf-8")
WORKFLOW = (ROOT / ".github" / "workflows" / "run-claude-code.yml").read_text(encoding="utf-8")
PUBLISHABLE = {
    "result/agent-fix.patch", "result/agent.yaml", "evidence/network-proof.log", "evidence/proxy.log",
}


class ArtifactPolicyTest(unittest.TestCase):
    def test_only_approved_files_are_written_under_the_output_directory(self) -> None:
        written = set(re.findall(r'\$OUT/((?:result|evidence)/[A-Za-z0-9_.-]+)', RUN_SCRIPT))
        self.assertTrue(written <= PUBLISHABLE | {"result/results"}, written - PUBLISHABLE)

    def test_transcript_and_stderr_stay_private_and_are_never_printed(self) -> None:
        self.assertNotIn("$OUT/evidence/transcript", RUN_SCRIPT)
        self.assertNotIn("$OUT/evidence/agent-stderr", RUN_SCRIPT)
        self.assertIn('"$PRIV/transcript.jsonl" "$PRIV/agent-stderr.log"', RUN_SCRIPT)
        self.assertNotRegex(RUN_SCRIPT, r"cat\s+[^\n]*transcript")
        self.assertNotRegex(RUN_SCRIPT, r"cat\s+[^\n]*agent-stderr")
        self.assertIn('rm -rf "$WORK" "$UPSTREAM" "$PRIV"', RUN_SCRIPT)

    def test_every_uploaded_directory_is_scanned_first(self) -> None:
        uploads = re.findall(r"upload-artifact@", WORKFLOW)
        scans = re.findall(r"collect_agent_run\.py scan", WORKFLOW)
        self.assertGreaterEqual(len(scans), len(uploads))
        for job in ("probe", "agent", "verify"):
            block = WORKFLOW[WORKFLOW.index(f"\n  {job}:"):]
            block = block[: block.index("upload-artifact@")]
            self.assertIn("collect_agent_run.py scan", block, job)


if __name__ == "__main__":
    unittest.main()

# SPDX-License-Identifier: MIT
# Copyright (c) 2026 U-Pump
"""Static checks that the Claude Code run publishes only what the owner approved."""

from __future__ import annotations

import re
import subprocess
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


class RunnerInvocationTest(unittest.TestCase):
    """Regression for run 43457724614: the attempt script called a non-executable script."""

    def test_shell_scripts_are_executable_in_git(self) -> None:
        listing = subprocess.run(
            ["git", "-C", str(ROOT), "ls-files", "-s", "scripts/*.sh"],
            capture_output=True, text=True, check=True,
        ).stdout.splitlines()
        self.assertTrue(listing)
        for row in listing:
            self.assertTrue(row.startswith("100755"), row)

    def test_the_sandbox_is_only_invoked_through_bash(self) -> None:
        self.assertIn('SANDBOX=(bash "$HERE/agent_sandbox.sh")', RUN_SCRIPT)
        self.assertNotRegex(RUN_SCRIPT, r'(?m)^\s*"\$SANDBOX"\s')
        self.assertNotIn("$($SANDBOX", RUN_SCRIPT)

    def test_a_failed_sandbox_build_prints_the_build_log_but_never_the_agent_output(self) -> None:
        self.assertIn('cat "$PRIV/build.log"', RUN_SCRIPT)

    def test_dry_run_stops_before_the_agent_and_is_exercised_by_the_probe_job(self) -> None:
        proof = RUN_SCRIPT.index('"${SANDBOX[@]}" proof')
        stop = RUN_SCRIPT.index('if [ -n "${DRY_RUN:-}" ]')
        agent = RUN_SCRIPT.index('"${SANDBOX[@]}" agent')
        self.assertLess(proof, stop)
        self.assertLess(stop, agent)
        probe = WORKFLOW[WORKFLOW.index("\n  probe:"): WORKFLOW.index("\n  agent:")]
        self.assertIn("DRY_RUN: '1'", probe)
        self.assertIn("scripts/run_claude_case.sh", probe)
        self.assertLess(probe.index("Remove the sandbox"), probe.index("Dry run of the attempt script"))

    def test_the_isolation_proof_runs_inside_every_real_attempt_before_the_agent(self) -> None:
        self.assertLess(RUN_SCRIPT.index('proof "$OUT/evidence/network-proof.log"'),
                        RUN_SCRIPT.index('"${SANDBOX[@]}" agent'))

    def test_only_a_dry_run_may_use_a_case_that_already_has_its_attempt(self) -> None:
        # Regression: the PR probe dry-run used fmt-4800, which became recorded on main.
        line = next(row for row in RUN_SCRIPT.splitlines() if "first patch already recorded" in row)
        self.assertIn('[ -s "$patch_file" ]', line)
        self.assertIn('[ -z "${DRY_RUN:-}" ]', line)

    def test_probe_runs_when_the_attempt_script_or_collector_changes(self) -> None:
        trigger = WORKFLOW[WORKFLOW.index("pull_request:"): WORKFLOW.index("permissions:")]
        for path in ("scripts/run_claude_case.sh", "scripts/collect_agent_run.py", "scripts/agent_sandbox.sh"):
            self.assertIn(f"'{path}'", trigger)


if __name__ == "__main__":
    unittest.main()

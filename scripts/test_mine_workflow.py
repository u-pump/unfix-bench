# SPDX-License-Identifier: MIT
# Copyright (c) 2026 U-Pump
"""Policy for .github/workflows/mine-candidates.yml: it builds other people's code, so privilege is kept to one job."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEXT = (ROOT / ".github" / "workflows" / "mine-candidates.yml").read_text(encoding="utf-8")
JOBS = ("discover", "image", "baseline", "collect", "record")


def job(name: str) -> str:
    start = TEXT.index(f"\n  {name}:\n")
    ends = [i for i in (TEXT.find(f"\n  {other}:\n", start + 1) for other in JOBS) if i > 0]
    return TEXT[start: min(ends)] if ends else TEXT[start:]


class MineWorkflowPolicyTest(unittest.TestCase):
    def test_all_five_jobs_exist(self) -> None:
        for name in JOBS:
            self.assertIn(f"\n  {name}:\n", TEXT)

    def test_only_triggered_by_hand(self) -> None:
        on = TEXT[TEXT.index("\non:"): TEXT.index("\npermissions:")]
        self.assertIn("workflow_dispatch:", on)
        for trigger in ("pull_request", "push:", "schedule:", "workflow_run", "pull_request_target"):
            self.assertNotIn(trigger, on)

    def test_default_permission_is_read_and_only_record_writes(self) -> None:
        self.assertRegex(TEXT, r"(?m)^permissions:\n  contents: read\n")
        for name in JOBS:
            block = job(name)
            if name == "record":
                self.assertIn("contents: write", block)
                self.assertIn("pull-requests: write", block)
            else:
                self.assertNotIn("write", block, name)
        self.assertNotIn("packages:", TEXT)

    def test_foreign_code_jobs_hold_no_secret_and_no_extra_token(self) -> None:
        self.assertNotIn("secrets.", TEXT)
        for name in ("image", "baseline", "collect"):
            self.assertNotIn("github.token", job(name), name)
            self.assertNotIn("GITHUB_TOKEN", job(name), name)
        # only the one job that writes keeps credentials in the checkout
        for name in ("discover", "image", "baseline", "collect"):
            self.assertIn("persist-credentials: false", job(name), name)
        self.assertNotIn("persist-credentials: false", job("record"))

    def test_the_record_job_runs_no_foreign_code(self) -> None:
        block = job("record")
        for word in ("docker", "baseline.py", "cmake", "ctest"):
            self.assertNotIn(word, block)
        self.assertIn("artifacts.py", block)  # it checks the files before reading them

    def test_nothing_is_pushed_to_a_registry_and_every_container_run_is_offline(self) -> None:
        for forbidden in ("docker push", "docker login", "ghcr.io", "build-push-action", "--push"):
            self.assertNotIn(forbidden, TEXT)
        for line in re.findall(r"(?m)^.*\bdocker run\b.*$", TEXT):
            self.assertIn("--network none", line)

    def test_baseline_hands_over_only_checked_files(self) -> None:
        block = job("baseline")
        self.assertLess(block.index("artifacts.py"), block.index("upload-artifact@"))
        self.assertIn("steps.policy.outcome == 'success'", block)
        self.assertLess(job("collect").index("artifacts.py"), job("collect").index("upload-artifact@"))

    def test_the_image_comes_from_docker_miner_build_with_the_first_party_cache(self) -> None:
        block = job("image")
        self.assertIn("docker/miner-build", block)
        self.assertIn("actions/cache@", block)
        self.assertNotIn("setup-buildx", TEXT)  # no third-party action for the build

    def test_actions_are_pinned_to_commits(self) -> None:
        uses = re.findall(r"(?m)^\s*- uses: (\S+)", TEXT)
        self.assertTrue(uses)
        for ref in uses:
            self.assertRegex(ref, r"@[0-9a-f]{40}$")

    def test_inputs_reach_the_shell_only_through_env(self) -> None:
        for block in re.findall(r"(?ms)^\s*run: \|\n(.*?)(?=^\s*- |\Z)", TEXT):
            self.assertNotIn("${{", block)

    def test_only_the_owner_runs_it_and_jobs_have_time_limits(self) -> None:
        self.assertIn("github.actor == 'u-pump'", job("discover"))
        self.assertIn("github.actor == 'u-pump'", job("record"))
        self.assertEqual(TEXT.count("timeout-minutes:"), TEXT.count("runs-on:"))

    def test_baseline_time_limit_covers_the_30_minute_build_budget(self) -> None:
        minutes = int(re.search(r"timeout-minutes: (\d+)", job("baseline")).group(1))  # type: ignore[union-attr]
        self.assertGreater(minutes, 30)

    def test_verify_lints_and_watches_the_workflow(self) -> None:
        verify = (ROOT / ".github" / "workflows" / "verify.yml").read_text(encoding="utf-8")
        self.assertGreaterEqual(verify.count("mine-candidates.yml"), 2)
        self.assertIn("'docker/**'", verify)  # a Dockerfile change reruns the checks


class DockerfileTest(unittest.TestCase):
    TEXT = (ROOT / "docker" / "miner-build" / "Dockerfile").read_text(encoding="utf-8")

    def test_base_is_pinned_by_digest_and_tools_by_version(self) -> None:
        self.assertRegex(self.TEXT, r"(?m)^FROM ubuntu:24\.04@sha256:[0-9a-f]{64}$")
        for name in ("CMAKE", "GCC", "RUBY"):
            self.assertRegex(self.TEXT, rf"(?m)^ARG {name}_VERSION=\d+\.\d+\.\d+$")
        self.assertIn("exit 1", self.TEXT)  # the build fails when a version drifts
        self.assertNotIn("@CMAKE@", self.TEXT)

    def test_same_base_digest_as_the_agent_image(self) -> None:
        agent = (ROOT / "docker" / "claude-agent" / "Dockerfile").read_text(encoding="utf-8")
        digest = re.search(r"sha256:[0-9a-f]{64}", self.TEXT).group(0)  # type: ignore[union-attr]
        self.assertIn(digest, agent)

    def test_the_image_holds_ruby_for_unity_and_no_agent_or_secret(self) -> None:
        self.assertIn("ruby", self.TEXT)
        code = chr(10).join(line for line in self.TEXT.splitlines() if not line.startswith("#"))
        for word in ("ANTHROPIC", "claude", "TOKEN", "npm"):
            self.assertNotIn(word, code)


if __name__ == "__main__":
    unittest.main()

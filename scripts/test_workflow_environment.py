# SPDX-License-Identifier: MIT
# Copyright (c) 2026 U-Pump
"""The verifying jobs must make ThreadSanitizer usable before the verifier runs."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SYSCTL = "sudo sysctl -w vm.mmap_rnd_bits=28"


def job(text: str, name: str) -> str:
    start = text.index(f"\n  {name}:")
    rest = text[start + 1:]
    following = [i for i in (rest.find("\n  " + other + ":") for other in ("probe", "agent", "verify", "record", "publish", "plan", "checks")) if i > 0]
    return rest[: min(following)] if following else rest


class ThreadSanitizerEnvironmentTest(unittest.TestCase):
    def test_both_verify_jobs_set_the_mmap_entropy_before_running_the_verifier(self) -> None:
        verify_yml = (ROOT / ".github" / "workflows" / "verify.yml").read_text(encoding="utf-8")
        run_yml = (ROOT / ".github" / "workflows" / "run-claude-code.yml").read_text(encoding="utf-8")
        block = job(verify_yml, "verify")
        self.assertIn(SYSCTL, block)
        self.assertLess(block.index(SYSCTL), block.index("scripts/verify_cases.py"))
        block = job(run_yml, "verify")
        self.assertIn(SYSCTL, block)
        self.assertLess(block.index(SYSCTL), block.index("scripts/verify_cases.py"))

    def test_the_agent_jobs_do_not_depend_on_it(self) -> None:
        run_yml = (ROOT / ".github" / "workflows" / "run-claude-code.yml").read_text(encoding="utf-8")
        self.assertNotIn(SYSCTL, job(run_yml, "agent"))


if __name__ == "__main__":
    unittest.main()

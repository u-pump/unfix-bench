# SPDX-License-Identifier: MIT
# Copyright (c) 2026 U-Pump
"""Offline tests of the agent-input check against throwaway git repositories."""

from __future__ import annotations

import hashlib
import subprocess
import tempfile
import unittest
from pathlib import Path

import check_input

ISSUE = "Something is broken.\n"


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", "-c", "core.autocrlf=false",
         "-C", str(repo), *args],
        capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


class CheckInputTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.upstream = self.root / "upstream"
        self.upstream.mkdir()
        git(self.upstream, "init", "-q")
        (self.upstream / "a.c").write_text("int main(void){return 0;}\n", encoding="utf-8")
        (self.upstream / "dir").mkdir()
        (self.upstream / "dir" / "b.h").write_text("#pragma once\n", encoding="utf-8")
        git(self.upstream, "add", "-A")
        git(self.upstream, "commit", "-q", "-m", "base")
        self.base = git(self.upstream, "rev-parse", "HEAD")
        (self.upstream / "a.c").write_text("fixed\n", encoding="utf-8")
        git(self.upstream, "commit", "-q", "-am", "fix")
        self.input = self.root / "input"
        self.input.mkdir()
        git(self.input, "init", "-q")
        archive = git_bytes(self.upstream, "archive", "--format=tar", self.base)
        subprocess.run(["tar", "-xf", "-", "-C", str(self.input)], input=archive, check=True)
        (self.input / "ISSUE.md").write_text(ISSUE, encoding="utf-8")
        (self.input / "TASK.md").write_text(check_input.TASK_TEXT + "\n", encoding="utf-8")
        git(self.input, "add", "-A")
        git(self.input, "commit", "-q", "-m", "input")
        digest = hashlib.sha256(
            archive + (self.input / "ISSUE.md").read_bytes() + (self.input / "TASK.md").read_bytes()
        ).hexdigest()
        self.case = {"id": "demo", "base": self.base, "input_sha256": digest}

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def commit_input(self) -> None:
        git(self.input, "add", "-A")
        git(self.input, "commit", "-q", "-m", "more")

    def test_exact_input_passes(self) -> None:
        self.assertEqual(check_input.check(self.case, self.input, self.upstream), [])

    def test_tampered_source_file_is_reported_by_both_checks(self) -> None:
        (self.input / "a.c").write_text("int main(void){return 1;}\n", encoding="utf-8")
        git(self.input, "commit", "-q", "-am", "tamper")
        problems = check_input.check(self.case, self.input, self.upstream)
        self.assertTrue(any("modified files, first: a.c" in p for p in problems), problems)

    def test_changed_issue_text_changes_the_digest(self) -> None:
        (self.input / "ISSUE.md").write_text(ISSUE + "Hint: change line 3.\n", encoding="utf-8")
        git(self.input, "commit", "-q", "-am", "hint")
        problems = check_input.check(self.case, self.input, self.upstream)
        self.assertIn("input_sha256 does not match the recomputed value", problems)

    def test_extra_file_and_history_are_rejected(self) -> None:
        (self.input / "FIX.md").write_text("answer\n", encoding="utf-8")
        self.commit_input()
        problems = check_input.check(self.case, self.input, self.upstream)
        self.assertIn("input repository does not have exactly one commit", problems)
        self.assertTrue(any("unexpected files, first: FIX.md" in p for p in problems), problems)

    def test_wrong_task_text_is_rejected(self) -> None:
        (self.input / "TASK.md").write_text("Fix it however you like.\n", encoding="utf-8")
        git(self.input, "commit", "-q", "-am", "task")
        problems = check_input.check(self.case, self.input, self.upstream)
        self.assertIn("TASK.md differs from the benchmark protocol", problems)


def git_bytes(repo: Path, *args: str) -> bytes:
    return subprocess.run(
        ["git", "-c", "core.autocrlf=false", "-C", str(repo), *args],
        capture_output=True, check=True,
    ).stdout


if __name__ == "__main__":
    unittest.main()

# SPDX-License-Identifier: MIT
# Copyright (c) 2026 U-Pump
"""Offline tests of the agent-input check against throwaway git repositories."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

import check_input

ISSUE = "Something is broken.\n"
ROOT = Path(__file__).resolve().parents[1]


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", "-c", "core.autocrlf=false",
         "-C", str(repo), *args],
        capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


def git_bytes(repo: Path, *args: str) -> bytes:
    return subprocess.run(
        ["git", "-c", "core.autocrlf=false", "-C", str(repo), *args],
        capture_output=True, check=True,
    ).stdout


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
        self.input = self.root / "input"
        self.input.mkdir()
        git(self.input, "init", "-q")
        archive = git_bytes(self.upstream, "archive", "--format=tar", self.base)
        subprocess.run(["tar", "-xf", "-", "-C", str(self.input)], input=archive, check=True)
        (self.input / "ISSUE.md").write_text(ISSUE, encoding="utf-8")
        (self.input / "TASK.md").write_text(check_input.TASK_TEXT + "\n", encoding="utf-8")
        git(self.input, "add", "-A")
        git(self.input, "commit", "-q", "-m", "input")
        self.head = git(self.input, "rev-parse", "HEAD")
        digest = hashlib.sha256(
            archive + (self.input / "ISSUE.md").read_bytes() + (self.input / "TASK.md").read_bytes()
        ).hexdigest()
        self.case = {"id": "demo", "base": self.base, "input_sha256": digest}

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_pinned_input_passes_and_reports_the_hash_and_files(self) -> None:
        problems, info = check_input.check(self.case, self.input, self.upstream, self.head)
        self.assertEqual(problems, [])
        self.assertIn("input_sha256 recomputed: matches case.yaml (information only)", info)
        self.assertIn("files identical to the upstream base archive", info)

    def test_a_different_head_is_blocking(self) -> None:
        problems, info = check_input.check(self.case, self.input, self.upstream, "0" * 40)
        self.assertEqual(problems, ["input HEAD is not the pinned commit"])
        self.assertEqual(info, [])

    def test_history_is_blocking(self) -> None:
        (self.input / "FIX.md").write_text("answer\n", encoding="utf-8")
        git(self.input, "add", "-A")
        git(self.input, "commit", "-q", "-m", "more")
        problems, _ = check_input.check(self.case, self.input, self.upstream, self.head)
        self.assertIn("input repository does not have exactly one commit", problems)
        self.assertIn("input HEAD is not the pinned commit", problems)

    def test_wrong_task_text_is_blocking(self) -> None:
        (self.input / "TASK.md").write_text("Fix it however you like.\n", encoding="utf-8")
        git(self.input, "commit", "-q", "-a", "--amend", "-m", "input")
        head = git(self.input, "rev-parse", "HEAD")
        problems, _ = check_input.check(self.case, self.input, self.upstream, head)
        self.assertIn("TASK.md differs from the benchmark protocol", problems)

    def test_hash_and_file_differences_are_information_only(self) -> None:
        (self.input / "a.c").write_text("int main(void){return 1;}\n", encoding="utf-8")
        (self.input / "ISSUE.md").write_text(ISSUE + "Another sentence.\n", encoding="utf-8")
        git(self.input, "commit", "-q", "-a", "--amend", "-m", "input")
        head = git(self.input, "rev-parse", "HEAD")
        problems, info = check_input.check(self.case, self.input, self.upstream, head)
        self.assertEqual(problems, [])
        self.assertIn("input_sha256 recomputed: does NOT match case.yaml (information only)", info)
        self.assertIn("1 files different from upstream, first: a.c", info)

    def test_missing_upstream_is_information_only(self) -> None:
        problems, info = check_input.check(self.case, self.input, None, self.head)
        self.assertEqual(problems, [])
        self.assertIn("not checked", info[0])


class SubmodulePinsTest(unittest.TestCase):
    """A case with `submodules`: the pins in case.yaml must equal the gitlinks of the upstream base."""

    PIN = "a" * 40

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.upstream = Path(self.tmp.name)
        git(self.upstream, "init", "-q")
        (self.upstream / "a.c").write_text("int main(void){return 0;}\n", encoding="utf-8")
        git(self.upstream, "add", "-A")
        git(self.upstream, "update-index", "--add", "--cacheinfo", f"160000,{self.PIN},test/unit-test/CMock")
        git(self.upstream, "commit", "-q", "-m", "base")
        self.base = git(self.upstream, "rev-parse", "HEAD")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def case(self, *pins: tuple[str, str]) -> dict[str, object]:
        return {"id": "demo", "base": self.base, "submodules": [{"path": p, "commit": c} for p, c in pins]}

    def test_equal_pins_pass(self) -> None:
        case = self.case(("test/unit-test/CMock", self.PIN))
        self.assertEqual(check_input.submodule_problems(case, self.upstream), [])

    def test_a_different_commit_is_blocking(self) -> None:
        problems = check_input.submodule_problems(self.case(("test/unit-test/CMock", "b" * 40)), self.upstream)
        self.assertEqual(len(problems), 1)
        self.assertIn("test/unit-test/CMock", problems[0])

    def test_a_missing_or_extra_pin_is_blocking(self) -> None:
        missing = check_input.submodule_problems(self.case(("x/y", self.PIN)), self.upstream)
        self.assertEqual(len(missing), 2)  # x/y has no gitlink, CMock is not pinned
        self.assertTrue(any("no gitlink" in p for p in missing))
        self.assertTrue(any("pins nothing" in p for p in missing))

    def test_a_case_without_submodules_or_without_upstream_is_not_checked(self) -> None:
        self.assertEqual(check_input.submodule_problems({"id": "demo", "base": self.base}, self.upstream), [])
        self.assertEqual(check_input.submodule_problems(self.case(("x", "b" * 40)), None), [])

    def test_the_reference_hash_is_labelled_for_such_a_case(self) -> None:
        inp = Path(self.tmp.name) / "input"
        inp.mkdir()
        git(inp, "init", "-q")
        (inp / "ISSUE.md").write_text(ISSUE, encoding="utf-8")
        (inp / "TASK.md").write_text(check_input.TASK_TEXT, encoding="utf-8")
        git(inp, "add", "-A")
        git(inp, "commit", "-q", "-m", "input")
        head = git(inp, "rev-parse", "HEAD")
        case = self.case(("test/unit-test/CMock", self.PIN))
        problems, info = check_input.check(case, inp, self.upstream, head)
        self.assertEqual(problems, [])
        self.assertTrue(any("reference only" in line for line in info))


class PinsTest(unittest.TestCase):
    def test_every_case_has_a_pinned_commit_and_tree(self) -> None:
        pins = json.loads((ROOT / "inputs" / "bench-in-heads.json").read_text(encoding="utf-8"))["inputs"]
        cases = sorted(path.name for path in (ROOT / "cases").iterdir() if path.is_dir())
        self.assertEqual(sorted(pins), cases)
        for case_id, pin in pins.items():
            for key in ("commit", "tree"):
                self.assertRegex(pin[key], re.compile(r"^[0-9a-f]{40}$"), f"{case_id} {key}")


if __name__ == "__main__":
    unittest.main()

# SPDX-License-Identifier: MIT
# Copyright (c) 2026 U-Pump
"""Regression for fmt-4978: saving the patch failed when the project ignores its build directory."""

from __future__ import annotations

import re
import shlex
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SANDBOX = (Path(__file__).resolve().parent / "agent_sandbox.sh").read_text(encoding="utf-8")


def pathspecs() -> list[str]:
    match = re.search(r"add -A -- \. ((?:\":\(exclude[^\"]*\"\s*)+)", SANDBOX)
    assert match, "the add command of cmd_patch was not found"
    return shlex.split(match.group(1))


def git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-c", "user.email=a@b", "-c", "user.name=x", "-c", "core.autocrlf=false", "-C", str(root), *args],
        capture_output=True, text=True,
    )


class PatchCaptureTest(unittest.TestCase):
    def repo(self, ignore: str) -> Path:
        directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, directory, True)
        git(directory, "init", "-q")
        (directory / ".gitignore").write_text(ignore, encoding="utf-8")
        (directory / "a.cpp").write_text("one\n", encoding="utf-8")
        git(directory, "add", "-A")
        git(directory, "commit", "-qm", "base")
        return directory

    def capture(self, root: Path) -> tuple[int, list[str]]:
        result = git(root, "add", "-A", "--", ".", *pathspecs())
        staged = git(root, "diff", "--cached", "--name-only", "HEAD").stdout.split()
        return result.returncode, staged

    def test_ignored_build_directory_does_not_fail_the_capture(self) -> None:
        root = self.repo("build\n")
        (root / "build").mkdir()
        (root / "build" / "out.o").write_text("x", encoding="utf-8")
        (root / "a.cpp").write_text("two\n", encoding="utf-8")
        code, staged = self.capture(root)
        self.assertEqual(code, 0, "git add must succeed when the build directory is ignored")
        self.assertEqual(staged, ["a.cpp"])

    def test_unignored_and_nested_build_directories_are_excluded(self) -> None:
        root = self.repo("")
        for name in ("build", "build-asan", "sub/build_x"):
            (root / name).mkdir(parents=True)
            (root / name / "out.o").write_text("x", encoding="utf-8")
        (root / "new.cpp").write_text("fix\n", encoding="utf-8")
        code, staged = self.capture(root)
        self.assertEqual(code, 0)
        self.assertEqual(staged, ["new.cpp"])

    def test_without_a_build_directory_the_capture_is_unchanged(self) -> None:
        root = self.repo("build\n")
        (root / "a.cpp").write_text("two\n", encoding="utf-8")
        (root / "src").mkdir()
        (root / "src" / "b.cpp").write_text("new\n", encoding="utf-8")
        code, staged = self.capture(root)
        self.assertEqual((code, staged), (0, ["a.cpp", "src/b.cpp"]))


if __name__ == "__main__":
    unittest.main()

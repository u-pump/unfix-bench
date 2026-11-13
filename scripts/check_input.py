# SPDX-License-Identifier: MIT
# Copyright (c) 2026 U-Pump
"""Check that an agent input repository is exactly the frozen input of its case.

The agent must receive the broken commit's files plus ISSUE.md and TASK.md, with no
history. Two independent checks run: ``input_sha256`` from case.yaml is recomputed
from the upstream base commit, and the input repository's files are compared with
that commit's archive entry by entry.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import subprocess
import sys
import tarfile
from pathlib import Path

TASK_TEXT = "Fix the bug described in ISSUE.md. Keep the change minimal. Run the existing tests."
EXTRA_FILES = {"ISSUE.md", "TASK.md"}


def git(repo: Path, *args: str) -> bytes:
    result = subprocess.run(
        ["git", "-c", "core.autocrlf=false", "-C", str(repo), *args],
        capture_output=True,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(f"git {args[0]} failed")
    return result.stdout


def archive_entries(archive: bytes) -> dict[str, str]:
    """Map every file and symlink in a git archive to a digest of its content."""
    entries: dict[str, str] = {}
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        for member in tar.getmembers():
            if member.isfile():
                data = tar.extractfile(member)
                assert data is not None
                entries[member.name] = hashlib.sha256(data.read()).hexdigest()
            elif member.issym():
                entries[member.name] = "symlink:" + member.linkname
    return entries


def input_entries(input_dir: Path) -> dict[str, str]:
    """Digest every tracked file of the input repository the same way."""
    entries: dict[str, str] = {}
    names = git(input_dir, "ls-files", "-z").decode("utf-8").split("\0")
    for name in filter(None, names):
        path = input_dir / name
        if path.is_symlink():
            entries[name] = "symlink:" + str(path.readlink())
        else:
            entries[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return entries


def check(case: dict[str, object], input_dir: Path, upstream_dir: Path) -> list[str]:
    """Return a list of problems; an empty list means the input is exactly as frozen."""
    problems: list[str] = []
    try:
        if git(input_dir, "rev-list", "--count", "HEAD").strip() != b"1":
            problems.append("input repository does not have exactly one commit")
        if b"\nparent " in git(input_dir, "cat-file", "-p", "HEAD"):
            problems.append("input commit has a parent")
        if git(input_dir, "status", "--porcelain").strip():
            problems.append("input checkout is not clean")
    except RuntimeError:
        return ["input is not a readable git repository"]
    issue, task = input_dir / "ISSUE.md", input_dir / "TASK.md"
    if not issue.is_file() or not task.is_file():
        return [*problems, "ISSUE.md or TASK.md is missing"]
    if task.read_text(encoding="utf-8").strip() != TASK_TEXT:
        problems.append("TASK.md differs from the benchmark protocol")
    try:
        archive = git(upstream_dir, "archive", "--format=tar", str(case["base"]))
    except RuntimeError:
        return [*problems, "upstream base commit is unavailable"]
    digest = hashlib.sha256(archive + issue.read_bytes() + task.read_bytes()).hexdigest()
    if digest != case["input_sha256"]:
        problems.append("input_sha256 does not match the recomputed value")
    expected = archive_entries(archive)
    actual = {k: v for k, v in input_entries(input_dir).items() if k not in EXTRA_FILES}
    missing, extra = sorted(expected.keys() - actual.keys()), sorted(actual.keys() - expected.keys())
    changed = sorted(k for k in expected.keys() & actual.keys() if expected[k] != actual[k])
    for label, names in (("missing", missing), ("unexpected", extra), ("modified", changed)):
        if names:
            problems.append(f"{len(names)} {label} files, first: {names[0]}")
    return problems


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True, help="path to case.yaml")
    parser.add_argument("--input", required=True, help="agent input checkout")
    parser.add_argument("--upstream", required=True, help="upstream clone containing the base commit")
    args = parser.parse_args(argv)
    case = json.loads(Path(args.case).read_text(encoding="utf-8"))
    problems = check(case, Path(args.input), Path(args.upstream))
    for problem in problems:
        print(f"input check failed: {problem}")
    if not problems:
        print(f"input check passed: {case['id']} input_sha256 {case['input_sha256']}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

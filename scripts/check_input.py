# SPDX-License-Identifier: MIT
# Copyright (c) 2026 U-Pump
"""Check that an agent input repository is the one Codex CLI received.

The reference is the HEAD commit of each ``bench-in-<id>`` repository, pinned in
``inputs/bench-in-heads.json``. Blocking checks: exactly one commit, HEAD equals the pinned
commit, ``TASK.md`` equals the protocol text, ``ISSUE.md`` exists. Information only
(printed, never failing): whether ``input_sha256`` from case.yaml can be recomputed from the
upstream base, and how the input differs from the upstream base. The frozen
``input_sha256`` of seven cases cannot be reproduced; see docs/DECISIONS.md (BENCH-13).
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
PINS = Path(__file__).resolve().parents[1] / "inputs" / "bench-in-heads.json"


def git(repo: Path, *args: str) -> bytes:
    result = subprocess.run(
        ["git", "-c", "core.autocrlf=false", "-c", "core.eol=lf", "-C", str(repo), *args],
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
    """Digest every tracked file from the git objects, so no checkout filter can matter."""
    entries: dict[str, str] = {}
    listing = git(input_dir, "ls-files", "-s", "-z").decode("utf-8").split(chr(0))
    for row in filter(None, listing):
        meta, name = row.split(chr(9), 1)
        mode, blob = meta.split()[0], meta.split()[1]
        content = git(input_dir, "cat-file", "blob", blob)
        if mode == "120000":
            entries[name] = "symlink:" + content.decode("utf-8")
        else:
            entries[name] = hashlib.sha256(content).hexdigest()
    return entries


def blocking_problems(input_dir: Path, pinned_commit: str) -> list[str]:
    problems: list[str] = []
    try:
        if git(input_dir, "rev-list", "--count", "HEAD").strip() != b"1":
            problems.append("input repository does not have exactly one commit")
        if b"\nparent " in git(input_dir, "cat-file", "-p", "HEAD"):
            problems.append("input commit has a parent")
        head = git(input_dir, "rev-parse", "HEAD").decode().strip()
        if head != pinned_commit:
            problems.append("input HEAD is not the pinned commit")
        task = git(input_dir, "cat-file", "blob", "HEAD:TASK.md")
        git(input_dir, "cat-file", "blob", "HEAD:ISSUE.md")
    except RuntimeError:
        return [*problems, "input is not a readable git repository with ISSUE.md and TASK.md"]
    if task.decode("utf-8").strip() != TASK_TEXT:
        problems.append("TASK.md differs from the benchmark protocol")
    return problems


def notes(case: dict[str, object], input_dir: Path, upstream_dir: Path | None) -> list[str]:
    """Information lines about the frozen hash and the difference from upstream."""
    if upstream_dir is None:
        return ["input_sha256 and upstream comparison not checked: upstream clone unavailable"]
    try:
        archive = git(upstream_dir, "archive", "--format=tar", str(case["base"]))
        issue = git(input_dir, "cat-file", "blob", "HEAD:ISSUE.md")
        task = git(input_dir, "cat-file", "blob", "HEAD:TASK.md")
    except RuntimeError:
        return ["input_sha256 and upstream comparison not checked: upstream base unavailable"]
    digest = hashlib.sha256(archive + issue + task).hexdigest()
    verdict = "matches case.yaml" if digest == case["input_sha256"] else "does NOT match case.yaml"
    lines = [f"input_sha256 recomputed: {verdict} (information only)"]
    expected = archive_entries(archive)
    actual = {k: v for k, v in input_entries(input_dir).items() if k not in EXTRA_FILES}
    missing = sorted(expected.keys() - actual.keys())
    extra = sorted(actual.keys() - expected.keys())
    changed = sorted(k for k in expected.keys() & actual.keys() if expected[k] != actual[k])
    for label, names in (("missing", missing), ("unexpected", extra), ("different from upstream", changed)):
        if names:
            lines.append(f"{len(names)} files {label}, first: {', '.join(names[:5])}")
    if not (missing or extra or changed):
        lines.append("files identical to the upstream base archive")
    return lines


def check(
    case: dict[str, object], input_dir: Path, upstream_dir: Path | None, pinned_commit: str
) -> tuple[list[str], list[str]]:
    """Return (blocking problems, information lines)."""
    problems = blocking_problems(input_dir, pinned_commit)
    return problems, ([] if problems else notes(case, input_dir, upstream_dir))


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True, help="path to case.yaml")
    parser.add_argument("--input", required=True, help="agent input checkout")
    parser.add_argument("--upstream", help="upstream clone with the base commit (information only)")
    parser.add_argument("--pins", default=str(PINS), help="pinned bench-in commits")
    args = parser.parse_args(argv)
    case = json.loads(Path(args.case).read_text(encoding="utf-8"))
    pins = json.loads(Path(args.pins).read_text(encoding="utf-8"))["inputs"]
    if case["id"] not in pins:
        print(f"input check failed: no pinned commit for {case['id']}")
        return 1
    upstream = Path(args.upstream) if args.upstream and Path(args.upstream).is_dir() else None
    pinned = pins[case["id"]]["commit"]
    problems, info = check(case, Path(args.input), upstream, pinned)
    for problem in problems:
        print(f"input check failed: {problem}")
    if problems:
        return 1
    print(f"input check passed: {case['id']} is the pinned bench-in commit {pinned[:12]}")
    for line in info:
        print(f"  info: {line}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

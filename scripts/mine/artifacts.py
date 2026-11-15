# SPDX-License-Identifier: MIT
# Copyright (c) 2026 U-Pump
"""Artifact policy for the miner: what may leave a job that built other people's code.

A baseline job uploads exactly ``result.json`` and ``baseline.log``. The collect job checks this again
before the record job, which can write to the repository, ever sees the files.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ALLOWED_FILES = frozenset({"result.json", "baseline.log"})
MAX_FILE_BYTES = 1_000_000
MAX_TOTAL_BYTES = 50_000_000
DIRECTORY = re.compile(r"baseline-\d{1,4}")
SECRET_SHAPES = (
    re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{30,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
)


def check(root: Path) -> list[str]:
    """Problems found under ``root`` (empty means the tree may be uploaded or recorded).

    ``root`` holds one ``baseline-<n>`` directory per candidate, each with only the allowed files; nothing
    else, no symbolic links, nothing large, nothing shaped like a secret.
    """
    problems: list[str] = []
    total = 0
    if not root.is_dir():
        return [f"{root} is not a directory"]
    for entry in sorted(root.iterdir()):
        if entry.is_symlink():
            problems.append(f"{entry.name}: symbolic link")
        elif not (entry.is_dir() and DIRECTORY.fullmatch(entry.name)):
            problems.append(f"{entry.name}: not a baseline-<n> directory")
        else:
            for item in sorted(entry.rglob("*")):
                rel = item.relative_to(root).as_posix()
                if item.is_symlink():
                    problems.append(f"{rel}: symbolic link")
                elif item.is_dir():
                    problems.append(f"{rel}: unexpected directory")
                elif item.parent != entry or item.name not in ALLOWED_FILES:
                    problems.append(f"{rel}: file not allowed (only {', '.join(sorted(ALLOWED_FILES))})")
                else:
                    size = item.stat().st_size
                    total += size
                    if size > MAX_FILE_BYTES:
                        problems.append(f"{rel}: {size} bytes is over {MAX_FILE_BYTES}")
                        continue
                    text = item.read_text(encoding="utf-8", errors="replace")
                    for shape in SECRET_SHAPES:
                        if shape.search(text):
                            problems.append(f"{rel}: contains something shaped like a secret")
                            break
    if total > MAX_TOTAL_BYTES:
        problems.append(f"total size {total} bytes is over {MAX_TOTAL_BYTES}")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check a directory of baseline outputs against the artifact policy.")
    parser.add_argument("root", type=Path)
    args = parser.parse_args(argv)
    problems = check(args.root)
    for problem in problems:
        print(f"artifact policy: {problem}", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())

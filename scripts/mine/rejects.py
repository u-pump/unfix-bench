# SPDX-License-Identifier: MIT
# Copyright (c) 2026 U-Pump
"""The append-only rejection log: one JSON object per line in candidates/_rejected/<source>.jsonl."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import candidates


class RejectionError(ValueError):
    """A rejection that does not fit the closed vocabulary or is not safe to write."""


def make(*, source: str, project: str, ref: str, fix_commit: str | None, stage: str, reason_code: str,
         detail: str, fix_date: str | None, miner_run: str) -> dict[str, Any]:
    """Build a rejection row and validate it against the schema of ``candidates.py``."""
    row: dict[str, Any] = {
        "source": source, "project": project, "ref": ref, "fix_commit": fix_commit, "stage": stage,
        "reason_code": reason_code, "detail": " ".join(detail.split()), "fix_date": fix_date,
        "miner_run": miner_run,
    }
    problems = candidates.Problems()
    candidates.validate_rejection(row, "rejection", problems)
    if problems:
        raise RejectionError("; ".join(problems))
    return row


def _log_path(root: Path, source: str) -> Path:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", source):
        raise RejectionError("source must match [a-z0-9][a-z0-9-]*")
    return root / "candidates" / "_rejected" / f"{source}.jsonl"


def read(root: Path, source: str) -> list[dict[str, Any]]:
    path = _log_path(root, source)
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def append(root: Path, row: dict[str, Any]) -> bool:
    """Append one row; returns False (and writes nothing) when the same decision is already logged.

    Existing lines are never rewritten. The same (project, ref, stage, reason_code) is logged once, so a
    repeated mining run does not grow the log.
    """
    problems = candidates.Problems()
    candidates.validate_rejection(row, "rejection", problems)
    if problems:
        raise RejectionError("; ".join(problems))
    path = _log_path(root, row["source"])
    key = (row["project"], row["ref"], row["stage"], row["reason_code"])
    if any((old["project"], old["ref"], old["stage"], old["reason_code"]) == key for old in read(root, row["source"])):
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    needs_break = path.is_file() and path.stat().st_size > 0 and not path.read_bytes().endswith(b"\n")
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(("\n" if needs_break else "") + json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return True


def summary(rows: list[dict[str, Any]]) -> dict[str, int]:
    """Counts per reason code, for a run's summary.json."""
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["reason_code"]] = counts.get(row["reason_code"], 0) + 1
    return dict(sorted(counts.items()))

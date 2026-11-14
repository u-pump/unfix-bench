# SPDX-License-Identifier: MIT
# Copyright (c) 2026 U-Pump
"""Static filters: decide from a PR's metadata and file list alone, with no clone and no build."""

from __future__ import annotations

import re
from datetime import date
from pathlib import PurePosixPath
from typing import Any

import candidates
from mine import rejects

TEST_DIRS = frozenset({"test", "tests", "unittest", "unittests", "unit-test", "unit_test", "testing"})
IGNORED_DIRS = frozenset({"cbmc", ".github", "docs", "doc", "changelog.d"})
SOURCE_SUFFIXES = frozenset({".c", ".h", ".cc", ".cpp", ".cxx", ".hh", ".hpp", ".hxx", ".inl", ".ipp"})
CONFIG_NAMES = re.compile(r"(?i)^(cmakelists\.txt|kconfig.*|makefile.*|.*\.cmake|\.gitignore|\.gitmodules)$")
TEST_NAME = re.compile(r"(?i)(^|[_-])u?tests?([_.-]|$)|_utest")
TEST_SUFFIXES = SOURCE_SUFFIXES | {".data", ".function", ".py"}  # a test is code or test data, not a config file
MIN_ISSUE_TEXT = 40


def classify(path: str) -> str:
    """``test``, ``source`` or ``other`` for one changed file."""
    parts = PurePosixPath(path).parts
    name = parts[-1]
    directories = [part.lower() for part in parts[:-1]]
    if any(part in IGNORED_DIRS for part in directories):
        return "other"
    if CONFIG_NAMES.match(name):
        return "other"
    if any(part in TEST_DIRS for part in directories) or TEST_NAME.search(PurePosixPath(name).stem):
        return "test" if PurePosixPath(name).suffix.lower() in TEST_SUFFIXES else "other"
    return "source" if PurePosixPath(name).suffix.lower() in SOURCE_SUFFIXES else "other"


def split_files(paths: list[str]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {"test": [], "source": [], "other": []}
    for path in paths:
        result[classify(path)].append(path)
    return result


_BACKPORT_TITLE = re.compile(r"(?i)^\s*(?:\[?(?:auto[- ])?(?:backport|cherry[- ]?pick)\]?\b[^:]*:?\s*)")
_VERSION_TAG = re.compile(r"(?i)^\s*(?:\[[^\]]*\]|v?\d+(?:\.\d+)+\s*:)\s*")


def is_backport(title: str, labels: list[str], base_ref: str, default_branch: str) -> bool:
    if base_ref and default_branch and base_ref != default_branch:
        return True
    if any("backport" in label.lower() for label in labels):
        return True
    return bool(_BACKPORT_TITLE.match(title))


def dedupe_key(project: str, title: str) -> str:
    """One key for a change and its backports: the title without the backport/version prefix."""
    text = title
    for _ in range(3):
        text = _BACKPORT_TITLE.sub("", text, count=1)
        text = _VERSION_TAG.sub("", text, count=1)
    words = re.sub(r"[^a-z0-9]+", " ", text.lower()).split()
    return f"{project}:{'-'.join(words)}"


def post_cutoff(fix_date: str) -> bool:
    return date.fromisoformat(fix_date) > candidates.POST_CUTOFF


def static_check(item: dict[str, Any], miner_run: str) -> dict[str, Any] | None:
    """The first failing static filter as a rejection row, or ``None`` when the candidate passes.

    ``item``: source, project, ref, fix_commit, title, body, labels, base_ref, default_branch,
    files (list of paths), spdx, fix_date.
    """
    def reject(stage: str, code: str, detail: str) -> dict[str, Any]:
        return rejects.make(source=item["source"], project=item["project"], ref=item["ref"],
                            fix_commit=item.get("fix_commit"), stage=stage, reason_code=code,
                            detail=detail, fix_date=item.get("fix_date"), miner_run=miner_run)

    if is_backport(item.get("title", ""), item.get("labels", []), item.get("base_ref", ""), item.get("default_branch", "")):
        return reject("static", "duplicate_backport", "backport or non-default base branch; the original change is the candidate")
    files = split_files(item.get("files", []))
    if not files["test"]:
        return reject("static", "no_test_in_diff", "the diff changes no test file")
    if not files["source"]:
        return reject("static", "test_only_fix", "the diff changes tests or configuration but no source file")
    if item.get("spdx") not in candidates.SPDX_ALLOWLIST:
        return reject("license", "license_unclear", f"licence {item.get('spdx')!r} is not on the SPDX allowlist")
    if len((item.get("body") or "").strip()) < MIN_ISSUE_TEXT:
        return reject("issue", "no_issue_text", f"no issue or PR text of at least {MIN_ISSUE_TEXT} characters")
    return None

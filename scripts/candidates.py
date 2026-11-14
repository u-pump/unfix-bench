# SPDX-License-Identifier: MIT
# Copyright (c) 2026 U-Pump
"""Schema and checks for ``candidates/`` (BENCH-20): drafts that are not yet cases.

A candidate lives in ``candidates/<id>/`` and is never a published case. Moving it to
``cases/`` and creating its private ``bench-in-*`` input is done only by the owner, so a
candidate must not carry the fields that the owner creates (``agent_input_repo``,
``input_sha256``).

    python scripts/candidates.py check          # validate candidates/ and the shape of cases/
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

# A fix dated after this day is "post cutoff". Nothing is claimed about any model's training.
POST_CUTOFF = date(2026, 6, 30)

SPDX_ALLOWLIST = frozenset({
    "MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC", "Zlib", "BSL-1.0", "CC0-1.0",
})
GRANULARITIES = ("function", "ctest_module")
SOURCES = ("freertos", "mbedtls", "zephyr", "nuttx", "littlefs", "lwip", "betaflight", "other")
REJECT_STAGES = ("discover", "static", "build", "baseline", "fix_run", "license", "issue", "cap")
REJECT_CODES = (
    "no_test_in_diff", "test_only_fix", "duplicate_backport", "base_not_failing_3of3",
    "fix_not_passing_3of3", "build_failed", "over_30_min", "needs_hardware",
    "needs_network_dependency", "noisy_module", "test_not_selectable", "unsupported_by_verifier",
    "license_unclear", "no_issue_text", "project_cap",
)

SHA = re.compile(r"[0-9a-f]{40}")
CASE_ID = re.compile(r"[a-z0-9][a-z0-9-]*")
HTTPS = re.compile(r"https://[^\s]+")
RUN_URL = re.compile(r"https://github\.com/[\w.-]+/[\w.-]+/actions/runs/\d+")

# Fields every case shares, published or candidate: the shape the existing cases already have.
COMMON_STRINGS = ("id", "repo", "base", "upstream_fix", "bug_test", "reference_selection",
                  "issue_url", "fix_url", "license", "category", "build", "test")
COMMON_OPTIONAL = ("reference_test_name", "reference_selection_note")
OWNER_ONLY = ("agent_input_repo", "input_sha256")
CANDIDATE_EXTRA = ("bug_test_granularity", "build_network", "module_other_tests", "submodules")
META_FIELDS = ("source", "spdx", "fix_date", "post_cutoff", "upstream_pr", "fuzz_origin",
               "dedupe_key", "mined_run_url", "miner_version")
REJECT_FIELDS = ("source", "project", "ref", "fix_commit", "stage", "reason_code", "detail",
                 "fix_date", "miner_run")


class Problems(list[str]):
    def add(self, where: str, message: str) -> None:
        self.append(f"{where}: {message}")


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _iso_date(value: Any) -> date | None:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def validate_common(data: Any, where: str, problems: Problems) -> bool:
    """The shape shared by cases/ and candidates/. Returns False when the file is unusable."""
    if not isinstance(data, dict):
        problems.add(where, "must be a JSON object")
        return False
    for key in COMMON_STRINGS:
        if not _text(data.get(key)):
            problems.add(where, f"{key} must be a non-empty string")
    for key in COMMON_OPTIONAL:
        if key in data and not _text(data[key]):
            problems.add(where, f"{key} must be a non-empty string when present")
    for key in ("base", "upstream_fix"):
        if _text(data.get(key)) and not SHA.fullmatch(data[key]):
            problems.add(where, f"{key} must be a full 40-hex commit")
    for key in ("repo", "issue_url", "fix_url"):
        if _text(data.get(key)) and not HTTPS.fullmatch(data[key]):
            problems.add(where, f"{key} must be an https URL")
    if _text(data.get("id")) and not CASE_ID.fullmatch(data["id"]):
        problems.add(where, "id must match [a-z0-9][a-z0-9-]*")
    if _text(data.get("license")) and data["license"] not in SPDX_ALLOWLIST:
        problems.add(where, f"license {data['license']!r} is not in the SPDX allowlist")
    if _text(data.get("fix_url")) and SHA.fullmatch(str(data.get("upstream_fix", ""))) \
            and data["upstream_fix"] not in data["fix_url"]:
        problems.add(where, "fix_url must point at upstream_fix")
    baseline = data.get("baseline_reproduction")
    if not (isinstance(baseline, dict) and baseline.get("verdict") == "REPRODUCED"
            and baseline.get("runs") == "3/3"
            and isinstance(baseline.get("elapsed_s"), (int, float))
            and not isinstance(baseline.get("elapsed_s"), bool)):
        problems.add(where, "baseline_reproduction must be {verdict: REPRODUCED, runs: 3/3, elapsed_s: number}")
    return True


def validate_candidate_case(data: Any, directory: str, problems: Problems) -> None:
    where = f"candidates/{directory}/case.yaml"
    if not validate_common(data, where, problems):
        return
    for key in OWNER_ONLY:
        if key in data:
            problems.add(where, f"{key} is created by the owner and must not be in a candidate")
    allowed = set(COMMON_STRINGS) | set(COMMON_OPTIONAL) | set(CANDIDATE_EXTRA) | {"baseline_reproduction"}
    for key in sorted(set(data) - allowed - set(OWNER_ONLY)):
        problems.add(where, f"unknown field {key}")
    if data.get("id") != directory:
        problems.add(where, "id must equal the directory name")
    if data.get("bug_test_granularity") not in GRANULARITIES:
        problems.add(where, "bug_test_granularity must be function or ctest_module")
    if data.get("bug_test_granularity") == "ctest_module" and data.get("module_other_tests") != "3/3 pass":
        problems.add(where, "ctest_module needs module_other_tests: '3/3 pass' (otherwise reject as noisy_module)")
    if data.get("build_network") != "none":
        problems.add(where, "build_network must be 'none': build and test ran with --network none")
    submodules = data.get("submodules", [])
    if not isinstance(submodules, list):
        problems.add(where, "submodules must be a list")
    else:
        paths: set[str] = set()
        for item in submodules:
            ok = (isinstance(item, dict) and set(item) == {"path", "commit"}
                  and _text(item["path"]) and isinstance(item["commit"], str)
                  and SHA.fullmatch(item["commit"]) and not item["path"].startswith(("/", ".."))
                  and ".." not in Path(item["path"]).parts)
            if not ok:
                problems.add(where, "each submodule must be {path, commit} with a relative path and a 40-hex commit")
            elif item["path"] in paths:
                problems.add(where, f"duplicate submodule path {item['path']}")
            else:
                paths.add(item["path"])


def validate_meta(data: Any, directory: str, case: Any, problems: Problems) -> None:
    where = f"candidates/{directory}/meta.yaml"
    if not isinstance(data, dict):
        problems.add(where, "must be a JSON object")
        return
    for key in sorted(set(data) - set(META_FIELDS)):
        problems.add(where, f"unknown field {key}")
    for key in META_FIELDS:
        if key not in data:
            problems.add(where, f"{key} is missing")
    if data.get("source") not in SOURCES:
        problems.add(where, f"source must be one of {', '.join(SOURCES)}")
    if isinstance(case, dict) and data.get("spdx") != case.get("license"):
        problems.add(where, "spdx must equal license in case.yaml")
    fixed = _iso_date(data.get("fix_date"))
    if fixed is None:
        problems.add(where, "fix_date must be YYYY-MM-DD")
    if not isinstance(data.get("post_cutoff"), bool):
        problems.add(where, "post_cutoff must be true or false")
    elif fixed is not None and data["post_cutoff"] != (fixed > POST_CUTOFF):
        problems.add(where, f"post_cutoff must be {str(fixed > POST_CUTOFF).lower()} for fix_date {data['fix_date']} (cutoff {POST_CUTOFF})")
    for key in ("upstream_pr", "fuzz_origin"):
        value = data.get(key)
        if key in data and value is not None and not (isinstance(value, str) and HTTPS.fullmatch(value)):
            problems.add(where, f"{key} must be null or an https URL")
    for key in ("dedupe_key", "miner_version"):
        if not _text(data.get(key)):
            problems.add(where, f"{key} must be a non-empty string")
    if not (isinstance(data.get("mined_run_url"), str) and RUN_URL.fullmatch(data["mined_run_url"])):
        problems.add(where, "mined_run_url must be a GitHub Actions run URL")


def validate_rejection(row: Any, where: str, problems: Problems) -> None:
    if not isinstance(row, dict):
        problems.add(where, "each line must be a JSON object")
        return
    if set(row) != set(REJECT_FIELDS):
        problems.add(where, f"fields must be exactly {', '.join(REJECT_FIELDS)}")
        return
    if row["stage"] not in REJECT_STAGES:
        problems.add(where, f"stage must be one of {', '.join(REJECT_STAGES)}")
    if row["reason_code"] not in REJECT_CODES:
        problems.add(where, f"reason_code {row['reason_code']!r} is not in the vocabulary")
    for key in ("source", "project", "ref", "detail", "miner_run"):
        if not _text(row[key]):
            problems.add(where, f"{key} must be a non-empty string")
    if row["fix_commit"] is not None and not (isinstance(row["fix_commit"], str) and SHA.fullmatch(row["fix_commit"])):
        problems.add(where, "fix_commit must be null or a 40-hex commit")
    if row["fix_date"] is not None and _iso_date(row["fix_date"]) is None:
        problems.add(where, "fix_date must be null or YYYY-MM-DD")


def _load(path: Path, where: str, problems: Problems) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError:
        problems.add(where, "missing")
    except ValueError:
        problems.add(where, "is not valid JSON")
    return None


def check_candidates(root: Path = ROOT) -> Problems:
    problems = Problems()
    base = root / "candidates"
    if not base.is_dir():
        return problems
    published = {p.name for p in (root / "cases").iterdir() if p.is_dir()} if (root / "cases").is_dir() else set()
    keys: dict[str, str] = {}
    for directory in sorted(p for p in base.iterdir() if p.is_dir() and not p.name.startswith("_")):
        name = directory.name
        if not CASE_ID.fullmatch(name):
            problems.add(f"candidates/{name}", "directory name must match [a-z0-9][a-z0-9-]*")
            continue
        if name in published:
            problems.add(f"candidates/{name}", "id already exists in cases/")
        case = _load(directory / "case.yaml", f"candidates/{name}/case.yaml", problems)
        if case is not None:
            validate_candidate_case(case, name, problems)
        meta = _load(directory / "meta.yaml", f"candidates/{name}/meta.yaml", problems)
        if meta is not None:
            validate_meta(meta, name, case, problems)
            key = meta.get("dedupe_key") if isinstance(meta, dict) else None
            if isinstance(key, str) and key.strip():
                if key in keys:
                    problems.add(f"candidates/{name}/meta.yaml", f"dedupe_key duplicates {keys[key]} (a backport counts once)")
                keys[key] = name
        for required in ("ISSUE.md", "baseline.log"):
            path = directory / required
            if not path.is_file() or not path.read_text(encoding="utf-8", errors="replace").strip():
                problems.add(f"candidates/{name}/{required}", "missing or empty")
    rejected = base / "_rejected"
    if rejected.is_dir():
        for log in sorted(rejected.glob("*.jsonl")):
            for number, line in enumerate(log.read_text(encoding="utf-8").splitlines(), 1):
                if not line.strip():
                    continue
                where = f"candidates/_rejected/{log.name}:{number}"
                try:
                    row = json.loads(line)
                except ValueError:
                    problems.add(where, "is not valid JSON")
                    continue
                validate_rejection(row, where, problems)
    return problems


def check_published_cases(root: Path = ROOT) -> Problems:
    """The shared shape must hold for every published case, so one schema serves both."""
    problems = Problems()
    for path in sorted((root / "cases").glob("*/case.yaml")):
        where = f"cases/{path.parent.name}/case.yaml"
        data = _load(path, where, problems)
        if data is None:
            continue
        validate_common(data, where, problems)
        if isinstance(data, dict) and data.get("id") != path.parent.name:
            problems.add(where, "id must equal the directory name")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["check"])
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    problems = Problems(check_candidates(args.root) + check_published_cases(args.root))
    for line in problems:
        print(line, file=sys.stderr)
    if problems:
        print(f"{len(problems)} problem(s)", file=sys.stderr)
        return 1
    print("candidates and cases are well-formed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

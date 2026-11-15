# SPDX-License-Identifier: MIT
# Copyright (c) 2026 U-Pump
"""Turn discovery and baseline outputs into ``candidates/`` drafts and rejection-log rows.

Runs in the one job that may write to the repository, on files that already passed ``artifacts.check``.
Nothing from a baseline result is trusted as-is: rejection rows are rebuilt from the verdict fields, every
text field is validated, and the written tree is checked by ``candidates.check_candidates`` afterwards.
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import candidates
from mine import cap, rejects

MINER_VERSION = "bench-20-pr6a"
MAX_LOG_BYTES = 200_000
MODULE = re.compile(r"[\w.+-]{1,120}")
FUNCTION = re.compile(r"test_\w{1,120}")
SHA = candidates.SHA


class RecordError(ValueError):
    pass


def case_id(project: str, number: int) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", project.split("/")[1].lower()).strip("-")
    return f"{slug}-{number}"


def ctest_regex(name: str) -> str:
    """``name`` as a CMake regular expression that matches only itself (``ctest -R`` uses CMake's engine)."""
    return re.sub(r"([\\^$.\[\]*+?()|])", r"\\\1", name)


def pr_number(ref: str) -> int:
    match = re.fullmatch(r"pull/(\d+)", ref)
    if not match:
        raise RecordError(f"unexpected ref {ref!r}")
    return int(match.group(1))


def load_result(directory: Path, item: dict[str, Any]) -> dict[str, Any]:
    """``result.json`` of one baseline, checked to belong to ``item`` and to have the expected shape."""
    path = directory / "result.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("ref") != item["ref"] or data.get("project") != item["project"]:
        raise RecordError(f"{directory.name}: result does not belong to {item['project']} {item['ref']}")
    verdict = data.get("verdict")
    if not isinstance(verdict, dict) or not isinstance(verdict.get("accepted"), bool):
        raise RecordError(f"{directory.name}: no verdict")
    if not isinstance(data.get("elapsed_s"), (int, float)) or isinstance(data.get("elapsed_s"), bool):
        raise RecordError(f"{directory.name}: elapsed_s is not a number")
    if verdict["accepted"]:
        if not (isinstance(verdict.get("module"), str) and MODULE.fullmatch(verdict["module"])
                and isinstance(verdict.get("bug_test"), str) and FUNCTION.fullmatch(verdict["bug_test"])
                and verdict.get("bug_test_granularity") == "ctest_module"
                and verdict.get("module_other_tests") == "3/3 pass"):
            raise RecordError(f"{directory.name}: accepted verdict has unexpected fields")
        for key in ("base", "fix"):
            if not (isinstance(data.get(key), str) and SHA.fullmatch(data[key])):
                raise RecordError(f"{directory.name}: {key} is not a commit")
        if data["fix"] != item["fix_commit"]:
            raise RecordError(f"{directory.name}: fix commit differs from the discovered one")
        if not (isinstance(data.get("build"), str) and isinstance(data.get("submodules"), list)):
            raise RecordError(f"{directory.name}: build or submodules missing")
    return data


def draft(root: Path, item: dict[str, Any], result: dict[str, Any], log: str, run_url: str) -> str:
    """Write ``candidates/<id>/``; returns the id."""
    number = pr_number(item["ref"])
    name = case_id(item["project"], number)
    directory = root / "candidates" / name
    if directory.exists():
        raise RecordError(f"candidates/{name} already exists")
    verdict = result["verdict"]
    project, fix = item["project"], item["fix_commit"]
    module = verdict["module"]
    case = {
        "id": name,
        "repo": f"https://github.com/{project}.git",
        "base": result["base"],
        "upstream_fix": fix,
        "bug_test": verdict["bug_test"],
        "reference_selection": ("first function added or changed by the upstream diff that fails 3/3 on the base; "
                                f"the reference is the whole ctest test {module} (ctest_module), no function filter exists"),
        "reference_selection_note": f"ctest test {module}; changed functions: {', '.join(result.get('changed_functions', []))}",
        "issue_url": item["url"],
        "fix_url": f"https://github.com/{project}/commit/{fix}",
        "license": item["spdx"],
        "category": "unclassified (the owner sets it)",
        "build": result["build"],
        "test": f"ctest --test-dir build -R {shlex.quote('^' + ctest_regex(module) + '$')} --output-on-failure",
        "bug_test_granularity": "ctest_module",
        "build_network": "none",
        "module_other_tests": "3/3 pass",
        "submodules": result["submodules"],
        "baseline_reproduction": {"verdict": "REPRODUCED", "runs": "3/3", "elapsed_s": result["elapsed_s"]},
    }
    meta = {
        "source": item["source"], "spdx": item["spdx"], "fix_date": item["fix_date"],
        "post_cutoff": item["fix_date"] > candidates.POST_CUTOFF.isoformat(), "upstream_pr": item["url"],
        "fuzz_origin": None, "dedupe_key": item["dedupe_key"], "mined_run_url": run_url,
        "miner_version": MINER_VERSION,
    }
    issue = (f"<!-- DRAFT. This is the text of the upstream pull request, which describes the fix. The owner removes "
             f"every solution hint before this becomes an issue; nothing was removed automatically. -->\n\n"
             f"# {item['title']}\n\nSource: {item['url']}\n\n{(item.get('body') or '').strip()}\n")
    directory.mkdir(parents=True)
    for filename, content in (("case.yaml", json.dumps(case, indent=2, ensure_ascii=False) + "\n"),
                              ("meta.yaml", json.dumps(meta, indent=2, ensure_ascii=False) + "\n"),
                              ("ISSUE.md", issue), ("baseline.log", log[-MAX_LOG_BYTES:])):
        (directory / filename).write_text(content, encoding="utf-8", newline="\n")
    return name


def apply(root: Path, discovered: Path, collected: Path, run_url: str) -> dict[str, Any]:
    """Record one run. Returns the summary also written to ``candidates/_runs/<run-id>/summary.json``."""
    data = json.loads(discovered.read_text(encoding="utf-8"))
    summary: dict[str, Any] = {"run": run_url, "source": data["source"], "written": [], "rejected_logged": 0,
                               "missing_results": [], "errors": [], "stats": data.get("stats", {})}

    def log_row(row: dict[str, Any]) -> None:
        if rejects.append(root, row, MINER_VERSION):
            summary["rejected_logged"] += 1

    for row in data["rejected"]:
        log_row(row)
    current = cap.counts(root)
    for index, item in enumerate(data["accepted"]):
        directory = collected / f"baseline-{index}"
        if not (directory / "result.json").is_file():
            summary["missing_results"].append(f"{item['project']} {item['ref']}")
            continue
        try:
            result = load_result(directory, item)
            verdict = result["verdict"]
            if not verdict["accepted"]:
                log_row(rejects.make(source=item["source"], project=item["project"], ref=item["ref"],
                                     fix_commit=item["fix_commit"], stage=verdict.get("stage"),
                                     reason_code=verdict.get("reason_code"), detail=str(verdict.get("detail", ""))[:500],
                                     fix_date=item["fix_date"], miner_run=run_url))
                continue
            repo_url = f"https://github.com/{item['project']}.git"
            if cap.exceeds(current, repo_url):
                log_row(rejects.make(source=item["source"], project=item["project"], ref=item["ref"],
                                     fix_commit=item["fix_commit"], stage="cap", reason_code="project_cap",
                                     detail=f"family {cap.family(repo_url)} is at the limit of {cap.LIMIT} of {cap.TOTAL}",
                                     fix_date=item["fix_date"], miner_run=run_url))
                continue
            log = (directory / "baseline.log").read_text(encoding="utf-8", errors="replace")
            summary["written"].append(draft(root, item, result, log, run_url))
            current[cap.family(repo_url)] += 1
        except (RecordError, rejects.RejectionError, KeyError, ValueError) as error:
            summary["errors"].append(f"{item['project']} {item['ref']}: {error}")
    run_id = run_url.rsplit("/", 1)[-1]
    target = root / "candidates" / "_runs" / run_id
    target.mkdir(parents=True, exist_ok=True)
    (target / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return summary


def matrix(discovered: Path) -> str:
    """JSON list of the accepted indices, for the baseline job matrix."""
    return json.dumps(list(range(len(json.loads(discovered.read_text(encoding="utf-8"))["accepted"]))))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Matrix and recording for the miner workflow.")
    sub = parser.add_subparsers(dest="command", required=True)
    one = sub.add_parser("matrix")
    one.add_argument("discovered", type=Path)
    two = sub.add_parser("apply")
    two.add_argument("--discovered", required=True, type=Path)
    two.add_argument("--collected", required=True, type=Path)
    two.add_argument("--run-url", required=True)
    two.add_argument("--root", type=Path, default=candidates.ROOT)
    args = parser.parse_args(argv)
    if args.command == "matrix":
        print(matrix(args.discovered))
        return 0
    if not candidates.RUN_URL.fullmatch(args.run_url):
        parser.error("--run-url must be a GitHub Actions run URL")
    summary = apply(args.root, args.discovered, args.collected, args.run_url)
    print(json.dumps({key: summary[key] for key in ("written", "rejected_logged", "missing_results", "errors")}, sort_keys=True))
    problems = candidates.check_candidates(args.root)
    for problem in problems:
        print(f"candidates check: {problem}", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())

# SPDX-License-Identifier: MIT
# Copyright (c) 2026 U-Pump
"""Rebuild the README result tables from results/<case>/<agent>.md.

Only the verdict cells and the totals are generated; the case, project and bug
cells of each row are kept as written. ``--check`` fails if the README differs.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
START, END = "<!-- results:start -->", "<!-- results:end -->"
AGENTS = {"Codex CLI": "codex-cli", "Claude Code": "claude-code"}
VERDICTS = ("VERIFIED", "REJECTED", "REVIEW", "NOT_VERIFIABLE", "NO_PATCH", "ERROR", "PENDING")
LABELS = {"INFRASTRUCTURE_ERROR": "ERROR"}
VERDICT_LINE = re.compile(r"(?m)^Verdict: \*\*([A-Z_]+)\*\*")
ROW = re.compile(r"^\| ([a-z0-9-]+) \| (.+?) \| (.+?) \| \[[A-Z_]+\]\(results/.+\) \|.*\|$")


def verdict_of(results: Path, case_id: str, agent_id: str) -> str:
    path = results / case_id / f"{agent_id}.md"
    match = VERDICT_LINE.search(path.read_text(encoding="utf-8"))
    if match is None:
        raise ValueError(f"No verdict in {path}")
    label = LABELS.get(match[1], match[1])
    if label not in VERDICTS:
        raise ValueError(f"Unknown verdict {match[1]} in {path}")
    return label


def render_block(block: str, results: Path) -> str:
    lines = block.strip("\n").splitlines()
    header = next(line for line in lines if line.startswith("| Case |"))
    columns = [cell.strip() for cell in header.strip("|").split("|")][3:]
    agents = [AGENTS[name] for name in columns]
    rows = [m for line in lines if (m := ROW.match(line))]
    out = [header, "| --- | --- | --- | " + " | ".join("---" for _ in agents) + " |"]
    counts = {agent: dict.fromkeys(VERDICTS, 0) for agent in agents}
    for row in rows:
        case_id = row[1]
        cells = []
        for agent in agents:
            label = verdict_of(results, case_id, agent)
            counts[agent][label] += 1
            cells.append(f"[{label}](results/{case_id}/{agent}.md)")
        out.append(f"| {case_id} | {row[2]} | {row[3]} | " + " | ".join(cells) + " |")
    totals = ["", "| Agent | " + " | ".join(VERDICTS) + " |", "| --- | " + " | ".join("---:" for _ in VERDICTS) + " |"]
    for name, agent in zip(columns, agents, strict=True):
        totals.append(f"| {name} | " + " | ".join(str(counts[agent][v]) for v in VERDICTS) + " |")
    return "\n".join([*out, *totals])


def render(readme: str, results: Path) -> str:
    start, end = readme.index(START) + len(START), readme.index(END)
    return readme[:start] + "\n" + render_block(readme[start:end], results) + "\n" + readme[end:]


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--readme", default=str(ROOT / "README.md"))
    parser.add_argument("--results", default=str(ROOT / "results"))
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    path = Path(args.readme)
    current = path.read_bytes().decode("utf-8")
    updated = render(current.replace("\r\n", "\n"), Path(args.results))
    if args.check:
        if updated != current.replace("\r\n", "\n"):
            print("README results tables are out of date; run scripts/render_readme.py")
            return 1
        print("README results tables are up to date")
        return 0
    path.write_bytes(updated.encode("utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

# SPDX-License-Identifier: MIT
# Copyright (c) 2026 U-Pump
"""Choose the cases an agent run may attempt: those with no recorded first attempt for that agent."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENT = "claude-code"  # the default; `--agent codex-cli` plans for run-codex.yml
AGENTS = ("claude-code", "codex-cli")


def is_pending(case_id: str, root: Path = ROOT, agent: str = AGENT) -> bool:
    """A case is open when its patch is empty and its metadata records no completed attempt."""
    base = root / "cases" / case_id / "agents" / agent
    try:
        meta = json.loads((base / "agent.yaml").read_text(encoding="utf-8"))
        patch = (base / "agent-fix.patch").read_bytes()
    except (OSError, ValueError):
        return False
    return not patch.strip() and meta.get("patch_sha256") is None and meta.get("outcome") is None


def plan(selected: str, root: Path = ROOT, agent: str = AGENT) -> list[str]:
    if selected:
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", selected):
            raise ValueError("Invalid case ID")
        if not is_pending(selected, root, agent):
            raise ValueError(f"{selected}: a first attempt is already recorded, or the case is unknown")
        return [selected]
    cases = sorted(path.name for path in (root / "cases").iterdir() if path.is_dir())
    return [case_id for case_id in cases if is_pending(case_id, root, agent)]


def main(argv: list[str]) -> int:
    args = list(argv)
    agent = AGENT
    if "--agent" in args:
        index = args.index("--agent")
        agent = args[index + 1] if index + 1 < len(args) else ""
        del args[index:index + 2]
        if agent not in AGENTS:
            print("plan: unknown agent", file=sys.stderr)
            return 1
    try:
        cases = plan(args[0].strip() if args else "", agent=agent)
    except ValueError as exc:
        print(f"plan: {exc}", file=sys.stderr)
        return 1
    if not cases:
        print("plan: no case is open for a first attempt", file=sys.stderr)
        return 1
    print(json.dumps(cases))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

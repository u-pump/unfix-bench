# SPDX-License-Identifier: MIT
# Copyright (c) 2026 U-Pump
"""Offline tests of README table generation and the committed README."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import render_readme

README = """intro
<!-- results:start -->
| Case | Project | Bug | Codex CLI | Claude Code |
| --- | --- | --- | --- | --- |
| a-1 | [p](u) | [bug a](u) | [REJECTED](results/a-1/codex-cli.md) | [PENDING](results/a-1/claude-code.md) |
| b-2 | [p](u) | [bug b](u) | [REJECTED](results/b-2/codex-cli.md) | [PENDING](results/b-2/claude-code.md) |
| c-3 | [p](u) | [bug c](u) | [REJECTED](results/c-3/codex-cli.md) | [PENDING](results/c-3/claude-code.md) |

| Agent | VERIFIED | REJECTED | PENDING |
| --- | ---: | ---: | ---: |
| Codex CLI | 0 | 0 | 0 |
| Claude Code | 0 | 0 | 0 |
<!-- results:end -->
outro
"""


def write(results: Path, case: str, agent: str, verdict: str) -> None:
    path = results / case / f"{agent}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"# {case}\n\nVerdict: **{verdict}**\n", encoding="utf-8")


class RenderReadmeTest(unittest.TestCase):
    def test_cells_and_totals_come_from_results(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            results = Path(directory)
            for case, codex, claude in (
                ("a-1", "VERIFIED", "VERIFIED"),
                ("b-2", "REJECTED", "NO_PATCH"),
                ("c-3", "REJECTED", "INFRASTRUCTURE_ERROR"),
            ):
                write(results, case, "codex-cli", codex)
                write(results, case, "claude-code", claude)
            text = render_readme.render(README, results)
        self.assertIn("| a-1 | [p](u) | [bug a](u) | [VERIFIED](results/a-1/codex-cli.md) | "
                      "[VERIFIED](results/a-1/claude-code.md) |", text)
        self.assertIn("[NO_PATCH](results/b-2/claude-code.md)", text)
        self.assertIn("[ERROR](results/c-3/claude-code.md)", text)
        self.assertIn("| Agent | VERIFIED | REJECTED | REVIEW | NOT_VERIFIABLE | NO_PATCH | ERROR | PENDING |", text)
        self.assertIn("| Codex CLI | 1 | 2 | 0 | 0 | 0 | 0 | 0 |", text)
        self.assertIn("| Claude Code | 1 | 0 | 0 | 0 | 1 | 1 | 0 |", text)
        self.assertTrue(text.startswith("intro\n") and text.endswith("outro\n"))

    def test_unknown_or_missing_verdict_is_an_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            results = Path(directory)
            for case in ("a-1", "b-2", "c-3"):
                write(results, case, "codex-cli", "VERIFIED")
                write(results, case, "claude-code", "MAYBE")
            with self.assertRaises(ValueError):
                render_readme.render(README, results)

    def test_committed_readme_matches_committed_results(self) -> None:
        readme = (render_readme.ROOT / "README.md").read_bytes().decode("utf-8").replace("\r\n", "\n")
        self.assertEqual(render_readme.render(readme, render_readme.ROOT / "results"), readme)


if __name__ == "__main__":
    unittest.main()

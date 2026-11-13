# SPDX-License-Identifier: MIT
# Copyright (c) 2026 U-Pump
"""A case can carry one public line about how its agent input differs from upstream."""

from __future__ import annotations

import unittest

import verify_cases


class InputNoteTest(unittest.TestCase):
    def test_note_is_rendered_after_the_result_note_and_before_elapsed(self) -> None:
        text = verify_cases.render(
            "demo-1", "REJECTED", {}, 12.0, "Agent", "1", "2026-11-13 10:00:00 UTC",
            "reason", "result note", "a" * 64, "input differs in 5 files",
        )
        order = [text.index(part) for part in
                 ("Reason: reason", "Note: result note", "Input: input differs in 5 files", "Elapsed:")]
        self.assertEqual(order, sorted(order))

    def test_no_note_leaves_the_report_unchanged(self) -> None:
        args = ("demo-1", "VERIFIED", {}, 1.0, "Agent", "1", "2026-11-13 10:00:00 UTC")
        self.assertEqual(verify_cases.render(*args), verify_cases.render(*args, input_note=None))
        self.assertNotIn("Input:", verify_cases.render(*args))

    def test_committed_reports_carry_the_note_of_their_case(self) -> None:
        notes = list((verify_cases.ROOT / "cases").glob("*/input-note.txt"))
        self.assertTrue(notes)
        for note_file in notes:
            case_id = note_file.parent.name
            line = verify_cases.case_input_note(case_id)
            self.assertNotIn("\n", str(line))
            for report in (verify_cases.ROOT / "results" / case_id).glob("*.md"):
                text = report.read_text(encoding="utf-8")
                if "Verdict: **PENDING**" in text:
                    continue  # a report that has not been produced yet gets the line when it is
                self.assertIn(f"\nInput: {line}\n", text.replace("\r\n", "\n"), report.name)


if __name__ == "__main__":
    unittest.main()

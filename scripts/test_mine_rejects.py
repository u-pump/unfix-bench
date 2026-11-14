# SPDX-License-Identifier: MIT
# Copyright (c) 2026 U-Pump
"""The rejection log is append-only, closed-vocabulary and valid for candidates.py."""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

import candidates
from mine import rejects

RUN = "https://github.com/u-pump/unfix-bench/actions/runs/1"


def row(**changes: object) -> dict[str, object]:
    base: dict[str, object] = dict(
        source="freertos", project="FreeRTOS/coreMQTT", ref="pull/382", fix_commit="a" * 40, stage="baseline",
        reason_code="noisy_module", detail="2 other tests failed on base", fix_date="2026-08-13", miner_run=RUN)
    return base | changes


class RejectsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, True)

    def test_make_validates_against_the_schema(self) -> None:
        self.assertEqual(rejects.make(**row())["reason_code"], "noisy_module")
        for bad in ({"reason_code": "whatever"}, {"stage": "later"}, {"detail": "  "}, {"fix_commit": "abc"}):
            with self.subTest(bad), self.assertRaises(rejects.RejectionError):
                rejects.make(**row(**bad))

    def test_detail_is_collapsed_to_one_line(self) -> None:
        self.assertEqual(rejects.make(**row(detail="a\nb\n  c"))["detail"], "a b c")

    def test_append_writes_valid_lines_the_checker_accepts(self) -> None:
        self.assertTrue(rejects.append(self.root, rejects.make(**row())))
        self.assertTrue(rejects.append(self.root, rejects.make(**row(ref="pull/383", reason_code="no_issue_text", stage="issue"))))
        self.assertEqual(len(rejects.read(self.root, "freertos")), 2)
        (self.root / "cases").mkdir()
        self.assertEqual(list(candidates.check_candidates(self.root)), [])

    def test_the_same_decision_is_logged_once(self) -> None:
        self.assertTrue(rejects.append(self.root, rejects.make(**row())))
        self.assertFalse(rejects.append(self.root, rejects.make(**row(detail="again, different words"))))
        self.assertEqual(len(rejects.read(self.root, "freertos")), 1)

    def test_a_new_reason_for_the_same_candidate_is_a_new_line(self) -> None:
        rejects.append(self.root, rejects.make(**row()))
        self.assertTrue(rejects.append(self.root, rejects.make(**row(reason_code="build_failed", stage="build"))))

    def test_existing_lines_are_never_rewritten(self) -> None:
        rejects.append(self.root, rejects.make(**row()))
        path = self.root / "candidates" / "_rejected" / "freertos.jsonl"
        before = path.read_bytes()
        rejects.append(self.root, rejects.make(**row(ref="pull/9")))
        self.assertTrue(path.read_bytes().startswith(before))

    def test_a_log_without_a_final_newline_is_continued_safely(self) -> None:
        rejects.append(self.root, rejects.make(**row()))
        path = self.root / "candidates" / "_rejected" / "freertos.jsonl"
        path.write_bytes(path.read_bytes().rstrip(b"\n"))
        rejects.append(self.root, rejects.make(**row(ref="pull/9")))
        self.assertEqual(len(rejects.read(self.root, "freertos")), 2)

    def test_an_invalid_row_is_never_written(self) -> None:
        with self.assertRaises(rejects.RejectionError):
            rejects.append(self.root, row(reason_code="nope"))
        self.assertFalse((self.root / "candidates").exists())

    def test_the_source_cannot_escape_the_log_directory(self) -> None:
        with self.assertRaises(rejects.RejectionError):
            rejects.append(self.root, row(source="../x"))

    def test_summary_counts_reasons(self) -> None:
        rows = [row(), row(ref="a"), row(ref="b", reason_code="build_failed")]
        self.assertEqual(rejects.summary(rows), {"build_failed": 1, "noisy_module": 2})


if __name__ == "__main__":
    unittest.main()

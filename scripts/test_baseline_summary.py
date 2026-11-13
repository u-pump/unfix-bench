# SPDX-License-Identifier: MIT
# Copyright (c) 2026 U-Pump
"""The bug-baseline line in the verify log carries numbers only."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import verify_cases


class BaselineSummaryTest(unittest.TestCase):
    def summary(self, data: object) -> str:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "spec.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            return verify_cases.baseline_summary(path)

    def test_counts_and_per_run_numbers_are_listed(self) -> None:
        text = self.summary({"completed_runs": 3, "failures": 2, "required_runs_after_fix": 3,
                             "runs": [{"exit_code": 1, "duration_seconds": 4.5}, {"exit_code": 0, "timed_out": False}]})
        self.assertIn("completed_runs=3 failures=2 required_runs_after_fix=3", text)
        self.assertIn("{exit_code=1,duration_seconds=4.5}", text)
        self.assertIn("{exit_code=0,timed_out=False}", text)

    def test_free_text_commands_and_paths_are_never_printed(self) -> None:
        text = self.summary({"completed_runs": 1, "command": "secret --flag", "project": "/home/runner/x",
                             "runs": [{"exit_code": 1, "stdout": "TEST OUTPUT", "status": "/etc/passwd and more text"}]})
        for hidden in ("secret", "/home", "TEST OUTPUT", "passwd"):
            self.assertNotIn(hidden, text)

    def test_unreadable_file(self) -> None:
        self.assertEqual(verify_cases.baseline_summary(Path("missing.json")), "bug baseline: not readable")


if __name__ == "__main__":
    unittest.main()

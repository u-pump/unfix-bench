# SPDX-License-Identifier: MIT
# Copyright (c) 2026 U-Pump
"""The planner must never offer a second attempt."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import plan_cases


def make(root: Path, case_id: str, patch: bytes, meta: dict[str, object]) -> None:
    base = root / "cases" / case_id / "agents" / "claude-code"
    base.mkdir(parents=True)
    (base / "agent-fix.patch").write_bytes(patch)
    (base / "agent.yaml").write_text(json.dumps(meta), encoding="utf-8")


class PlanCasesTest(unittest.TestCase):
    def test_only_cases_without_a_recorded_attempt_are_planned(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make(root, "open-1", b"", {"patch_sha256": None})
            make(root, "patched-2", b"diff\n", {"patch_sha256": "a" * 64})
            make(root, "empty-3", b"", {"patch_sha256": None, "outcome": "NO_PATCH"})
            self.assertEqual(plan_cases.plan("", root), ["open-1"])
            self.assertEqual(plan_cases.plan("open-1", root), ["open-1"])
            for recorded in ("patched-2", "empty-3", "missing-4"):
                with self.subTest(recorded), self.assertRaises(ValueError):
                    plan_cases.plan(recorded, root)

    def test_case_id_must_be_a_plain_slug(self) -> None:
        with self.assertRaises(ValueError):
            plan_cases.plan("../etc", Path("."))


if __name__ == "__main__":
    unittest.main()

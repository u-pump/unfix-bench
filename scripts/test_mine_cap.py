# SPDX-License-Identifier: MIT
# Copyright (c) 2026 U-Pump
"""The cap counts from 100 and treats every FreeRTOS repository as one family."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from mine import cap


def put(root: Path, group: str, name: str, repo: str) -> None:
    path = root / group / name / "case.yaml"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"repo": repo}), encoding="utf-8")


class FamilyTest(unittest.TestCase):
    def test_all_freertos_repositories_are_one_family(self) -> None:
        for repo in ("https://github.com/FreeRTOS/FreeRTOS-Kernel.git", "https://github.com/FreeRTOS/FreeRTOS-Plus-TCP",
                     "https://github.com/FreeRTOS/coreMQTT.git", "https://github.com/FreeRTOS/coreJSON/",
                     "https://github.com/FreeRTOS/coreHTTP.git"):
            with self.subTest(repo):
                self.assertEqual(cap.family(repo), "freertos")

    def test_other_families_and_plain_projects(self) -> None:
        self.assertEqual(cap.family("https://github.com/zephyrproject-rtos/zephyr.git"), "zephyr")
        self.assertEqual(cap.family("https://github.com/apache/nuttx.git"), "nuttx")
        self.assertEqual(cap.family("https://github.com/apache/nuttx-apps"), "nuttx")
        self.assertEqual(cap.family("https://github.com/Mbed-TLS/mbedtls.git"), "mbedtls")
        self.assertEqual(cap.family("https://github.com/fmtlib/fmt.git"), "fmtlib/fmt")
        self.assertEqual(cap.family("https://github.com/lwip-tcpip/lwip.git"), "lwip-tcpip/lwip")

    def test_a_non_github_url_is_an_error(self) -> None:
        with self.assertRaises(ValueError):
            cap.family("https://example.com/x/y.git")


class CapTest(unittest.TestCase):
    def test_the_limit_is_30_of_100(self) -> None:
        self.assertEqual((cap.TOTAL, cap.LIMIT), (100, 30))

    def test_the_31st_case_of_a_family_is_refused(self) -> None:
        repo = "https://github.com/FreeRTOS/coreMQTT.git"
        self.assertFalse(cap.exceeds(Counter({"freertos": 29}), repo))
        self.assertTrue(cap.exceeds(Counter({"freertos": 30}), repo))

    def test_the_cap_is_counted_from_100_not_from_the_cases_found(self) -> None:
        # One case so far is 100% of the cases found, but only 1% of the 100: it must not trip the cap.
        self.assertFalse(cap.exceeds(Counter({"freertos": 1}), "https://github.com/FreeRTOS/coreMQTT.git"))

    def test_counts_read_published_cases_and_candidates(self) -> None:
        root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root, True)
        put(root, "cases", "fmt-1", "https://github.com/fmtlib/fmt.git")
        put(root, "cases", "fmt-2", "https://github.com/fmtlib/fmt.git")
        put(root, "candidates", "coremqtt-1", "https://github.com/FreeRTOS/coreMQTT.git")
        put(root, "candidates", "plus-tcp-1", "https://github.com/FreeRTOS/FreeRTOS-Plus-TCP.git")
        put(root, "candidates", "_hidden", "https://github.com/FreeRTOS/coreJSON.git")
        found = cap.counts(root)
        self.assertEqual(found, Counter({"fmtlib/fmt": 2, "freertos": 2}))
        self.assertEqual(cap.shares(found), {"fmtlib/fmt": 2.0, "freertos": 2.0})

    def test_the_repository_today_is_within_the_cap(self) -> None:
        found = cap.counts(Path(__file__).resolve().parents[1])
        self.assertEqual(found["fmtlib/fmt"], 7)
        self.assertTrue(all(number <= cap.LIMIT for number in found.values()))


if __name__ == "__main__":
    unittest.main()

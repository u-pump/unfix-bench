# SPDX-License-Identifier: MIT
# Copyright (c) 2026 U-Pump
"""Static filters, on the file lists of real pull requests read for the BENCH-20 plan (no network)."""

from __future__ import annotations

import unittest

from mine import filters

RUN = "https://github.com/u-pump/unfix-bench/actions/runs/1"
BODY = "Fix the bounds check so that the topic filter length is honoured when subscribing."

# File lists as read from GitHub on 2026-11-14.
COREMQTT_383 = [
    "source/core_mqtt.c",
    "test/cbmc/proofs/MQTT_Subscribe_BoundedTopicFilter/MQTT_Subscribe_BoundedTopicFilter_harness.c",
    "test/cbmc/proofs/MQTT_Subscribe_BoundedTopicFilter/Makefile",
    "test/cbmc/proofs/MQTT_Subscribe_BoundedTopicFilter/README.md",
    "test/unit-test/core_mqtt_utest.c",
]
PLUS_TCP_1357 = [
    "source/FreeRTOS_IPv6_Sockets.c",
    "test/cbmc/proofs/FreeRTOS_inet_ntop6/FreeRTOS_inet_ntop6_harness.c",
    "test/cbmc/proofs/FreeRTOS_inet_ntop6/Makefile.json",
    "test/unit-test/FreeRTOS_Sockets_IPv6/FreeRTOS_Sockets_IPv6_utest.c",
]
ZEPHYR_122423 = ["subsys/storage/stream/stream_flash.c", "tests/subsys/storage/stream/stream_flash/src/main.c"]
ZEPHYR_121899 = [
    "subsys/net/lib/coap/coap_server.c", "subsys/net/lib/sockets/sockets_tls.c",
    "tests/net/lib/coap_server/common/prj.conf", "tests/net/lib/coap_server/common/sections-ram.ld",
    "tests/net/lib/coap_server/common/src/main.c", "tests/net/lib/coap_server/common/tests.yaml",
]
MBEDTLS_10985 = ["ChangeLog.d/x509-empty-authority-key-id.txt", "library/x509_crt.c", "tests/suites/test_suite_x509parse.data"]


def item(**changes: object) -> dict[str, object]:
    base: dict[str, object] = {
        "source": "freertos", "project": "FreeRTOS/coreMQTT", "ref": "pull/383",
        "fix_commit": "a" * 40, "title": "Fix subscribe wildcard check bounds", "body": BODY,
        "labels": [], "base_ref": "main", "default_branch": "main", "files": COREMQTT_383,
        "spdx": "MIT", "fix_date": "2026-08-06",
    }
    return base | changes


class ClassifyTest(unittest.TestCase):
    def test_real_file_lists(self) -> None:
        got = filters.split_files(COREMQTT_383)
        self.assertEqual(got["source"], ["source/core_mqtt.c"])
        self.assertEqual(got["test"], ["test/unit-test/core_mqtt_utest.c"])
        self.assertEqual(len(got["other"]), 3)  # the CBMC proof is neither a test nor a source file
        self.assertEqual(filters.split_files(PLUS_TCP_1357)["test"],
                         ["test/unit-test/FreeRTOS_Sockets_IPv6/FreeRTOS_Sockets_IPv6_utest.c"])
        self.assertEqual(filters.split_files(ZEPHYR_122423)["test"], ["tests/subsys/storage/stream/stream_flash/src/main.c"])

    def test_test_config_files_are_not_tests(self) -> None:
        got = filters.split_files(ZEPHYR_121899)
        self.assertEqual(got["test"], ["tests/net/lib/coap_server/common/src/main.c"])
        self.assertEqual(got["source"], ["subsys/net/lib/coap/coap_server.c", "subsys/net/lib/sockets/sockets_tls.c"])

    def test_data_file_tests_count_and_change_logs_do_not(self) -> None:
        got = filters.split_files(MBEDTLS_10985)
        self.assertEqual(got["test"], ["tests/suites/test_suite_x509parse.data"])
        self.assertEqual(got["source"], ["library/x509_crt.c"])

    def test_build_files_and_docs_are_other(self) -> None:
        for path in ("CMakeLists.txt", "tests/CMakeLists.txt", "Kconfig", "docs/a.c", ".github/x.yml", "README.md", "a.cmake"):
            with self.subTest(path):
                self.assertEqual(filters.classify(path), "other")

    def test_look_alike_names_are_not_tests(self) -> None:
        for path in ("src/latest.c", "src/contest.c", "src/attestation.c"):
            with self.subTest(path):
                self.assertEqual(filters.classify(path), "source")
        for path in ("src/foo_test.cc", "src/test_foo.c", "src/foo_utest.c"):
            with self.subTest(path):
                self.assertEqual(filters.classify(path), "test")


class StaticCheckTest(unittest.TestCase):
    def reject(self, **changes: object) -> dict[str, object]:
        row = filters.static_check(item(**changes), RUN)
        assert row is not None
        return row

    def test_real_candidates_pass(self) -> None:
        self.assertIsNone(filters.static_check(item(), RUN))
        self.assertIsNone(filters.static_check(item(project="FreeRTOS/FreeRTOS-Plus-TCP", files=PLUS_TCP_1357), RUN))
        self.assertIsNone(filters.static_check(item(source="zephyr", spdx="Apache-2.0", files=ZEPHYR_122423), RUN))

    def test_no_test_in_the_diff(self) -> None:
        row = self.reject(files=["source/core_mqtt.c", "README.md"])
        self.assertEqual((row["reason_code"], row["stage"]), ("no_test_in_diff", "static"))

    def test_test_only_fix(self) -> None:
        row = self.reject(files=["test/unit-test/core_mqtt_utest.c", "test/unit-test/CMakeLists.txt"])
        self.assertEqual(row["reason_code"], "test_only_fix")

    def test_licence_outside_the_allowlist(self) -> None:
        for spdx in (None, "GPL-3.0-only", "NOASSERTION"):
            with self.subTest(spdx):
                self.assertEqual(self.reject(spdx=spdx)["reason_code"], "license_unclear")

    def test_missing_issue_text(self) -> None:
        for body in (None, "", "  fixes  "):
            with self.subTest(body):
                self.assertEqual(self.reject(body=body)["reason_code"], "no_issue_text")

    def test_backports_are_not_candidates(self) -> None:
        for change in ({"title": "Backport 4.1: x509_crt: accept empty AuthorityKeyIdentifier sequence"},
                       {"title": "[Backport] fix"}, {"labels": ["backport"]},
                       {"base_ref": "mbedtls-4.1", "default_branch": "development"}):
            with self.subTest(change):
                self.assertEqual(self.reject(**change)["reason_code"], "duplicate_backport")

    def test_the_first_failing_filter_wins_and_rows_are_valid(self) -> None:
        row = self.reject(files=[], spdx=None, body="")
        self.assertEqual(row["reason_code"], "no_test_in_diff")
        self.assertEqual(row["miner_run"], RUN)
        self.assertEqual(row["project"], "FreeRTOS/coreMQTT")


class DedupeAndDateTest(unittest.TestCase):
    def test_a_change_and_its_backports_share_one_key(self) -> None:
        keys = {
            filters.dedupe_key("Mbed-TLS/mbedtls", "x509_crt: accept empty AuthorityKeyIdentifier sequence"),
            filters.dedupe_key("Mbed-TLS/mbedtls", "Backport 3.6: x509_crt: accept empty AuthorityKeyIdentifier sequence"),
            filters.dedupe_key("Mbed-TLS/mbedtls", "Backport 4.1: x509_crt: accept empty AuthorityKeyIdentifier sequence"),
        }
        self.assertEqual(len(keys), 1, keys)

    def test_different_changes_and_projects_differ(self) -> None:
        self.assertNotEqual(filters.dedupe_key("a/b", "Fix one"), filters.dedupe_key("a/b", "Fix two"))
        self.assertNotEqual(filters.dedupe_key("a/b", "Fix one"), filters.dedupe_key("a/c", "Fix one"))

    def test_post_cutoff_is_only_a_date(self) -> None:
        self.assertFalse(filters.post_cutoff("2026-06-30"))
        self.assertTrue(filters.post_cutoff("2026-07-01"))
        self.assertTrue(filters.post_cutoff("2026-11-09"))
        self.assertFalse(filters.post_cutoff("2025-12-05"))


if __name__ == "__main__":
    unittest.main()

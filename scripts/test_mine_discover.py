# SPDX-License-Identifier: MIT
# Copyright (c) 2026 U-Pump
"""Discovery on fixtures: a fake GitHub client (no network). The file lists are the ones read for the plan;
the rest of each response is reduced to the fields discover.py reads."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

import candidates
from mine import discover, rejects
from test_mine_filters import COREMQTT_383, PLUS_TCP_1357

RUN = "https://github.com/u-pump/unfix-bench/actions/runs/1"
BODY = "Fix the bounds check so that the topic filter length is honoured when subscribing."
MQTT = "FreeRTOS/coreMQTT"
TCP = "FreeRTOS/FreeRTOS-Plus-TCP"


def pull(title: str, sha: str, merged: str | None = "2026-08-06T10:00:00Z", base: str = "main",
         labels: tuple[str, ...] = (), body: str = BODY) -> dict[str, Any]:
    return {"title": title, "body": body, "merge_commit_sha": sha if merged else None, "merged_at": merged,
            "base": {"ref": base}, "labels": [{"name": name} for name in labels]}


class FakeClient:
    def __init__(self, routes: dict[str, Any]) -> None:
        self.routes = routes
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        self.calls.append((path, dict(params or {})))
        if path.endswith("/files") or path == "/search/issues":
            page = (params or {}).get("page", 1)
            value = self.routes[path]
            size = discover.PER_PAGE
            chunk = value[(page - 1) * size: page * size]
            return {"items": chunk} if path == "/search/issues" else chunk
        return self.routes[path]


def files(names: list[str]) -> list[dict[str, str]]:
    return [{"filename": name} for name in names]


def routes() -> dict[str, Any]:
    return {
        f"/repos/{MQTT}": {"default_branch": "main", "license": {"spdx_id": "MIT"}},
        f"/repos/{TCP}": {"default_branch": "main", "license": {"spdx_id": "MIT"}},
        f"/repos/{MQTT}/pulls/383": pull("Fix subscribe wildcard check bounds", "a" * 40),
        f"/repos/{MQTT}/pulls/383/files": files(COREMQTT_383),
        f"/repos/{TCP}/pulls/1357": pull("Fix IPv6 inet_ntop6 bounds", "b" * 40),
        f"/repos/{TCP}/pulls/1357/files": files(PLUS_TCP_1357),
        # a backport to a release branch of the same change as 383
        f"/repos/{MQTT}/pulls/390": pull("Backport: Fix subscribe wildcard check bounds", "c" * 40, base="v2.x"),
        # the same change landed again on the default branch later, without a backport marker
        f"/repos/{MQTT}/pulls/391": pull("Fix subscribe wildcard check bounds", "d" * 40, merged="2026-08-20T10:00:00Z"),
        f"/repos/{MQTT}/pulls/391/files": files(COREMQTT_383),
        f"/repos/{MQTT}/pulls/392": pull("Refactor docs", "e" * 40),
        f"/repos/{MQTT}/pulls/392/files": files(["README.md"]),
        f"/repos/{MQTT}/pulls/393": pull("Fix not merged", "f" * 40, merged=None),
    }


class SearchTest(unittest.TestCase):
    def test_search_builds_a_scoped_query_and_pages(self) -> None:
        many = [{"number": number} for number in range(1, 251)]
        client = FakeClient({"/search/issues": many})
        numbers = discover.search_merged(client, MQTT, "2026-01-01", 230)
        self.assertEqual(numbers, list(range(1, 231)))
        path, params = client.calls[0]
        self.assertEqual(path, "/search/issues")
        self.assertIn(f"repo:{MQTT} is:pr is:merged merged:>=2026-01-01", params["q"])
        self.assertEqual([call[1]["page"] for call in client.calls], [1, 2, 3])

    def test_a_short_page_ends_the_search(self) -> None:
        client = FakeClient({"/search/issues": [{"number": 7}]})
        self.assertEqual(discover.search_merged(client, MQTT, "2026-01-01", 50), [7])
        self.assertEqual(len(client.calls), 1)

    def test_repo_names_and_references_are_checked(self) -> None:
        for bad in ("../x", "a b/c", "owner", "a/b/c", "x/y;z"):
            with self.subTest(bad):
                with self.assertRaises(ValueError):
                    discover.check_repo(bad)
        self.assertEqual(discover.parse_refs("FreeRTOS/coreMQTT#383, FreeRTOS/coreJSON#179"),
                         [(MQTT, 383), ("FreeRTOS/coreJSON", 179)])
        with self.assertRaises(ValueError):
            discover.parse_refs("coreMQTT#383")


class DiscoverTest(unittest.TestCase):
    def run_discover(self, client: FakeClient, **kwargs: Any) -> dict[str, Any]:
        with tempfile.TemporaryDirectory() as tmp:
            return discover.discover(client, source="freertos", miner_run=RUN, root=Path(tmp), **kwargs)

    def test_real_prs_pass_and_carry_the_fields_the_next_stage_needs(self) -> None:
        result = self.run_discover(FakeClient(routes()), refs=[(MQTT, 383), (TCP, 1357)])
        self.assertEqual([item["ref"] for item in result["accepted"]], ["pull/1357", "pull/383"])  # sorted by date, then project
        first = next(item for item in result["accepted"] if item["ref"] == "pull/383")
        self.assertEqual((first["fix_commit"], first["fix_date"], first["spdx"]), ("a" * 40, "2026-08-06", "MIT"))
        self.assertEqual(first["url"], "https://github.com/FreeRTOS/coreMQTT/pull/383")
        self.assertEqual(first["dedupe_key"], "FreeRTOS/coreMQTT:fix-subscribe-wildcard-check-bounds")
        self.assertEqual(result["rejected"], [])

    def test_every_rejection_has_a_valid_reason(self) -> None:
        result = self.run_discover(FakeClient(routes()), refs=[(MQTT, 383), (MQTT, 390), (MQTT, 391), (MQTT, 392)])
        by_ref = {row["ref"]: row["reason_code"] for row in result["rejected"]}
        self.assertEqual(by_ref, {"pull/390": "duplicate_backport", "pull/391": "duplicate_backport",
                                  "pull/392": "no_test_in_diff"})
        for row in result["rejected"]:
            problems = candidates.Problems()
            candidates.validate_rejection(row, "row", problems)
            self.assertEqual(list(problems), [])
        self.assertEqual([item["ref"] for item in result["accepted"]], ["pull/383"])  # the earliest fix is kept
        self.assertEqual(result["stats"]["rejected"], {"duplicate_backport": 2, "no_test_in_diff": 1})

    def test_a_backport_is_rejected_without_fetching_its_files(self) -> None:
        client = FakeClient(routes())
        self.run_discover(client, refs=[(MQTT, 390)])
        self.assertNotIn(f"/repos/{MQTT}/pulls/390/files", [path for path, _ in client.calls])

    def test_unmerged_pull_requests_are_skipped_not_logged(self) -> None:
        result = self.run_discover(FakeClient(routes()), refs=[(MQTT, 393)])
        self.assertEqual((result["accepted"], result["rejected"]), ([], []))
        self.assertEqual(result["skipped"], [f"{MQTT}#393: not merged"])

    def test_repository_info_is_fetched_once_per_repository(self) -> None:
        client = FakeClient(routes())
        self.run_discover(client, refs=[(MQTT, 383), (MQTT, 392)])
        self.assertEqual(sum(1 for path, _ in client.calls if path == f"/repos/{MQTT}"), 1)

    def test_search_mode_uses_the_source_repositories_and_the_cap_per_repository(self) -> None:
        table = routes()
        table["/search/issues"] = [{"number": 383}]
        result = self.run_discover(FakeClient(table), repos=[MQTT], max_prs=5)
        self.assertEqual(result["stats"]["looked_at"], 1)
        self.assertEqual(len(result["accepted"]), 1)
        with self.assertRaises(ValueError):
            self.run_discover(FakeClient(table), refs=None, repos=[])  # no repositories, no refs

    def test_existing_candidates_are_not_proposed_again(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            meta = Path(tmp) / "candidates" / "x-1"
            meta.mkdir(parents=True)
            (meta / "meta.yaml").write_text(json.dumps({"dedupe_key": "FreeRTOS/coreMQTT:fix-subscribe-wildcard-check-bounds"}))
            result = discover.discover(FakeClient(routes()), source="freertos", miner_run=RUN, root=Path(tmp),
                                       refs=[(MQTT, 383)])
        self.assertEqual(result["accepted"], [])
        self.assertEqual(result["rejected"][0]["reason_code"], "duplicate_backport")

    def test_rejections_fit_the_log_and_repeat_runs_do_not_grow_it(self) -> None:
        result = self.run_discover(FakeClient(routes()), refs=[(MQTT, 392)])
        with tempfile.TemporaryDirectory() as tmp:
            first = [rejects.append(Path(tmp), row) for row in result["rejected"]]
            again = [rejects.append(Path(tmp), row) for row in result["rejected"]]
        self.assertEqual((first, again), ([True], [False]))

    def test_max_candidates_defers_the_rest_without_rejecting_them(self) -> None:
        result = self.run_discover(FakeClient(routes()), refs=[(MQTT, 383), (TCP, 1357)], max_accepted=1)
        self.assertEqual(len(result["accepted"]), 1)
        self.assertEqual((result["stats"]["accepted"], result["stats"]["deferred"], result["rejected"]), (1, 1, []))

    def test_unknown_source_is_an_error(self) -> None:
        with self.assertRaises(ValueError):
            discover.discover(FakeClient({}), source="nope", miner_run=RUN, root=Path("."), refs=[])


class CommandLineTest(unittest.TestCase):
    def test_bad_arguments_stop_before_any_request(self) -> None:
        for argv in (["--source", "freertos", "--run-url", "https://example.com", "--out", "x.json"],
                     ["--source", "freertos", "--run-url", RUN, "--since", "yesterday", "--out", "x.json"],
                     ["--source", "freertos", "--run-url", RUN, "--query", "a;b", "--out", "x.json"]):
            with self.subTest(argv):
                with self.assertRaises(SystemExit):
                    discover.main(argv)

    def test_bad_reference_list_is_an_error_exit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code = discover.main(["--source", "freertos", "--run-url", RUN, "--prs", "nonsense",
                                  "--out", str(Path(tmp) / "x.json")])
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()

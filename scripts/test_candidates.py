# SPDX-License-Identifier: MIT
# Copyright (c) 2026 U-Pump
"""The candidates/ schema: one shape with cases/, no owner-only fields, a closed rejection vocabulary."""

from __future__ import annotations

import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path

import candidates

SHA = "a" * 40
CASE = {
    "id": "coremqtt-383",
    "repo": "https://github.com/FreeRTOS/coreMQTT.git",
    "base": "b" * 40,
    "upstream_fix": SHA,
    "bug_test": "test_MQTTV5_Subscribe_WildcardCheck_HonorsTopicFilterLength",
    "reference_selection": "first upstream diff test with a 3/3 base failure",
    "issue_url": "https://github.com/FreeRTOS/coreMQTT/pull/383",
    "fix_url": f"https://github.com/FreeRTOS/coreMQTT/commit/{SHA}",
    "license": "MIT",
    "category": "out-of-bounds read / memory",
    "build": "cmake -S test/unit-test -B build && cmake --build build",
    "test": "ctest --test-dir build -R core_mqtt_utest --output-on-failure",
    "baseline_reproduction": {"verdict": "REPRODUCED", "runs": "3/3", "elapsed_s": 41.5},
    "bug_test_granularity": "ctest_module",
    "module_other_tests": "3/3 pass",
    "build_network": "none",
    "submodules": [{"path": "test/unit-test/CMock", "commit": "c" * 40}],
}
META = {
    "source": "freertos",
    "spdx": "MIT",
    "fix_date": "2026-08-06",
    "post_cutoff": True,
    "upstream_pr": "https://github.com/FreeRTOS/coreMQTT/pull/383",
    "fuzz_origin": None,
    "dedupe_key": "coreMQTT:subscribe-wildcard-bounds",
    "mined_run_url": "https://github.com/u-pump/unfix-bench/actions/runs/1",
    "miner_version": "0",
}
REJECT = {
    "source": "freertos", "project": "FreeRTOS/coreMQTT", "ref": "pull/382", "fix_commit": SHA,
    "stage": "baseline", "reason_code": "noisy_module", "detail": "2 unrelated tests failed on base",
    "fix_date": "2026-08-13", "miner_run": "https://github.com/u-pump/unfix-bench/actions/runs/1",
}


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


class Fixture(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, True)
        (self.root / "cases").mkdir()

    def candidate(self, case: dict[str, object] | None = None, meta: dict[str, object] | None = None,
                  name: str = "coremqtt-383") -> Path:
        directory = self.root / "candidates" / name
        write_json(directory / "case.yaml", CASE if case is None else case)
        write_json(directory / "meta.yaml", META if meta is None else meta)
        (directory / "ISSUE.md").write_text("Subscribe reads past the topic filter.\n", encoding="utf-8")
        (directory / "baseline.log").write_text("base: FAIL x3\nfix: PASS x3\n", encoding="utf-8")
        return directory

    def problems(self) -> list[str]:
        return list(candidates.check_candidates(self.root))


class ValidCandidateTest(Fixture):
    def test_a_complete_candidate_has_no_problems(self) -> None:
        self.candidate()
        self.assertEqual(self.problems(), [])

    def test_no_candidates_directory_is_fine(self) -> None:
        self.assertEqual(self.problems(), [])

    def test_function_granularity_needs_no_module_check(self) -> None:
        case = {k: v for k, v in CASE.items() if k != "module_other_tests"} | {"bug_test_granularity": "function"}
        self.candidate(case)
        self.assertEqual(self.problems(), [])

    def test_submodules_are_optional(self) -> None:
        self.candidate({k: v for k, v in CASE.items() if k != "submodules"})
        self.assertEqual(self.problems(), [])


class CaseRulesTest(Fixture):
    def broken(self, **changes: object) -> list[str]:
        self.candidate(copy.deepcopy(CASE) | changes)
        return self.problems()

    def test_owner_only_fields_are_refused(self) -> None:
        for field in ("agent_input_repo", "input_sha256"):
            with self.subTest(field):
                found = self.broken(**{field: "x"})
                self.assertTrue(any(field in p and "owner" in p for p in found), found)

    def test_granularity_must_be_one_of_two_values(self) -> None:
        self.assertTrue(any("bug_test_granularity" in p for p in self.broken(bug_test_granularity="class")))

    def test_ctest_module_requires_the_clean_module_record(self) -> None:
        found = self.broken(module_other_tests="2 failed")
        self.assertTrue(any("noisy_module" in p for p in found), found)

    def test_the_build_must_have_run_without_network(self) -> None:
        self.assertTrue(any("build_network" in p for p in self.broken(build_network="on")))

    def test_submodules_are_pinned_to_commits(self) -> None:
        for bad in ([{"path": "x", "commit": "main"}], [{"path": "../x", "commit": SHA}],
                    [{"path": "/x", "commit": SHA}], "none",
                    [{"path": "x", "commit": SHA}, {"path": "x", "commit": "d" * 40}]):
            with self.subTest(bad):
                self.assertTrue(any("submodule" in p for p in self.broken(submodules=bad)))

    def test_commits_licence_and_baseline_are_checked(self) -> None:
        self.assertTrue(any("base" in p for p in self.broken(base="abc")))
        self.assertTrue(any("license" in p for p in self.broken(license="GPL-3.0-only")))
        self.assertTrue(any("baseline_reproduction" in p for p in self.broken(
            baseline_reproduction={"verdict": "REPRODUCED", "runs": "2/3", "elapsed_s": 1})))
        self.assertTrue(any("fix_url" in p for p in self.broken(fix_url="https://example.com/x")))

    def test_unknown_fields_and_wrong_id_are_refused(self) -> None:
        self.assertTrue(any("unknown field" in p for p in self.broken(surprise=1)))
        self.assertTrue(any("directory name" in p for p in self.broken(id="other")))

    def test_an_id_that_is_already_a_case_is_refused(self) -> None:
        (self.root / "cases" / "coremqtt-383").mkdir()
        self.candidate()
        self.assertTrue(any("already exists in cases/" in p for p in self.problems()))


class MetaRulesTest(Fixture):
    def broken(self, **changes: object) -> list[str]:
        self.candidate(meta=copy.deepcopy(META) | changes)
        return self.problems()

    def test_post_cutoff_must_follow_the_fix_date(self) -> None:
        self.assertTrue(any("post_cutoff" in p for p in self.broken(post_cutoff=False)))
        self.assertTrue(any("post_cutoff" in p for p in self.broken(fix_date="2026-06-30", post_cutoff=True)))
        self.assertEqual(self.broken(fix_date="2026-06-30", post_cutoff=False), [])
        self.assertEqual(self.broken(fix_date="2026-07-01", post_cutoff=True), [])

    def test_spdx_must_match_the_case_licence(self) -> None:
        self.assertTrue(any("spdx" in p for p in self.broken(spdx="Apache-2.0")))

    def test_fix_date_source_and_urls_are_checked(self) -> None:
        self.assertTrue(any("fix_date" in p for p in self.broken(fix_date="06/08/2026")))
        self.assertTrue(any("fix_date" in p for p in self.broken(fix_date="2026-13-40")))
        self.assertTrue(any("source" in p for p in self.broken(source="github")))
        self.assertTrue(any("mined_run_url" in p for p in self.broken(mined_run_url="http://x")))
        self.assertTrue(any("fuzz_origin" in p for p in self.broken(fuzz_origin="a fuzzer maybe")))
        self.assertEqual(self.broken(fuzz_origin="https://github.com/google/oss-fuzz/issues/1"), [])

    def test_a_missing_field_is_named(self) -> None:
        meta = {k: v for k, v in META.items() if k != "dedupe_key"}
        self.candidate(meta=meta)
        self.assertTrue(any("dedupe_key is missing" in p for p in self.problems()))

    def test_two_candidates_with_one_dedupe_key_are_refused(self) -> None:
        self.candidate()
        self.candidate(case=CASE | {"id": "coremqtt-383-backport"}, name="coremqtt-383-backport")
        self.assertTrue(any("dedupe_key duplicates" in p for p in self.problems()))


class FilesTest(Fixture):
    def test_issue_and_baseline_log_are_required(self) -> None:
        directory = self.candidate()
        (directory / "ISSUE.md").unlink()
        (directory / "baseline.log").write_text("  \n", encoding="utf-8")
        found = self.problems()
        self.assertTrue(any("ISSUE.md" in p for p in found))
        self.assertTrue(any("baseline.log" in p for p in found))

    def test_invalid_json_is_reported_not_raised(self) -> None:
        directory = self.candidate()
        (directory / "case.yaml").write_text("{", encoding="utf-8")
        self.assertTrue(any("not valid JSON" in p for p in self.problems()))


class RejectionLogTest(Fixture):
    def log(self, *rows: object, raw: str = "") -> list[str]:
        path = self.root / "candidates" / "_rejected" / "freertos.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(json.dumps(r) + "\n" for r in rows) + raw, encoding="utf-8")
        return self.problems()

    def test_a_valid_log_has_no_problems(self) -> None:
        self.assertEqual(self.log(REJECT, REJECT | {"fix_commit": None, "fix_date": None}), [])

    def test_the_reason_code_is_a_closed_vocabulary(self) -> None:
        self.assertTrue(any("reason_code" in p for p in self.log(REJECT | {"reason_code": "other"})))
        self.assertTrue(any("stage" in p for p in self.log(REJECT | {"stage": "later"})))

    def test_every_planned_code_exists(self) -> None:
        for code in ("noisy_module", "needs_network_dependency", "unsupported_by_verifier", "project_cap",
                     "duplicate_backport", "test_not_selectable"):
            self.assertIn(code, candidates.REJECT_CODES)

    def test_fields_are_exact_and_lines_parse(self) -> None:
        extra = dict(REJECT, note="x")
        self.assertTrue(any("exactly" in p for p in self.log(extra)))
        self.assertTrue(any("not valid JSON" in p for p in self.log(raw="{bad\n")))

    def test_an_unexplained_rejection_is_refused(self) -> None:
        self.assertTrue(any("detail" in p for p in self.log(REJECT | {"detail": " "})))


class PublishedCasesTest(unittest.TestCase):
    def test_every_published_case_has_the_shared_shape(self) -> None:
        self.assertEqual(list(candidates.check_published_cases()), [])

    def test_the_repository_itself_passes_the_check(self) -> None:
        self.assertEqual(candidates.main(["check"]), 0)

    def test_a_broken_published_case_is_found(self) -> None:
        root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root, True)
        source = Path(__file__).resolve().parents[1] / "cases" / "fmt-4800" / "case.yaml"
        data = json.loads(source.read_text(encoding="utf-8"))
        data["base"] = "short"
        write_json(root / "cases" / "fmt-4800" / "case.yaml", data)
        self.assertTrue(any("base" in p for p in candidates.check_published_cases(root)))


class CiAndDocsTest(unittest.TestCase):
    ROOT = Path(__file__).resolve().parents[1]

    def test_ci_runs_the_check_and_watches_candidates(self) -> None:
        workflow = (self.ROOT / ".github" / "workflows" / "verify.yml").read_text(encoding="utf-8")
        trigger = workflow[workflow.index("pull_request:"): workflow.index("push:")]
        self.assertIn("'candidates/**'", trigger)
        self.assertIn("python scripts/candidates.py check", workflow)

    def test_the_protocol_and_decisions_state_the_granularity_rule(self) -> None:
        for name in ("protocol.md", "DECISIONS.md"):
            text = (self.ROOT / "docs" / name).read_text(encoding="utf-8")
            self.assertIn("bug_test_granularity", text, name)
            self.assertIn("noisy_module", text, name)
            self.assertIn("build_network" if name == "protocol.md" else "needs_network_dependency", text, name)

    def test_every_documented_reason_code_is_in_the_vocabulary(self) -> None:
        text = (self.ROOT / "docs" / "plans" / "bench-20-miner.md").read_text(encoding="utf-8")
        line = next(row for row in text.splitlines() if row.startswith("Запись журнала"))
        for code in __import__("re").findall(r"`([a-z_0-9]+)`", line.split("Коды:", 1)[1]):
            self.assertIn(code, candidates.REJECT_CODES)


if __name__ == "__main__":
    unittest.main()

# SPDX-License-Identifier: MIT
# Copyright (c) 2026 U-Pump
"""Artifact policy, drafting and recording, on temporary trees (no network, no Docker)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

import candidates
from mine import artifacts, baseline, record, rejects

RUN = "https://github.com/u-pump/unfix-bench/actions/runs/777"
FIX = "a" * 40
BASE = "b" * 40
HERE = Path(__file__).resolve().parent


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def item(number: int = 383, project: str = "FreeRTOS/coreMQTT", key: str | None = None, **changes: Any) -> dict[str, Any]:
    base = {"source": "freertos", "project": project, "ref": f"pull/{number}", "fix_commit": FIX, "title": "Fix bounds",
            "body": "Fix the bounds check so that the topic filter length is honoured when subscribing.",
            "spdx": "MIT", "fix_date": "2026-08-06", "url": f"https://github.com/{project}/pull/{number}",
            "dedupe_key": key or f"{project}:fix-bounds-{number}", "files": []}
    return base | changes


def accepted_result(it: dict[str, Any]) -> dict[str, Any]:
    return {"ref": it["ref"], "project": it["project"], "base": BASE, "fix": it["fix_commit"], "submodules": [],
            "changed_functions": ["test_new"], "build": "cmake -S . -B build && cmake --build build -j2",
            "elapsed_s": 91.5, "verdict": {"accepted": True, "module": "core_mqtt_utest", "bug_test": "test_new",
                                           "reference_functions": ["test_new"], "bug_test_granularity": "ctest_module",
                                           "module_other_tests": "3/3 pass"}}


def rejected_result(it: dict[str, Any], code: str = "noisy_module", stage: str = "baseline") -> dict[str, Any]:
    return {"ref": it["ref"], "project": it["project"], "elapsed_s": 5,
            "verdict": {"accepted": False, "stage": stage, "reason_code": code, "detail": "x failed"}}


class Env:
    def __init__(self, tmp: str, items: list[dict[str, Any]], results: dict[int, dict[str, Any] | None],
                 rejected: list[dict[str, Any]] | None = None) -> None:
        self.root = Path(tmp) / "repo"
        (self.root / "candidates").mkdir(parents=True)
        self.discovered = Path(tmp) / "discovered.json"
        write(self.discovered, json.dumps({"source": "freertos", "accepted": items, "rejected": rejected or [],
                                           "skipped": [], "stats": {"looked_at": len(items)}}))
        self.collected = Path(tmp) / "collected"
        self.collected.mkdir()
        for index, result in results.items():
            if result is not None:
                write(self.collected / f"baseline-{index}" / "result.json", json.dumps(result))
                write(self.collected / f"baseline-{index}" / "baseline.log", "=== base run 1\n=== verdict\n")

    def apply(self) -> dict[str, Any]:
        return record.apply(self.root, self.discovered, self.collected, RUN)


class ArtifactPolicyTest(unittest.TestCase):
    def tree(self, tmp: str) -> Path:
        root = Path(tmp)
        write(root / "baseline-0" / "result.json", "{}")
        write(root / "baseline-0" / "baseline.log", "ok")
        return root

    def test_a_clean_tree_passes_and_an_empty_one_too(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(artifacts.check(self.tree(tmp)), [])
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(artifacts.check(Path(tmp)), [])

    def test_unexpected_names_are_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.tree(tmp)
            write(root / "baseline-0" / "build.tar", "x")
            write(root / "baseline-0" / "sub" / "result.json", "x")
            write(root / "stray.txt", "x")
            write(root / "other-1" / "result.json", "x")
            problems = " | ".join(artifacts.check(root))
        for fragment in ("build.tar", "sub", "stray.txt", "other-1"):
            self.assertIn(fragment, problems)

    def test_secrets_and_big_files_are_refused(self) -> None:
        for secret in ("sk-ant-" + "a" * 30, "ghp_" + "A" * 36, "github_pat_" + "B" * 40, "-----BEGIN RSA PRIVATE KEY-----"):
            with self.subTest(secret[:8]):
                with tempfile.TemporaryDirectory() as tmp:
                    root = self.tree(tmp)
                    write(root / "baseline-0" / "baseline.log", f"x {secret} y")
                    self.assertTrue(any("secret" in p for p in artifacts.check(root)))
        with tempfile.TemporaryDirectory() as tmp:
            root = self.tree(tmp)
            write(root / "baseline-0" / "baseline.log", "x" * (artifacts.MAX_FILE_BYTES + 1))
            self.assertTrue(any("over" in p for p in artifacts.check(root)))

    def test_symbolic_links_are_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.tree(tmp)
            try:
                (root / "baseline-0" / "baseline.log").unlink()
                (root / "baseline-0" / "baseline.log").symlink_to(root / "baseline-0" / "result.json")
            except (OSError, NotImplementedError):
                self.skipTest("symbolic links are not available here")
            self.assertTrue(any("symbolic" in p for p in artifacts.check(root)))

    def test_command_line_exit_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.tree(tmp)
            self.assertEqual(artifacts.main([str(root)]), 0)
            write(root / "baseline-0" / "x.bin", "x")
            self.assertEqual(artifacts.main([str(root)]), 1)
        self.assertEqual(artifacts.main(["no-such-directory"]), 1)

    def test_what_baseline_py_writes_is_what_the_policy_allows(self) -> None:
        self.assertEqual(artifacts.ALLOWED_FILES, {"result.json", "baseline.log"})
        source = (HERE / "mine" / "baseline.py").read_text(encoding="utf-8")
        for name in artifacts.ALLOWED_FILES:
            self.assertIn(f'"{name}"', source)


class RecordTest(unittest.TestCase):
    def test_accepted_baseline_becomes_a_valid_draft(self) -> None:
        it = item()
        with tempfile.TemporaryDirectory() as tmp:
            env = Env(tmp, [it], {0: accepted_result(it)})
            summary = env.apply()
            self.assertEqual(summary["written"], ["coremqtt-383"])
            self.assertEqual(list(candidates.check_candidates(env.root)), [])
            case = json.loads((env.root / "candidates" / "coremqtt-383" / "case.yaml").read_text(encoding="utf-8"))
            meta = json.loads((env.root / "candidates" / "coremqtt-383" / "meta.yaml").read_text(encoding="utf-8"))
            self.assertEqual((case["bug_test"], case["bug_test_granularity"], case["build_network"]),
                             ("test_new", "ctest_module", "none"))
            self.assertEqual(case["test"], "ctest --test-dir build -R '^core_mqtt_utest$' --output-on-failure")
            self.assertEqual((meta["post_cutoff"], meta["fuzz_origin"], meta["mined_run_url"]), (True, None, RUN))
            self.assertNotIn("agent_input_repo", case)
            issue = (env.root / "candidates" / "coremqtt-383" / "ISSUE.md").read_text(encoding="utf-8")
            self.assertIn("nothing was removed automatically", issue)
            self.assertTrue((env.root / "candidates" / "_runs" / "777" / "summary.json").is_file())

    def test_rejected_baseline_goes_to_the_log_with_its_code(self) -> None:
        it = item()
        with tempfile.TemporaryDirectory() as tmp:
            env = Env(tmp, [it], {0: rejected_result(it)})
            summary = env.apply()
            self.assertEqual((summary["written"], summary["rejected_logged"]), ([], 1))
            rows = rejects.read(env.root, "freertos")
            self.assertEqual((rows[0]["reason_code"], rows[0]["stage"], rows[0]["miner_run"]), ("noisy_module", "baseline", RUN))
            self.assertFalse((env.root / "candidates" / "coremqtt-383").exists())

    def test_a_forged_reason_code_cannot_enter_the_log(self) -> None:
        it = item()
        with tempfile.TemporaryDirectory() as tmp:
            env = Env(tmp, [it], {0: rejected_result(it, code="'; rm -rf /")})
            summary = env.apply()
            self.assertEqual(summary["rejected_logged"], 0)
            self.assertEqual(len(summary["errors"]), 1)
            self.assertEqual(rejects.read(env.root, "freertos"), [])

    def test_a_result_of_another_candidate_or_odd_fields_is_refused(self) -> None:
        it = item()
        wrong = accepted_result(item(number=999))
        odd = accepted_result(it)
        odd["verdict"]["bug_test"] = "../../etc"
        other_fix = accepted_result(it)
        other_fix["fix"] = "c" * 40
        for bad in (wrong, odd, other_fix):
            with self.subTest(bad["verdict"]["bug_test"], ref=bad["ref"]):
                with tempfile.TemporaryDirectory() as tmp:
                    env = Env(tmp, [it], {0: bad})
                    summary = env.apply()
                    self.assertEqual((summary["written"], len(summary["errors"])), ([], 1))
                    self.assertFalse((env.root / "candidates" / "coremqtt-383").exists())

    def test_missing_result_is_reported_not_logged(self) -> None:
        it = item()
        with tempfile.TemporaryDirectory() as tmp:
            env = Env(tmp, [it], {0: None})
            summary = env.apply()
            self.assertEqual(summary["missing_results"], ["FreeRTOS/coreMQTT pull/383"])
            self.assertEqual(rejects.read(env.root, "freertos"), [])

    def test_discovery_rejections_are_logged_once_over_repeated_runs(self) -> None:
        row = rejects.make(source="freertos", project="FreeRTOS/coreMQTT", ref="pull/392", fix_commit=None, stage="static",
                           reason_code="no_test_in_diff", detail="no test", fix_date="2026-08-06", miner_run=RUN)
        with tempfile.TemporaryDirectory() as tmp:
            env = Env(tmp, [], {}, rejected=[row])
            self.assertEqual(env.apply()["rejected_logged"], 1)
            self.assertEqual(env.apply()["rejected_logged"], 0)

    def test_the_family_cap_stops_drafting(self) -> None:
        it = item(number=500)
        with tempfile.TemporaryDirectory() as tmp:
            env = Env(tmp, [it], {0: accepted_result(it)})
            for number in range(30):  # 30 accepted candidates of the FreeRTOS family already exist
                write(env.root / "candidates" / f"x-{number}" / "case.yaml", json.dumps({"repo": "https://github.com/FreeRTOS/coreHTTP.git"}))
            summary = env.apply()
            self.assertEqual(summary["written"], [])
            self.assertEqual(rejects.read(env.root, "freertos")[0]["reason_code"], "project_cap")
            self.assertEqual(rejects.read(env.root, "freertos")[0]["stage"], "cap")

    def test_an_existing_candidate_is_not_overwritten(self) -> None:
        it = item()
        with tempfile.TemporaryDirectory() as tmp:
            env = Env(tmp, [it], {0: accepted_result(it)})
            self.assertEqual(env.apply()["written"], ["coremqtt-383"])
            again = env.apply()
            self.assertEqual(again["written"], [])
            self.assertEqual(len(again["errors"]), 1)

    def test_ids_and_matrix(self) -> None:
        self.assertEqual(record.case_id("FreeRTOS/FreeRTOS-Plus-TCP", 1357), "freertos-plus-tcp-1357")
        self.assertEqual(record.case_id("FreeRTOS/coreJSON", 179), "corejson-179")
        with self.assertRaises(record.RecordError):
            record.pr_number("issues/4")
        with tempfile.TemporaryDirectory() as tmp:
            env = Env(tmp, [item(1), item(2), item(3)], {})
            self.assertEqual(record.matrix(env.discovered), "[0, 1, 2]")
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(record.matrix(Env(tmp, [], {}).discovered), "[]")


class RealCtestOutputTest(unittest.TestCase):
    def test_junit_written_by_ctest_in_the_miner_image(self) -> None:
        """scripts/fixtures/ctest-junit-real.xml was produced by `ctest --output-junit` in docker/miner-build
        (CMake 3.28.3) for a one-test project whose executable prints Unity-style result lines."""
        text = (HERE / "fixtures" / "ctest-junit-real.xml").read_text(encoding="utf-8")
        modules, functions = baseline.parse_junit(text)
        self.assertEqual(modules, {"mod": False})
        self.assertEqual(functions, {"mod": {"test_old": True, "test_new": False}})


if __name__ == "__main__":
    unittest.main()

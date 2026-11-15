# SPDX-License-Identifier: MIT
# Copyright (c) 2026 U-Pump
"""Baseline verdicts, parsing and the pipeline with a fake runner and a temporary git repository (no Docker, no network).

The JUnit and Unity samples are written by hand from the documented formats, not recorded from a real build."""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import Any

import candidates
from mine import baseline

RUN = "https://github.com/u-pump/unfix-bench/actions/runs/1"


def junit(cases: dict[str, tuple[bool, str]]) -> str:
    rows = []
    for name, (ok, out) in cases.items():
        failure = "" if ok else '<failure message="Failed"/>'
        rows.append(f'<testcase name="{name}" status="{"run" if ok else "fail"}">{failure}<system-out>{out}</system-out></testcase>')
    return f'<?xml version="1.0"?><testsuite name="ctest">{"".join(rows)}</testsuite>'


def unity(**results: bool) -> str:
    return "\n".join(f"test/unit-test/x_utest.c:{10 + i}:{name}:{'PASS' if ok else 'FAIL'}" for i, (name, ok) in enumerate(results.items()))


def run(module_ok: bool, **functions: bool) -> dict[str, Any]:
    return {"modules": {"mod": module_ok, "other": True}, "functions": {"mod": dict(functions)}}


class ParsingTest(unittest.TestCase):
    def test_junit_with_unity_output(self) -> None:
        text = junit({"mod": (False, unity(test_old=True, test_new=False)), "other": (True, "")})
        modules, functions = baseline.parse_junit(text)
        self.assertEqual(modules, {"mod": False, "other": True})
        self.assertEqual(functions, {"mod": {"test_old": True, "test_new": False}})

    def test_ignored_tests_are_not_results_and_entities_are_refused(self) -> None:
        _, functions = baseline.parse_junit(junit({"m": (True, "a.c:1:test_a:IGNORE\na.c:2:test_b:PASS")}))
        self.assertEqual(functions, {"m": {"test_b": True}})
        with self.assertRaises(ValueError):
            baseline.parse_junit('<!DOCTYPE x [<!ENTITY a "b">]><testsuite/>')

    def test_changed_functions_follow_the_hunks(self) -> None:
        new = "\n".join([
            "static int x;",                            # 1
            "void test_a( void )",                      # 2
            "{",                                        # 3
            "    TEST_ASSERT_EQUAL( 1, 1 );",           # 4
            "}",                                        # 5
            "",                                         # 6
            "void test_b(void)",                        # 7
            "{",                                        # 8
            "    TEST_ASSERT_EQUAL( 2, 2 );",           # 9
            "}",                                        # 10
            "void test_c( void ) {",                    # 11
            "}",                                        # 12
        ])
        diff = "@@ -8,0 +9,1 @@\n+x\n@@ -20,0 +11,2 @@\n+y\n"
        self.assertEqual(baseline.changed_test_functions(diff, new), ["test_b", "test_c"])
        self.assertEqual(baseline.changed_test_functions("@@ -1 +1 @@\n", new), [])  # a line outside every function
        self.assertEqual(baseline.changed_test_functions("@@ -3,2 +4,0 @@\n", new), ["test_a"])  # pure deletion


class EvaluateTest(unittest.TestCase):
    def verdict(self, base: list[dict[str, Any]], fix: list[dict[str, Any]], changed: list[str]) -> dict[str, Any]:
        return baseline.evaluate(base, fix, changed)

    def test_accepts_a_module_where_only_the_changed_function_fails(self) -> None:
        base = [run(False, test_old=True, test_new=False)] * 3
        fix = [run(True, test_old=True, test_new=True)] * 3
        got = self.verdict(base, fix, ["test_new"])
        self.assertEqual((got["accepted"], got["module"], got["bug_test"]), (True, "mod", "test_new"))
        self.assertEqual((got["bug_test_granularity"], got["module_other_tests"]), ("ctest_module", "3/3 pass"))

    def test_noisy_module_when_an_unchanged_function_fails(self) -> None:
        base = [run(False, test_old=False, test_new=False)] * 3
        got = self.verdict(base, [run(True, test_old=True, test_new=True)] * 3, ["test_new"])
        self.assertEqual((got["reason_code"], got["stage"]), ("noisy_module", "baseline"))
        self.assertIn("test_old", got["detail"])

    def test_a_sometimes_failing_unchanged_function_is_noise_too(self) -> None:
        base = [run(False, test_old=False, test_new=False), run(False, test_old=True, test_new=False), run(False, test_old=True, test_new=False)]
        got = self.verdict(base, [run(True, test_old=True, test_new=True)] * 3, ["test_new"])
        self.assertEqual(got["reason_code"], "noisy_module")

    def test_base_must_fail_three_times(self) -> None:
        base = [run(False, test_new=False), run(True, test_new=True), run(False, test_new=False)]
        got = self.verdict(base, [run(True, test_new=True)] * 3, ["test_new"])
        self.assertEqual(got["reason_code"], "base_not_failing_3of3")
        self.assertIn("mod", got["detail"])
        self.assertEqual(self.verdict([run(True, test_new=True)] * 3, [run(True, test_new=True)] * 3, ["test_new"])["reason_code"],
                         "base_not_failing_3of3")

    def test_fix_must_pass_three_times(self) -> None:
        base = [run(False, test_new=False)] * 3
        fix = [run(True, test_new=True), run(False, test_new=False), run(True, test_new=True)]
        got = self.verdict(base, fix, ["test_new"])
        self.assertEqual((got["reason_code"], got["stage"]), ("fix_not_passing_3of3", "fix_run"))

    def test_not_selectable_without_unity_results_or_without_a_failing_changed_function(self) -> None:
        bare = [{"modules": {"mod": False}, "functions": {}}] * 3
        self.assertEqual(self.verdict(bare, [run(True)] * 3, ["test_new"])["reason_code"], "test_not_selectable")
        base = [run(False, test_new=True, test_x=False)] * 3  # fails, but not in a changed function
        self.assertEqual(self.verdict(base, [run(True, test_x=True)] * 3, ["test_new"])["reason_code"], "noisy_module")
        base = [run(False, test_new=True)] * 3
        self.assertEqual(self.verdict(base, [run(True, test_new=True)] * 3, ["test_new"])["reason_code"], "test_not_selectable")

    def test_incomplete_runs_are_rejected(self) -> None:
        self.assertFalse(self.verdict([run(False, a=False)], [run(True, a=True)], ["a"])["accepted"])

    def test_the_second_module_is_tried_when_the_first_is_noisy(self) -> None:
        def two(ok: bool) -> dict[str, Any]:
            return {"modules": {"a": ok, "b": ok},
                    "functions": {"a": {"test_x": ok, "test_y": ok and True}, "b": {"test_x": ok}}}
        base = [{"modules": {"a": False, "b": False},
                 "functions": {"a": {"test_x": False, "test_noise": False}, "b": {"test_x": False}}}] * 3
        fix = [two(True)] * 3
        got = self.verdict(base, fix, ["test_x"])
        self.assertEqual((got["accepted"], got["module"]), (True, "b"))


class BuildRejectionTest(unittest.TestCase):
    def test_network_hints_and_timeouts(self) -> None:
        net = baseline.build_rejection(baseline.Result(1, "fatal: unable to access 'https://github.com/x/y.git/': Could not resolve host: github.com"), "base")
        self.assertEqual((net["reason_code"], net["stage"]), ("needs_network_dependency", "build"))
        plain = baseline.build_rejection(baseline.Result(2, "error: 'foo' undeclared"), "fix")
        self.assertEqual(plain["reason_code"], "build_failed")
        self.assertEqual(baseline.build_rejection(baseline.Result(124, "", True), "base")["reason_code"], "over_30_min")

    def test_commands_quote_options(self) -> None:
        build, test = baseline.commands("test/unit-test", ("-DX=a b",))
        self.assertIn("-S test/unit-test -B build '-DX=a b'", build)
        self.assertIn("ctest --test-dir build", test)


# ---- pipeline on a temporary repository -------------------------------------------------

def sh(directory: Path, *args: str) -> str:
    done = subprocess.run(["git", "-C", str(directory), "-c", "user.name=t", "-c", "user.email=t@example.com",
                           "-c", "commit.gpgsign=false", *args], capture_output=True, text=True, check=True)
    return done.stdout.strip()


TEST_V1 = "void test_old( void )\n{\n}\n"
TEST_V2 = TEST_V1 + "\nvoid test_new( void )\n{\n    TEST_ASSERT_EQUAL( 1, 2 );\n}\n"


def make_repo(root: Path) -> tuple[Path, str]:
    repo = root / "origin"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    (repo / "src").mkdir()
    (repo / "test" / "unit-test").mkdir(parents=True)
    (repo / "src" / "lib.c").write_text("int f(void) { return 0; }\n")
    (repo / "test" / "unit-test" / "lib_utest.c").write_text(TEST_V1)
    (repo / "test" / "unit-test" / "CMakeLists.txt").write_text("# v1\n")
    sh(repo, "add", "-A")
    sh(repo, "commit", "-q", "-m", "base")
    (repo / "src" / "lib.c").write_text("int f(void) { return 1; }\n")
    (repo / "test" / "unit-test" / "lib_utest.c").write_text(TEST_V2)
    (repo / "test" / "unit-test" / "CMakeLists.txt").write_text("# v2 registers test_new\n")
    sh(repo, "add", "-A")
    sh(repo, "commit", "-q", "-m", "fix")
    return repo, sh(repo, "rev-parse", "HEAD")


class FakeRunner:
    """Pretends to build and test: the base (the directory whose lib.c returns 0) fails test_new, the fix passes."""

    def __init__(self, noisy: bool = False, build_ok: bool = True) -> None:
        self.noisy, self.build_ok, self.calls = noisy, build_ok, []

    def run(self, workdir: Path, command: str, timeout: int) -> baseline.Result:
        self.calls.append((workdir.name, command))
        if command.startswith("cmake"):
            return baseline.Result(0 if self.build_ok else 2, "" if self.build_ok else "error: boom")
        base_side = "return 0" in (workdir / "src" / "lib.c").read_text()
        cases = {"mod": (not base_side, unity(test_old=not (base_side and self.noisy), test_new=not base_side))}
        (workdir / "build").mkdir(exist_ok=True)
        (workdir / "build" / "junit.xml").write_text(junit(cases), encoding="utf-8")
        return baseline.Result(1 if base_side else 0, "")


class PipelineTest(unittest.TestCase):
    def go(self, runner: FakeRunner, files: list[str] | None = None) -> dict[str, Any]:
        with tempfile.TemporaryDirectory() as tmp:
            repo, fix = make_repo(Path(tmp))
            item = {"source": "freertos", "project": "FreeRTOS/coreMQTT", "ref": "pull/1", "fix_commit": fix,
                    "fix_date": "2026-08-06",
                    "files": files or ["src/lib.c", "test/unit-test/lib_utest.c", "test/unit-test/CMakeLists.txt"]}
            return baseline.run_baseline(item, Path(tmp) / "work", runner, miner_run=RUN, clone_url=str(repo))

    def test_accepted_candidate_with_the_fix_tests_laid_over_the_base(self) -> None:
        runner = FakeRunner()
        result = self.go(runner)
        self.assertTrue(result["verdict"]["accepted"], result["verdict"])
        self.assertEqual(result["verdict"]["bug_test"], "test_new")
        self.assertEqual(result["changed_functions"], ["test_new"])
        self.assertEqual((result["build_network"], result["submodules"], result["rejection"]), ("none", [], None))
        self.assertEqual([c[0] for c in runner.calls if c[1].startswith("cmake")], ["base", "fix"])
        self.assertEqual(len([c for c in runner.calls if c[1].startswith("rm")]), 6)  # 3 runs per side
        self.assertIn("base run 3", result["log"])
        self.assertIn("test_new", result["log"])

    def test_noisy_module_becomes_a_valid_rejection_row(self) -> None:
        result = self.go(FakeRunner(noisy=True))
        self.assertFalse(result["verdict"]["accepted"])
        row = result["rejection"]
        self.assertEqual((row["reason_code"], row["stage"], row["miner_run"]), ("noisy_module", "baseline", RUN))
        problems = candidates.Problems()
        candidates.validate_rejection(row, "row", problems)
        self.assertEqual(list(problems), [])

    def test_build_failure_stops_before_the_fix_and_is_logged(self) -> None:
        runner = FakeRunner(build_ok=False)
        result = self.go(runner)
        self.assertEqual(result["rejection"]["reason_code"], "build_failed")
        self.assertEqual(len(runner.calls), 1)

    def test_zero_time_budget_is_over_30_min(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, fix = make_repo(Path(tmp))
            item = {"source": "freertos", "project": "FreeRTOS/coreMQTT", "ref": "pull/1", "fix_commit": fix,
                    "fix_date": "2026-08-06", "files": ["src/lib.c", "test/unit-test/lib_utest.c"]}
            result = baseline.run_baseline(item, Path(tmp) / "w", FakeRunner(), miner_run=RUN, clone_url=str(repo), time_limit=0)
        self.assertEqual(result["rejection"]["reason_code"], "over_30_min")

    def test_symlinked_junit_is_refused_and_never_read(self) -> None:
        secret = "TOP-SECRET-OUTSIDE-THE-SIDE-DIRECTORY"

        class Linking(FakeRunner):
            def run(self, workdir: Path, command: str, timeout: int) -> baseline.Result:
                if command.startswith("cmake"):
                    return baseline.Result(0, "")
                (workdir / "build").mkdir(exist_ok=True)
                try:
                    (workdir / "build" / "junit.xml").symlink_to(outside)
                except (OSError, NotImplementedError):
                    raise unittest.SkipTest("cannot create symbolic links here")
                return baseline.Result(1, "")

        with tempfile.TemporaryDirectory() as tmp:
            outside = Path(tmp) / "outside.txt"
            outside.write_text(secret, encoding="utf-8")
            result = self.go_in(tmp, Linking())
        row = result["rejection"]
        self.assertEqual((row["reason_code"], row["stage"]), ("build_failed", "baseline"))
        self.assertIn("symbolic link", row["detail"])
        self.assertNotIn(secret, row["detail"] + result["log"])

    def test_symlinked_build_directory_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            side = Path(tmp) / "side"
            elsewhere = Path(tmp) / "elsewhere"
            side.mkdir(), elsewhere.mkdir()
            (elsewhere / "junit.xml").write_text("<testsuites/>", encoding="utf-8")
            try:
                (side / "build").symlink_to(elsewhere, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("cannot create symbolic links here")
            with self.assertRaises(baseline.BaselineError):
                baseline.read_junit(side)

    def test_missing_junit_is_none_and_a_regular_one_is_read(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            side = Path(tmp)
            self.assertIsNone(baseline.read_junit(side))
            (side / "build").mkdir()
            (side / "build" / "junit.xml").write_text("<testsuites/>", encoding="utf-8")
            self.assertEqual(baseline.read_junit(side), "<testsuites/>")

    def go_in(self, tmp: str, runner: FakeRunner) -> dict[str, Any]:
        repo, fix = make_repo(Path(tmp))
        item = {"source": "freertos", "project": "FreeRTOS/coreMQTT", "ref": "pull/1", "fix_commit": fix,
                "fix_date": "2026-08-06", "files": ["src/lib.c", "test/unit-test/lib_utest.c", "test/unit-test/CMakeLists.txt"]}
        return baseline.run_baseline(item, Path(tmp) / "work", runner, miner_run=RUN, clone_url=str(repo))

    def test_unknown_commit_is_an_infrastructure_error_not_a_rejection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, _ = make_repo(Path(tmp))
            item = {"source": "freertos", "project": "a/b", "ref": "pull/1", "fix_commit": "f" * 40,
                    "fix_date": "2026-08-06", "files": []}
            with self.assertRaises(baseline.BaselineError):
                baseline.prepare(item, Path(tmp) / "w", str(repo))

    def test_submodule_pins_come_from_the_tree(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, _ = make_repo(Path(tmp))
            sha = "1" * 40
            sh(repo, "update-index", "--add", "--cacheinfo", f"160000,{sha},test/unit-test/Unity")
            self.assertEqual(baseline.gitlinks(repo, "HEAD"), {})  # not committed yet
            sh(repo, "commit", "-q", "-m", "pin")
            self.assertEqual(baseline.gitlinks(repo, "HEAD"), {"test/unit-test/Unity": sha})


if __name__ == "__main__":
    unittest.main()

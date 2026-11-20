# SPDX-License-Identifier: MIT
# Copyright (c) 2026 U-Pump
"""Build recipes per repository, the always-off clone option, and re-evaluation of build-stage rejections."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Any

import candidates
from mine import baseline, discover, recipes, rejects
from test_mine_baseline import FakeRunner, make_repo

RUN = "https://github.com/u-pump/unfix-bench/actions/runs/777"


class RecipeTest(unittest.TestCase):
    def test_every_pilot_repository_has_a_recipe_with_cites(self) -> None:
        for project in ("FreeRTOS/FreeRTOS-Plus-TCP", "FreeRTOS/coreMQTT", "FreeRTOS/coreHTTP", "FreeRTOS/coreJSON"):
            recipe = recipes.recipe_for(project)
            self.assertIsNotNone(recipe, project)
            assert recipe is not None
            self.assertTrue(recipe.evidence, project)
            self.assertTrue(any("ci.yml:" in cite for cite in recipe.evidence), project)
            self.assertIn(project, recipes.EVIDENCE_AT)
            self.assertRegex(recipes.EVIDENCE_AT[project], r"[0-9a-f]{40}")
            self.assertEqual(recipe.ctest_exclude, "system", project)

    def test_the_recipe_is_chosen_by_repository(self) -> None:
        tcp, mqtt = recipes.recipe_for("FreeRTOS/FreeRTOS-Plus-TCP"), recipes.recipe_for("FreeRTOS/coreMQTT")
        assert tcp is not None and mqtt is not None
        self.assertEqual((tcp.cmake_dir, tcp.generator), ("test/unit-test", "Ninja"))
        self.assertEqual((mqtt.cmake_dir, mqtt.generator), ("test", None))
        for project in ("FreeRTOS/coreMQTT", "FreeRTOS/coreHTTP", "FreeRTOS/coreJSON"):
            recipe = recipes.recipe_for(project)
            assert recipe is not None
            self.assertEqual(recipe.cmake_dir, "test")
            self.assertIn("-DUNITTEST=1", recipe.options)
        self.assertIsNone(recipes.recipe_for("FreeRTOS/FreeRTOS-Kernel"))

    def test_clone_submodules_is_always_off_and_never_on(self) -> None:
        for recipe in recipes.RECIPES.values():
            build, test = baseline.commands(recipe.cmake_dir, recipe.options, recipe.generator, recipe.ctest_exclude)
            self.assertEqual(build.count("BUILD_CLONE_SUBMODULES"), 1, recipe.project)
            self.assertIn("-DBUILD_CLONE_SUBMODULES=OFF", build)
            self.assertFalse(any("CLONE" in option for option in recipe.options), recipe.project)
        # a manual option cannot turn it on; repeating OFF does not duplicate it
        with self.assertRaises(ValueError):
            baseline.commands(".", ("-DBUILD_CLONE_SUBMODULES=ON",))
        with self.assertRaises(ValueError):
            baseline.commands(".", ("-DBUILD_CLONE_SUBMODULES:BOOL=1",))
        self.assertEqual(baseline.commands(".", ("-DBUILD_CLONE_SUBMODULES=OFF",))[0].count("BUILD_CLONE_SUBMODULES"), 1)

    def test_commands_follow_the_recipe(self) -> None:
        tcp = recipes.recipe_for("FreeRTOS/FreeRTOS-Plus-TCP")
        assert tcp is not None
        build, test = baseline.commands(tcp.cmake_dir, tcp.options, tcp.generator, tcp.ctest_exclude)
        self.assertEqual(build, "cmake -S test/unit-test -B build -G Ninja -DBUILD_CLONE_SUBMODULES=OFF && cmake --build build -j2")
        self.assertIn("ctest --test-dir build -j1 --output-junit junit.xml --test-output-size-passed", test)
        self.assertTrue(test.endswith(" -E system"), test)

    def run_for(self, project: str) -> tuple[dict[str, Any], FakeRunner]:
        runner = FakeRunner()
        with tempfile.TemporaryDirectory() as tmp:
            repo, fix = make_repo(Path(tmp))
            item = {"source": "freertos", "project": project, "ref": "pull/1", "fix_commit": fix, "fix_date": "2026-08-06",
                    "files": ["src/lib.c", "test/unit-test/lib_utest.c", "test/unit-test/CMakeLists.txt"]}
            return baseline.run_baseline(item, Path(tmp) / "work", runner, miner_run=RUN, clone_url=str(repo)), runner

    def test_run_baseline_uses_the_recipe_of_the_items_repository(self) -> None:
        result, runner = self.run_for("FreeRTOS/FreeRTOS-Plus-TCP")
        self.assertTrue(result["verdict"]["accepted"], result["verdict"])
        builds = [command for _, command in runner.calls if command.startswith("cmake -S")]
        self.assertTrue(builds and all(b.startswith("cmake -S test/unit-test -B build -G Ninja ") for b in builds), builds)
        result, runner = self.run_for("FreeRTOS/coreJSON")
        builds = [command for _, command in runner.calls if command.startswith("cmake -S")]
        self.assertTrue(builds and all(b.startswith("cmake -S test -B build -DCMAKE_BUILD_TYPE=Debug -DUNITTEST=1 ") for b in builds), builds)
        self.assertIn("-DBUILD_CLONE_SUBMODULES=OFF", result["build"])
        self.assertTrue(result["test"].endswith("-E system"))

    def test_a_repository_without_a_recipe_is_a_logged_build_rejection(self) -> None:
        result, runner = self.run_for("FreeRTOS/FreeRTOS-Kernel")
        row = result["rejection"]
        self.assertEqual((row["stage"], row["reason_code"]), ("build", "build_failed"))
        self.assertIn("no build recipe", row["detail"])
        self.assertEqual(runner.calls, [])
        problems = candidates.Problems()
        candidates.validate_rejection(row, "row", problems)
        self.assertEqual(list(problems), [])
        self.assertTrue(rejects.reevaluable(row))


def row(**changes: Any) -> dict[str, Any]:
    base = {"source": "freertos", "project": "FreeRTOS/coreMQTT", "ref": "pull/383", "fix_commit": "a" * 40, "stage": "build",
            "reason_code": "build_failed", "detail": "base: build failed", "fix_date": "2026-08-06", "miner_run": RUN}
    return base | changes


class ReevaluationTest(unittest.TestCase):
    def test_which_rejections_a_new_miner_version_may_judge_again(self) -> None:
        self.assertTrue(rejects.reevaluable(row()))
        self.assertTrue(rejects.reevaluable(row(reason_code="needs_network_dependency")))
        self.assertTrue(rejects.reevaluable(row(reason_code="over_30_min")))
        self.assertTrue(rejects.reevaluable(row(stage="baseline", reason_code="build_failed")))
        for code, stage in (("noisy_module", "baseline"), ("base_not_failing_3of3", "baseline"),
                            ("fix_not_passing_3of3", "fix_run"), ("fix_runs_not_clean", "fix_run"), ("duplicate_backport", "static"),
                            ("test_only_fix", "static"), ("project_cap", "cap"),
                            ("not_a_behavior_bug", "owner_review")):
            self.assertFalse(rejects.reevaluable(row(stage=stage, reason_code=code)), code)

    def test_a_newer_version_adds_its_own_line_and_the_old_one_stays(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertTrue(rejects.append(root, row(), "bench-20-pr5"))
            self.assertFalse(rejects.append(root, row(), "bench-20-pr5"))      # same version, same decision: once
            self.assertTrue(rejects.append(root, row(), "bench-20-pr6a"))      # new version: its own line
            lines = rejects.read(root, "freertos")
            self.assertEqual([r["miner_version"] for r in lines], ["bench-20-pr5", "bench-20-pr6a"])
            problems = candidates.Problems()
            for line in lines:
                candidates.validate_rejection(line, "row", problems)
            self.assertEqual(list(problems), [])

    def test_final_refs_exclude_build_stage_rejections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rejects.append(root, row(ref="pull/1"), "v1")                                              # build: not final
            rejects.append(root, row(ref="pull/2", stage="baseline", reason_code="noisy_module"), "v1")  # final
            rejects.append(root, row(ref="pull/3"), "v1")                                              # build, then
            rejects.append(root, row(ref="pull/3", stage="baseline", reason_code="noisy_module"), "v2")  # judged: final
            self.assertEqual(rejects.final_refs(root, "freertos"),
                             {("FreeRTOS/coreMQTT", "pull/2"), ("FreeRTOS/coreMQTT", "pull/3")})

    def test_discovery_skips_final_rejections_but_not_build_ones_or_an_explicit_list(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rejects.append(root, row(ref="pull/1"), "v1")
            rejects.append(root, row(ref="pull/2", stage="baseline", reason_code="noisy_module"), "v1")
            client = discover_client()
            result = discover.discover(client, source="freertos", miner_run=RUN, root=root, repos=["FreeRTOS/coreMQTT"])
            looked = set(client.pulls_fetched)
            self.assertEqual(result["stats"]["already_rejected"], 1)
            self.assertIn(1, looked)
            self.assertNotIn(2, looked)
            client = discover_client()
            result = discover.discover(client, source="freertos", miner_run=RUN, root=root, refs=[("FreeRTOS/coreMQTT", 2)])
            self.assertEqual(result["stats"]["already_rejected"], 0)
            self.assertIn(2, client.pulls_fetched)


class FakeSearch:
    """Just enough GitHub to show which pull requests discovery looks at (none of them is merged)."""

    def __init__(self) -> None:
        self.pulls_fetched: list[int] = []

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        if path == "/search/issues":
            return {"items": [{"number": 1}, {"number": 2}], "total_count": 2}
        if path == "/repos/FreeRTOS/coreMQTT":
            return {"default_branch": "main", "license": {"spdx_id": "MIT"}}
        if path.startswith("/repos/FreeRTOS/coreMQTT/pulls/"):
            self.pulls_fetched.append(int(path.rsplit("/", 1)[1]))
            return {"merged_at": None}
        raise AssertionError(path)


def discover_client() -> FakeSearch:
    return FakeSearch()


if __name__ == "__main__":
    unittest.main()

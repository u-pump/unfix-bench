# SPDX-License-Identifier: MIT
# Copyright (c) 2026 U-Pump
"""Baseline for CMake/CTest projects: build the base (with the fix's tests) and the fix, run each 3 times.

Two phases, as the plan requires. ``prepare`` uses the network (clone, submodules at recorded commits).
Everything that builds or runs the project's code goes through a ``Runner``; the real one is a Docker
container started with ``--network none``. The verdict (``evaluate``) is pure and tested on recorded shapes.

Granularity: no function-level filter exists for Unity yet, so the reference is the whole ctest test of a
module (``ctest_module``). It is accepted only if on the base nothing but the functions the upstream diff
added or changed fails in that module (otherwise ``noisy_module``).

JUnit/Unity output parsing is written against the documented formats and tested on hand-written samples;
it has **not** been checked against real CTest output yet (the pilot does that).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import stat
import subprocess
import sys
import time
import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import candidates
from mine import filters, rejects

RUNS = 3
MAX_JUNIT_BYTES = 20_000_000
TIME_LIMIT_S = 30 * 60
MAX_XML_BYTES = 20_000_000
UNITY_LINE = re.compile(r"^(?P<file>[^\s:][^:\n]*):(?P<line>\d+):(?P<name>test_\w+):(?P<result>PASS|FAIL|IGNORE)\b", re.M)
TEST_FUNCTION = re.compile(r"^\s*void\s+(test_\w+)\s*\(\s*(?:void)?\s*\)")
HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", re.M)
NETWORK_HINT = re.compile(
    r"(?i)could not resolve host|temporary failure in name resolution|network is unreachable|failed to connect to"
    r"|unable to access 'https?://|fatal: unable to connect|connection refused|file download|fetchcontent")


class BaselineError(RuntimeError):
    """Infrastructure failure (clone, missing commit): the job fails, nothing is recorded as a rejection."""


@dataclass
class Result:
    returncode: int
    output: str
    timed_out: bool = False


class Runner(Protocol):
    def run(self, workdir: Path, command: str, timeout: int) -> Result: ...


class DockerRunner:
    """Runs ``command`` in a throw-away container with no network. ``workdir`` is mounted at /work."""

    def __init__(self, image: str, cpus: str = "2", memory: str = "6g") -> None:
        self.image, self.cpus, self.memory = image, cpus, memory

    def run(self, workdir: Path, command: str, timeout: int) -> Result:
        name = f"bench-miner-{uuid.uuid4().hex[:12]}"
        argv = ["docker", "run", "--rm", "--name", name, "--network", "none", "--cpus", self.cpus,
                "--memory", self.memory, "--pids-limit", "2048", "--cap-drop", "ALL",
                "--security-opt", "no-new-privileges", "-v", f"{workdir.resolve()}:/work", "-w", "/work"]
        if hasattr(os, "getuid"):
            argv += ["--user", f"{os.getuid()}:{os.getgid()}"]
        argv += [self.image, "bash", "-c", command]
        try:
            done = subprocess.run(argv, capture_output=True, timeout=timeout, check=False)
        except subprocess.TimeoutExpired:
            subprocess.run(["docker", "kill", name], capture_output=True, check=False)
            return Result(124, "", True)
        text = (done.stdout + done.stderr).decode("utf-8", errors="replace")
        return Result(done.returncode, text[-400_000:])


# ---------------------------------------------------------------- parsing

def parse_junit(text: str) -> tuple[dict[str, bool], dict[str, dict[str, bool]]]:
    """``(modules, functions)``: ctest test name -> passed, and ctest test name -> Unity function -> passed."""
    if len(text) > MAX_XML_BYTES or "<!DOCTYPE" in text or "<!ENTITY" in text:
        raise ValueError("JUnit file is too large or declares entities")
    root = ET.fromstring(text)
    modules: dict[str, bool] = {}
    functions: dict[str, dict[str, bool]] = {}
    for case in root.iter("testcase"):
        name = case.get("name") or ""
        failed = case.find("failure") is not None or case.find("error") is not None
        modules[name] = not failed and case.get("status") not in ("fail", "failed")
        output = case.findtext("system-out") or ""
        found = {m["name"]: m["result"] != "FAIL" for m in UNITY_LINE.finditer(output) if m["result"] != "IGNORE"}
        if found:
            functions[name] = found
    return modules, functions


def changed_test_functions(diff: str, new_text: str) -> list[str]:
    """Unity test functions of the new file touched by the hunks of ``diff``, in diff order."""
    lines = new_text.splitlines()
    spans: list[tuple[str, int, int]] = []  # name, first line, last line (1-based)
    for index, line in enumerate(lines, start=1):
        match = TEST_FUNCTION.match(line)
        if match:
            end = next((j for j in range(index, len(lines) + 1) if lines[j - 1].rstrip() == "}"), len(lines))
            spans.append((match.group(1), index, end))
    changed: list[str] = []
    for hunk in HUNK.finditer(diff):
        start = int(hunk.group(1))
        length = int(hunk.group(2)) if hunk.group(2) is not None else 1
        last = start + max(length, 1) - 1
        for name, first, end in spans:
            if first <= last and start <= end and name not in changed:
                changed.append(name)
    return changed


# ---------------------------------------------------------------- verdict

def _failing(run: dict[str, Any]) -> set[str]:
    return {name for name, ok in run["modules"].items() if not ok}


def _failing_functions(runs: list[dict[str, Any]], module: str) -> list[set[str]]:
    return [{f for f, ok in run["functions"].get(module, {}).items() if not ok} for run in runs]


def evaluate(base: list[dict[str, Any]], fix: list[dict[str, Any]], changed: list[str]) -> dict[str, Any]:
    """The verdict from 3 runs on the base and 3 on the fix.

    A run is ``{"modules": {ctest name: passed}, "functions": {ctest name: {function: passed}}}``.
    Returns ``{"accepted": True, ...}`` or ``{"accepted": False, "stage", "reason_code", "detail"}``.
    """
    def reject(stage: str, code: str, detail: str) -> dict[str, Any]:
        return {"accepted": False, "stage": stage, "reason_code": code, "detail": detail}

    if len(base) < RUNS or len(fix) < RUNS:
        return reject("baseline", "build_failed", f"fewer than {RUNS} complete runs")
    failing_always = set.intersection(*(_failing(run) for run in base))
    failing_ever = set.union(*(_failing(run) for run in base))
    if not failing_always:
        flaky = sorted(failing_ever)
        return reject("baseline", "base_not_failing_3of3",
                      "no ctest test fails in all 3 base runs" + (f"; failed only sometimes: {', '.join(flaky)}" if flaky else ""))
    fix_failing = set.union(*(_failing(run) for run in fix))
    modules = [name for name in sorted(failing_always) if name not in fix_failing]
    if not modules:
        return reject("fix_run", "fix_not_passing_3of3", f"fails on the fix in some run: {', '.join(sorted(fix_failing & failing_always))}")
    problem: dict[str, Any] | None = None
    for module in modules:
        base_sets = _failing_functions(base, module)
        if not any(run["functions"].get(module) for run in base):
            problem = problem or reject("baseline", "test_not_selectable", f"{module}: no Unity function result in the output")
            continue
        always = set.intersection(*base_sets)
        ever = set.union(*base_sets)
        extra = sorted(ever - set(changed))
        if extra:
            problem = reject("baseline", "noisy_module",
                             f"{module}: functions not changed by the upstream diff fail on the base: {', '.join(extra)}")
            continue
        reference = [name for name in changed if name in always]
        if not reference:
            problem = problem or reject("baseline", "test_not_selectable",
                                        f"{module}: no changed function fails in all 3 base runs")
            continue
        return {"accepted": True, "module": module, "bug_test": reference[0], "reference_functions": reference,
                "bug_test_granularity": "ctest_module", "module_other_tests": "3/3 pass"}
    assert problem is not None
    return problem


# ---------------------------------------------------------------- git (network allowed, builds are not run here)

def git(directory: Path, *args: str, check: bool = True) -> str:
    done = subprocess.run(["git", "-C", str(directory), *args], capture_output=True, text=True, check=False,
                          env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
    if check and done.returncode != 0:
        raise BaselineError(f"git {' '.join(args[:2])} failed: {done.stderr.strip()[:300]}")
    return done.stdout


def gitlinks(directory: Path, rev: str) -> dict[str, str]:
    """Submodule path -> commit recorded in ``rev`` (gitlinks in the tree)."""
    found = {}
    for line in git(directory, "ls-tree", "-r", rev).splitlines():
        meta, _, path = line.partition("\t")
        mode, kind, sha = meta.split()
        if mode == "160000" and kind == "commit":
            found[path] = sha
    return found


def prepare(item: dict[str, Any], work: Path, clone_url: str | None = None) -> dict[str, Any]:
    """Clone, check out ``base`` (with the fix's non-source files laid over it) and ``fix``; fetch submodules.

    ``base`` is the first parent of the fix commit. Returns paths, commits and submodule pins.
    """
    work.mkdir(parents=True, exist_ok=True)
    repo = work / "repo"
    url = clone_url or f"https://github.com/{item['project']}.git"
    done = subprocess.run(["git", "clone", "--quiet", "--no-checkout", url, str(repo)], capture_output=True,
                          text=True, check=False, env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
    if done.returncode != 0:
        raise BaselineError(f"clone failed: {done.stderr.strip()[:300]}")
    fix = git(repo, "rev-parse", "--verify", item["fix_commit"] + "^{commit}").strip()
    base = git(repo, "rev-parse", "--verify", fix + "^1").strip()
    pins = gitlinks(repo, base)
    if pins != gitlinks(repo, fix):
        raise BaselineError("submodule commits differ between base and fix")
    split = filters.split_files(item["files"])
    overlay = [path for path in item["files"] if path not in split["source"]]
    present = set(git(repo, "ls-tree", "-r", "--name-only", fix).splitlines())
    overlay = [path for path in overlay if path in present]
    for name, rev in (("base", base), ("fix", fix)):
        git(repo, "worktree", "add", "--quiet", "--detach", str(work / name), rev)
    if overlay:
        git(work / "base", "checkout", fix, "--", *overlay)
    if pins:
        for name in ("base", "fix"):
            git(work / name, "submodule", "update", "--init", "--recursive", "--quiet")
    test_files = [path for path in split["test"] if path in present]
    changed: list[str] = []
    for path in test_files:
        part = git(repo, "diff", "--unified=0", base, fix, "--", path)
        text = git(repo, "show", f"{fix}:{path}")
        changed += [name for name in changed_test_functions(part, text) if name not in changed]
    return {"base": base, "fix": fix, "base_dir": work / "base", "fix_dir": work / "fix",
            "submodules": [{"path": path, "commit": sha} for path, sha in sorted(pins.items())],
            "overlay": overlay, "changed_functions": changed}


# ---------------------------------------------------------------- build and test

def commands(cmake_dir: str = ".", options: tuple[str, ...] = ()) -> tuple[str, str]:
    """``(build, test)`` shell commands, run inside the container at /work."""
    source = shlex.quote(cmake_dir)
    configure = " ".join(["cmake", "-S", source, "-B", "build", *(shlex.quote(o) for o in options)])
    return f"{configure} && cmake --build build -j2", "rm -f build/junit.xml; ctest --test-dir build -j1 --output-junit junit.xml"


def build_rejection(result: Result, which: str) -> dict[str, Any]:
    if result.timed_out:
        return {"accepted": False, "stage": "build", "reason_code": "over_30_min", "detail": f"{which}: build did not finish in time"}
    code = "needs_network_dependency" if NETWORK_HINT.search(result.output) else "build_failed"
    tail = " ".join(result.output.strip().splitlines()[-3:])[:300]
    return {"accepted": False, "stage": "build", "reason_code": code, "detail": f"{which}: build failed (exit {result.returncode}): {tail}"}


def read_junit(directory: Path) -> str | None:
    """Text of ``build/junit.xml``, or ``None`` if absent. Raises ``BaselineError`` for a link or an escape.

    The file is written by the project's own code in a mounted directory, so it is not trusted to be a regular
    file: a symbolic link there could point at a file of this runner. Neither ``build`` nor the file may be a
    link, the resolved path must stay inside ``directory``, and the file is opened without following links.
    """
    root = directory.resolve()
    build, junit = directory / "build", directory / "build" / "junit.xml"
    for path in (build, junit):
        try:
            mode = os.lstat(path).st_mode
        except FileNotFoundError:
            return None
        if stat.S_ISLNK(mode):
            raise BaselineError(f"{path.relative_to(directory).as_posix()} is a symbolic link")
    if not stat.S_ISREG(os.lstat(junit).st_mode):
        raise BaselineError("build/junit.xml is not a regular file")
    if not junit.resolve().is_relative_to(root):
        raise BaselineError("build/junit.xml resolves outside the working directory")
    descriptor = os.open(junit, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(descriptor, "rb") as handle:
        return handle.read(MAX_JUNIT_BYTES).decode("utf-8", errors="replace")


def run_side(runner: Runner, directory: Path, which: str, build: str, test: str, deadline: float,
             log: list[str]) -> tuple[list[dict[str, Any]] | None, dict[str, Any] | None]:
    """Build once and run the tests ``RUNS`` times. Returns ``(runs, None)`` or ``(None, rejection)``."""
    remaining = int(deadline - time.monotonic())
    if remaining <= 0:
        return None, build_rejection(Result(124, "", True), which)
    built = runner.run(directory, build, remaining)
    log.append(f"=== {which}: build exit {built.returncode}")
    if built.timed_out or built.returncode != 0:
        log.append("\n".join(built.output.splitlines()[-40:]))
        return None, build_rejection(built, which)
    runs = []
    for number in range(1, RUNS + 1):
        remaining = int(deadline - time.monotonic())
        if remaining <= 0:
            return None, {"accepted": False, "stage": "baseline", "reason_code": "over_30_min",
                          "detail": f"{which}: run {number} not finished in time"}
        done = runner.run(directory, test, remaining)
        try:
            text = None if done.timed_out else read_junit(directory)
        except BaselineError as error:
            return None, {"accepted": False, "stage": "baseline", "reason_code": "build_failed",
                          "detail": f"{which} run {number}: refused the JUnit file: {error}"}
        if text is None:
            return None, {"accepted": False, "stage": "baseline", "reason_code": "over_30_min" if done.timed_out else "build_failed",
                          "detail": f"{which} run {number}: " + ("timed out" if done.timed_out else "ctest wrote no JUnit file")}
        modules, functions = parse_junit(text)
        failed = sorted(name for name, ok in modules.items() if not ok)
        log.append(f"=== {which} run {number}: {len(modules)} ctest tests, failed: {', '.join(failed) or 'none'}")
        for module in failed:
            bad = sorted(f for f, ok in functions.get(module, {}).items() if not ok)
            log.append(f"    {module}: failing functions: {', '.join(bad) or 'unknown'}")
        runs.append({"modules": modules, "functions": functions})
    return runs, None


def run_baseline(item: dict[str, Any], work: Path, runner: Runner, *, miner_run: str, cmake_dir: str = ".",
                 options: tuple[str, ...] = (), clone_url: str | None = None, time_limit: int = TIME_LIMIT_S) -> dict[str, Any]:
    started = time.monotonic()
    prepared = prepare(item, work, clone_url)
    build, test = commands(cmake_dir, options)
    deadline = started + time_limit
    log: list[str] = []
    verdict: dict[str, Any] | None = None
    sides: dict[str, list[dict[str, Any]]] = {}
    for which in ("base", "fix"):
        runs, problem = run_side(runner, prepared[f"{which}_dir"], which, build, test, deadline, log)
        if problem:
            verdict = problem
            break
        assert runs is not None
        sides[which] = runs
    if verdict is None:
        verdict = evaluate(sides["base"], sides["fix"], prepared["changed_functions"])
    elapsed = round(time.monotonic() - started, 1)
    result: dict[str, Any] = {
        "ref": item["ref"], "project": item["project"], "base": prepared["base"], "fix": prepared["fix"],
        "submodules": prepared["submodules"], "changed_functions": prepared["changed_functions"],
        "build_network": "none", "build": build, "test": test, "elapsed_s": elapsed, "verdict": verdict,
        "rejection": None,
    }
    if not verdict["accepted"]:
        result["rejection"] = rejects.make(
            source=item["source"], project=item["project"], ref=item["ref"], fix_commit=item["fix_commit"],
            stage=verdict["stage"], reason_code=verdict["reason_code"], detail=verdict["detail"],
            fix_date=item["fix_date"], miner_run=miner_run)
    result["log"] = "\n".join(log) + f"\n=== verdict: {json.dumps(verdict, sort_keys=True)}\n=== elapsed {elapsed}s\n"
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Baseline one discovered candidate (clone with network, build and test with none).")
    parser.add_argument("--discovered", required=True, type=Path, help="discover.py output")
    parser.add_argument("--index", required=True, type=int, help="position in the accepted list")
    parser.add_argument("--image", required=True, help="Docker image with cmake, a compiler and ruby")
    parser.add_argument("--run-url", required=True)
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--cmake-dir", default=".")
    parser.add_argument("--option", action="append", default=[], help="extra cmake option, repeatable")
    args = parser.parse_args(argv)
    if not candidates.RUN_URL.fullmatch(args.run_url):
        parser.error("--run-url must be a GitHub Actions run URL")
    accepted = json.loads(args.discovered.read_text(encoding="utf-8"))["accepted"]
    if not 0 <= args.index < len(accepted):
        parser.error(f"--index {args.index} is outside the {len(accepted)} accepted items")
    try:
        result = run_baseline(accepted[args.index], args.work, DockerRunner(args.image), miner_run=args.run_url,
                              cmake_dir=args.cmake_dir, options=tuple(args.option))
    except BaselineError as error:
        print(f"baseline: {error}", file=sys.stderr)
        return 1
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "baseline.log").write_text(result.pop("log"), encoding="utf-8")
    (args.out / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    print(json.dumps({"ref": result["ref"], "accepted": result["verdict"]["accepted"], "elapsed_s": result["elapsed_s"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())

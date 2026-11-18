# SPDX-License-Identifier: MIT
# Copyright (c) 2026 U-Pump
"""Unity cases in verify_cases.py: cplus judges, the verifier revision is pinned per case, submodules are checked out."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

import candidates
import verify_cases

ROOT = Path(__file__).resolve().parents[1]
NEW = candidates.VERIFIER_FOR_NEW_CASES
LEGACY = "81c0fda242fef1daf55d3164e06127d372c81caa"
PATCH = b"diff --git a/src/a.c b/src/a.c\n"
BASE = "b" * 40
FIX = "f" * 40


def completed(stdout: str, returncode: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=(), returncode=returncode, stdout=stdout, stderr="")


def unity_case(**changes: Any) -> dict[str, Any]:
    case = {"id": "coremqtt-383", "repo": "https://github.com/FreeRTOS/coreMQTT.git", "base": BASE, "upstream_fix": FIX,
            "bug_test": "test_new", "reference_selection": "x", "issue_url": "https://example.test/i", "fix_url": "https://example.test/f",
            "license": "MIT", "category": "logic", "build": "cmake -S test -B build -DBUILD_CLONE_SUBMODULES=OFF && cmake --build build -j2",
            "test": r"ctest --test-dir build -R '^core\.mqtt_utest$' --output-on-failure", "bug_test_granularity": "ctest_module",
            "build_network": "none", "module_other_tests": "3/3 pass", "submodules": [], "verifier_revision": NEW}
    return case | changes


def lay_out(root: Path, case: dict[str, Any], case_id: str = "coremqtt-383") -> None:
    folder = root / "cases" / case_id
    agent = folder / "agents" / "codex-cli"
    agent.mkdir(parents=True)
    (folder / "case.yaml").write_text(json.dumps(case), encoding="utf-8")
    (agent / "agent-fix.patch").write_bytes(PATCH)
    (agent / "agent.yaml").write_text(json.dumps({
        "name": "Mock", "version": "1", "model": "m", "invocation": "i", "date_utc": "2026-11-01", "environment": "e",
        "attempt_note": "n", "patch_sha256": hashlib.sha256(PATCH).hexdigest()}), encoding="utf-8")


def report(**changes: Any) -> dict[str, Any]:
    base = {"schema_version": 1, "verdict": "VERIFIED", "infrastructure_error": None,
            "gates": [{"name": name, "status": "PASS", "evidence": {}} for name in verify_cases.GATES],
            "reference_test": {"framework": "unity", "granularity": "ctest_module", "reason": "r",
                               "description": "Reference test granularity: ctest_module (module core.mqtt_utest; only tests added by the fix fail on the base)"}}
    return base | changes


class Cplus:
    """A fake ``quiet``: records the calls and answers like cplus would."""

    def __init__(self, spec: dict[str, Any] | None = None, verify: dict[str, Any] | None = None) -> None:
        self.calls: list[tuple[str, ...]] = []
        self.spec = {"test_framework": "unity", "granularity": "ctest_module",
                     "command": "ctest --test-dir build -R '^core.mqtt_utest$' --output-on-failure"} if spec is None else spec
        self.verify = report() if verify is None else verify

    def __call__(self, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
        self.calls.append(args)
        if args[:2] == ("git", "clone"):
            Path(args[-1]).mkdir(parents=True, exist_ok=True)
        if args[:2] == ("git", "diff"):
            return completed("diff --git a/src/a.c b/src/a.c\n")
        if args[1:2] == ("bug",):
            Path(args[args.index("--export") + 1]).write_text(json.dumps(self.spec), encoding="utf-8")
            return completed("REPRODUCED")
        if args[1:2] == ("verify",):
            return completed(json.dumps(self.verify))
        return completed("")


def run_main(root: Path, fake: Cplus, **env: str) -> str:
    with (patch.object(verify_cases, "ROOT", root), patch.object(verify_cases, "RESULTS_DIR", root / "results"),
          patch.object(verify_cases, "TEMP", root / "tmp"), patch.object(verify_cases, "quiet", side_effect=fake),
          patch.dict(os.environ, {"SELECT_CASE": "coremqtt-383", **env})):
        verify_cases.main()
    return (root / "results" / "coremqtt-383" / "codex-cli.md").read_text(encoding="utf-8")


class RevisionPerCaseTest(unittest.TestCase):
    def test_the_published_cases_stay_on_their_revision(self) -> None:
        legacy_ids = set()
        for folder in sorted((ROOT / "cases").iterdir()):
            case = json.loads((folder / "case.yaml").read_text(encoding="utf-8"))
            if "verifier_revision" in case:  # a mined case (BENCH-20) names its own full revision
                self.assertRegex(case["verifier_revision"], r"^[0-9a-f]{40}$", folder.name)
                self.assertEqual(verify_cases.case_revision(folder.name), case["verifier_revision"], folder.name)
                continue
            legacy_ids.add(folder.name)
            self.assertEqual(verify_cases.case_revision(folder.name), LEGACY, folder.name)
        self.assertEqual(len(legacy_ids), 10)
        reports = sorted(p for p in (ROOT / "results").glob("*/*.md") if p.parent.name in legacy_ids)
        self.assertTrue(reports)
        for path in reports:
            self.assertRegex(path.read_text(encoding="utf-8"), rf"(?m)^Verifier: cplus {LEGACY} ·", path.as_posix())
        self.assertEqual(verify_cases.VERIFIER_REVISION, LEGACY)

    def test_a_new_case_names_its_revision_and_drafts_carry_it(self) -> None:
        self.assertEqual(NEW, "dadf0588efee26730378c298fdddd212437aed86")
        self.assertNotEqual(NEW, LEGACY)
        with tempfile.TemporaryDirectory() as tmp, patch.object(verify_cases, "ROOT", Path(tmp)):
            lay_out(Path(tmp), unity_case())
            self.assertEqual(verify_cases.case_revision("coremqtt-383"), NEW)
            lay_out(Path(tmp), unity_case(verifier_revision="nope"), "bad-1")
            with self.assertRaises(ValueError):
                verify_cases.case_revision("bad-1")
            self.assertEqual(verify_cases.case_revision_or_legacy("bad-1"), LEGACY)

    def test_a_report_is_current_only_for_the_revision_of_its_case(self) -> None:
        digest = hashlib.sha256(PATCH).hexdigest()
        with tempfile.TemporaryDirectory() as tmp, patch.object(verify_cases, "ROOT", Path(tmp)):
            root = Path(tmp)
            lay_out(root, unity_case())
            out = root / "results" / "coremqtt-383"
            out.mkdir(parents=True)
            for revision, current in ((LEGACY, False), (NEW, True)):
                (out / "codex-cli.md").write_text(f"# x\n\nVerifier: cplus {revision} · 2026-11-01 00:00:00 UTC\n\nPatch: sha256 {digest}\n", encoding="utf-8")
                self.assertEqual(verify_cases.report_is_current("coremqtt-383", "codex-cli", digest), current, revision)

    def test_the_revisions_the_install_step_needs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.object(verify_cases, "ROOT", Path(tmp)):
            root = Path(tmp)
            lay_out(root, unity_case())
            lay_out(root, {k: v for k, v in unity_case().items() if k != "verifier_revision"}, "old-1")
            with patch.dict(os.environ, {"SELECT_CASE": "", "SELECT_AGENT": "", "BEFORE_SHA": "", "HEAD_SHA": ""}):
                pairs = verify_cases.selected_pairs()
                self.assertEqual(sorted(c for c, _ in pairs), ["coremqtt-383", "old-1"])
                self.assertEqual(sorted({verify_cases.case_revision_or_legacy(c) for c, _ in pairs}), sorted([LEGACY, NEW]))

    def test_cplus_comes_from_the_virtual_environment_of_the_revision(self) -> None:
        with patch.dict(os.environ, {"CPLUS_VENV_ROOT": ""}):
            self.assertEqual(verify_cases.cplus_command(NEW), "cplus")
        with patch.dict(os.environ, {"CPLUS_VENV_ROOT": "/venvs"}):
            command = verify_cases.cplus_command(NEW).replace(chr(92), "/")
            self.assertRegex(command, rf"/venvs/{NEW}/(bin|Scripts)/cplus$")
            with self.assertRaises(verify_cases.CaseExecutionError):
                verify_cases.cplus_command("../x")


class UnityCaseTest(unittest.TestCase):
    def test_the_case_goes_to_cplus_of_its_revision_and_cplus_judges(self) -> None:
        fake = Cplus()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            lay_out(root, unity_case())
            text = run_main(root, fake, CPLUS_VENV_ROOT="/venvs")
        bug = next(c for c in fake.calls if c[1:2] == ("bug",))
        verify = next(c for c in fake.calls if c[1:2] == ("verify",))
        for call in (bug, verify):
            self.assertRegex(call[0].replace(chr(92), "/"), rf"/venvs/{NEW}/(bin|Scripts)/cplus$")
        self.assertNotIn("--reference-test-name", verify)   # cplus selects the Unity reference itself
        self.assertNotIn("--command", bug)
        self.assertIn("Verdict: **VERIFIED**", text)
        self.assertRegex(text, rf"(?m)^Verifier: cplus {NEW} · ")
        self.assertRegex(text, r"(?m)^Reference: ctest_module \(module core\.mqtt_utest; only tests added by the fix fail on the base\)$")

    def test_cplus_choosing_another_module_or_granularity_is_an_error_not_a_verdict(self) -> None:
        cases = {
            "module": Cplus(spec={"test_framework": "unity", "granularity": "ctest_module",
                                  "command": "ctest --test-dir build -R '^other_utest$'"}),
            "granularity": Cplus(spec={"test_framework": "unity", "granularity": "function", "command": "ctest -R '^core.mqtt_utest$'"}),
            "not unity": Cplus(spec={"granularity": None, "test_framework": None, "command": "ctest"}),
            "report": Cplus(verify=report(reference_test={"framework": "unity", "granularity": "function", "reason": "r", "description": "d"})),
        }
        for name, fake in cases.items():
            with self.subTest(name), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                lay_out(root, unity_case())
                text = run_main(root, fake)
                self.assertIn("Verdict: **INFRASTRUCTURE_ERROR**", text)
                self.assertRegex(text, r"Reason: (cplus bug baseline|verify): cplus ")

    def test_not_verifiable_from_cplus_is_published_as_it_is(self) -> None:
        fake = Cplus(verify=report(verdict="NOT_VERIFIABLE", summary="a test outside the fix fails in the module", gates=[]))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            lay_out(root, unity_case())
            text = run_main(root, fake)
        self.assertIn("Verdict: **NOT_VERIFIABLE**", text)
        self.assertIn("Reason: a test outside the fix fails in the module", text)

    def test_a_case_without_granularity_is_not_checked_as_unity(self) -> None:
        fake = Cplus(spec={})
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            lay_out(root, {k: v for k, v in unity_case().items() if k not in ("bug_test_granularity", "verifier_revision")})
            text = run_main(root, fake)   # no CPLUS_VENV_ROOT: plain "cplus" from PATH, legacy revision
        self.assertRegex(text, rf"(?m)^Verifier: cplus {LEGACY} ·")
        self.assertNotIn("Reference:", text)
        self.assertTrue(all(c[0] in ("git", "cplus") for c in fake.calls))


class SubmoduleTest(unittest.TestCase):
    def git(self, directory: Path, *args: str) -> str:
        done = subprocess.run(["git", "-C", str(directory), "-c", "user.name=t", "-c", "user.email=t@example.com",
                               "-c", "commit.gpgsign=false", "-c", "protocol.file.allow=always", *args],
                              capture_output=True, text=True, check=True)
        return done.stdout.strip()

    def repo_with_submodule(self, root: Path) -> tuple[Path, str, str]:
        dep = root / "dep"
        dep.mkdir()
        subprocess.run(["git", "init", "-q", "-b", "main", str(dep)], check=True)
        (dep / "unity.c").write_text("/* unity */" + chr(10), encoding="utf-8")
        self.git(dep, "add", "-A")
        self.git(dep, "commit", "-q", "-m", "dep")
        pin = self.git(dep, "rev-parse", "HEAD")
        repo = root / "origin"
        repo.mkdir()
        subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
        self.git(repo, "submodule", "add", "-q", str(dep), "test/unit-test/Unity")
        self.git(repo, "config", "-f", ".gitmodules", "submodule.test/unit-test/Unity.update", "none")
        self.git(repo, "add", "-A")
        self.git(repo, "commit", "-q", "-m", "base")
        return repo, self.git(repo, "rev-parse", "HEAD"), pin

    def test_submodule_with_update_none_is_checked_out_at_the_pin(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo, base, pin = self.repo_with_submodule(root)
            scratch = root / "scratch"
            subprocess.run(["git", "clone", "-q", "--no-checkout", str(repo), str(scratch)], check=True)
            self.git(scratch, "checkout", "-q", "--detach", base)
            case = {"submodules": [{"path": "test/unit-test/Unity", "commit": pin}]}
            file_only = ("-c", "protocol.allow=never", "-c", "protocol.file.allow=always")
            self.git(scratch, "submodule", "update", "--init", "--recursive")   # premise: update = none skips it
            self.assertFalse((scratch / "test/unit-test/Unity/unity.c").exists())
            with patch.object(verify_cases, "HTTPS_ONLY", file_only):
                verify_cases.prepare_submodules(scratch, case, base)
            self.assertTrue((scratch / "test/unit-test/Unity/unity.c").is_file())
            self.assertEqual(self.git(scratch / "test/unit-test/Unity", "rev-parse", "HEAD"), pin)

    def test_pins_that_differ_from_the_tree_stop_the_case(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo, base, _ = self.repo_with_submodule(root)
            scratch = root / "scratch"
            subprocess.run(["git", "clone", "-q", "--no-checkout", str(repo), str(scratch)], check=True)
            with self.assertRaises(verify_cases.CaseExecutionError) as caught:
                verify_cases.prepare_submodules(scratch, {"submodules": [{"path": "test/unit-test/Unity", "commit": "1" * 40}]}, base)
            self.assertIn("differ", caught.exception.public_reason)

    def test_https_is_the_only_transfer_protocol_by_default(self) -> None:
        self.assertIn("protocol.allow=never", verify_cases.HTTPS_ONLY)
        self.assertIn("protocol.https.allow=always", verify_cases.HTTPS_ONLY)
        self.assertFalse(any("file" in option for option in verify_cases.HTTPS_ONLY))

    def test_a_case_without_submodules_runs_no_git_submodule_command(self) -> None:
        calls: list[tuple[str, ...]] = []
        with patch.object(verify_cases, "quiet", side_effect=lambda *a, cwd=None: calls.append(a) or completed("")):
            verify_cases.prepare_submodules(Path("."), {"submodules": []}, BASE)
        self.assertEqual(calls, [])


class InstallScriptTest(unittest.TestCase):
    SCRIPT = (ROOT / "scripts" / "install_private.sh").read_text(encoding="utf-8")

    def test_one_environment_per_revision_and_only_full_hashes(self) -> None:
        self.assertIn('python -m venv "$venv_root/$revision"', self.SCRIPT)
        self.assertIn('"$venv_root/$revision/bin/python" -m pip install', self.SCRIPT)
        self.assertNotRegex(self.SCRIPT, r"(?m)^python -m pip install")           # nothing into the shared interpreter
        self.assertIn('[ "${#revision}" -ne 40 ]', self.SCRIPT)
        self.assertNotIn("81c0fda", self.SCRIPT)                                  # no revision is written into the script
        self.assertIn("CPLUS_VENV_ROOT", self.SCRIPT)

    def test_workflows_install_what_the_selected_pairs_need(self) -> None:
        for name in ("verify.yml", "run-claude-code.yml"):
            text = (ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")
            self.assertIn('"$(python scripts/verify_cases.py --revisions)"', text, name)
            self.assertIn('bash scripts/install_private.sh "${revisions[@]}"', text, name)
            self.assertNotRegex(text, r"(?m)run: bash scripts/install_private\.sh\s*$", name)

    @unittest.skipUnless(os.name == "posix", "needs a POSIX shell and path")
    def test_a_bad_revision_stops_before_any_network_use(self) -> None:
        for argument in ("main", "ABC", "a" * 39, "a" * 41, "../" + "a" * 37):
            with tempfile.TemporaryDirectory() as tmp:
                done = subprocess.run(["bash", str(ROOT / "scripts" / "install_private.sh"), argument], capture_output=True, text=True,
                                      env={"PATH": os.environ["PATH"], "RUNNER_TEMP": tmp, "CPLUS_READ_TOKEN": "x"}, check=False)
                self.assertEqual(done.returncode, 1, argument)
                self.assertIn("Invalid verifier revision", done.stdout, argument)
                self.assertEqual(list(Path(tmp).iterdir()), [], argument)


class DocsTest(unittest.TestCase):
    def test_the_rule_is_written_down(self) -> None:
        protocol = (ROOT / "docs" / "protocol.md").read_text(encoding="utf-8")
        self.assertIn("verifier_revision", protocol)
        self.assertRegex(protocol, re.escape(LEGACY[:7]))
        self.assertIn(NEW, (ROOT / "docs" / "DECISIONS.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

# SPDX-License-Identifier: MIT
# Copyright (c) 2026 U-Pump
"""cplus 0.2.5 exit code 5 (licence) is an INFRASTRUCTURE_ERROR with the licence line as its reason."""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

import collect_agent_run
import verify_cases

LINES = (
    "No licence. Run: unfix activate <key>. Keys come with the Team subscription at https://unfix.dev/#pricing",
    "Licence expired on 2026-12-01. Renew at https://unfix.dev/#pricing or write hello@unfix.dev",
    "Licence key is not valid — check it was copied whole",
)
WARNING = "WARN: Licence expired on 2026-11-20; 13 days of grace left — renew at https://unfix.dev/#pricing"


def done(stdout: str = "", returncode: int = 0, stderr: str = "") -> CompletedProcess[str]:
    return CompletedProcess(args=(), returncode=returncode, stdout=stdout, stderr=stderr)


class LicenceExitCodeTest(unittest.TestCase):
    def run_case(self, bug: CompletedProcess[str], verify: CompletedProcess[str], env: dict[str, str] | None = None):
        calls: list[str] = []
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)

            def fake_quiet(*args: str, cwd: Path | None = None):
                if args[:2] == ("git", "clone"):
                    Path(args[-1]).mkdir(parents=True, exist_ok=True)
                if args[:2] == ("git", "diff"):
                    return done("diff --git a/a b/a\n")
                if args[:2] == ("cplus", "bug"):
                    calls.append("bug")
                    if bug.returncode == 0:
                        Path(args[args.index("--export") + 1]).write_text("{}", encoding="utf-8")
                    return bug
                if args[:2] == ("cplus", "verify"):
                    calls.append("verify")
                    return verify
                return done()

            out = io.StringIO()
            with (patch.object(verify_cases, "TEMP", temp),
                  patch.object(verify_cases, "quiet", side_effect=fake_quiet),
                  patch.dict("os.environ", env or {}, clear=False),
                  contextlib.redirect_stdout(out)):
                try:
                    result = verify_cases.run_case("cpp-peglib-121", "codex-cli")
                    error = None
                except verify_cases.CaseExecutionError as exc:
                    result, error = None, exc
        return result, error, calls, out.getvalue()

    def test_exit_5_of_bug_is_the_licence_line(self) -> None:
        for line in LINES:
            with self.subTest(line=line):
                _, error, calls, out = self.run_case(done("", 5, "PRIVATE\n" + line + "\n"), done())
                self.assertIsInstance(error, verify_cases.LicenceError)
                self.assertEqual(error.public_reason, line)
                self.assertEqual(calls, ["bug"])
                self.assertNotIn("PRIVATE", out)

    def test_urls_stay_whole_and_paths_are_still_replaced(self) -> None:
        for line in LINES[:2]:
            self.assertEqual(verify_cases.licence_line("x\n" + line + "\n"), line)
            _, error, _, _ = self.run_case(done("", 5, line + "\n"), done())
            self.assertIn("https://unfix.dev/#pricing", error.public_reason)
            self.assertNotIn("[path]", error.public_reason)
        mixed = verify_cases.licence_line("No licence. See /etc/unfix/key and https://unfix.dev/#pricing")
        self.assertEqual(mixed, "No licence. See [path] and https://unfix.dev/#pricing")

    def test_exit_5_of_verify_is_the_licence_line_even_with_json_on_stdout(self) -> None:
        stdout = json.dumps({"schema_version": 1, "verdict": "NOT_VERIFIABLE", "summary": "x",
                             "infrastructure_error": None, "gates": []})
        _, error, calls, _ = self.run_case(done("REPRODUCED"), done(stdout, 5, LINES[1] + "\n"))
        self.assertIsInstance(error, verify_cases.LicenceError)
        self.assertEqual(error.public_reason, LINES[1])
        self.assertEqual(calls, ["bug", "verify"])

    def test_the_result_is_infrastructure_error_with_the_line_as_reason(self) -> None:
        report = verify_cases.render("fmt-4800", "INFRASTRUCTURE_ERROR", {}, None, "Codex CLI", "1", "now",
                                     LINES[0])
        self.assertIn("Verdict: **INFRASTRUCTURE_ERROR**", report)
        self.assertIn(f"Reason: {LINES[0]}", report)
        self.assertNotIn("REJECTED", report)

    def test_exit_3_is_still_not_verifiable_and_exit_5_is_not(self) -> None:
        stdout = json.dumps({"schema_version": 1, "verdict": "NOT_VERIFIABLE", "summary": "no baseline",
                             "infrastructure_error": None, "gates": []})
        result, error, _, _ = self.run_case(done("REPRODUCED"), done(stdout, 3, ""))
        self.assertIsNone(error)
        self.assertEqual(result[0], "NOT_VERIFIABLE")

    def test_other_text_with_exit_5_gets_a_fixed_reason(self) -> None:
        _, error, _, out = self.run_case(done("", 5, "Traceback (most recent call last):\nboom /x/y\n"), done())
        self.assertEqual(error.public_reason, verify_cases.LICENCE_FALLBACK)
        self.assertNotIn("Traceback", out)

    def test_the_key_and_paths_never_reach_the_line(self) -> None:
        key = "k3y-SECRET-0123456789"
        line = f"Licence key is not valid: {key} in /home/runner/work/_temp/unfix/licence.key"
        _, error, _, _ = self.run_case(done("", 5, line), done(), {"UNFIX_LICENCE": key})
        self.assertNotIn(key, error.public_reason)
        self.assertNotIn("/home/runner", error.public_reason)
        self.assertTrue(error.public_reason.startswith("Licence key is not valid"))

    def test_the_key_from_the_file_is_redacted_too(self) -> None:
        key = "file-key-0123456789"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "licence.key"
            path.write_text(key + "\n", encoding="utf-8")
            line = f"Licence key is not valid: {key}"
            _, error, _, _ = self.run_case(done("", 5, line), done(), {"UNFIX_LICENCE_FILE": str(path)})
        self.assertNotIn(key, error.public_reason)

    def test_grace_period_warning_is_logged_and_does_not_fail(self) -> None:
        stdout = json.dumps({"schema_version": 1, "verdict": "VERIFIED", "summary": "ok",
                             "infrastructure_error": None, "gates": []})
        result, error, _, out = self.run_case(
            done("REPRODUCED", 0, WARNING + "\n"),
            done(stdout, 0, ""))
        self.assertIsNone(error)
        self.assertEqual(result[0], "VERIFIED")
        self.assertIn(WARNING, out)


class LicenceScanTest(unittest.TestCase):
    def test_scan_removes_files_that_contain_the_licence_key(self) -> None:
        key = "licence-key-0123456789abcdef"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            keyfile = root / "licence.key"
            keyfile.write_text(key, encoding="utf-8")
            leak, clean = root / "leak.log", root / "clean.log"
            leak.write_text(f"env dump\nUNFIX_LICENCE={key}\n", encoding="utf-8")
            clean.write_text("nothing here\n", encoding="utf-8")
            args = type("Args", (), {"files": [str(leak), str(clean)]})()
            with (patch.dict("os.environ", {"UNFIX_LICENCE_FILE": str(keyfile)}),
                  contextlib.redirect_stdout(io.StringIO()) as out):
                code = collect_agent_run.cmd_scan(args)
            self.assertEqual(code, 4)
            self.assertFalse(leak.exists() or clean.exists())
            self.assertNotIn(key, out.getvalue())


if __name__ == "__main__":
    unittest.main()

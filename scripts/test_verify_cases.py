# SPDX-License-Identifier: MIT
# Copyright (c) 2026 U-Pump
"""Offline smoke test of case selection and public report generation."""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import verify_cases


class VerifyCasesSmokeTest(unittest.TestCase):
    def test_changed_pairs_ignore_rename_and_current_report(self) -> None:
        source = verify_cases.ROOT / "cases" / "fmt-4800" / "agents"
        existing = (verify_cases.ROOT / "results" / "fmt-4800" / "codex-cli.md").read_bytes()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for agent_id in ("codex-cli", "claude-code"):
                target = root / "cases" / "fmt-4800" / "agents" / agent_id
                target.mkdir(parents=True)
                if agent_id == "claude-code":
                    # A case with no recorded attempt, whatever the repository holds today.
                    (target / "agent.yaml").write_text(json.dumps({"patch_sha256": None}), encoding="utf-8")
                    (target / "agent-fix.patch").write_bytes(b"")
                    continue
                for name in ("agent.yaml", "agent-fix.patch"):
                    (target / name).write_bytes((source / agent_id / name).read_bytes())
            result = root / "results" / "fmt-4800" / "codex-cli.md"
            result.parent.mkdir(parents=True)
            result.write_bytes(existing)
            migrated = completed(
                "R100\tcases/fmt-4800/agent-fix.patch\t"
                "cases/fmt-4800/agents/codex-cli/agent-fix.patch\n"
                "A\tcases/fmt-4800/agents/codex-cli/agent.yaml\n"
                "A\tcases/fmt-4800/agents/claude-code/agent.yaml\n"
                "A\tcases/fmt-4800/agents/claude-code/agent-fix.patch\n"
            )
            with (patch.object(verify_cases, "ROOT", root),
                  patch.object(verify_cases, "quiet", return_value=migrated),
                  patch.dict("os.environ", {"BEFORE_SHA": "a" * 40, "HEAD_SHA": "b" * 40,
                                          "SELECT_CASE": "", "SELECT_AGENT": ""})):
                self.assertEqual(verify_cases.selected_pairs(), [])
                with patch.object(verify_cases, "run_case", side_effect=AssertionError("must not rerun")):
                    self.assertEqual(verify_cases.main(), 0)
                self.assertEqual(result.read_bytes(), existing)
                claude = root / "cases" / "fmt-4800" / "agents" / "claude-code"
                patch_bytes = b"diff --git a/a.cc b/a.cc\n+fixed\n"
                (claude / "agent-fix.patch").write_bytes(patch_bytes)
                metadata = json.loads((claude / "agent.yaml").read_text(encoding="utf-8"))
                metadata["patch_sha256"] = hashlib.sha256(patch_bytes).hexdigest()
                (claude / "agent.yaml").write_text(json.dumps(metadata), encoding="utf-8")
                self.assertEqual(verify_cases.selected_pairs(), [("fmt-4800", "claude-code")])
                self.assertEqual(result.read_bytes(), existing)

    def test_explicit_selection_forces_current_report(self) -> None:
        with patch.dict("os.environ", {"SELECT_CASE": "fmt-4800", "SELECT_AGENT": "codex-cli"}):
            self.assertEqual(verify_cases.selected_pairs(), [("fmt-4800", "codex-cli")])

    def test_all_agent_pairs_get_separate_reports(self) -> None:
        source = verify_cases.ROOT / "cases" / "cpp-peglib-121"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            case_dir = root / "cases" / "cpp-peglib-121"
            for agent_id in ("claude-code", "codex-cli"):
                target = case_dir / "agents" / agent_id
                target.mkdir(parents=True)
                (target / "agent.yaml").write_bytes((source / "agents" / agent_id / "agent.yaml").read_bytes())
                (target / "agent-fix.patch").write_bytes((source / "agents" / agent_id / "agent-fix.patch").read_bytes())
            (case_dir / "case.yaml").write_bytes((source / "case.yaml").read_bytes())
            with (patch.object(verify_cases, "ROOT", root),
                  patch.object(verify_cases, "RESULTS_DIR", root / "results"),
                  patch.object(verify_cases, "run_case", side_effect=[("PENDING", {}, None, None), ("REJECTED", {}, 1.0, "test failed")]) as run,
                  patch.dict("os.environ", {"SELECT_CASE": "cpp-peglib-121"}),
                  contextlib.redirect_stdout(io.StringIO())):
                self.assertEqual(verify_cases.main(), 0)
            self.assertEqual(run.call_args_list[0].args, ("cpp-peglib-121", "claude-code"))
            self.assertEqual(run.call_args_list[1].args, ("cpp-peglib-121", "codex-cli"))
            self.assertIn("**PENDING**", (root / "results" / "cpp-peglib-121" / "claude-code.md").read_text())
            self.assertIn("**REJECTED**", (root / "results" / "cpp-peglib-121" / "codex-cli.md").read_text())

    def test_empty_patch_is_pending_and_hash_mismatch_stops_verification(self) -> None:
        source = verify_cases.ROOT / "cases" / "cpp-peglib-121"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            case_dir = root / "cases" / "cpp-peglib-121"
            for agent_id in ("claude-code", "codex-cli"):
                target = case_dir / "agents" / agent_id
                target.mkdir(parents=True)
                (target / "agent.yaml").write_bytes((source / "agents" / agent_id / "agent.yaml").read_bytes())
                (target / "agent-fix.patch").write_bytes((source / "agents" / agent_id / "agent-fix.patch").read_bytes())
            (case_dir / "case.yaml").write_bytes((source / "case.yaml").read_bytes())
            with (patch.object(verify_cases, "ROOT", root),
                  patch.object(verify_cases, "quiet", side_effect=AssertionError("verifier must not run"))):
                self.assertEqual(verify_cases.run_case("cpp-peglib-121", "claude-code")[0], "PENDING")
                (case_dir / "agents" / "codex-cli" / "agent-fix.patch").write_bytes(b"changed")
                with self.assertRaisesRegex(verify_cases.CaseExecutionError, "patch hash mismatch"):
                    verify_cases.run_case("cpp-peglib-121", "codex-cli")

    def test_reference_selection_is_recorded_for_every_case(self) -> None:
        case_dirs = sorted((verify_cases.ROOT / "cases").iterdir())
        self.assertEqual(len(case_dirs), 10)
        for case_dir in case_dirs:
            with self.subTest(case=case_dir.name):
                case = json.loads((case_dir / "case.yaml").read_text(encoding="utf-8"))
                self.assertEqual(
                    case["reference_selection"],
                    "first upstream diff test with a 3/3 base failure",
                )
                self.assertTrue(case["bug_test"])
                if "reference_test_name" in case:
                    self.assertEqual(case["reference_test_name"], case["bug_test"])

    def test_run_case_uses_public_verifier_summary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)

            def fake_quiet(*args: str, cwd: Path | None = None):
                if args[:2] == ("git", "clone"):
                    Path(args[-1]).mkdir(parents=True, exist_ok=True)
                if args[:2] == ("git", "diff"):
                    return completed("diff --git a/test.cc b/test.cc\n")
                if args[:2] == ("cplus", "bug"):
                    Path(args[args.index("--export") + 1]).write_text("{}", encoding="utf-8")
                    return completed("REPRODUCED")
                if args[:2] == ("cplus", "verify"):
                    return completed(json.dumps({
                        "schema_version": 1, "verdict": current_verdict,
                        "summary": "the fix patch differs from the one whose test reproduced this bug",
                        "infrastructure_error": None, "gates": [],
                    }))
                return completed("")

            for current_verdict in ("NOT_VERIFIABLE", "ERROR"):
                with (self.subTest(verdict=current_verdict),
                      patch.object(verify_cases, "TEMP", temp),
                      patch.object(verify_cases, "quiet", side_effect=fake_quiet)):
                    verdict, gates, _elapsed, reason = verify_cases.run_case("cpp-peglib-121", "codex-cli")
                self.assertEqual(verdict, current_verdict)
                self.assertEqual(gates, {})
                self.assertEqual(
                    reason, "the fix patch differs from the one whose test reproduced this bug"
                )

    def test_nonverifiable_and_error_reasons_are_short_and_public(self) -> None:
        summary = "the fix patch differs from the one whose test reproduced this bug\nPRIVATE_CPLUS_LOG"
        self.assertEqual(
            verify_cases.summary_reason(summary, "fallback"),
            "the fix patch differs from the one whose test reproduced this bug",
        )
        self.assertEqual(
            verify_cases.summary_reason("build failed at D:\\runner\\private\\log", "verifier returned error"),
            "verifier returned error",
        )
        for verdict in ("NOT_VERIFIABLE", "ERROR", "INFRASTRUCTURE_ERROR"):
            report = verify_cases.render(
                "fmt-4800", verdict, {}, 0.7, "Codex CLI", "0.163.0",
                "2026-10-20 18:00:00 UTC", verify_cases.summary_reason(summary, "fallback"),
            )
            self.assertEqual(report.count("Reason:"), 1)
            self.assertNotIn("PRIVATE_CPLUS_LOG", report)
            self.assertNotIn("D:\\runner", report)

    def test_rejected_case_note_flows_from_agent_metadata_to_result(self) -> None:
        note = (
            "agent implemented the wait but broke the upstream discard_new behaviour "
            "(differs from expected upstream behaviour)"
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            case_dir = root / "cases" / "spdlog-3049"
            agent_dir = case_dir / "agents" / "codex-cli"
            agent_dir.mkdir(parents=True)
            (agent_dir / "agent.yaml").write_text(
                json.dumps({"result_note": note}), encoding="utf-8"
            )
            with (patch.object(verify_cases, "ROOT", root),
                  patch.object(verify_cases, "RESULTS_DIR", root / "results"),
                  patch.object(verify_cases, "selected_pairs", return_value=[("spdlog-3049", "codex-cli")]),
                  patch.object(verify_cases, "agent_identity", return_value=("Codex CLI", "0.164.0")),
                  patch.object(verify_cases, "run_case", return_value=("REJECTED", {"anti_cheat": "PASS"}, 1.0, "reference still fails")),
                  contextlib.redirect_stdout(io.StringIO())):
                self.assertEqual(verify_cases.main(), 0)
            report = (root / "results" / "spdlog-3049" / "codex-cli.md").read_text(encoding="utf-8")
            self.assertIn(f"Note: {note}", report)
            self.assertIn("Reason: reference still fails", report)

            (agent_dir / "agent.yaml").write_text(
                json.dumps({"result_note": "private log at D:\\runner\\secret"}), encoding="utf-8"
            )
            with patch.object(verify_cases, "ROOT", root):
                with self.assertRaises(verify_cases.CaseExecutionError):
                    verify_cases.agent_result_note("spdlog-3049", "codex-cli")

        self.assertNotIn(
            "Note:",
            verify_cases.render("spdlog-3049", "VERIFIED", {}, 1.0, "Codex CLI", "0.164.0",
                                "2026-10-24 12:00:00 UTC", "fix proven", note),
        )

    def test_infrastructure_error_reports_generic_reason_without_exception_details(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with (patch.object(verify_cases, "ROOT", root),
                  patch.object(verify_cases, "RESULTS_DIR", root / "results"),
                  patch.object(verify_cases, "selected_pairs", return_value=[("fmt-4800", "codex-cli")]),
                  patch.object(verify_cases, "agent_identity", return_value=("Codex CLI", "0.163.0")),
                  patch.object(verify_cases, "run_case", side_effect=RuntimeError("D:\\runner\\private\\log PRIVATE_CPLUS_LOG")),
                  contextlib.redirect_stdout(io.StringIO())):
                self.assertEqual(verify_cases.main(), 1)
            result = (root / "results" / "fmt-4800" / "codex-cli.md").read_text(encoding="utf-8")
            self.assertIn("Verdict: **INFRASTRUCTURE_ERROR**", result)
            self.assertIn("Reason: parse: unexpected case processing error", result)
            self.assertNotIn("D:\\runner", result)
            self.assertNotIn("PRIVATE_CPLUS_LOG", result)

    def test_infrastructure_stages_have_safe_public_reasons(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)

            def fake_quiet(*args: str, cwd: Path | None = None):
                if args[:2] == ("git", "clone"):
                    if broken_stage == "clone":
                        return completed("", 1)
                    Path(args[-1]).mkdir(parents=True, exist_ok=True)
                if args[:2] == ("git", "checkout") and broken_stage == "checkout base":
                    return completed("", 1)
                if args[:2] == ("git", "diff"):
                    return completed("" if broken_stage == "upstream fix" else "diff --git a/a b/a\n")
                if args[:2] == ("cplus", "bug"):
                    if broken_stage == "cplus bug baseline":
                        return completed("", 1)
                    Path(args[args.index("--export") + 1]).write_text("{}", encoding="utf-8")
                    return completed("REPRODUCED")
                if args[:2] == ("cplus", "verify"):
                    if broken_stage == "parse":
                        return completed("not JSON")
                    return completed(json.dumps({"schema_version": 1, "verdict": "ERROR",
                                                 "infrastructure_error": "PRIVATE_CPLUS_LOG D:\\runner",
                                                 "gates": []}))
                return completed("")

            for broken_stage in ("clone", "checkout base", "upstream fix",
                                 "cplus bug baseline", "verify", "parse"):
                stage_temp = temp / broken_stage.replace(" ", "-")
                with (self.subTest(stage=broken_stage),
                      patch.object(verify_cases, "TEMP", stage_temp),
                      patch.object(verify_cases, "quiet", side_effect=fake_quiet)):
                    with self.assertRaises(verify_cases.CaseExecutionError) as caught:
                        verify_cases.run_case("cpp-peglib-121", "codex-cli")
                self.assertEqual(caught.exception.stage, broken_stage)
                self.assertNotIn("PRIVATE_CPLUS_LOG", caught.exception.public_reason)
                self.assertNotIn("D:\\runner", caught.exception.public_reason)
            with (patch.object(verify_cases, "TEMP", temp / "missing-command"),
                  patch.object(verify_cases, "quiet", side_effect=FileNotFoundError("D:\\private\\git"))):
                with self.assertRaises(verify_cases.CaseExecutionError) as caught:
                    verify_cases.run_case("cpp-peglib-121", "codex-cli")
            self.assertEqual(caught.exception.stage, "clone")

    def test_inconclusive_verifier_diagnostic_stays_out_of_public_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            current_verdict = "NOT_VERIFIABLE"

            def fake_quiet(*args: str, cwd: Path | None = None):
                if args[:2] == ("git", "clone"):
                    Path(args[-1]).mkdir(parents=True, exist_ok=True)
                if args[:2] == ("git", "diff"):
                    return completed("diff --git a/a b/a\n")
                if args[:2] == ("cplus", "bug"):
                    Path(args[args.index("--export") + 1]).write_text("{}", encoding="utf-8")
                    return completed("REPRODUCED")
                if args[:2] == ("cplus", "verify"):
                    return completed(json.dumps({
                        "schema_version": 1, "verdict": current_verdict,
                        "summary": "reference test conflicts with agent test edits",
                        "infrastructure_error": None,
                        "gates": [{"name": "apply:reference", "status": "ERROR",
                                   "evidence": {"secret": "PRIVATE_CPLUS_LOG"}}],
                    }))
                return completed("")

            with (patch.object(verify_cases, "TEMP", temp),
                  patch.object(verify_cases, "quiet", side_effect=fake_quiet)):
                verdict, gates, _elapsed, reason = verify_cases.run_case("cpp-peglib-121", "codex-cli")
            self.assertEqual(verdict, "NOT_VERIFIABLE")
            self.assertEqual(gates, {})
            self.assertEqual(reason, "reference test conflicts with agent test edits")
            self.assertNotIn("PRIVATE_CPLUS_LOG", reason)
            current_verdict = "VERIFIED"
            with (patch.object(verify_cases, "TEMP", temp),
                  patch.object(verify_cases, "quiet", side_effect=fake_quiet)):
                with self.assertRaises(verify_cases.CaseExecutionError) as caught:
                    verify_cases.run_case("cpp-peglib-121", "codex-cli")
            self.assertEqual(caught.exception.public_reason, "parse: unexpected verifier check")

    def test_multi_test_reference_is_focused_for_bug_and_verified_by_name(self) -> None:
        source = Path(__file__).resolve().parents[1] / "cases" / "fmt-4490"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            case_dir = root / "cases" / "fmt-4490"
            case_dir.mkdir(parents=True)
            (case_dir / "case.yaml").write_bytes((source / "case.yaml").read_bytes())
            (case_dir / "agents" / "codex-cli").mkdir(parents=True)
            (case_dir / "agents" / "codex-cli" / "agent.yaml").write_bytes((source / "agents" / "codex-cli" / "agent.yaml").read_bytes())
            (case_dir / "agents" / "codex-cli" / "agent-fix.patch").write_bytes((source / "agents" / "codex-cli" / "agent-fix.patch").read_bytes())
            calls: list[tuple[str, ...]] = []

            def fake_quiet(*args: str, cwd: Path | None = None):
                calls.append(args)
                if args[:2] == ("git", "clone"):
                    Path(args[-1]).mkdir(parents=True, exist_ok=True)
                if args[:2] == ("git", "diff"):
                    return completed("diff --git a/test/a.cc b/test/a.cc\n")
                if args[:2] == ("cplus", "bug"):
                    Path(args[args.index("--export") + 1]).write_text("{}", encoding="utf-8")
                    return completed("REPRODUCED")
                if args[:2] == ("cplus", "verify"):
                    return completed(json.dumps({"schema_version": 1, "verdict": "REJECTED",
                                                 "infrastructure_error": None,
                                                 "gates": [], "summary": "still fails"}))
                return completed("")

            with (patch.object(verify_cases, "ROOT", root),
                  patch.object(verify_cases, "TEMP", root / "tmp"),
                  patch.object(verify_cases, "quiet", side_effect=fake_quiet)):
                verdict, _gates, _elapsed, _reason = verify_cases.run_case("fmt-4490", "codex-cli")
            self.assertEqual(verdict, "REJECTED")
            bug = next(call for call in calls if call[:2] == ("cplus", "bug"))
            selected = "memory_buffer_test.move_ctor_inline_buffer_non_propagating"
            self.assertIn(f"GTEST_FILTER={selected}", bug[bug.index("--command") + 1])
            verify = next(call for call in calls if call[:2] == ("cplus", "verify"))
            self.assertEqual(verify[verify.index("--reference-test-name") + 1], selected)

    def test_rejected_report_has_only_public_one_line_gate_reason(self) -> None:
        gate = {
            "name": "anti_cheat",
            "status": "FAIL",
            "evidence": {"reason": "protected test edited at test/test1.cc:756; checkout D:\\runner\\private\\case\nPRIVATE_CPLUS_LOG"},
        }
        reason = verify_cases.gate_reason(gate)
        report = verify_cases.render(
            "cpp-peglib-121", "REJECTED", {"anti_cheat": "FAIL"}, 0.9,
            "Codex CLI", "0.163.0", "2026-10-19 21:00:00 UTC", reason,
        )
        self.assertIn("Reason: protected test edited at test/test1.cc:756", report)
        self.assertIn("[path]", report)
        self.assertNotIn("D:\\runner", report)
        self.assertNotIn("PRIVATE_CPLUS_LOG", report)
        self.assertEqual(report.count("Reason:"), 1)

    def test_one_case_without_private_verifier_or_token(self) -> None:
        source = Path(__file__).resolve().parents[1] / "cases" / "cpp-peglib-121"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            case_dir = root / "cases" / "cpp-peglib-121"
            case_dir.mkdir(parents=True)
            case = json.loads((source / "case.yaml").read_text(encoding="utf-8"))
            (case_dir / "agents" / "codex-cli").mkdir(parents=True)
            agent = json.loads((source / "agents" / "codex-cli" / "agent.yaml").read_text(encoding="utf-8"))
            agent.update(name="MockAgent", version="2026.10", patch_sha256=hashlib.sha256(b"diff --git a/a b/a\n").hexdigest())
            (case_dir / "agents" / "codex-cli" / "agent.yaml").write_text(json.dumps(agent), encoding="utf-8")
            (case_dir / "case.yaml").write_text(json.dumps(case), encoding="utf-8")
            (case_dir / "agents" / "codex-cli" / "agent-fix.patch").write_bytes(b"diff --git a/a b/a\n")
            calls: list[tuple[str, ...]] = []

            def fake_quiet(*args: str, cwd: Path | None = None):
                calls.append(args)
                if args[:2] == ("git", "clone"):
                    Path(args[-1]).mkdir(parents=True)
                    return completed("")
                if args[:2] == ("git", "diff"):
                    return completed("diff --git a/a b/a\n")
                if args[:2] == ("cplus", "bug"):
                    Path(args[args.index("--export") + 1]).write_text("{}", encoding="utf-8")
                    return completed("REPRODUCED — bug reproduced in 3/3 runs")
                if args[:2] == ("cplus", "verify"):
                    report = {
                        "schema_version": 1,
                        "verdict": "VERIFIED",
                        "infrastructure_error": None,
                        "gates": [{"name": name, "status": "PASS", "evidence": {"private": "TOKEN_SENTINEL D:\\private\\cplus PRIVATE_CPLUS_LOG"}}
                                  for name in verify_cases.GATES],
                    }
                    return completed(json.dumps(report) + "\nVERIFIED")
                return completed("")

            public_log = io.StringIO()
            with (patch.object(verify_cases, "ROOT", root),
                  patch.object(verify_cases, "RESULTS_DIR", root / "results"),
                  patch.object(verify_cases, "TEMP", root / "tmp"),
                  patch.object(verify_cases, "quiet", side_effect=fake_quiet),
                  patch.dict("os.environ", {"SELECT_CASE": "cpp-peglib-121"}),
                  contextlib.redirect_stdout(public_log)):
                self.assertEqual(verify_cases.main(), 0)
            result = (root / "results" / "cpp-peglib-121" / "codex-cli.md").read_text(encoding="utf-8")
            self.assertIn("Verdict: **VERIFIED**", result)
            self.assertRegex(result, rf"Verifier: cplus {verify_cases.VERIFIER_REVISION} · \d{{4}}-\d{{2}}-\d{{2}} \d{{2}}:\d{{2}}:\d{{2}} UTC")
            self.assertIn("Agent: MockAgent · Version: 2026.10", result)
            self.assertEqual(result.count("| PASS |"), 8)
            self.assertIn("| anti_cheat | PASS |", result)
            for sensitive in ("TOKEN_SENTINEL", "D:\\private\\cplus", "PRIVATE_CPLUS_LOG"):
                self.assertNotIn(sensitive, result)
                self.assertNotIn(sensitive, public_log.getvalue())
            self.assertTrue(any(call[:2] == ("cplus", "bug") for call in calls))
            self.assertTrue(any(call[:2] == ("cplus", "verify") for call in calls))
            verify_call = next(call for call in calls if call[:2] == ("cplus", "verify"))
            self.assertEqual(
                Path(verify_call[verify_call.index("--reference-test-from-fix") + 1]).name,
                "cpp-peglib-121-codex-cli-upstream.patch",
            )

    def test_reference_test_reason_is_public_for_verified_and_rejected(self) -> None:
        summary = (
            "judged by upstream reference test 'printf_test.zero_positional_width_precision'; "
            "fix proven"
        )
        self.assertEqual(verify_cases.summary_reason(summary, "fallback"), summary)
        report = verify_cases.render(
            "fmt-4800", "VERIFIED", {}, 1.0, "Codex CLI", "0.163.0",
            "2026-10-20 18:00:00 UTC", summary,
        )
        self.assertIn(f"Reason: {summary}", report)

    def test_reference_reason_is_used_even_when_a_gate_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)

            def fake_quiet(*args: str, cwd: Path | None = None):
                if args[:2] == ("git", "clone"):
                    Path(args[-1]).mkdir(parents=True, exist_ok=True)
                if args[:2] == ("git", "diff"):
                    return completed("diff --git a/test.cc b/test.cc\n")
                if args[:2] == ("cplus", "bug"):
                    Path(args[args.index("--export") + 1]).write_text("{}", encoding="utf-8")
                    return completed("REPRODUCED")
                if args[:2] == ("cplus", "verify"):
                    return completed(json.dumps({
                        "schema_version": 1, "verdict": "REJECTED",
                        "summary": "judged by upstream reference test 'Regression'; still fails",
                        "infrastructure_error": None,
                        "gates": [{"name": "repro:patched", "status": "FAIL",
                                   "evidence": {"reason": "the reproducer still fails"}}],
                    }))
                return completed("")

            with (patch.object(verify_cases, "TEMP", temp),
                  patch.object(verify_cases, "quiet", side_effect=fake_quiet)):
                verdict, gates, _elapsed, reason = verify_cases.run_case("cpp-peglib-121", "codex-cli")
            self.assertEqual(verdict, "REJECTED")
            self.assertEqual(gates["repro:patched"], "FAIL")
            self.assertEqual(reason, "judged by upstream reference test 'Regression'; still fails")

    def test_empty_patch_skips_verifier_and_says_no_agent_fix_yet(self) -> None:
        source = Path(__file__).resolve().parents[1] / "cases" / "cpp-peglib-121"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            case_dir = root / "cases" / "cpp-peglib-121"
            case_dir.mkdir(parents=True)
            case = json.loads((source / "case.yaml").read_text(encoding="utf-8"))
            (case_dir / "agents" / "codex-cli").mkdir(parents=True)
            agent = json.loads((source / "agents" / "codex-cli" / "agent.yaml").read_text(encoding="utf-8"))
            agent.update(name="not run", version=None, patch_sha256=None)
            (case_dir / "agents" / "codex-cli" / "agent.yaml").write_text(json.dumps(agent), encoding="utf-8")
            (case_dir / "case.yaml").write_text(json.dumps(case), encoding="utf-8")
            (case_dir / "agents" / "codex-cli" / "agent-fix.patch").write_bytes(b"")
            public_log = io.StringIO()
            with (patch.object(verify_cases, "ROOT", root),
                  patch.object(verify_cases, "RESULTS_DIR", root / "results"),
                  patch.object(verify_cases, "TEMP", root / "tmp"),
                  patch.object(verify_cases, "quiet", side_effect=AssertionError("cplus must not run")),
                  patch.dict("os.environ", {"SELECT_CASE": "cpp-peglib-121"}),
                  contextlib.redirect_stdout(public_log)):
                self.assertEqual(verify_cases.main(), 0)
            self.assertIn("no agent fix yet", public_log.getvalue())
            result = (root / "results" / "cpp-peglib-121" / "codex-cli.md").read_text(encoding="utf-8")
            self.assertIn("Status: no agent fix yet", result)
            self.assertIn("(configured; not run)", result)
            self.assertIn("Agent: not run · Version: not recorded", result)


def completed(stdout: str, returncode: int = 0):
    from subprocess import CompletedProcess
    return CompletedProcess(args=(), returncode=returncode, stdout=stdout, stderr="")


if __name__ == "__main__":
    unittest.main()

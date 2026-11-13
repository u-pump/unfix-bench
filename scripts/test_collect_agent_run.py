# SPDX-License-Identifier: MIT
# Copyright (c) 2026 U-Pump
"""Offline tests of the Claude Code evidence, network-attempt and secret-scan logic."""

from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import collect_agent_run as collect

INIT = {"type": "system", "subtype": "init", "model": "claude-opus-5-5", "session_id": "s-1"}
SUCCESS = {"type": "result", "subtype": "success", "is_error": False}
FAILURE = {"type": "result", "subtype": "error_during_execution", "is_error": True}


def tool_use(name: str, tool_id: str, **tool_input: str) -> dict[str, object]:
    block = {"type": "tool_use", "name": name, "id": tool_id, "input": tool_input}
    return {"type": "assistant", "message": {"content": [block]}}


def tool_result(tool_id: str, content: str, is_error: bool = False) -> dict[str, object]:
    block = {"type": "tool_result", "tool_use_id": tool_id, "is_error": is_error, "content": content}
    return {"type": "user", "message": {"content": [block]}}


class EvidenceTest(unittest.TestCase):
    def test_completed_attempt_returns_model_and_session(self) -> None:
        events = [INIT, tool_use("Bash", "b1", command="ctest"), tool_result("b1", "100% passed"), SUCCESS]
        self.assertEqual(
            collect.evidence(events), {"model": "claude-opus-5-5", "session_id": "s-1"}
        )

    def test_incomplete_runs_are_not_attempts(self) -> None:
        bash = [tool_use("Bash", "b1", command="ctest")]
        cases = {
            "no init": [SUCCESS],
            "no result": [INIT, *bash, tool_result("b1", "ok")],
            "failed result": [INIT, *bash, tool_result("b1", "ok"), FAILURE],
            "no bash": [INIT, tool_use("Edit", "e1"), tool_result("e1", "edited"), SUCCESS],
            "bash error": [INIT, *bash, tool_result("b1", "boom", is_error=True), SUCCESS],
            "bash exit 1": [INIT, *bash, tool_result("b1", "Exit code: 1\nfailed"), SUCCESS],
        }
        for name, events in cases.items():
            with self.subTest(name), self.assertRaises(collect.AttemptNotRecorded):
                collect.evidence(events)


class NetworkAttemptsTest(unittest.TestCase):
    def test_commands_errors_and_proxy_hosts_are_summarized_without_urls(self) -> None:
        events = [
            INIT,
            tool_use("Bash", "n1", command="curl https://example.com/private/path"),
            tool_use("WebSearch", "n2"),
            tool_use("Bash", "b1", command="cmake --build build"),
            tool_result("n1", "curl: (6) Could not resolve host: example.com", True),
            tool_result("b1", "Temporary failure in name resolution"),
            SUCCESS,
        ]
        log = (
            'INFO Proxying refused on filtered domain "github.com"\n'
            'INFO Established connection to host "api.anthropic.com" using file descriptor 7.\n'
        )
        result = collect.network_attempts(events, log)
        self.assertEqual(result["count"], 3)
        self.assertEqual(result["commands"], ["WebSearch", "curl", "network error"])
        self.assertEqual(result["proxy_denied_hosts"], ["github.com"])
        self.assertEqual(result["proxy_allowed_hosts"], ["api.anthropic.com"])
        self.assertNotIn("example.com", json.dumps(result))

    def test_a_quiet_run_has_no_attempts(self) -> None:
        result = collect.network_attempts([INIT, SUCCESS])
        self.assertEqual((result["count"], result["commands"]), (0, []))


class SecretScanTest(unittest.TestCase):
    def test_token_and_token_shaped_strings_are_found_without_printing_them(self) -> None:
        token = "sk-ant-api03-" + "a" * 40
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            clean = root / "clean.txt"
            clean.write_text("nothing here", encoding="utf-8")
            exact = root / "exact.txt"
            exact.write_text(f"echo {token}", encoding="utf-8")
            shaped = root / "shaped.txt"
            shaped.write_text("sk-ant-" + "b" * 30, encoding="utf-8")
            hits = collect.scan_for_secret([clean, exact, shaped], token)
        self.assertEqual(sorted(hits), ["exact.txt", "shaped.txt"])

    def test_a_hit_removes_every_file_and_fails(self) -> None:
        token = "custom-token-value-123456"
        with tempfile.TemporaryDirectory() as directory:
            first, second = Path(directory, "a.txt"), Path(directory, "b.txt")
            first.write_text("fine", encoding="utf-8")
            second.write_text(f"leak {token}", encoding="utf-8")
            output = io.StringIO()
            with (patch.dict(os.environ, {collect.TOKEN_ENV: token}),
                  contextlib.redirect_stdout(output)):
                code = collect.main(["scan", str(first), str(second)])
            self.assertEqual(code, 4)
            self.assertFalse(first.exists() or second.exists())
        self.assertNotIn(token, output.getvalue())

    def test_a_clean_scan_keeps_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "a.txt")
            path.write_text("fine", encoding="utf-8")
            with patch.dict(os.environ, {collect.TOKEN_ENV: "x" * 30}), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(collect.main(["scan", str(path)]), 0)
            self.assertTrue(path.exists())


class RecordTest(unittest.TestCase):
    def record(self, patch_bytes: bytes) -> dict[str, object]:
        events = [
            INIT,
            tool_use("Bash", "b1", command="ctest --secret-marker-xyz"),
            tool_result("b1", "ok"),
            tool_use("Edit", "e1"),
            tool_result("e1", "edited"),
            {**SUCCESS, "num_turns": 7},
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "t.jsonl").write_text("\n".join(json.dumps(e) for e in events), encoding="utf-8")
            (root / "p.patch").write_bytes(patch_bytes)
            with contextlib.redirect_stdout(io.StringIO()):
                code = collect.main([
                    "record", "--transcript", str(root / "t.jsonl"), "--patch", str(root / "p.patch"),
                    "--out-dir", str(root), "--version", "2.1.323 (Claude Code)",
                    "--requested-model", "claude-opus-5-5", "--run-url", "https://example.invalid/run",
                    "--image", "sha256:abc", "--duration-seconds", "42",
                ])
            self.assertEqual(code, 0)
            text = (root / "agent.yaml").read_text(encoding="utf-8")
            self.assertNotIn("secret-marker-xyz", text)  # the transcript content is never copied
            return json.loads(text)

    def test_patch_run_records_hash_model_and_version(self) -> None:
        data = self.record(b"diff --git a/a b/a\n+x\n")
        self.assertEqual(data["model"], "claude-opus-5-5")
        self.assertEqual(data["version"], "2.1.323 (Claude Code)")
        self.assertEqual(len(str(data["patch_sha256"])), 64)
        self.assertNotIn("outcome", data)
        self.assertEqual(
            data["metrics"],
            {"bash_commands": 1, "tool_calls": 2, "turns": 7, "duration_seconds": 42, "tokens": None},
        )
        for key in ("name", "invocation", "date_utc", "environment", "attempt_note"):
            self.assertTrue(data[key])

    def test_empty_patch_is_recorded_as_no_patch(self) -> None:
        data = self.record(b"")
        self.assertIsNone(data["patch_sha256"])
        self.assertEqual(data["outcome"], "NO_PATCH")

    def test_error_report_is_public_and_has_no_patch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with contextlib.redirect_stdout(io.StringIO()):
                collect.main(["error", "--case", "fmt-4800", "--reason", "input: input_sha256 mismatch",
                              "--results-dir", directory])
            text = Path(directory, "fmt-4800", "claude-code.md").read_text(encoding="utf-8")
        self.assertIn("Verdict: **INFRASTRUCTURE_ERROR**", text)
        self.assertIn("Reason: input: input_sha256 mismatch", text)
        self.assertIn("Patch: sha256 pending", text)


if __name__ == "__main__":
    unittest.main()

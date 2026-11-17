# SPDX-License-Identifier: MIT
# Copyright (c) 2026 U-Pump
"""Offline tests of the Codex CLI evidence, diagnosis and secret-scan logic (collect_codex_run.py)."""

from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import collect_codex_run as collect

ROOT = Path(__file__).resolve().parents[1]
THREAD = {"type": "thread.started", "thread_id": "t-1"}
TURN = {"type": "turn.started"}
DONE = {"type": "turn.completed", "usage": {"input_tokens": 100, "cached_input_tokens": 40,
                                              "output_tokens": 10, "reasoning_output_tokens": 4}}
FAILED = {"type": "turn.failed", "error": {"message": "unexpected status 401 Unauthorized: Incorrect API key"}}


def command(item_id: str, text: str, code: int | None = 0, output: str = "", status: str = "completed") -> dict[str, object]:
    item = {"id": item_id, "type": "command_execution", "command": text, "aggregated_output": output,
            "exit_code": code, "status": status}
    return {"type": "item.completed", "item": item}


class EvidenceTest(unittest.TestCase):
    def test_completed_attempt_returns_the_thread_id(self) -> None:
        events = [THREAD, TURN, command("i0", "ctest"), DONE]
        self.assertEqual(collect.evidence(events), {"session_id": "t-1"})

    def test_incomplete_runs_are_not_attempts(self) -> None:
        message = {"type": "item.completed", "item": {"id": "i1", "type": "agent_message"}}
        cases = {
            "no thread": [TURN, command("i0", "ctest"), DONE],
            "no finished turn": [THREAD, TURN, command("i0", "ctest")],
            "failed turn": [THREAD, TURN, command("i0", "ctest"), FAILED],
            "no command": [THREAD, TURN, message, DONE],
            "command failed": [THREAD, TURN, command("i0", "ctest", code=1), DONE],
            "command never finished": [THREAD, TURN, command("i0", "ctest", code=None, status="in_progress"), DONE],
        }
        for name, events in cases.items():
            with self.subTest(name), self.assertRaises(collect.AttemptNotRecorded):
                collect.evidence(events)

    def test_reconnect_errors_do_not_hide_a_completed_attempt(self) -> None:
        events = [THREAD, TURN, {"type": "error", "message": "Reconnecting... 1/5"}, command("i0", "ctest"), DONE]
        self.assertEqual(collect.evidence(events)["session_id"], "t-1")


class NetworkAndMetricsTest(unittest.TestCase):
    def test_network_commands_are_named_without_urls(self) -> None:
        search = {"type": "item.completed", "item": {"id": "n4", "type": "web_search", "query": "secret"}}
        events = [
            THREAD,
            command("n1", "curl https://example.com/private/path"),
            command("n2", "ls", output="Could not resolve host: x"),
            command("n3", "cmake --build build"),
            search,
        ]
        log = 'refused on filtered domain "chatgpt.com"\nEstablished connection to host "api.openai.com"\n'
        found = collect.network_attempts(events, log)
        self.assertEqual(found["commands"], ["curl", "network error", "web_search"])
        self.assertEqual(found["count"], 3)
        self.assertEqual(found["proxy_denied_hosts"], ["chatgpt.com"])
        self.assertNotIn("example.com", json.dumps(found))

    def test_metrics_count_items_once_and_sum_the_turns(self) -> None:
        started = {"type": "item.started", "item": {"id": "i0", "type": "command_execution", "command": "ctest",
                                                    "status": "in_progress"}}
        edit = {"type": "item.completed", "item": {"id": "i2", "type": "file_change"}}
        events = [THREAD, TURN, started, command("i0", "ctest"), command("i1", "ls"), edit, DONE, DONE]
        metrics = collect.transcript_metrics(events, 90)
        self.assertEqual((metrics["bash_commands"], metrics["tool_calls"], metrics["turns"], metrics["duration_seconds"]),
                         (2, 3, 2, 90))
        self.assertEqual(metrics["tokens"], {"input": 200, "cached_input": 80, "output": 20, "reasoning_output": 8})
        self.assertIsNone(collect.transcript_metrics([THREAD], 1)["tokens"])


class DiagnosisTest(unittest.TestCase):
    def test_a_refused_key_is_classified_from_the_real_event_shapes(self) -> None:
        # the shapes `codex exec --json` printed for a deliberately wrong key
        reconnect = {"type": "error", "message": "Reconnecting... 2/5 (unexpected status 401 Unauthorized: "
                                                 "Incorrect API key provided: sk-probe****)"}
        fallback = {"type": "item.completed", "item": {"id": "i0", "type": "error", "message": "Falling back"}}
        found = collect.diagnose_failure([THREAD, TURN, reconnect, fallback, FAILED])
        self.assertEqual(found["http_status"], 401)
        self.assertIn("refused the key", found["problem"])
        self.assertEqual(found["model_responses"], 0)
        line = collect.describe_failure(found, 1)
        self.assertEqual(line, "agent: Codex CLI exited with code 1; API refused the key: invalid, disabled, "
                               "deleted or from another project (HTTP 401); the model gave no response")
        self.assertNotIn("sk-", line)

    def test_other_problems_use_fixed_phrases(self) -> None:
        cases = {
            "You exceeded your current quota, please check your plan and billing details": "quota exhausted",
            "unexpected status 429 Too Many Requests": "rate limit",
            "The model x does not exist or you do not have access to it": "model is not available",
            "unexpected status 503 Service Unavailable": "temporarily unavailable",
        }
        for message, expected in cases.items():
            with self.subTest(message):
                found = collect.diagnose_failure([THREAD, {"type": "turn.failed", "error": {"message": message}}])
                self.assertIn(expected, found["problem"])

    def test_an_unknown_failure_says_so_and_counts_responses(self) -> None:
        failed = {"type": "turn.failed", "error": {"message": "weird"}}
        found = collect.diagnose_failure([THREAD, command("i0", "ls"), failed])
        self.assertIn("unclassified", found["problem"])
        self.assertEqual(found["model_responses"], 1)


class SecretScanTest(unittest.TestCase):
    def test_key_shaped_strings_and_the_key_itself_are_found(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            clean, shaped, exact = root / "clean.txt", root / "shaped.txt", root / "exact.txt"
            clean.write_text("nothing here", encoding="utf-8")
            shaped.write_text("key sk-proj-" + "a" * 30, encoding="utf-8")
            exact.write_text("my-secret-value-1234567890", encoding="utf-8")
            self.assertEqual(collect.scan_for_secret([clean], "my-secret-value-1234567890"), [])
            self.assertEqual(collect.scan_for_secret([shaped, clean], None), ["shaped.txt"])
            self.assertEqual(collect.scan_for_secret([exact], "my-secret-value-1234567890"), ["exact.txt"])

    def test_scan_deletes_every_file_when_something_leaks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            a, b = Path(directory) / "a", Path(directory) / "b"
            a.write_text("fine", encoding="utf-8")
            b.write_text("sk-" + "x" * 40, encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()), patch.dict(os.environ, {}, clear=False):
                self.assertEqual(collect.main(["scan", str(a), str(b)]), 4)
            self.assertFalse(a.exists() or b.exists())


class RecordTest(unittest.TestCase):
    def build(self, patch_bytes: bytes) -> dict[str, object]:
        return collect.build_agent_yaml(
            version="0.164.0", requested_model="gpt-6-sol", session_id="t-1", patch_bytes=patch_bytes,
            attempt={"commands": []}, run_url="https://example.invalid/run", image="sha256:x", proof_note="ok",
            date_utc="2026-11-18T00:00:00Z", metrics={}, proxy={},
        )

    def test_agent_yaml_has_what_the_verifier_requires_and_names_the_codex_conditions(self) -> None:
        data = self.build(b"diff\n")
        required = {"name", "version", "model", "invocation", "date_utc", "environment", "patch_sha256", "attempt_note"}
        self.assertLessEqual(required, data.keys())
        self.assertTrue(all(data[key] for key in required))
        self.assertEqual((data["name"], data["model"], data["reasoning"]), ("Codex CLI", "gpt-6-sol", "medium"))
        self.assertIn("api.openai.com:443", str(data["environment"]))
        self.assertIn("--dangerously-bypass-approvals-and-sandbox", str(data["invocation"]))
        self.assertNotIn("outcome", data)

    def test_an_empty_patch_is_a_recorded_no_patch(self) -> None:
        data = self.build(b"")
        self.assertEqual((data["patch_sha256"], data["outcome"]), (None, "NO_PATCH"))

    def test_the_invocation_in_agent_yaml_is_the_one_the_sandbox_runs(self) -> None:
        script = (ROOT / "scripts" / "agent_sandbox.sh").read_text(encoding="utf-8")
        invocation = str(self.build(b"x")["invocation"])
        for flag in ("--json", "--ephemeral", "--skip-git-repo-check", "--ignore-user-config", "--ignore-rules",
                     "--strict-config", "--dangerously-bypass-approvals-and-sandbox", "project_doc_max_bytes=0"):
            self.assertIn(flag, invocation)
            self.assertIn(flag, script)
        for feature in ("apps", "browser_use", "computer_use", "plugins", "hooks", "multi_agent", "image_generation"):
            self.assertIn(f"--disable {feature}", invocation)
            self.assertIn(f"--disable {feature}", script)

    def test_error_report_is_written_for_codex(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with contextlib.redirect_stdout(io.StringIO()):
                collect.main(["error", "--case", "demo-1", "--reason", "agent: no result", "--results-dir", directory])
            text = (Path(directory) / "demo-1" / "codex-cli.md").read_text(encoding="utf-8")
            self.assertIn("INFRASTRUCTURE_ERROR", text)
            self.assertIn("Agent: Codex CLI", text)


if __name__ == "__main__":
    unittest.main()

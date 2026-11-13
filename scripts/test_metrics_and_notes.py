# SPDX-License-Identifier: MIT
# Copyright (c) 2026 U-Pump
"""Proxy-counted network traffic, token totals and the attempt/network lines of a report."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import collect_agent_run as collect
import verify_cases

PROOF = """\
CONNECT   Nov 13 21:12:10.1 [1]: Request (file descriptor 5): CONNECT github.com:443 HTTP/1.1
NOTICE    Nov 13 21:12:10.1 [1]: Proxying refused on filtered domain "github.com"
CONNECT   Nov 13 21:12:10.3 [1]: Request (file descriptor 5): CONNECT example.com:443 HTTP/1.1
NOTICE    Nov 13 21:12:10.3 [1]: Proxying refused on filtered domain "example.com"
CONNECT   Nov 13 21:12:10.4 [1]: Request (file descriptor 5): CONNECT api.anthropic.com:8443 HTTP/1.1
INFO      Nov 13 21:12:10.4 [1]: Refused CONNECT method on port 8443
CONNECT   Nov 13 21:12:10.6 [1]: Request (file descriptor 5): CONNECT api.anthropic.com:443 HTTP/1.1
CONNECT   Nov 13 21:12:10.6 [1]: Established connection to host "api.anthropic.com" using file descriptor 6.
"""
AGENT = """\
CONNECT   Nov 13 21:12:39.9 [1]: Request (file descriptor 5): CONNECT api.anthropic.com:443 HTTP/1.1
CONNECT   Nov 13 21:12:39.9 [1]: Established connection to host "api.anthropic.com" using file descriptor 7.
NOTICE    Nov 13 21:12:39.98 [1]: Proxying refused on filtered domain "github.com"
NOTICE    Nov 13 21:12:39.99 [1]: Proxying refused on filtered domain "github.com"
NOTICE    Nov 13 21:12:40.00 [1]: Proxying refused on filtered domain "github.com"
CONNECT   Nov 13 21:12:41.0 [1]: Established connection to host "api.anthropic.com" using file descriptor 8.
"""


class ProxyTrafficTest(unittest.TestCase):
    def test_the_proof_is_excluded_and_the_agent_refusals_are_counted(self) -> None:
        traffic = collect.agent_proxy_traffic(PROOF + AGENT, PROOF)
        self.assertEqual(traffic["refused_requests"], 3)
        self.assertEqual(traffic["refused"], {"github.com": 3})
        self.assertEqual(traffic["allowed_connections"], {"api.anthropic.com": 2})

    def test_a_clean_agent_run_has_zero_refusals(self) -> None:
        only_api = AGENT.replace('Proxying refused on filtered domain "github.com"', "INFO other")
        traffic = collect.agent_proxy_traffic(PROOF + only_api, PROOF)
        self.assertEqual(traffic["refused_requests"], 0)
        self.assertEqual(traffic["refused"], {})

    def test_the_whole_log_counts_the_proof_too_when_no_snapshot_exists(self) -> None:
        traffic = collect.agent_proxy_traffic(PROOF + AGENT)
        self.assertEqual(traffic["refused"], {"api.anthropic.com:8443": 1, "example.com": 1, "github.com": 4})

    def test_a_refused_port_is_attributed_to_the_requested_host(self) -> None:
        counts = collect.proxy_counts(PROOF)
        self.assertEqual(counts["denied"]["api.anthropic.com:8443"], 1)


class TokenTest(unittest.TestCase):
    USAGE = {"input_tokens": 12, "output_tokens": 3400, "cache_creation_input_tokens": 500, "cache_read_input_tokens": 90000}

    def test_result_usage_gives_the_totals(self) -> None:
        events = [{"type": "result", "usage": self.USAGE}]
        self.assertEqual(collect.token_usage(events), {
            "input": 12, "output": 3400, "cache_creation_input": 500, "cache_read_input": 90000,
        })

    def test_without_a_result_usage_the_assistant_messages_are_summed_once_each(self) -> None:
        message = {"id": "m1", "usage": {"input_tokens": 5, "output_tokens": 7}}
        events = [
            {"type": "assistant", "message": message},
            {"type": "assistant", "message": message},  # the same message repeated by the stream
            {"type": "assistant", "message": {"id": "m2", "usage": {"input_tokens": 1, "output_tokens": 2}}},
        ]
        totals = collect.token_usage(events)
        assert totals is not None
        self.assertEqual((totals["input"], totals["output"]), (6, 9))

    def test_no_usage_means_none_not_zero(self) -> None:
        self.assertIsNone(collect.token_usage([{"type": "result", "subtype": "success"}]))
        self.assertIsNone(collect.transcript_metrics([], 5)["tokens"])

    def test_metrics_carry_only_numbers(self) -> None:
        metrics = collect.transcript_metrics([{"type": "result", "usage": self.USAGE, "num_turns": 3}], 9)
        self.assertTrue(all(isinstance(v, int) for v in metrics["tokens"].values()))
        self.assertEqual(metrics["turns"], 3)


class ReportLinesTest(unittest.TestCase):
    def report_dir(self, files: dict[str, str]) -> Path:
        root = Path(tempfile.mkdtemp())
        self.addCleanup(__import__("shutil").rmtree, root, True)
        for name, text in files.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        return root

    def test_attempt_and_network_lines_appear_in_the_rendered_report(self) -> None:
        text = verify_cases.render("c-1", "REJECTED", {}, 1.0, "Claude Code", "2", "now", "r", "n", None, None,
                                   "First attempt lost to a stand error; this is the rerun.",
                                   "the proxy refused 3 request(s) (github.com x3)")
        self.assertIn("\n\nAttempt: First attempt lost to a stand error; this is the rerun.\n", text)
        self.assertIn("\n\nNetwork: the proxy refused 3 request(s) (github.com x3)\n", text)

    def test_no_lines_when_there_is_nothing_to_say(self) -> None:
        text = verify_cases.render("c-1", "REJECTED", {}, 1.0, "Codex CLI", "1", "now")
        self.assertNotIn("Attempt:", text)
        self.assertNotIn("Network:", text)

    def test_attempt_note_file_is_read_and_must_be_one_line(self) -> None:
        root = self.report_dir({"cases/c-1/agents/claude-code/attempt-note.txt": "Rerun after a stand error.\n"})
        with patch.object(verify_cases, "ROOT", root):
            self.assertEqual(verify_cases.agent_attempt_note("c-1", "claude-code"), "Rerun after a stand error.")
            self.assertIsNone(verify_cases.agent_attempt_note("c-2", "claude-code"))
        root = self.report_dir({"cases/c-1/agents/claude-code/attempt-note.txt": "two\nlines"})
        with patch.object(verify_cases, "ROOT", root), self.assertRaises(verify_cases.CaseExecutionError):
            verify_cases.agent_attempt_note("c-1", "claude-code")

    def test_network_note_comes_from_the_recorded_proxy_counts_and_not_for_codex(self) -> None:
        proxy = {"refused_requests": 3, "refused": {"github.com": 3}, "allowed_connections": {"api.anthropic.com": 9}}
        root = self.report_dir({
            "cases/c-1/agents/claude-code/agent.yaml": json.dumps({"proxy": proxy}),
            "cases/c-1/agents/codex-cli/agent.yaml": json.dumps({"name": "Codex"}),
        })
        with patch.object(verify_cases, "ROOT", root):
            note = verify_cases.agent_network_note("c-1", "claude-code")
            assert note is not None
            self.assertIn("refused 3 request(s)", note)
            self.assertIn("github.com x3", note)
            self.assertIn("api.anthropic.com x9", note)
            self.assertIsNone(verify_cases.agent_network_note("c-1", "codex-cli"))

    def test_recorded_yaml_has_proxy_counts_tokens_and_the_note(self) -> None:
        data = collect.build_agent_yaml(
            version="2", model="m", requested_model="m", session_id="s", patch_bytes=b"diff\n",
            attempt={"commands": ["curl"]}, run_url="u", image="i", proof_note="p", date_utc="d",
            metrics={"tokens": {"input": 1}}, proxy=collect.agent_proxy_traffic(PROOF + AGENT, PROOF),
            attempt_note="Rerun after a stand error.",
        )
        self.assertEqual(data["attempt_note"], "Rerun after a stand error.")
        self.assertEqual(data["proxy"]["refused"], {"github.com": 3})
        self.assertEqual(data["network_commands_seen_in_transcript"], ["curl"])
        self.assertNotIn("proxy_hosts", data)
        self.assertNotIn("network_attempts", data)


if __name__ == "__main__":
    unittest.main()

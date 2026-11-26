# SPDX-License-Identifier: MIT
# Copyright (c) 2026 U-Pump
"""Static checks of the Codex CLI workflow and sandbox: the conditions must stay the ones the protocol states."""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

import plan_cases

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github" / "workflows" / "run-codex.yml").read_text(encoding="utf-8")
CLAUDE_WORKFLOW = (ROOT / ".github" / "workflows" / "run-claude-code.yml").read_text(encoding="utf-8")
SANDBOX = (ROOT / "scripts" / "agent_sandbox.sh").read_text(encoding="utf-8")
DOCKERFILE = (ROOT / "docker" / "claude-agent" / "Dockerfile").read_text(encoding="utf-8")


def job(text: str, name: str) -> str:
    start = text.index(f"\n  {name}:")
    rest = text[start + 1:]
    following = [i for i in (rest.find("\n  " + other + ":")
                             for other in ("plan", "probe", "agent", "verify", "record")) if i > 0]
    return rest[: min(following)] if following else rest


class WorkflowTest(unittest.TestCase):
    def test_it_is_owner_only_manual_and_has_the_two_inputs(self) -> None:
        self.assertIn("workflow_dispatch:", WORKFLOW)
        for name in ("case_id", "probe_only"):
            self.assertRegex(WORKFLOW, rf"(?m)^      {name}:$")
        for name in ("plan", "probe", "agent", "verify", "record"):
            self.assertIn("github.actor == 'u-pump'", job(WORKFLOW, name), name)

    def test_the_pull_request_trigger_is_the_probe_only(self) -> None:
        self.assertRegex(job(WORKFLOW, "probe"), r"if: \$\{\{ \(github\.event_name != 'workflow_dispatch' \|\| inputs\.probe_only\)")
        for name in ("plan", "agent", "verify", "record"):
            self.assertIn("github.event_name == 'workflow_dispatch'", job(WORKFLOW, name), name)

    def test_the_key_reaches_only_the_attempt_and_the_scan_after_it(self) -> None:
        self.assertEqual(len(re.findall(r"secrets\.OPENAI_API_KEY", WORKFLOW)), 2)
        self.assertNotIn("OPENAI_API_KEY", job(WORKFLOW, "probe"))
        self.assertNotIn("OPENAI_API_KEY", job(WORKFLOW, "verify"))
        self.assertNotIn("OPENAI_API_KEY", job(WORKFLOW, "record"))
        self.assertNotRegex(WORKFLOW, r"(?i)anthropic")

    def test_the_agent_and_the_model_are_fixed(self) -> None:
        self.assertRegex(WORKFLOW, r"(?m)^  AGENT_MODEL: gpt-6-sol$")
        self.assertRegex(WORKFLOW, r"(?m)^  SANDBOX_AGENT: codex$")
        self.assertRegex(DOCKERFILE, r"(?m)^ARG CODEX_CLI_VERSION=\d+\.\d+\.\d+$")
        self.assertIn('"@openai/codex@${CODEX_CLI_VERSION}"', DOCKERFILE)
        self.assertIn('test "$(codex --version', DOCKERFILE)  # the build fails if the version drifts
        self.assertIn("""-c 'model_reasoning_effort="medium"'""", SANDBOX)

    def test_model_effort_and_the_newest_version_are_the_ones_the_first_ten_cases_used(self) -> None:
        recorded = []
        with_patch = 0
        for path in sorted((ROOT / "cases").glob("*/agents/codex-cli/agent.yaml")):
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("patch_sha256"):
                with_patch += 1
            if data.get("version"):
                recorded.append((data["version"], data["model"], data["reasoning"]))
        # The count grows with every merged Codex attempt of a later batch, so it is not a constant: a case counts
        # as recorded when its agent.yaml names a version, and that must be exactly the cases that saved a patch.
        # The ten first cases and coremqtt-331 are the floor; a placeholder (all null) stays out of the count.
        self.assertGreaterEqual(len(recorded), 11)
        self.assertEqual(len(recorded), with_patch)
        self.assertEqual({(model, effort) for _, model, effort in recorded}, {("gpt-6-sol", "medium")})
        newest = max((tuple(int(x) for x in version.split(".")), version) for version, _, _ in recorded)[1]
        self.assertIn(f"ARG CODEX_CLI_VERSION={newest}", DOCKERFILE)  # eight cases used it, two used 0.163.0
        self.assertRegex(WORKFLOW, r"(?m)^  AGENT_MODEL: gpt-6-sol$")
        self.assertIn('model_reasoning_effort="medium"', SANDBOX)

    def test_actions_are_pinned_by_commit_and_match_the_claude_workflow(self) -> None:
        uses = re.findall(r"(?m)^\s*- uses: (\S+)", WORKFLOW)
        self.assertTrue(uses)
        for item in uses:
            self.assertRegex(item, r"@[0-9a-f]{40}$")
        self.assertEqual(sorted(set(uses)), sorted(set(re.findall(r"(?m)^\s*- uses: (\S+)", CLAUDE_WORKFLOW))))

    def test_one_attempt_per_case_is_planned_for_codex_and_the_patch_is_recorded_unchanged(self) -> None:
        self.assertIn("plan_cases.py --agent codex-cli", WORKFLOW)
        self.assertIn("run_codex_case.sh", WORKFLOW)
        self.assertIn("SELECT_AGENT: codex-cli", job(WORKFLOW, "verify"))
        self.assertIn("scripts/render_readme.py --check", WORKFLOW)
        self.assertNotIn("claude-code", WORKFLOW.replace("Claude Code", ""))

    def test_the_scan_runs_before_every_upload(self) -> None:
        for name in ("probe", "agent", "verify"):
            block = job(WORKFLOW, name)
            self.assertIn("collect_codex_run.py scan", block, name)
            self.assertLess(block.index("collect_codex_run.py scan"), block.index("upload-artifact"), name)

    def test_the_workflow_is_linted_by_ci(self) -> None:
        verify = (ROOT / ".github" / "workflows" / "verify.yml").read_text(encoding="utf-8")
        self.assertIn(".github/workflows/run-codex.yml", verify)


class SandboxTest(unittest.TestCase):
    def test_the_proxy_lets_one_host_through_per_agent(self) -> None:
        openai = (ROOT / "docker" / "egress-proxy" / "allow-openai.list").read_text(encoding="utf-8").split()
        anthropic = (ROOT / "docker" / "egress-proxy" / "allow.list").read_text(encoding="utf-8").split()
        self.assertEqual(openai, [r"^api\.openai\.com$"])
        self.assertEqual(anthropic, [r"^api\.anthropic\.com$"])
        self.assertIn("ConnectPort 443", (ROOT / "docker" / "egress-proxy" / "tinyproxy.conf").read_text(encoding="utf-8"))
        self.assertIn('codex) API_HOST="api.openai.com"', SANDBOX)
        self.assertIn("allow-openai.list", SANDBOX)
        self.assertIn(':/etc/tinyproxy/allow.list:ro', SANDBOX)

    def test_the_hardening_and_the_patch_capture_are_shared(self) -> None:
        # one `hardening` array and one `patch` command serve both agents
        self.assertEqual(SANDBOX.count("hardening=("), 1)
        self.assertEqual(SANDBOX.count("cmd_patch() {"), 1)
        self.assertIn("--read-only", SANDBOX)
        self.assertIn("--cap-drop ALL", SANDBOX)
        self.assertIn('--network "$INTERNAL_NET"', SANDBOX)

    def test_the_proof_runs_before_the_agent_and_stops_the_attempt_when_it_fails(self) -> None:
        script = (ROOT / "scripts" / "run_codex_case.sh").read_text(encoding="utf-8")
        self.assertLess(script.index('"${SANDBOX[@]}" proof'), script.index('"${SANDBOX[@]}" agent'))
        self.assertIn("|| fail", script[script.index('"${SANDBOX[@]}" proof'):script.index('"${SANDBOX[@]}" agent')])
        self.assertIn('network-proof.log" || fail', script)
        self.assertIn("SANDBOX_AGENT=codex", script)

    def test_one_codex_invocation_serves_the_proof_and_the_attempt(self) -> None:
        self.assertEqual(SANDBOX.count("codex_args=("), 1)
        self.assertEqual(SANDBOX.count('"${codex_args[@]}"'), 2)
        array = SANDBOX[SANDBOX.index("codex_args=("):]
        array = array[: array.index(chr(10) + ")")]
        for flag in ("--dangerously-bypass-approvals-and-sandbox", "--strict-config", "--ephemeral", "--json"):
            self.assertIn(flag, array)

    def test_only_the_codex_key_variable_reaches_the_container(self) -> None:
        script = (ROOT / "scripts" / "run_codex_case.sh").read_text(encoding="utf-8")
        self.assertIn('export CODEX_API_KEY="$OPENAI_API_KEY"', script)
        self.assertIn("-e CODEX_API_KEY ", SANDBOX)
        self.assertNotIn("-e OPENAI_API_KEY", SANDBOX)


class PlanTest(unittest.TestCase):
    def test_the_planner_looks_at_the_codex_agent_when_asked(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for case_id, agent, patch in (("a-1", "claude-code", b"diff\n"), ("a-1", "codex-cli", b""),
                                          ("b-2", "claude-code", b""), ("b-2", "codex-cli", b"diff\n")):
                base = root / "cases" / case_id / "agents" / agent
                base.mkdir(parents=True)
                (base / "agent-fix.patch").write_bytes(patch)
                (base / "agent.yaml").write_text(json.dumps({"patch_sha256": "a" * 64 if patch else None}), encoding="utf-8")
            self.assertEqual(plan_cases.plan("", root), ["b-2"])
            self.assertEqual(plan_cases.plan("", root, agent="codex-cli"), ["a-1"])
            with self.assertRaises(ValueError):
                plan_cases.plan("b-2", root, agent="codex-cli")


if __name__ == "__main__":
    unittest.main()

# SPDX-License-Identifier: MIT
# Copyright (c) 2026 U-Pump
"""Turn one Codex CLI run into recorded evidence, or into a public ERROR report.

The counterpart of ``collect_agent_run.py`` for ``codex exec --json``. The transcript is a stream of
JSON events (``thread.started``, ``turn.started``, ``item.completed`` with a ``command_execution``,
``file_change`` or ``agent_message`` item, ``turn.completed`` with token usage, ``turn.failed``).
It is private and never published: only counts, fixed phrases and the patch leave the job.

Everything that leaves the CI job passes through ``scan`` first: a file that contains the API key (or
anything shaped like an OpenAI or Anthropic key) is deleted and the run fails closed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import collect_agent_run as shared
import verify_cases

AGENT_ID = "codex-cli"
AGENT_NAME = "Codex CLI"
TOKEN_ENV = "OPENAI_API_KEY"
TOKEN_SHAPE = re.compile(r"sk-[A-Za-z0-9_-]{20,}")
STATUS = re.compile(r"unexpected status (\d{3})")
COMMAND_TYPES = {"command_execution"}
ACTION_TYPES = {"command_execution", "file_change", "mcp_tool_call", "web_search"}
RESPONSE_TYPES = {"agent_message", "reasoning", "command_execution", "file_change"}
USAGE_FIELDS = (
    ("input", "input_tokens"),
    ("cached_input", "cached_input_tokens"),
    ("output", "output_tokens"),
    ("reasoning_output", "reasoning_output_tokens"),
)
REASONING = "medium"


class AttemptNotRecorded(Exception):
    """The run did not complete a real attempt; its public reason is the message."""


def items(events: list[dict[str, Any]], *, completed_only: bool = True) -> list[dict[str, Any]]:
    """The items of the run, one per id (the last event of an id wins)."""
    wanted = ("item.completed",) if completed_only else ("item.started", "item.updated", "item.completed")
    seen: dict[str, dict[str, Any]] = {}
    for index, event in enumerate(events):
        item = event.get("item")
        if event.get("type") in wanted and isinstance(item, dict):
            seen[str(item.get("id") or f"anon-{index}")] = item
    return list(seen.values())


def evidence(events: list[dict[str, Any]]) -> dict[str, str]:
    """Return the thread id of a completed attempt, or raise AttemptNotRecorded.

    A completed attempt has a ``thread.started`` event, at least one finished turn, no failed turn,
    and at least one shell command that completed with exit code 0. The transcript does not name the
    model, so the requested model is what is recorded.
    """
    started = next((e for e in events if e.get("type") == "thread.started"), None)
    if started is None or not started.get("thread_id"):
        raise AttemptNotRecorded("agent: Codex CLI did not start a session")
    if any(e.get("type") == "turn.failed" for e in events):
        raise AttemptNotRecorded("agent: Codex CLI did not finish successfully")
    if not any(e.get("type") == "turn.completed" for e in events):
        raise AttemptNotRecorded("agent: Codex CLI did not finish successfully")
    ok = any(
        item.get("type") in COMMAND_TYPES and item.get("status") == "completed" and item.get("exit_code") == 0
        for item in items(events)
    )
    if not ok:
        raise AttemptNotRecorded("agent: no shell command completed successfully")
    return {"session_id": str(started["thread_id"])}


def network_attempts(events: list[dict[str, Any]], proxy_log: str = "") -> dict[str, Any]:
    """Short names of commands that tried to reach the network, plus proxy-observed hosts."""
    labels: list[str] = []
    for item in items(events):
        kind = item.get("type")
        label = None
        if kind == "web_search":
            label = "web_search"
        elif kind in COMMAND_TYPES:
            command = str(item.get("command", ""))
            label = next((name for pattern, name in shared.NETWORK_COMMANDS if pattern.search(command)), None)
            if label is None and shared.NETWORK_ERROR.search(str(item.get("aggregated_output", ""))):
                label = "network error"
        if label:
            labels.append(label)
    return {
        "count": len(labels),
        "commands": sorted(set(labels)),
        "proxy_denied_hosts": sorted(set(shared.DENIED_HOST.findall(proxy_log))),
        "proxy_allowed_hosts": sorted(set(shared.ALLOWED_HOST.findall(proxy_log))),
    }


def token_usage(events: list[dict[str, Any]]) -> dict[str, int] | None:
    """Token totals over all finished turns (numbers only), or None when the transcript has no usage."""
    usages = [e["usage"] for e in events if e.get("type") == "turn.completed" and isinstance(e.get("usage"), dict)]
    if not usages:
        return None
    return {name: sum(int(u.get(key) or 0) for u in usages) for name, key in USAGE_FIELDS}


def transcript_metrics(events: list[dict[str, Any]], duration_seconds: int) -> dict[str, Any]:
    """Counts taken from the transcript, which itself is never published."""
    done = items(events)
    return {
        "bash_commands": sum(1 for item in done if item.get("type") in COMMAND_TYPES),
        "tool_calls": sum(1 for item in done if item.get("type") in ACTION_TYPES),
        "turns": sum(1 for e in events if e.get("type") == "turn.completed"),
        "duration_seconds": duration_seconds,
        "tokens": token_usage(events),
    }


API_PROBLEMS = (
    (re.compile(r"insufficient_quota|exceeded your current quota|billing|credit balance|spend limit"),
     "API refused: quota exhausted or spend limit reached (check the project's billing and limit)"),
    (re.compile(r"invalid_api_key|incorrect api key|unauthorized|authentication|forbidden|permission"),
     "API refused the key: invalid, disabled, deleted or from another project"),
    (re.compile(r"rate.?limit|too many requests|429"),
     "API rate limit reached"),
    (re.compile(r"model.{0,40}(?:not found|not available|does not exist|unavailable|not supported)|model_not_found"),
     "API: the model is not available for this key"),
    (re.compile(r"overloaded|service unavailable|internal server error|bad gateway|timed? ?out|server_error"),
     "API temporarily unavailable or timed out"),
)


def api_status(events: list[dict[str, Any]], stderr_text: str = "") -> int | None:
    """The HTTP status Codex reports in its last error message, if any."""
    messages = [str(e.get("message", "")) for e in events if e.get("type") == "error"]
    messages += [str((e.get("error") or {}).get("message", "")) for e in events if e.get("type") == "turn.failed"]
    for text in reversed([*messages, stderr_text]):
        found = STATUS.findall(text)
        if found:
            return int(found[-1])
    return None


def model_responses(events: list[dict[str, Any]]) -> int:
    """Items that really came from the model (messages, reasoning, commands, edits), not errors."""
    return sum(1 for item in items(events) if item.get("type") in RESPONSE_TYPES)


def diagnose_failure(events: list[dict[str, Any]], stderr_text: str = "") -> dict[str, Any]:
    """Classify why Codex stopped, from fixed phrases only.

    The raw API message, the transcript and stderr are never returned: only the HTTP status, a
    classification chosen from a fixed list and counts.
    """
    haystack = [stderr_text]
    for event in events:
        if event.get("type") == "error":
            haystack.append(str(event.get("message", "")))
        if event.get("type") == "turn.failed":
            haystack.append(str((event.get("error") or {}).get("message", "")))
        item = event.get("item")
        if isinstance(item, dict) and item.get("type") == "error":
            haystack.append(str(item.get("message", "")))
    text = chr(10).join(haystack).lower()
    status = api_status(events, stderr_text)
    problem = next((label for pattern, label in API_PROBLEMS if pattern.search(text)), "")
    if not problem and status in (401, 403):
        problem = API_PROBLEMS[1][1]
    if not problem and status == 402:
        problem = API_PROBLEMS[0][1]
    if not problem and status == 429:
        problem = API_PROBLEMS[2][1]
    if not problem and status is not None and status >= 500:
        problem = API_PROBLEMS[4][1]
    return {
        "started_session": any(e.get("type") == "thread.started" for e in events),
        "events": len(events),
        "model_responses": model_responses(events),
        "http_status": status,
        "problem": problem or "no API problem recognised (unclassified failure)",
    }


def describe_failure(diagnosis: dict[str, Any], exit_code: int) -> str:
    """One public line: exit code, API problem, whether the model answered."""
    answered = diagnosis["model_responses"]
    status = f" (HTTP {diagnosis['http_status']})" if diagnosis["http_status"] else ""
    tail = "the model gave no response" if answered == 0 else f"the model had given {answered} responses"
    return f"agent: Codex CLI exited with code {exit_code}; {diagnosis['problem']}{status}; {tail}"


def scan_for_secret(paths: list[Path], token: str | None) -> list[str]:
    """Names of files that contain the key or a key-shaped string. Never returns content."""
    hits: list[str] = []
    needle = token.encode() if token and len(token) >= 16 else None
    for path in paths:
        if not path.is_file():
            continue
        data = path.read_bytes()
        text = data.decode("utf-8", errors="replace")
        if (needle is not None and needle in data) or TOKEN_SHAPE.search(text) or shared.TOKEN_SHAPE.search(text):
            hits.append(path.name)
    return hits


def build_agent_yaml(
    *,
    version: str,
    requested_model: str,
    session_id: str,
    patch_bytes: bytes,
    attempt: dict[str, Any],
    run_url: str,
    image: str,
    proof_note: str,
    date_utc: str,
    metrics: dict[str, Any],
    proxy: dict[str, Any],
    attempt_note: str | None = None,
) -> dict[str, Any]:
    patch_sha = hashlib.sha256(patch_bytes).hexdigest() if patch_bytes.strip() else None
    data: dict[str, Any] = {
        "name": AGENT_NAME,
        "version": version,
        # `codex exec --json` does not report the model; the requested one is recorded.
        "model": requested_model,
        "requested_model": requested_model,
        "model_source": "requested (the Codex transcript does not name the model)",
        "reasoning": REASONING,
        "date_utc": date_utc,
        "environment": (
            "GitHub Actions ubuntu-latest; agent in a Docker container (read-only root, "
            "non-root uid, writable only /work and a tmpfs home, all capabilities dropped); "
            "container network is internal and egress goes through a proxy that allows only "
            "api.openai.com:443; Codex's own sandbox bypassed (the container is the sandbox), "
            "no web search, apps, browser, plugins, hooks or AGENTS.md"
        ),
        "invocation": (
            "codex exec --json --ephemeral --skip-git-repo-check --ignore-user-config --ignore-rules "
            "--strict-config --dangerously-bypass-approvals-and-sandbox "
            f"-c model_reasoning_effort=\"{REASONING}\" -c web_search=\"disabled\" -c project_doc_max_bytes=0 "
            "--disable apps --disable browser_use --disable computer_use --disable plugins --disable hooks "
            f"--disable multi_agent --disable image_generation -m {requested_model} - (task text on stdin)"
        ),
        "session_id": session_id,
        "patch_sha256": patch_sha,
        "attempt_note": attempt_note or (
            "First completed attempt; build*/ output excluded from the patch."
            if patch_sha
            else "First completed attempt; the agent finished without changing any file."
        ),
        "metrics": metrics,
        "network_commands_seen_in_transcript": attempt["commands"],
        "proxy": proxy,
        "run_url": run_url,
        "image": image,
        "network_proof": proof_note,
    }
    if patch_sha is None:
        data["outcome"] = "NO_PATCH"
    return data


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def cmd_record(args: argparse.Namespace) -> int:
    proxy_log = ""
    if args.proxy_log:
        proxy_log = Path(args.proxy_log).read_text(encoding="utf-8", errors="replace")
    baseline = ""
    if args.proxy_baseline and Path(args.proxy_baseline).is_file():
        baseline = Path(args.proxy_baseline).read_text(encoding="utf-8", errors="replace")
    attempt_note = None
    if args.attempt_note_file and Path(args.attempt_note_file).is_file():
        attempt_note = Path(args.attempt_note_file).read_text(encoding="utf-8").strip() or None
    events = shared.load_events(Path(args.transcript))
    out_dir = Path(args.out_dir)
    try:
        found = evidence(events)
    except AttemptNotRecorded as exc:
        print(f"not recorded: {exc}")
        (out_dir / "error-reason.txt").write_text(str(exc), encoding="utf-8")
        return 3
    data = build_agent_yaml(
        version=args.version,
        requested_model=args.requested_model,
        session_id=found["session_id"],
        patch_bytes=Path(args.patch).read_bytes(),
        attempt=network_attempts(events, proxy_log),
        run_url=args.run_url,
        image=args.image,
        proof_note=args.proof_note,
        date_utc=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        metrics=transcript_metrics(events, int(args.duration_seconds)),
        proxy=shared.agent_proxy_traffic(proxy_log, baseline),
        attempt_note=attempt_note,
    )
    _write_json(out_dir / "agent.yaml", data)
    print(f"recorded: model={args.requested_model} patch_sha256={data['patch_sha256']}")
    return 0


def cmd_diagnose(args: argparse.Namespace) -> int:
    transcript = Path(args.transcript)
    events = shared.load_events(transcript) if transcript.is_file() else []
    stderr_path = Path(args.stderr)
    stderr_text = stderr_path.read_text(encoding="utf-8", errors="replace") if stderr_path.is_file() else ""
    line = describe_failure(diagnose_failure(events, stderr_text), int(args.exit_code))
    token = os.environ.get(TOKEN_ENV)
    if (token and token in line) or TOKEN_SHAPE.search(line):
        line = f"agent: Codex CLI exited with code {int(args.exit_code)}"
    print(line)
    return 0


def cmd_error(args: argparse.Namespace) -> int:
    reason = args.reason.splitlines()[0].strip()
    if verify_cases.summary_reason(reason, "") != reason:
        reason = "agent: run failed before an attempt was recorded"
    text = verify_cases.render(
        args.case,
        "INFRASTRUCTURE_ERROR",
        {},
        None,
        AGENT_NAME,
        args.version or "not recorded",
        datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC"),
        reason,
        None,
        None,
    )
    out = Path(args.results_dir) / args.case / f"{AGENT_ID}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(f"{args.case}/{AGENT_ID}: INFRASTRUCTURE_ERROR; Reason: {reason}")
    return 0


def cmd_scan(args: argparse.Namespace) -> int:
    files = [Path(p) for p in args.files]
    hits = scan_for_secret(files, os.environ.get(TOKEN_ENV))
    if hits:
        for path in files:
            if path.is_file():
                path.unlink()
        names = ", ".join(sorted(set(hits)))
        print(
            f"SECRET FOUND in: {names}; all files were removed and nothing is uploaded. "
            "Revoke and recreate the key."
        )
        return 4
    print(f"secret scan clean: {len(files)} files")
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    record = sub.add_parser("record")
    for name in ("transcript", "patch", "out-dir", "version", "requested-model", "run-url", "image"):
        record.add_argument(f"--{name}", required=True)
    record.add_argument("--duration-seconds", default="0")
    record.add_argument("--proxy-log", default="")
    record.add_argument("--proxy-baseline", default="")
    record.add_argument("--attempt-note-file", default="")
    record.add_argument("--proof-note", default="")
    record.set_defaults(handler=cmd_record)
    error = sub.add_parser("error")
    error.add_argument("--case", required=True)
    error.add_argument("--reason", required=True)
    error.add_argument("--results-dir", required=True)
    error.add_argument("--version", default="")
    error.set_defaults(handler=cmd_error)
    diagnose = sub.add_parser("diagnose")
    diagnose.add_argument("--transcript", required=True)
    diagnose.add_argument("--stderr", required=True)
    diagnose.add_argument("--exit-code", required=True)
    diagnose.set_defaults(handler=cmd_diagnose)
    scan = sub.add_parser("scan")
    scan.add_argument("files", nargs="+")
    scan.set_defaults(handler=cmd_scan)
    args = parser.parse_args(argv)
    return int(args.handler(args))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

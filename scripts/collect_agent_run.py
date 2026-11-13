# SPDX-License-Identifier: MIT
# Copyright (c) 2026 U-Pump
"""Turn one Claude Code run into recorded evidence, or into a public ERROR report.

Everything that leaves the CI job passes through ``scan`` first: a file that
contains the API key (or anything shaped like an Anthropic key) is deleted
and the run fails closed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import verify_cases

AGENT_ID = "claude-code"
AGENT_NAME = "Claude Code"
TOKEN_ENV = "ANTHROPIC_API_KEY"
TOKEN_SHAPE = re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}")
DENIED_HOST = re.compile(r'refused on filtered domain "([^"]+)"')
ALLOWED_HOST = re.compile(r'Established connection to host "([^"]+)"')
PROXY_REQUEST = re.compile(r"Request \(file descriptor \d+\): CONNECT ([^\s:]+):(\d+)")
PROXY_PORT_REFUSED = re.compile(r"Refused CONNECT method on port (\d+)")
TOKEN_FIELDS = (
    ("input", "input_tokens"),
    ("output", "output_tokens"),
    ("cache_creation_input", "cache_creation_input_tokens"),
    ("cache_read_input", "cache_read_input_tokens"),
)
EXIT_CODE = re.compile(
    r"(?im)^\s*(?:Exit code|Process exited with code|Command exited with code)\s*:?\s*(\d+)"
)
NETWORK_COMMANDS = (
    (re.compile(r"(?i)(?:^|[;&|\s])curl(?:\s|$)"), "curl"),
    (re.compile(r"(?i)(?:^|[;&|\s])wget(?:\s|$)"), "wget"),
    (re.compile(r"(?i)\bgit\b[^;&|\n]{0,120}\b(clone|fetch|pull|submodule)\b"), "git"),
    (re.compile(r"(?i)(?:^|[;&|\s/])gh(?:\s|$)"), "gh"),
    (re.compile(r"(?i)\b(?:pip|pip3)\s+install\b"), "pip install"),
    (re.compile(r"(?i)\bnpm\s+(?:install|ci)\b"), "npm install"),
    (re.compile(r"(?i)\bcargo\s+(?:install|fetch)\b"), "cargo fetch/install"),
    (re.compile(r"(?i)\b(?:apt|apt-get)\s+install\b"), "apt install"),
)
NETWORK_ERROR = re.compile(
    r"(?i)host_not_allowed|network (?:is )?unreachable|network access (?:is )?denied|"
    r"connection (?:refused|timed out)|could not resolve host|"
    r"temporary failure in name resolution|CONNECT tunnel failed"
)


class AttemptNotRecorded(Exception):
    """The run did not complete a real attempt; its public reason is the message."""


def load_events(path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            value = json.loads(line)
        except ValueError:
            continue
        if isinstance(value, dict):
            events.append(value)
    return events


def result_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(str(item.get("text", "")) for item in content if isinstance(item, dict))
    return ""


def _blocks(event: dict[str, Any]) -> list[dict[str, Any]]:
    message = event.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, list):
        return []
    return [block for block in content if isinstance(block, dict)]


def evidence(events: list[dict[str, Any]]) -> dict[str, str]:
    """Return model and session id of a completed attempt, or raise AttemptNotRecorded.

    A completed attempt has an init event with a model, a successful final result and at
    least one Bash command that finished without an error and with exit code 0.
    """
    init = next(
        (e for e in events if e.get("type") == "system" and e.get("subtype") == "init"), None
    )
    results = [e for e in events if e.get("type") == "result"]
    result = results[-1] if results else None
    if init is None or not init.get("model"):
        raise AttemptNotRecorded("agent: Claude Code did not start a session")
    if result is None or result.get("is_error") or result.get("subtype") != "success":
        raise AttemptNotRecorded("agent: Claude Code did not finish successfully")
    bash_ids = {
        str(block.get("id"))
        for event in events
        if event.get("type") == "assistant"
        for block in _blocks(event)
        if block.get("type") == "tool_use" and block.get("name") == "Bash"
    }
    succeeded = False
    for event in events:
        if event.get("type") != "user":
            continue
        for block in _blocks(event):
            if block.get("type") != "tool_result" or str(block.get("tool_use_id")) not in bash_ids:
                continue
            if block.get("is_error"):
                continue
            exit_code = EXIT_CODE.search(result_text(block.get("content")))
            if exit_code is None or int(exit_code.group(1)) == 0:
                succeeded = True
    if not succeeded:
        raise AttemptNotRecorded("agent: no Bash command completed successfully")
    return {"model": str(init["model"]), "session_id": str(init.get("session_id") or "")}


def network_attempts(events: list[dict[str, Any]], proxy_log: str = "") -> dict[str, Any]:
    """Short names of commands that tried to reach the network, plus proxy-observed hosts."""
    labels: list[str] = []
    network_ids: set[str] = set()
    for event in events:
        if event.get("type") != "assistant":
            continue
        for block in _blocks(event):
            if block.get("type") != "tool_use":
                continue
            label = None
            if block.get("name") in {"WebFetch", "WebSearch"}:
                label = str(block["name"])
            elif block.get("name") == "Bash":
                command = str((block.get("input") or {}).get("command", ""))
                label = next(
                    (name for pattern, name in NETWORK_COMMANDS if pattern.search(command)), None
                )
            if label:
                labels.append(label)
                network_ids.add(str(block.get("id")))
    for event in events:
        if event.get("type") != "user":
            continue
        for block in _blocks(event):
            if (
                block.get("type") == "tool_result"
                and str(block.get("tool_use_id")) not in network_ids
                and NETWORK_ERROR.search(result_text(block.get("content")))
            ):
                labels.append("network error")
    return {
        "count": len(labels),
        "commands": sorted(set(labels)),
        "proxy_denied_hosts": sorted(set(DENIED_HOST.findall(proxy_log))),
        "proxy_allowed_hosts": sorted(set(ALLOWED_HOST.findall(proxy_log))),
    }


def proxy_counts(log: str) -> dict[str, Counter[str]]:
    """Requests the proxy refused, and connections it allowed, counted per host from its log."""
    denied: Counter[str] = Counter()
    allowed: Counter[str] = Counter()
    last = ""
    for line in log.splitlines():
        request = PROXY_REQUEST.search(line)
        if request:
            last = f"{request.group(1)}:{request.group(2)}"
            continue
        domain = DENIED_HOST.search(line)
        if domain:
            denied[domain.group(1)] += 1
            continue
        port = PROXY_PORT_REFUSED.search(line)
        if port:
            denied[last or f"port {port.group(1)}"] += 1
            continue
        host = ALLOWED_HOST.search(line)
        if host:
            allowed[host.group(1)] += 1
    return {"denied": denied, "allowed": allowed}


def agent_proxy_traffic(full_log: str, before_agent_log: str = "") -> dict[str, Any]:
    """Proxy traffic of the agent run only: the log at the end minus the log after the proof.

    The isolation proof makes its own refused requests (github.com, example.com, a bad
    port); they are taken from the snapshot made right after the proof and left out.
    """
    full, base = proxy_counts(full_log), proxy_counts(before_agent_log)
    denied = full["denied"] - base["denied"]
    allowed = full["allowed"] - base["allowed"]
    return {
        "refused_requests": sum(denied.values()),
        "refused": dict(sorted(denied.items())),
        "allowed_connections": dict(sorted(allowed.items())),
        "scope": "agent run only, counted from the proxy log; the isolation proof's requests are excluded",
    }


def token_usage(events: list[dict[str, Any]]) -> dict[str, int] | None:
    """Token totals of the run (numbers only), or None when the transcript has no usage."""
    results = [e for e in events if e.get("type") == "result" and isinstance(e.get("usage"), dict)]
    totals: dict[str, int] | None = None
    if results:
        usage = results[-1]["usage"]
        totals = {name: int(usage.get(key) or 0) for name, key in TOKEN_FIELDS}
    else:
        seen: dict[str, dict[str, Any]] = {}
        for index, event in enumerate(events):
            message = event.get("message")
            if event.get("type") == "assistant" and isinstance(message, dict) and isinstance(message.get("usage"), dict):
                seen[str(message.get("id") or f"anon-{index}")] = message["usage"]
        if seen:
            totals = {name: sum(int(u.get(key) or 0) for u in seen.values()) for name, key in TOKEN_FIELDS}
    return totals


def transcript_metrics(events: list[dict[str, Any]], duration_seconds: int) -> dict[str, Any]:
    """Counts taken from the transcript, which itself is never published."""
    tool_uses = [
        block
        for event in events
        if event.get("type") == "assistant"
        for block in _blocks(event)
        if block.get("type") == "tool_use"
    ]
    results = [e for e in events if e.get("type") == "result"]
    turns = results[-1].get("num_turns") if results else None
    return {
        "bash_commands": sum(1 for block in tool_uses if block.get("name") == "Bash"),
        "tool_calls": len(tool_uses),
        "turns": turns if isinstance(turns, int) else 0,
        "duration_seconds": duration_seconds,
        "tokens": token_usage(events),
    }


def scan_for_secret(paths: list[Path], token: str | None) -> list[str]:
    """Names of files that contain the token or a token-shaped string. Never returns content."""
    hits: list[str] = []
    needle = token.encode() if token and len(token) >= 16 else None
    for path in paths:
        if not path.is_file():
            continue
        data = path.read_bytes()
        text = data.decode("utf-8", errors="replace")
        if (needle is not None and needle in data) or TOKEN_SHAPE.search(text):
            hits.append(path.name)
    return hits


def build_agent_yaml(
    *,
    version: str,
    model: str,
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
        "model": model,
        "requested_model": requested_model,
        "effort": "default (not set)",
        "date_utc": date_utc,
        "environment": (
            "GitHub Actions ubuntu-latest; agent in a Docker container (read-only root, "
            "non-root uid, writable only /work and a tmpfs home, all capabilities dropped); "
            "container network is internal and egress goes through a proxy that allows only "
            "api.anthropic.com:443; --safe-mode, no web tools, no MCP, no memory or CLAUDE.md"
        ),
        "invocation": (
            "claude -p --output-format stream-json --verbose --no-session-persistence "
            "--safe-mode --strict-mcp-config --disable-slash-commands "
            "--permission-mode acceptEdits --permission-prompts none "
            "--tools Bash,Read,Edit,Write,Glob,Grep "
            "--allowedTools Bash,Read,Edit,Write,Glob,Grep "
            f"--disallowedTools WebSearch,WebFetch --model {requested_model} "
            "(task text on stdin)"
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
    events = load_events(Path(args.transcript))
    out_dir = Path(args.out_dir)
    try:
        found = evidence(events)
    except AttemptNotRecorded as exc:
        print(f"not recorded: {exc}")
        (out_dir / "error-reason.txt").write_text(str(exc), encoding="utf-8")
        return 3
    data = build_agent_yaml(
        version=args.version,
        model=found["model"],
        requested_model=args.requested_model,
        session_id=found["session_id"],
        patch_bytes=Path(args.patch).read_bytes(),
        attempt=network_attempts(events, proxy_log),
        run_url=args.run_url,
        image=args.image,
        proof_note=args.proof_note,
        date_utc=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        metrics=transcript_metrics(events, int(args.duration_seconds)),
        proxy=agent_proxy_traffic(proxy_log, baseline),
        attempt_note=attempt_note,
    )
    _write_json(out_dir / "agent.yaml", data)
    print(f"recorded: model={found['model']} patch_sha256={data['patch_sha256']}")
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
            "Revoke and recreate the token."
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
    scan = sub.add_parser("scan")
    scan.add_argument("files", nargs="+")
    scan.set_defaults(handler=cmd_scan)
    args = parser.parse_args(argv)
    return int(args.handler(args))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

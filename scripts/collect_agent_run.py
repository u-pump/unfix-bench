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


def transcript_metrics(events: list[dict[str, Any]], duration_seconds: int) -> dict[str, int]:
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
    }


API_PROBLEMS = (
    (re.compile(r"credit balance|billing|payment|insufficient (?:credit|fund)|spend limit|usage limit"),
     "API refused: credit balance too low or spend limit reached (check the workspace balance and limit)"),
    (re.compile(r"invalid x-api-key|invalid api key|authentication|unauthorized|permission_error|forbidden"),
     "API refused the key: invalid, disabled, deleted or from another workspace"),
    (re.compile(r"rate.?limit|too many requests|quota"),
     "API rate limit reached"),
    (re.compile(r"model.{0,40}(?:not found|not available|does not exist|unavailable)|not_found_error"),
     "API: the model is not available for this key"),
    (re.compile(r"overloaded|service unavailable|internal server error|api_error|bad gateway|timed? ?out"),
     "API temporarily unavailable or timed out"),
)


def api_status(events: list[dict[str, Any]]) -> int | None:
    for event in reversed(events):
        for key in ("api_error_status", "status", "http_status"):
            value = event.get(key)
            if isinstance(value, int) and 100 <= value <= 599:
                return value
    return None


def model_responses(events: list[dict[str, Any]]) -> int:
    """Assistant messages that really came from the model, not synthetic error messages."""
    count = 0
    for event in events:
        if event.get("type") != "assistant" or event.get("error") or event.get("isApiErrorMessage"):
            continue
        message = event.get("message")
        if isinstance(message, dict) and message.get("model") != "<synthetic>" and _blocks(event):
            count += 1
    return count


def diagnose_failure(events: list[dict[str, Any]], stderr_text: str = "") -> dict[str, Any]:
    """Classify why Claude Code stopped, from fixed phrases only.

    The raw API message, the transcript and stderr are never returned: only the HTTP status,
    a classification chosen from a fixed list and counts. Reads private files, prints nothing
    that could hold a key or model output.
    """
    haystack = [stderr_text]
    for event in events:
        if event.get("type") == "result" and isinstance(event.get("result"), str):
            haystack.append(event["result"])
        if isinstance(event.get("error"), str):
            haystack.append(event["error"])
        for block in _blocks(event):
            if block.get("type") == "text" and (event.get("error") or event.get("isApiErrorMessage")):
                haystack.append(str(block.get("text", "")))
    text = chr(10).join(haystack).lower()
    status = api_status(events)
    problem = next((label for pattern, label in API_PROBLEMS if pattern.search(text)), "")
    if not problem and status in (401, 403):
        problem = API_PROBLEMS[1][1]
    if not problem and status == 402:
        problem = API_PROBLEMS[0][1]
    if not problem and status == 429:
        problem = API_PROBLEMS[2][1]
    if not problem and status is not None and status >= 500:
        problem = API_PROBLEMS[4][1]
    init = any(e.get("type") == "system" and e.get("subtype") == "init" for e in events)
    return {
        "started_session": init,
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
    return f"agent: Claude Code exited with code {exit_code}; {diagnosis['problem']}{status}; {tail}"


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
    metrics: dict[str, int],
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
        "attempt_note": (
            "First completed attempt; build*/ output excluded from the patch."
            if patch_sha
            else "First completed attempt; the agent finished without changing any file."
        ),
        "metrics": metrics,
        "network_attempts": {key: attempt[key] for key in ("count", "commands")},
        "proxy_hosts": {
            "allowed": attempt["proxy_allowed_hosts"],
            "denied": attempt["proxy_denied_hosts"],
        },
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
    )
    _write_json(out_dir / "agent.yaml", data)
    print(f"recorded: model={found['model']} patch_sha256={data['patch_sha256']}")
    return 0


def cmd_diagnose(args: argparse.Namespace) -> int:
    transcript = Path(args.transcript)
    events = load_events(transcript) if transcript.is_file() else []
    stderr_path = Path(args.stderr)
    stderr_text = stderr_path.read_text(encoding="utf-8", errors="replace") if stderr_path.is_file() else ""
    diagnosis = diagnose_failure(events, stderr_text)
    line = describe_failure(diagnosis, int(args.exit_code))
    token = os.environ.get(TOKEN_ENV)
    if (token and token in line) or TOKEN_SHAPE.search(line):
        line = f"agent: Claude Code exited with code {int(args.exit_code)}"
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

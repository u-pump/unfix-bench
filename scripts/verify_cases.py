# SPDX-License-Identifier: MIT
# Copyright (c) 2026 U-Pump
"""Run private cplus and publish only a small allowlisted summary."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMP = Path(os.environ.get("RUNNER_TEMP", str(ROOT / ".tmp")))
RESULTS_DIR = Path(os.environ.get("RESULTS_DIR", str(ROOT / "results")))
GATES = (
    "anti_cheat",
    "build:baseline",
    "repro:baseline",
    "build:patched",
    "repro:patched",
    "repeat",
    "revert",
    "regression",
)
STATUSES = {"PASS", "FAIL", "ERROR", "REVIEW", "SKIPPED"}
VERDICTS = {"VERIFIED", "REJECTED", "REVIEW", "NOT_VERIFIABLE", "ERROR"}
# The verifier is pinned per case. A case without ``verifier_revision`` in case.yaml is one of the first ten:
# its results were made with this revision and stay on it (they are not verified again).
LEGACY_REVISION = "81c0fda242fef1daf55d3164e06127d372c81caa"
VERIFIER_REVISION = LEGACY_REVISION
REVISION = re.compile(r"[0-9a-f]{40}")
HTTPS_ONLY = ("-c", "protocol.allow=never", "-c", "protocol.https.allow=always")
MODULE_IN_TEST = re.compile(r"-R\s+'?\^(.+)\$'?(?:\s|$)")
# The reference test of a Unity case as cplus reports it, kept so the result file can say it (see main()).
reference_lines: dict[tuple[str, str], str] = {}


class CaseExecutionError(RuntimeError):
    """An infrastructure failure with an allowlisted public stage and reason."""

    def __init__(self, stage: str, reason: str) -> None:
        self.stage = stage
        self.public_reason = f"{stage}: {reason}"
        super().__init__(self.public_reason)


def quiet(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, text=True, capture_output=True, check=False)


def quiet_stage(stage: str, reason: str, *args: str,
                cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    try:
        return quiet(*args, cwd=cwd)
    except OSError as exc:
        raise CaseExecutionError(stage, reason) from exc


def case_revision(case_id: str) -> str:
    """The cplus revision this case is verified with: ``verifier_revision`` of its case.yaml, else the legacy one."""
    case = json.loads((ROOT / "cases" / case_id / "case.yaml").read_text(encoding="utf-8"))
    revision = case.get("verifier_revision", LEGACY_REVISION)
    if not isinstance(revision, str) or not REVISION.fullmatch(revision):
        raise ValueError("verifier_revision must be a full 40-hex commit")
    return revision


def cplus_command(revision: str) -> str:
    """The ``cplus`` of one revision: ``$CPLUS_VENV_ROOT/<revision>/bin/cplus`` as installed by install_private.sh.

    Without CPLUS_VENV_ROOT (local runs, tests) it is the ``cplus`` on PATH, and nothing guarantees its revision.
    """
    root = os.environ.get("CPLUS_VENV_ROOT", "").strip()
    if not root:
        return "cplus"
    if not REVISION.fullmatch(revision):
        raise CaseExecutionError("parse", "invalid verifier revision")
    folder = "Scripts" if os.name == "nt" else "bin"
    return str(Path(root) / revision / folder / "cplus")


def selected_cases() -> list[str]:
    explicit = os.environ.get("SELECT_CASE", "").strip()
    if explicit:
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", explicit):
            raise ValueError("Invalid case ID")
        return [explicit]
    return sorted(path.name for path in (ROOT / "cases").iterdir() if path.is_dir())


def patch_digest(case_id: str, agent_id: str) -> str | None:
    path = ROOT / "cases" / case_id / "agents" / agent_id / "agent-fix.patch"
    if not path.is_file():
        return None
    content = path.read_bytes()
    return hashlib.sha256(content).hexdigest() if content.strip() else None


def no_patch_recorded(case_id: str, agent_id: str) -> bool:
    """True when the agent completed its attempt and recorded that it changed nothing."""
    base = ROOT / "cases" / case_id / "agents" / agent_id
    try:
        agent = json.loads((base / "agent.yaml").read_text(encoding="utf-8"))
        return (base / "agent-fix.patch").read_bytes().strip() == b"" and (
            agent.get("outcome") == "NO_PATCH" and agent.get("patch_sha256") is None
        )
    except (OSError, ValueError):
        return False


def no_patch_report_is_current(case_id: str, agent_id: str) -> bool:
    report = ROOT / "results" / case_id / f"{agent_id}.md"
    try:
        text = report.read_text(encoding="utf-8")
    except OSError:
        return False
    return re.search(r"(?m)^Verdict: \*\*NO_PATCH\*\*$", text) is not None


def case_revision_or_legacy(case_id: str) -> str:
    try:
        return case_revision(case_id)
    except (OSError, ValueError):
        return LEGACY_REVISION


def report_is_current(case_id: str, agent_id: str, digest: str) -> bool:
    report = ROOT / "results" / case_id / f"{agent_id}.md"
    metadata = ROOT / "cases" / case_id / "agents" / agent_id / "agent.yaml"
    if not report.is_file() or not metadata.is_file():
        return False
    try:
        agent = json.loads(metadata.read_text(encoding="utf-8"))
        text = report.read_text(encoding="utf-8")
    except (OSError, ValueError):
        return False
    return (
        agent.get("patch_sha256") == digest
        and re.search(rf"(?m)^Patch: sha256 {digest}$", text) is not None
        and re.search(rf"(?m)^Verifier: cplus {case_revision_or_legacy(case_id)} ·", text) is not None
    )


def selected_pairs() -> list[tuple[str, str]]:
    explicit_case = os.environ.get("SELECT_CASE", "").strip()
    explicit_agent = os.environ.get("SELECT_AGENT", "").strip()
    if explicit_agent and not re.fullmatch(r"[a-z0-9][a-z0-9-]*", explicit_agent):
        raise ValueError("Invalid agent ID")
    if explicit_case or explicit_agent:
        cases = selected_cases()
        pairs = [(case_id, agent_id) for case_id in cases for agent_id in selected_agents(case_id)
                 if not explicit_agent or agent_id == explicit_agent]
        if explicit_agent and not pairs:
            raise ValueError("Selected agent unavailable")
        return pairs

    before = os.environ.get("BEFORE_SHA", "").strip()
    head = os.environ.get("HEAD_SHA", "").strip()
    if before and before != "0" * 40 and head:
        diff = quiet("git", "diff", "-M100%", "--name-status", before, head,
                     "--", "cases/", cwd=ROOT)
        if diff.returncode:
            raise ValueError("Could not compare submitted agent files")
        candidates: set[tuple[str, str]] = set()
        for row in diff.stdout.splitlines():
            fields = row.split("\t")
            status = fields[0]
            if status == "R100" or status.startswith("D"):
                continue
            path = fields[-1]
            match = re.fullmatch(
                r"cases/([a-z0-9][a-z0-9-]*)/agents/([a-z0-9][a-z0-9-]*)/(?:agent-fix\.patch|agent\.yaml)",
                path,
            )
            if match:
                candidates.add((match[1], match[2]))
    else:
        candidates = {(case_id, agent_id) for case_id in selected_cases()
                      for agent_id in selected_agents(case_id)}
    return sorted(
        (case_id, agent_id) for case_id, agent_id in candidates
        if ((digest := patch_digest(case_id, agent_id))
            and not report_is_current(case_id, agent_id, digest))
        or (no_patch_recorded(case_id, agent_id)
            and not no_patch_report_is_current(case_id, agent_id))
    )


def extract_json(output: str) -> dict[str, object]:
    decoder = json.JSONDecoder()
    for match in re.finditer(r'\{\s*"schema_version"\s*:', output):
        try:
            value, _ = decoder.raw_decode(output[match.start():])
            if isinstance(value, dict):
                return value
        except json.JSONDecodeError:
            pass
    raise ValueError("No verifier result")


def selected_agents(case_id: str) -> list[str]:
    root = ROOT / "cases" / case_id / "agents"
    if not root.is_dir():
        raise CaseExecutionError("parse", "agent directory unavailable")
    agents = sorted(path.name for path in root.iterdir() if path.is_dir())
    if not agents or any(not re.fullmatch(r"[a-z0-9][a-z0-9-]*", name) for name in agents):
        raise CaseExecutionError("parse", "invalid agent directory")
    return agents


def agent_identity(case_id: str, agent_id: str) -> tuple[str, str]:
    agent = json.loads(
        (ROOT / "cases" / case_id / "agents" / agent_id / "agent.yaml").read_text(encoding="utf-8")
    )
    if not isinstance(agent, dict):
        raise ValueError("Invalid agent metadata")
    required = {"name", "version", "model", "invocation", "date_utc", "environment", "patch_sha256", "attempt_note"}
    if not required <= agent.keys():
        raise ValueError("Missing agent metadata")
    name = str(agent.get("name") or "not run").replace("\n", " ").replace("\r", " ")
    version = str(agent.get("version") or "not recorded").replace("\n", " ").replace("\r", " ")
    return name, version


def agent_result_note(case_id: str, agent_id: str) -> str | None:
    """Read a curated, single-line note from public agent metadata."""
    agent = json.loads(
        (ROOT / "cases" / case_id / "agents" / agent_id / "agent.yaml").read_text(encoding="utf-8")
    )
    note = agent.get("result_note")
    if note is None:
        return None
    if not isinstance(note, str) or not note or summary_reason(note, "") != note:
        raise CaseExecutionError("parse", "invalid case result note")
    return note


def agent_attempt_note(case_id: str, agent_id: str) -> str | None:
    """A public line about an attempt that is not the plain first one (for example a rerun)."""
    path = ROOT / "cases" / case_id / "agents" / agent_id / "attempt-note.txt"
    if not path.is_file():
        return None
    note = path.read_text(encoding="utf-8").strip()
    if not note or "\n" in note or len(note) > 600:
        raise CaseExecutionError("parse", "invalid attempt note")
    return note


def agent_network_note(case_id: str, agent_id: str) -> str | None:
    """Proxy-counted network traffic of the agent run, from its recorded metadata (if any)."""
    path = ROOT / "cases" / case_id / "agents" / agent_id / "agent.yaml"
    try:
        proxy = json.loads(path.read_text(encoding="utf-8")).get("proxy")
    except (OSError, ValueError):
        return None
    if not isinstance(proxy, dict) or not isinstance(proxy.get("refused"), dict):
        return None
    refused = ", ".join(f"{host} x{count}" for host, count in proxy["refused"].items()) or "none"
    head = f"the proxy refused {int(proxy.get('refused_requests', 0))} request(s) from the agent run ({refused}); "
    if proxy.get("reconstructed"):
        hosts = ", ".join(proxy.get("allowed_hosts", [])) or "none"
        return (head + f"allowed hosts: {hosts}. Reconstructed from the stored proxy log, "
                "proof requests subtracted by their known number.")
    allowed = ", ".join(f"{host} x{count}" for host, count in proxy.get("allowed_connections", {}).items()) or "none"
    return (head + f"allowed connections: {allowed}. "
            "Counted from the proxy log; the isolation proof's own requests are excluded.")


def case_input_note(case_id: str) -> str | None:
    """One public line about how this case's agent input differs from upstream, if any."""
    path = ROOT / "cases" / case_id / "input-note.txt"
    if not path.is_file():
        return None
    note = path.read_text(encoding="utf-8").strip()
    if not note or "\n" in note or len(note) > 600:
        raise CaseExecutionError("parse", "invalid case input note")
    return note


def gate_reason(gate: dict[str, object]) -> str:
    name = str(gate["name"])
    evidence = gate.get("evidence")
    raw = evidence.get("reason") if isinstance(evidence, dict) else None
    if not isinstance(raw, str) or not raw.strip():
        return f"{name}: failed"
    first_line = raw.splitlines()[0].strip()
    # The gate's reason is public, but checkout locations and raw logs are not.
    without_paths = re.sub(r"(?<!\w)(?:[A-Za-z]:[\\/]|/(?!/))\S+", "[path]", first_line)
    return " ".join(without_paths.split())[:240] or f"{name}: failed"


def summary_reason(raw: object, fallback: str) -> str:
    """Publish a short verifier summary, never a path or raw diagnostic log."""
    if not isinstance(raw, str) or not raw.strip():
        return fallback
    first_line = " ".join(raw.splitlines()[0].split())
    if (
        not first_line
        or len(first_line) > 240
        or re.search(r"[\\/]|\b(?:traceback|stdout|stderr|log)\b", first_line, re.I)
    ):
        return fallback
    return first_line


def render(case_id: str, verdict: str, gates: dict[str, str], seconds: float | None,
           agent_name: str, agent_version: str, checked_at_utc: str,
           reason: str | None = None, result_note: str | None = None,
           patch_sha256: str | None = None, input_note: str | None = None,
           attempt_note: str | None = None, network_note: str | None = None,
           revision: str = LEGACY_REVISION, reference_line: str | None = None) -> str:
    duration = "pending" if seconds is None else f"{seconds:.1f} s"
    rows = "\n".join(f"| {gate} | {gates.get(gate, 'SKIPPED')} |" for gate in GATES)
    note = "\n\nStatus: no agent fix yet" if verdict == "PENDING" else ""
    verifier_note = " (configured; not run)" if verdict == "PENDING" else ""
    if verdict == "INFRASTRUCTURE_ERROR":
        verifier_note = " (attempted; no code verdict)"
    if verdict == "NO_PATCH":
        verifier_note = " (not run; nothing to verify)"
    patch_line = (
        f"sha256 {patch_sha256}" if patch_sha256
        else "none (empty)" if verdict == "NO_PATCH" else "sha256 pending"
    )
    reason_line = f"\n\nReason: {reason}" if reason is not None else ""
    note_line = f"\n\nNote: {result_note}" if verdict == "REJECTED" and result_note else ""
    if input_note:
        note_line += f"\n\nInput: {input_note}"
    if attempt_note:
        note_line += f"\n\nAttempt: {attempt_note}"
    if network_note:
        note_line += f"\n\nNetwork: {network_note}"
    return (f"# {case_id}\n\nVerdict: **{verdict}**{note}{reason_line}{note_line}\n\nElapsed: {duration}\n\n"
            f"Verifier: cplus {revision} · {checked_at_utc}{verifier_note}\n\n"
            + (f"Reference: {reference_line}\n\n" if reference_line else "") +
            f"Patch: {patch_line}\n\n"
            f"Agent: {agent_name} · Version: {agent_version}\n\n"
            f"| Check | Status |\n| --- | --- |\n{rows}\n")


def baseline_summary(spec_path: Path) -> str:
    """Numbers only: how the bug baseline went (runs, failures, planned runs after the fix).

    Printed to the job log so a NOT_VERIFIABLE for a missing baseline can be explained.
    No command output, paths or test text is included.
    """
    try:
        data = json.loads(spec_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "bug baseline: not readable"
    parts = [f"{key}={data[key]}" for key in ("completed_runs", "failures", "required_runs_after_fix")
             if isinstance(data.get(key), int)]
    runs = data.get("runs")
    if isinstance(runs, list):
        per_run = []
        for run in runs:
            if not isinstance(run, dict):
                continue
            fields = [f"{key}={run[key]}" for key in ("exit_code", "timed_out", "duration_seconds", "status", "verdict")
                      if isinstance(run.get(key), (int, float, bool)) or (
                          isinstance(run.get(key), str) and re.fullmatch(r"[A-Za-z_ -]{1,24}", run[key]))]
            per_run.append("{" + ",".join(fields) + "}")
        parts.append("runs=[" + " ".join(per_run) + "]")
        parts.append("signatures=" + _signature_counts(runs))
    for key in ("kind", "frequency", "timed_out_runs", "requested_runs", "run_timeout_s", "duration_s"):
        value = data.get(key)
        if isinstance(value, (int, float)) or (isinstance(value, str) and re.fullmatch(r"[a-z_]{1,24}", value)):
            parts.append(f"{key}={value}")
    return "bug baseline: " + " ".join(parts)


def _signature_counts(runs: list[object]) -> str:
    """Which failures the runs had: kind, test name, file name, line (short, character-limited)."""
    counts: dict[str, int] = {}
    for run in runs:
        signature = run.get("signature") if isinstance(run, dict) else None
        if not isinstance(signature, dict):
            label = "none"
        else:
            fields = []
            for key in ("kind", "test_name", "file", "line", "function", "exit_status"):
                value = signature.get(key)
                if key == "file" and isinstance(value, str):
                    value = value.replace(chr(92), "/").rsplit("/", 1)[-1]
                if isinstance(value, int) or (isinstance(value, str) and re.fullmatch(r"[\w .:+<>~-]{1,60}", value)):
                    fields.append(f"{key}={value}")
            label = "(" + ",".join(fields) + ")"
        counts[label] = counts.get(label, 0) + 1
    return "[" + " ".join(f"{label}x{count}" for label, count in sorted(counts.items())) + "]"


def case_gitlinks(scratch: Path, base: str) -> dict[str, str]:
    """Submodule path -> commit pinned in the tree of ``base``."""
    listing = quiet_stage("submodules", "snapshot unavailable", "git", "ls-tree", "-r", base, cwd=scratch)
    if listing.returncode:
        raise CaseExecutionError("submodules", "snapshot unavailable")
    found = {}
    for line in listing.stdout.splitlines():
        meta, _, path = line.partition("\t")
        fields = meta.split()
        if len(fields) == 3 and fields[0] == "160000":
            found[path] = fields[2]
    return found


def prepare_submodules(scratch: Path, case: dict[str, object], base: str) -> None:
    """Fetch the submodules of the base, recursively and at the pinned commits, before cplus runs without network.

    ``--checkout`` is required: these repositories set ``update = none`` in .gitmodules, which a plain
    ``git submodule update --init`` obeys. Only https is allowed, because .gitmodules belongs to the project.
    The pins in case.yaml must be the ones in the tree.
    """
    pins = case.get("submodules")
    if not pins:
        return
    if not isinstance(pins, list) or not all(isinstance(pin, dict) for pin in pins):
        raise CaseExecutionError("submodules", "invalid snapshot description")
    expected = {pin.get("path"): pin.get("commit") for pin in pins}
    if expected != case_gitlinks(scratch, base):
        raise CaseExecutionError("submodules", "pins in case.yaml differ from the base revision")
    done = quiet_stage("submodules", "snapshot unavailable", "git", *HTTPS_ONLY, "submodule", "update",
                       "--checkout", "--init", "--recursive", "--quiet", cwd=scratch)
    if done.returncode:
        raise CaseExecutionError("submodules", "snapshot unavailable")


def case_module(case: dict[str, object]) -> str | None:
    """The ctest module a Unity case names in its ``test`` command (``-R '^module$'``), unescaped."""
    match = MODULE_IN_TEST.search(str(case.get("test", "")))
    return None if match is None else re.sub(r"\\(.)", r"\1", match.group(1))


def check_unity_reference(case: dict[str, object], granularity: object, command: object, framework: object,
                          stage: str) -> None:
    """cplus chooses the reference test of a Unity case itself; its choice must be the one case.yaml records."""
    if framework is None:
        raise CaseExecutionError(stage, "cplus did not detect Unity in the checkout")
    if granularity != case.get("bug_test_granularity"):
        raise CaseExecutionError(stage, "cplus chose a different reference granularity than case.yaml")
    module = MODULE_IN_TEST.search(str(command or ""))
    if module is None or re.sub(r"\\(.)", r"\1", module.group(1)) != case_module(case):
        raise CaseExecutionError(stage, "cplus chose a different reference test than case.yaml")


def public_reference_line(raw: object) -> str | None:
    """cplus's one-line description of the reference test, if it is short and has no path or log."""
    if not isinstance(raw, str):
        return None
    line = " ".join(raw.split())
    line = line.removeprefix("Reference test granularity: ")
    return line if 0 < len(line) <= 240 and not re.search(r"[\\/]|\b(?:traceback|stdout|stderr)\b", line, re.I) else None


def run_case(case_id: str, agent_id: str) -> tuple[str, dict[str, str], float | None, str | None]:
    case_dir = ROOT / "cases" / case_id
    if not case_dir.is_dir():
        raise CaseExecutionError("parse", "case metadata unavailable")
    try:
        case = json.loads((case_dir / "case.yaml").read_text(encoding="utf-8"))
        patch = case_dir / "agents" / agent_id / "agent-fix.patch"
        patch_bytes = patch.read_bytes()
        agent = json.loads((patch.parent / "agent.yaml").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise CaseExecutionError("parse", "case metadata unavailable") from exc
    if not patch_bytes.strip():
        if no_patch_recorded(case_id, agent_id):
            if any(not agent.get(key) for key in (
                "name", "version", "model", "invocation", "date_utc", "environment", "attempt_note"
            )):
                raise CaseExecutionError("parse", "incomplete agent metadata")
            return "NO_PATCH", {}, None, "the agent finished its attempt without changing any file"
        if patch_bytes or agent.get("patch_sha256") is not None:
            raise CaseExecutionError("parse", "invalid pending patch metadata")
        return "PENDING", {}, None, None
    if not isinstance(agent, dict) or any(not agent.get(key) for key in (
        "name", "version", "model", "invocation", "date_utc", "environment", "attempt_note"
    )):
        raise CaseExecutionError("parse", "incomplete agent metadata")
    if hashlib.sha256(patch_bytes).hexdigest() != agent.get("patch_sha256"):
        raise CaseExecutionError("parse", "patch hash mismatch")
    scratch = TEMP / "case-checkouts" / case_id / agent_id
    scratch.parent.mkdir(parents=True, exist_ok=True)
    clone = quiet_stage("clone", "source repository unavailable", "git", "clone", "--quiet",
                        "--no-checkout", case["repo"], str(scratch))
    if clone.returncode:
        raise CaseExecutionError("clone", "source repository unavailable")
    base, fix = case["base"], case["upstream_fix"]
    if quiet_stage("checkout base", "base revision unavailable", "git", "checkout",
                   "--quiet", "--detach", base, cwd=scratch).returncode:
        raise CaseExecutionError("checkout base", "base revision unavailable")
    prepare_submodules(scratch, case, base)
    fix_patch = quiet_stage("upstream fix", "reference revision unavailable", "git", "diff",
                            base, fix, cwd=scratch)
    if fix_patch.returncode or not fix_patch.stdout:
        raise CaseExecutionError("upstream fix", "reference revision unavailable")
    upstream_patch = TEMP / f"{case_id}-{agent_id}-upstream.patch"
    upstream_patch.write_text(fix_patch.stdout, encoding="utf-8")
    config = ("version: 1\nbuild_system: cmake\n"
              f"build: {case['build']}\ntest: {case['test']}\n"
              "build_environment: default image\nprotected_paths:\n"
              "- test/**\n- tests/**\n- .github/**\n- '**/*.supp'\n")
    (scratch / "cplus.yaml").write_text(config, encoding="utf-8")
    spec = TEMP / f"{case_id}-{agent_id}-bug-spec.json"
    reference_name = case.get("reference_test_name")
    if reference_name is not None and (
        not isinstance(reference_name, str)
        or not re.fullmatch(r"[A-Za-z_]\w*\.[A-Za-z_]\w*", reference_name)
    ):
        raise CaseExecutionError("parse", "invalid reference test selection")
    try:
        revision = case_revision(case_id)
    except (OSError, ValueError) as exc:
        raise CaseExecutionError("parse", "invalid verifier revision") from exc
    cplus = cplus_command(revision)
    unity = case.get("bug_test_granularity") is not None
    bug_args = [cplus, "bug", "--project", str(scratch), "--from-fix",
                str(upstream_patch), "--export", str(spec)]
    if reference_name is not None:
        bug_args.extend(("--command", f"GTEST_FILTER={reference_name} {case['test']}"))
    bug = quiet_stage("cplus bug baseline", "reference test did not reproduce", *bug_args)
    verdict_words = sorted(set(re.findall(r"(REPRODUCED|NOT_VERIFIABLE|ERROR)", bug.stdout or "")))
    print(f"{case_id}/{agent_id}: cplus bug exit={bug.returncode} words={verdict_words} "
          f"{baseline_summary(spec) if spec.is_file() else 'no bug spec written'}", flush=True)
    if bug.returncode or "REPRODUCED" not in bug.stdout or not spec.is_file():
        raise CaseExecutionError("cplus bug baseline", "reference test did not reproduce")
    if unity:
        try:
            recorded = json.loads(spec.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise CaseExecutionError("cplus bug baseline", "bug specification unreadable") from exc
        if not isinstance(recorded, dict):
            raise CaseExecutionError("cplus bug baseline", "bug specification unreadable")
        check_unity_reference(case, recorded.get("granularity"), recorded.get("command"),
                              recorded.get("test_framework"), "cplus bug baseline")
    started = time.monotonic()
    verify_args = [cplus, "verify", "--project", str(scratch), "--patch",
                   str(patch), "--bug-spec", str(spec),
                   "--reference-test-from-fix", str(upstream_patch), "--json"]
    if reference_name is not None:
        verify_args.extend(("--reference-test-name", reference_name))
    verify = quiet_stage("verify", "verifier could not evaluate patch", *verify_args)
    elapsed = time.monotonic() - started
    try:
        report = extract_json(verify.stdout)
    except ValueError as exc:
        raise CaseExecutionError("parse", "no valid verifier result") from exc
    reference_lines.pop((case_id, agent_id), None)
    reported = report.get("reference_test")
    if unity and isinstance(reported, dict) and reported.get("granularity") != case.get("bug_test_granularity"):
        raise CaseExecutionError("verify", "cplus reported a different reference granularity than case.yaml")
    if unity and isinstance(reported, dict):
        line = public_reference_line(reported.get("description"))
        if line is not None:
            reference_lines[(case_id, agent_id)] = line
    verdict = report.get("verdict")
    infrastructure = report.get("infrastructure_error")
    if infrastructure:
        if isinstance(infrastructure, str) and "reference test has no unique test name" in infrastructure:
            raise CaseExecutionError("verify", "upstream reference test could not be selected")
        if isinstance(infrastructure, str) and "did not reproduce the bug after revert" in infrastructure:
            raise CaseExecutionError("verify", "reference failure was absent after source revert")
        raise CaseExecutionError("verify", "verifier could not evaluate patch")
    if verdict not in VERDICTS:
        raise CaseExecutionError("parse", "invalid verifier verdict")
    raw_gates = report.get("gates")
    if not isinstance(raw_gates, list):
        raise CaseExecutionError("parse", "invalid verifier result")
    gates: dict[str, str] = {}
    reason: str | None = None
    for gate in raw_gates:
        if not isinstance(gate, dict):
            raise CaseExecutionError("parse", "invalid verifier result")
        name, status = gate.get("name"), gate.get("status")
        if status not in STATUSES:
            raise CaseExecutionError("parse", "invalid verifier result")
        if name not in GATES:
            # The verifier may include a diagnostic gate on an inconclusive result.
            # Keep its name and evidence out of the public summary, but never
            # publish a positive code verdict if an unknown check appeared.
            if verdict in {"NOT_VERIFIABLE", "ERROR"}:
                continue
            raise CaseExecutionError("parse", "unexpected verifier check")
        gates[str(name)] = str(status)
        if status == "FAIL" and reason is None:
            reason = gate_reason(gate)
    if verdict == "REJECTED" and reason is None:
        reason = "verifier rejected the patch; no failing gate reason provided"
    if verdict in {"NOT_VERIFIABLE", "ERROR"} and reason is None:
        reason = summary_reason(report.get("summary"), f"verifier returned {str(verdict).lower()}")
    reference_reason = summary_reason(report.get("summary"), "")
    if reference_reason.startswith("judged by upstream reference test '"):
        reason = reference_reason
    return str(verdict), gates, elapsed, reason


def main() -> int:
    failed = False
    checked_at_utc = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    for case_id, agent_id in selected_pairs():
        agent_name, agent_version = "not recorded", "not recorded"
        revision = case_revision_or_legacy(case_id)
        reference_lines.pop((case_id, agent_id), None)
        result_note = None
        input_note = None
        attempt_note = None
        network_note = None
        try:
            agent_name, agent_version = agent_identity(case_id, agent_id)
            verdict, gates, seconds, reason = run_case(case_id, agent_id)
            result_note = agent_result_note(case_id, agent_id)
            input_note = case_input_note(case_id)
            attempt_note = agent_attempt_note(case_id, agent_id)
            network_note = agent_network_note(case_id, agent_id)
        except Exception as exc:
            public_reason = (exc.public_reason if isinstance(exc, CaseExecutionError)
                             else "parse: unexpected case processing error")
            verdict, gates, seconds, reason = (
                "INFRASTRUCTURE_ERROR", {}, None, public_reason
            )
            failed = True
        result = RESULTS_DIR / case_id / f"{agent_id}.md"
        result.parent.mkdir(parents=True, exist_ok=True)
        result.write_text(
            render(case_id, verdict, gates, seconds, agent_name, agent_version, checked_at_utc,
                   reason, result_note, patch_digest(case_id, agent_id), input_note, attempt_note, network_note,
                   revision, reference_lines.get((case_id, agent_id))),
            encoding="utf-8",
        )
        label = f"{verdict} - no agent fix yet" if verdict == "PENDING" else verdict
        print(f"{case_id}/{agent_id}: {label}" + (f"; Reason: {reason}" if reason else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    if sys.argv[1:] == ["--has-patches"]:
        print("true" if any((ROOT / "cases" / case_id / "agents" / agent_id / "agent-fix.patch").read_bytes().strip()
                            for case_id, agent_id in selected_pairs()) else "false")
    elif sys.argv[1:] == ["--revisions"]:
        # the cplus revisions the selected pairs need, for scripts/install_private.sh (one per case, deduplicated)
        print(" ".join(sorted({case_revision_or_legacy(case_id) for case_id, _ in selected_pairs()})))
    elif sys.argv[1:] == ["--list-pairs"]:
        for case_id, agent_id in selected_pairs():
            print(f"{case_id}/{agent_id}")
    else:
        sys.exit(main())

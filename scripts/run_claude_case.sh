#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 U-Pump
#
# One Claude Code attempt on one case, inside the Docker sandbox of agent_sandbox.sh.
#
# Usage: run_claude_case.sh <case-id> <out-dir>
# With DRY_RUN=1 it stops after the isolation proof, before the agent, and needs no API key.
# Environment: BENCH_INPUT_TOKEN (read access to u-pump/bench-in-*),
#              ANTHROPIC_API_KEY, AGENT_MODEL, GITHUB_RUN_URL.
#
# <out-dir> receives only what may be published: result/agent-fix.patch, result/agent.yaml
# (or a public ERROR report), evidence/network-proof.log and evidence/proxy.log. The agent's
# transcript, its stderr and every other log stay in a private directory that is deleted at
# the end; only counts taken from the transcript (commands, network attempts, duration) are
# written to agent.yaml. Nothing of the transcript is printed to the job log.
set -u

CASE_ID=${1:?case id}
OUT=${2:?out dir}
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
SANDBOX=(bash "$HERE/agent_sandbox.sh")
MODEL=${AGENT_MODEL:?AGENT_MODEL}
PY=${PYTHON:-python3}
TMP=${RUNNER_TEMP:-/tmp}
WORK="$TMP/work/$CASE_ID"
UPSTREAM="$TMP/upstream/$CASE_ID"
PRIV="$TMP/private/$CASE_ID"
mkdir -p "$OUT/result/results" "$OUT/evidence" "$PRIV"
OUT=$(cd "$OUT" && pwd)
VERSION=""

fail() {
    "$PY" "$HERE/collect_agent_run.py" error --case "$CASE_ID" --reason "$1" \
        --results-dir "$OUT/result/results" --version "$VERSION" >/dev/null
    echo "ERROR: $1"
    exit 1
}

cleanup() {
    "${SANDBOX[@]}" down >/dev/null 2>&1 || true
    rm -rf "$WORK" "$UPSTREAM" "$PRIV" "${ASKPASS:-}"
}
trap cleanup EXIT

[ -n "${BENCH_INPUT_TOKEN:-}" ] || fail "input: BENCH_INPUT_TOKEN is not configured"
if [ -z "${DRY_RUN:-}" ]; then
    [ -n "${ANTHROPIC_API_KEY:-}" ] || fail "auth: ANTHROPIC_API_KEY is not configured"
fi

case_file="$ROOT/cases/$CASE_ID/case.yaml"
[ -f "$case_file" ] || fail "input: unknown case"
upstream_repo=$("$PY" -c 'import json,sys;print(json.load(open(sys.argv[1]))["repo"])' "$case_file")
patch_file="$ROOT/cases/$CASE_ID/agents/claude-code/agent-fix.patch"
if [ -s "$patch_file" ]; then fail "input: first patch already recorded"; fi

# 1. Fetch the frozen input (private) with a token that never reaches the agent.
ASKPASS="$TMP/askpass-$CASE_ID"
printf '#!/bin/sh\ncase "$1" in *Username*) printf "x-access-token";; *) printf "%%s" "$BENCH_INPUT_TOKEN";; esac\n' > "$ASKPASS"
chmod 700 "$ASKPASS"
rm -rf "$WORK" "$UPSTREAM"
mkdir -p "$(dirname "$WORK")" "$(dirname "$UPSTREAM")"
GIT_ASKPASS="$ASKPASS" GIT_TERMINAL_PROMPT=0 git -c core.autocrlf=false clone -q --depth 1 --single-branch \
    "https://github.com/u-pump/bench-in-$CASE_ID.git" "$WORK" >/dev/null 2>&1 || fail "input: bench-in repository unavailable"
rm -f "$ASKPASS"
git clone -q --no-checkout "$upstream_repo" "$UPSTREAM" >/dev/null 2>&1 || echo "info: upstream clone unavailable; the hash comparison is skipped"

# 2. The input must be exactly the frozen one (the log holds only hashes and file names).
if ! "$PY" "$HERE/check_input.py" --case "$case_file" --input "$WORK" --upstream "$UPSTREAM" > "$PRIV/input-check.log"; then
    cat "$PRIV/input-check.log"
    fail "input: input check failed"
fi
cat "$PRIV/input-check.log"
"$PY" -c 'import sys;from pathlib import Path;Path(sys.argv[2]).write_text(Path(sys.argv[1]).read_text(encoding="utf-8").strip(), encoding="utf-8")' \
    "$WORK/TASK.md" "$PRIV/task.txt"

# 3. Build the sandbox and prove what it blocks, before the agent runs.
# The sandbox logs hold only build and probe output, never agent content, so they are
# printed when a step fails; the agent's own output never is.
if ! "${SANDBOX[@]}" build > "$PRIV/build.log" 2>&1; then
    cat "$PRIV/build.log"
    fail "sandbox: image build failed"
fi
VERSION=$(sed -n 's/^claude version: //p' "$PRIV/build.log")
IMAGE_ID=$(sed -n 's/^agent image id: //p' "$PRIV/build.log")
"${SANDBOX[@]}" up || fail "sandbox: egress proxy did not start"
"${SANDBOX[@]}" proof "$OUT/evidence/network-proof.log" || fail "sandbox: network isolation proof failed"
if [ -n "${DRY_RUN:-}" ]; then
    echo "dry run: input checked and sandbox proven; stopped before the agent, no API call"
    exit 0
fi

# 4. One attempt. Only the exit status and the files in $WORK are kept; the transcript
#    goes to the private directory and is never printed.
started=$(date +%s)
"${SANDBOX[@]}" agent "$WORK" "$PRIV/task.txt" "$PRIV/transcript.jsonl" "$PRIV/agent-stderr.log" "$MODEL"
agent_exit=$?
duration=$(( $(date +%s) - started ))
"${SANDBOX[@]}" proxy-log "$OUT/evidence/proxy.log"
if [ "$agent_exit" -eq 124 ] || [ "$agent_exit" -eq 137 ]; then fail "agent: timed out after 60 minutes"; fi
[ "$agent_exit" -eq 0 ] || fail "agent: Claude Code exited with code $agent_exit"

# 5. Save the first patch exactly as produced, then the evidence.
"${SANDBOX[@]}" patch "$WORK" "$OUT/result" || fail "agent: could not save the patch"
"$PY" "$HERE/collect_agent_run.py" record --transcript "$PRIV/transcript.jsonl" \
    --patch "$OUT/result/agent-fix.patch" --out-dir "$PRIV" --version "$VERSION" \
    --requested-model "$MODEL" --run-url "${GITHUB_RUN_URL:-local}" --image "$IMAGE_ID" \
    --proxy-log "$OUT/evidence/proxy.log" --duration-seconds "$duration" \
    --proof-note "all isolation proofs passed before the run; log in the run artifact" \
    || fail "$(cat "$PRIV/error-reason.txt" 2>/dev/null || echo 'agent: attempt not recorded')"
cp "$PRIV/agent.yaml" "$OUT/result/agent.yaml"
exit 0

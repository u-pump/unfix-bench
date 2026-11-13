#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 U-Pump
#
# Check every case's frozen agent input against its case.yaml (input_sha256 and files).
# Usage: probe_inputs.sh <log-file>   Environment: BENCH_INPUT_TOKEN
set -u
LOG=${1:?log file}
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
TMP=${RUNNER_TEMP:-/tmp}/probe-inputs
: > "$LOG"
if [ -z "${BENCH_INPUT_TOKEN:-}" ]; then
    echo "SKIPPED: BENCH_INPUT_TOKEN is not configured; inputs were not checked" | tee -a "$LOG"
    exit 0
fi
ASKPASS="$TMP.askpass"
printf '#!/bin/sh\ncase "$1" in *Username*) printf "x-access-token";; *) printf "%%s" "$BENCH_INPUT_TOKEN";; esac\n' > "$ASKPASS"
chmod 700 "$ASKPASS"
trap 'rm -rf "$ASKPASS" "$TMP"' EXIT
failed=0
for case_file in "$ROOT"/cases/*/case.yaml; do
    id=$(basename "$(dirname "$case_file")")
    repo=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["repo"])' "$case_file")
    rm -rf "$TMP"; mkdir -p "$TMP"
    if ! GIT_ASKPASS="$ASKPASS" GIT_TERMINAL_PROMPT=0 git -c core.autocrlf=false clone -q --depth 1 --single-branch \
        "https://github.com/u-pump/bench-in-$id.git" "$TMP/input" >/dev/null 2>&1; then
        echo "FAIL  $id: bench-in repository unavailable" | tee -a "$LOG"; failed=1; continue
    fi
    if ! git clone -q --no-checkout "$repo" "$TMP/upstream" >/dev/null 2>&1; then
        echo "FAIL  $id: upstream repository unavailable" | tee -a "$LOG"; failed=1; continue
    fi
    if python3 "$HERE/check_input.py" --case "$case_file" --input "$TMP/input" --upstream "$TMP/upstream" >> "$LOG" 2>&1; then
        echo "OK    $id" | tee -a "$LOG"
    else
        echo "FAIL  $id: input check failed" | tee -a "$LOG"; failed=1
    fi
done
exit "$failed"

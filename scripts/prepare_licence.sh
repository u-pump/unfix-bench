#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 U-Pump
# Put the cplus licence key (secret UNFIX_LICENCE) into a file for cplus 0.2.5+: UNFIX_LICENCE_FILE.
# The key goes to a file, never to the environment of a later step: a process started by unfix inherits the
# environment, and a file in $RUNNER_TEMP/unfix is outside every checkout and every agent workspace.
# Outputs: available=true|false, file=<path> (the path is not a secret; the key is never printed).
# Without a key: a pull request from a fork has no secrets, so the cplus steps are skipped (available=false) and the
# run summary says so; anywhere else a missing key is a configuration error and the step fails.
set -eu
out="${GITHUB_OUTPUT:-/dev/null}"
summary="${GITHUB_STEP_SUMMARY:-/dev/null}"
if [ -z "${UNFIX_LICENCE:-}" ]; then
  if [ "${IS_FORK_PR:-}" = 'true' ]; then
    message='Skipped: licence key is not available to pull requests from forks. A maintainer re-runs this from a branch in the main repository.'
    echo "$message"
    echo "$message" >> "$summary"
    echo 'available=false' >> "$out"
    exit 0
  fi
  echo 'Licence key missing: the repository secret UNFIX_LICENCE is empty'
  exit 1
fi
case "${RUNNER_TEMP:-}" in
  /*) ;;
  *) echo 'Runner temp unavailable'; exit 1 ;;
esac
dir="$RUNNER_TEMP/unfix"
umask 077
mkdir -p "$dir"
chmod 700 "$dir"
printf '%s' "$UNFIX_LICENCE" > "$dir/licence.key"
chmod 600 "$dir/licence.key"
echo 'available=true' >> "$out"
echo "file=$dir/licence.key" >> "$out"
echo 'Licence key written to a private file'

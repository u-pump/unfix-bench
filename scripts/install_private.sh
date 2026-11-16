#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 U-Pump
# Install the private verifier, one virtual environment per revision: scripts/install_private.sh <revision>...
# The revisions come from `python scripts/verify_cases.py --revisions` (each case is pinned to one). The first
# ten cases stay on their own revision; newer cases use a newer one. verify_cases.py runs
# $CPLUS_VENV_ROOT/<revision>/bin/cplus, so a result can only carry the revision that produced it.
set -eu
if [ -z "${CPLUS_READ_TOKEN:-}" ]; then
  echo 'Verifier token missing'
  exit 1
fi
case "${RUNNER_TEMP:-}" in
  /*) ;;
  *) echo 'Runner temp unavailable'; exit 1 ;;
esac
if [ "$#" -eq 0 ]; then
  echo 'No verifier revision requested'
  exit 1
fi
for revision in "$@"; do
  case "$revision" in
    *[!0-9a-f]*|'') echo 'Invalid verifier revision'; exit 1 ;;
  esac
  if [ "${#revision}" -ne 40 ]; then
    echo 'Invalid verifier revision'
    exit 1
  fi
done
source_dir="$RUNNER_TEMP/cplus-src"
venv_root="$RUNNER_TEMP/cplus-venvs"
printf '#!/bin/sh\ncase "$1" in *Username*) printf "x-access-token";; *) printf "%%s" "$CPLUS_READ_TOKEN";; esac\n' > "$RUNNER_TEMP/askpass"
chmod 700 "$RUNNER_TEMP/askpass"
trap 'rm -f "$RUNNER_TEMP/askpass"; rm -rf -- "$source_dir"' EXIT
GIT_ASKPASS="$RUNNER_TEMP/askpass" GIT_TERMINAL_PROMPT=0 git clone -q https://github.com/u-pump/c-plus.git "$source_dir" >/dev/null 2>&1 || { echo 'Verifier install failed'; exit 1; }
rm -f "$RUNNER_TEMP/askpass"
for revision in "$@"; do
  if [ -d "$venv_root/$revision" ]; then
    continue
  fi
  git -C "$source_dir" checkout -q --detach "$revision" >/dev/null 2>&1 || { echo 'Verifier revision unavailable'; exit 1; }
  python -m venv "$venv_root/$revision" >/dev/null 2>&1 || { echo 'Verifier install failed'; exit 1; }
  "$venv_root/$revision/bin/python" -m pip install -q "$source_dir" >/dev/null 2>&1 || { echo 'Verifier install failed'; exit 1; }
  test -x "$venv_root/$revision/bin/cplus" || { echo 'Verifier install failed'; exit 1; }
  git -C "$source_dir" clean -qfdx >/dev/null 2>&1 || true
  echo "Installed verifier revision $revision"
done
rm -rf -- "$source_dir"
if [ -n "${GITHUB_ENV:-}" ]; then
  echo "CPLUS_VENV_ROOT=$venv_root" >> "$GITHUB_ENV"
fi

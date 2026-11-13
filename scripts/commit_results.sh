#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 U-Pump
set -eu
git add results
if git diff --cached --quiet; then exit 0; fi
git -c user.name='cplus-bench-bot' -c user.email='cplus-bench-bot@users.noreply.github.com' commit -qm 'Update verification summaries'
printf '#!/bin/sh\ncase "$1" in *Username*) printf "x-access-token";; *) printf "%%s" "$RESULTS_TOKEN";; esac\n' > "$RUNNER_TEMP/askpass"
chmod 700 "$RUNNER_TEMP/askpass"
trap 'rm -f "$RUNNER_TEMP/askpass"' EXIT
GIT_ASKPASS="$RUNNER_TEMP/askpass" GIT_TERMINAL_PROMPT=0 git push -q origin HEAD:"$GITHUB_REF_NAME" >/dev/null 2>&1

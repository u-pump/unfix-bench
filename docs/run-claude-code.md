# Running Claude Code on a case

Claude Code runs only in GitHub Actions: workflow **Run Claude Code attempt** (`.github/workflows/run-claude-code.yml`). Only the repository owner can start it. It never runs on a pull request.

## What one run does

1. **Plan.** Picks the cases with no recorded first attempt. A case that already has a patch, or a recorded `NO_PATCH`, is refused: one attempt per case.
2. **Input.** Clones the private `u-pump/bench-in-<id>` snapshot, then checks it against `case.yaml`: one root commit, exact `TASK.md`, `input_sha256` recomputed from the upstream base commit, and a file-by-file comparison. Any mismatch stops the case with an ERROR.
3. **Sandbox.** Builds two images (the agent image pinned to Claude Code `2.1.323`, and a filtering proxy), creates a Docker network with `--internal` (no route to anything), and starts the proxy on it. The proxy forwards `CONNECT` to `api.anthropic.com:443` and refuses every other host and port.
4. **Proof.** Before the agent starts, the log shows that from the agent's container `github.com`, `example.com`, `1.1.1.1` and `api.anthropic.com` (without the proxy) are unreachable, DNS does not resolve, `api.anthropic.com:443` through the proxy is reachable, the root filesystem is read-only, the user is not root and has no capabilities, and the invocation flags are accepted. If any proof fails the agent is not started.
5. **Attempt.** Runs `claude -p` once with the exact `TASK.md` on stdin, model `claude-opus-5-5`, effort at the default, 60 minutes at most. Tools: Bash, Read, Edit, Write, Glob, Grep. Web tools, MCP, memory, `CLAUDE.md`, plugins and hooks are off. The OAuth token is passed in the environment of the container; it is not scrubbed from the commands the agent runs (see the residual risk in [DECISIONS.md](DECISIONS.md)), which is why every uploaded file is scanned.
6. **Patch.** In a separate container with no network: `git add -A` (excluding `build*/`) and `git diff --cached --binary`. The first patch is saved byte-for-byte; nothing edits it.
7. **Evidence.** `agent.yaml` records the Claude Code version, requested and actual model, session id, UTC date, patch SHA-256, image id, counts taken from the transcript (Bash commands, tool calls, turns, duration), the commands that tried to reach the network, and the hosts the proxy allowed and refused. An attempt counts only if Claude Code started, ended normally, and at least one Bash command finished successfully.
8. **What is published.** The agent's transcript and its stderr are never printed to the job log and never uploaded; they live in a private directory of the runner that is deleted at the end. The run artifact holds only the patch, `agent.yaml`, the network-isolation proof log and the proxy log, each scanned first for the token and for anything shaped like an Anthropic token. A hit deletes all files of the run and fails it. Artifacts of a public repository can be downloaded by anyone, so nothing is uploaded unscanned.
9. **Verdict.** `scripts/verify_cases.py` runs with the pinned verifier revision, exactly as for Codex CLI. An empty patch from a completed attempt is **NO_PATCH**.
10. **Pull request.** A job commits the patch, `agent.yaml`, the report and the regenerated README tables to a branch and opens a pull request. Nothing is published until the owner merges it.

A run that does not complete an attempt (input mismatch, failed isolation proof, API unavailable, timeout, no successful command) publishes an **ERROR** report with its reason and records no patch; the case stays open for a rerun.

## Running it

**Actions → Run Claude Code attempt → Run workflow.**

- `case_id`: one case, or blank for every open case.
- `probe_only`: builds the sandbox and prints the isolation proof and the input check for all ten cases, without the Claude token and without an attempt. Run this first.

Setup of the secrets is in [owner-setup.md](owner-setup.md).

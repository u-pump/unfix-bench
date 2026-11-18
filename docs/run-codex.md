# Running Codex CLI

Codex CLI runs in GitHub Actions for cases 11 and later: workflow **Run Codex CLI attempt** (`.github/workflows/run-codex.yml`). Cases 1-10 were run with Codex CLI on a local machine and are not run again. Only the repository owner can start it. It is the counterpart of [the Claude Code workflow](run-claude-code.md); read that page for the steps both share. Only the differences are listed here.

## What is the same as for Claude Code

The image (`docker/claude-agent`, which contains both CLIs, `ruby` and `unifdef`), the hardening flags (read-only root, non-root user, no capabilities, `--internal` network), the egress proxy (one API host on port 443, everything else refused), the input check against `inputs/bench-in-heads.json`, the isolation proof before the agent starts (a failed proof stops the case), one attempt of at most 60 minutes, the patch taken in a separate container without network and saved byte for byte, the secret scan before every upload, the verifier revision of the case, and the pull request opened by the `record` job.

## What differs

| | Claude Code | Codex CLI |
| --- | --- | --- |
| Reachable host | `api.anthropic.com:443` | `api.openai.com:443` |
| Secret | `ANTHROPIC_API_KEY` | `OPENAI_API_KEY` (passed to the container as `CODEX_API_KEY`) |
| Version, model | `2.1.323`, `claude-opus-5-5` | `0.164.0`, `gpt-6-sol`, reasoning `medium` (fixed in the workflow, the Dockerfile and `agent_sandbox.sh`) |
| Invocation | `claude -p ... --safe-mode` | `codex exec --json --ephemeral --strict-config --dangerously-bypass-approvals-and-sandbox ...` (the container is the sandbox) |
| Transcript | stream-json | `--json` events; never published |
| Model in `agent.yaml` | reported by the CLI | the requested one (the transcript does not name it) |

`scripts/collect_codex_run.py` replaces `collect_agent_run.py` for this agent. An attempt counts if a thread started, a turn finished, no turn failed and at least one shell command ended with exit code 0. Anything else is published as an **ERROR** report with a reason from a fixed list, and the case stays open.

Codex asks hosts other than `api.openai.com` (for example `chatgpt.com` for a model list). The proxy refuses them, Codex goes on, and the refusals are counted per host in `agent.yaml` and in the result.

## Running it

**Actions → Run Codex CLI attempt → Run workflow.**

- `case_id`: one case, or blank for every case without a recorded Codex CLI attempt (the first ten cases already have one and are never planned).
- `probe_only`: builds the sandbox and prints the isolation proof and the input check, without the key and without an attempt. A pull request that changes the sandbox runs the same probe automatically. Run it first.

The secret and its handling are in [owner-setup.md](owner-setup.md).

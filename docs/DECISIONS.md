# Decisions

## BENCH-10: One result per case and agent

Each case keeps its frozen source metadata in `case.yaml`. Each agent gets its own immutable first patch and run metadata under `agents/<agent-id>/`, with a separate public verifier report under `results/<id>/<agent-id>.md`. Existing Codex patches and reports are moved byte-for-byte. This permits a second agent on the same frozen input without overwriting the original evidence.

## BENCH-10 review: sandboxed Claude commands and immutable reports

*The Claude Code part of this decision (WSL2 Bash sandbox) is superseded by BENCH-13; the report-caching part stands.*

Claude Code attempts run only under its Linux/WSL2 Bash sandbox with an empty strict network allowlist, no unsandboxed retry, and a required seccomp filter on WSL2. Sandbox availability is a startup gate; a successful Bash result is required before recording an attempt. Native Windows cannot run this agent. The CLI process, file tools, and host files readable by sandboxed commands remain outside the Bash boundary, and are disclosed in run metadata.

CI selects changed `(case, agent)` pairs from patch and metadata content. A byte-identical patch rename alone does not select a pair. A report with the same patch SHA-256 and verifier revision is retained unchanged. The ten preexisting Codex reports receive only a `Patch: sha256 <hash>` line; their verdicts, checks, elapsed times, and dates are unchanged. Explicit workflow dispatch selections override this cache.
Agent patch files use Git's `-text` attribute so a Windows checkout cannot change their bytes through line-ending conversion and cause a false SHA mismatch or rerun.

## BENCH-13: Claude Code runs in GitHub Actions, in a network-isolated container

**Where.** Claude Code runs in a workflow on `ubuntu-latest`, inside Docker. The WSL2 Bash-sandbox path was removed: its network block covered only Bash children, not the Claude process or file tools, and it could not be proven from a log. The Codex CLI local path is unchanged.

**Network.** The agent container is on an `--internal` Docker network, so it has no route to anything. A tinyproxy container on the same network forwards `CONNECT` to `api.anthropic.com:443` only (hostname filter, default deny, port 443 only). Before the agent starts, the log shows that `github.com`, `example.com`, a raw IP and `api.anthropic.com` without the proxy are unreachable and that `api.anthropic.com` through the proxy is reachable; a failed proof stops the case. The proxy log lists the hosts that were allowed and refused and goes into `agent.yaml`. If Claude Code needs another host, the run shows it as a refused host and the host is not added silently.

**Authentication and the token.** Subscription OAuth token (`claude setup-token`) as a repository secret, passed to the agent container as `CLAUDE_CODE_OAUTH_TOKEN`. The first plan was to also set `CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=1`, which strips credentials from the environment of the commands the agent runs. Claude Code 2.1.323 refuses to start with it unless bubblewrap works, and bubblewrap needs user namespaces, which means weakening the container (custom seccomp profile or extra capabilities). The container profile was kept strict and the scrub is off (`CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=0`), so a command the agent runs can read the token from its own environment or from `/proc/1/environ`. The agent has no reason to, but a deliberate or accidental read cannot be prevented. Mitigations: the only reachable host is `api.anthropic.com`, so the token cannot be sent anywhere else; nothing is uploaded before every file (patch, transcript, proxy log, proof log, metadata) is scanned for the token and for any `sk-ant-` string, and a hit deletes the run's files and fails it (an encoded copy would not be caught); artifacts live seven days; the token only makes model requests; the owner retires it on the day of the last run (revoking a `setup-token` token is not documented; see `owner-setup.md`). A gateway that injects the credential outside the container would remove the risk, at the price of a non-standard `ANTHROPIC_BASE_URL`; it was not chosen.

**Public surface.** The agent's transcript and stderr are not printed to the job log and not uploaded. Only the patch, `agent.yaml` (with counts of commands, network attempts and duration), the proof log and the proxy log are uploaded, after the secret scan.

**Same input, same verdict.** `input_sha256` is recomputed from the upstream base commit and the input repository is compared file by file before every attempt. The first patch is taken in a container with no network and is never edited. The verdict path is `verify_cases.py` with the pinned verifier revision, with no exception for Claude Code.

**Outcomes.** A run that completes an attempt with an empty patch is **NO_PATCH** (separate in the table; not PENDING, not VERIFIED). A run that does not complete an attempt is published as **ERROR** with a reason, records no patch and leaves the case open; this does not count as the single attempt. The README tables and totals are generated from `results/` by `scripts/render_readme.py` and checked in CI.

**Publishing.** The workflow opens a pull request with the patch, metadata, report and README; nothing is published until the owner merges it.

**Model.** `claude-opus-5-5`, effort at the default, both recorded. A run of another model (for example Fable 5.2) would be a separate column, not a replacement.

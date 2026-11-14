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

**Authentication and the key.** `ANTHROPIC_API_KEY` from a dedicated Console workspace with a monthly spend limit, as a repository secret, passed to the agent container and deleted after the ten runs. Anthropic's documentation states that in non-interactive mode (`-p`) the key "is always used when present" and ranks it above `CLAUDE_CODE_OAUTH_TOKEN` and the `/login` credentials, so no OAuth login is attempted. (An earlier plan used a subscription token from `claude setup-token`; its revocation is not documented and deleting the secret does not invalidate it, so it was dropped.) `CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=1`, which strips credentials from the commands the agent runs, makes Claude Code 2.1.323 require bubblewrap, and bubblewrap needs user namespaces, i.e. a weaker container profile. The container profile was kept strict and the scrub is off (`CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=0`), so a command the agent runs can read the key from its environment or from `/proc/1/environ`. The agent has no reason to, but a read cannot be prevented. Mitigations: the key can only spend inside its workspace and only up to the spend limit; the only reachable host is `api.anthropic.com`, so the key cannot be sent anywhere else; nothing is uploaded before every file (patch, proxy log, proof log, metadata) is scanned for the key and for any `sk-ant-` string, and a hit deletes the run's files and fails it (an encoded copy would not be caught); the transcript is never uploaded; artifacts live seven days; the key is deleted on the day of the last run. The documentation does not say which hosts Claude Code needs when authenticated by an API key; the proxy log of the isolation proof shows the hosts it actually contacted, and a refused host is reported, not added silently.

**Public surface.** The agent's transcript and stderr are not printed to the job log and not uploaded. Only the patch, `agent.yaml` (with counts of commands, network attempts and duration), the proof log and the proxy log are uploaded, after the secret scan.

**Same input, same verdict.** `input_sha256` is recomputed from the upstream base commit and the input repository is compared file by file before every attempt. The first patch is taken in a container with no network and is never edited. The verdict path is `verify_cases.py` with the pinned verifier revision, with no exception for Claude Code.

**Outcomes.** A run that completes an attempt with an empty patch is **NO_PATCH** (separate in the table; not PENDING, not VERIFIED). A run that does not complete an attempt is published as **ERROR** with a reason, records no patch and leaves the case open; this does not count as the single attempt. The README tables and totals are generated from `results/` by `scripts/render_readme.py` and checked in CI.

**Publishing.** The workflow opens a pull request with the patch, metadata, report and README; nothing is published until the owner merges it.

**Model.** `claude-opus-5-5`, effort at the default, both recorded. A run of another model (for example Fable 5.2) would be a separate column, not a replacement.

## BENCH-13: pinned agent inputs and the frozen `input_sha256`

**Reference input.** The agent input for Claude Code is exactly what Codex CLI received: the HEAD commit of each private `bench-in-<id>` repository, pinned in `inputs/bench-in-heads.json` (full commit and tree ids). No repository was pushed after the date of its Codex run; for `cpp-peglib-121`, `fmt-4800` and `spdlog-3049` the push and the run are on the same day, so their order cannot be shown. A run is refused unless the repository has exactly one commit, HEAD equals the pinned commit, and `TASK.md` equals the protocol text.

**`input_sha256` is information only.** Recomputing it from the upstream base (`git -c core.autocrlf=false archive --format=tar <base>` followed by the bytes of `ISSUE.md` and `TASK.md`, as `protocol.md` describes) matches `case.yaml` for `cpp-peglib-121`, `fmt-4800` and `zlibng-2465` and does not match for `fmt-4490`, `fmt-4742`, `fmt-4933`, `fmt-4942`, `fmt-4960`, `fmt-4978` and `spdlog-3049`. The frozen values were not changed. Searched for the code that produced them: the history of this repository (commits `05e7dbc`, `56419c0`, `7a06435` only add the values and describe the method) and the read-only copy of the benchmark repository contain no preparation script, so the method could not be reproduced. Variants tried without a match: order of the two files, trailing newlines, CRLF, BOM, `core.eol`, `tar`, `zip` and `tar.gz` formats, `--prefix`, `--worktree-attributes`, an archive of the input repository. For the seven cases the file contents of `bench-in-<id>` are still compared with the upstream base and printed in every run log.

**What differs from upstream.** In all ten input repositories the executable bit of files is not preserved. `bench-in-spdlog-3049` also differs in five non-test files (`.gitignore`, `INSTALL`, `LICENSE`, `README.md`, `cmake/spdlogConfig.cmake.in`): upstream stores them with CRLF line endings and the input repository with LF. The Codex patch for spdlog-3049 touches only `include/spdlog/async_logger-inl.h`, `include/spdlog/details/thread_pool-inl.h`, `include/spdlog/details/thread_pool.h` and `tests/test_async.cpp`, and the verifier applies a patch to the upstream base, not to the input repository, so the difference cannot change its verdict. It is stated in the report of the case (`cases/spdlog-3049/input-note.txt`).

## BENCH-20: candidate drafts, selection rules, granularity of the reference test

**Drafts live apart from cases.** Mined candidates go to `candidates/<id>/` (`case.yaml`, `meta.yaml`, `ISSUE.md`, `baseline.log`) and to the append-only `candidates/_rejected/*.jsonl`. They carry no `agent_input_repo` or `input_sha256`: the owner creates the private input and moves the draft to `cases/`. A rejected candidate is "not a candidate" with a reason code from a closed list, not a public NOT_VERIFIABLE.

**Order of sources follows what the verifier can judge today** (read from its code, not from the README): FreeRTOS libraries first (CMake, CTest, Unity); mbedTLS needs an adapter because its tests are lines in `.data` files, which the verifier does not recognise as tests; Zephyr, NuttX, littlefs and lwIP need product work first.

**Reference test granularity (changes the protocol for new cases only).** A function-level filter is used when the project has one. Without it the whole ctest test of a module may be the reference, but only if no other test of that module fails on the base (otherwise `noisy_module`); `bug_test_granularity` is recorded and shown. Existing cases are not edited.

**No network for builds.** Neither the verifier nor the agent has network access during build and test. Submodules are part of the frozen snapshot at recorded commits; a candidate that cannot build with `--network none` is rejected (`needs_network_dependency`).

**Cap and families.** At most 30% of the 100 cases per project, counted from 100 (10 existing + 90 new); all FreeRTOS repositories are one family.

**Dates.** `fix_date` is recorded and `post_cutoff` marks fixes after 2026-06-30; at least half of the new cases should be post-cutoff and are shown separately. This is a date, not a statement about what any model has seen.

**Fuzz origin** is recorded only when the commit or issue directly names a fuzzer or OSS-Fuzz.

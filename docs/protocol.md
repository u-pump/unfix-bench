# Agent and verifier protocol

1. The curator selects an upstream C/C++ CMake/CTest bug with a precise broken commit, a later fix, and a test added or strengthened by that fix. Enumerate the test cases added or changed by the upstream fix in unified-diff order (file order, then hunk and line order). For each test, run the upstream test on the broken base three times in isolation. Because this version of cplus judges one reference test, select the first test that fails on the base 3/3, record its exact name in `case.yaml` as `bug_test` with `reference_selection`, and freeze both fields **before** the agent runs. Later agent output cannot change the choice. If no test qualifies, reject the candidate. Record the elapsed time separately from any agent run.
2. Freeze the issue title and body as `ISSUE.md`, removing only passages that reveal the solution, and record each removal in the curator report. Export the broken commit with `git -c core.autocrlf=false archive --format=tar <base>`. Add the same `TASK.md` to every input: `Fix the bug described in ISSUE.md. Keep the change minimal. Run the existing tests.` Publish each snapshot as a private `u-pump/bench-in-<id>` repository with one root commit and no upstream history. `input_sha256` is SHA-256 of the raw archive bytes followed by the UTF-8 bytes of `ISSUE.md` and `TASK.md`, in that order. The agent receives only this repository; do not connect the benchmark repository, upstream fix commits or tests, cplus binaries/source, previous results, or curator credentials.
3. Run each agent once on the same frozen input repository and exact `TASK.md`, without prior agent patches or results. Record the agent product, exact model/version, invocation, UTC date, environment, patch hash and attempt note in `cases/<id>/agents/<agent-id>/agent.yaml` before judging. Save the first emitted unified diff unchanged as `cases/<id>/agents/<agent-id>/agent-fix.patch`; no human edits or retries within the same attempt. An empty patch before any attempt means PENDING. An attempt that completed (at least one command finished successfully and the agent ended normally) but left every file unchanged is recorded as **NO_PATCH**: it is shown and counted separately in the README and is never VERIFIED. Failed connections and runs with no completed actions are not recorded as attempts; for Claude Code such a run is published as **ERROR** with its reason, no patch is recorded, and the case stays open for a rerun.
4. For each case and agent, reconstruct the upstream base and the selected upstream fix test, create a BugSpec using `cplus bug --from-fix`, then run `cplus verify --project <base> --patch <agent-fix.patch> --bug-spec <spec> --reference-test-from-fix <upstream.patch> --json` (with `--reference-test-name` for an explicitly selected Google Test). The agent patch is applied whole, including its own tests. VERIFIED requires the selected reference test to pass with that patch and fail again after reverting only the agent's source edits. The verifier keeps its private logs and source. The public report is `results/<id>/<agent-id>.md` and contains only verdict, the eight check names/statuses, and elapsed time. Failures to clone, build, reproduce, or verify are infrastructure errors, not code verdicts.
5. The owner reviews case provenance and generated results before publishing any aggregate results in README.

The original `fmt-4960` `bug_test` field named `compile_test.high_precision_constexpr_float`. It was changed after the agent run. A retrospective audit of the upstream diff found that this first test and the second test (`memory_buffer_test.constexpr_grow`) do not fail on the base 3/3; the third (`format_test.high_precision_trailing_zeros`) does. The final choice follows the rule above, but this case does **not** meet its prospective-freeze requirement. This exception remains visible in the case metadata; no agent patch was edited.

**Attempt lost by the test bench.** If the agent finished its work but the bench lost the patch before any verification (for example the patch could not be saved because of a bench bug), no patch exists and no verdict was ever known, so the attempt cannot influence anything. The case is rerun **once**, with an explicit note in its report (`cases/<id>/agents/<agent-id>/attempt-note.txt`, shown as an `Attempt:` line): the first attempt was lost because of the bench error (run and cause named), no verdict for it was known, and this is the rerun. The rule does not apply once a patch has been saved or judged: such an attempt is final whatever its verdict, and a second lost attempt is not rerun without the owner's decision. Which cases were rerun under this rule is visible in the reports.

## Running the agents

**Codex CLI** is run by the owner on a local Windows machine with [the local script](run-agent.md), once per case. It clones only the private `bench-in-<id>` snapshot, passes the exact `TASK.md` text, records the first patch without build output, and deletes the checkout.

**Claude Code** is run by the [`Run Claude Code attempt` workflow](run-claude-code.md) on GitHub Actions: one case at a time, in a Docker container whose only reachable host is `api.anthropic.com`. The log of every run shows the isolation proof before the agent starts. The workflow checks that the snapshot is a single commit at the pinned HEAD with the exact `TASK.md`, saves the first patch byte-for-byte, runs the same verifier at the same pinned revision as for Codex CLI, and opens a pull request; nothing is published until the owner merges it.

The agent must not receive the benchmark repository, the upstream fix or reference test, cplus source or binaries, previous results, or curator credentials. The verifier runs separately after the agent patch and metadata are submitted. CI selects changed `(case, agent)` content pairs and retains a report whose patch hash and verifier revision already match; explicit dispatch can force a rerun.

## Conditions: Codex CLI and Claude Code

Both agents get the same frozen input, the same `TASK.md`, one attempt, the first patch saved unchanged, and the same verifier. The conditions below are not identical; every difference is listed.

| | Codex CLI | Claude Code |
| --- | --- | --- |
| Where it ran | Local Windows machine, MSVC 2019 Build Tools | GitHub Actions `ubuntu-latest`, Docker container, GCC and Clang (the compilers of the verifier's image) |
| Network | Not restricted or measured; not independently verified. `workspace-write` is recorded in `agent.yaml` for all ten cases; the recorded invocation for cpp-peglib-121 and fmt-4800 is plain `codex exec`, without the flag | Container on an internal Docker network; the only reachable host is `api.anthropic.com:443` through a proxy. Each run's log proves that `github.com` is unreachable, directly and through the proxy |
| Failed starts | Some attempts failed with a network error before any command and were rerun; the notes in `agent.yaml` say which | A run with no completed action is published as ERROR and not counted; the case stays open |
| Isolation of files | Codex `workspace-write` sandbox | Read-only container root, non-root user, no capabilities, writable only the case directory and a temporary home |
| Tools | Codex defaults | Bash, Read, Edit, Write, Glob, Grep; no web tools, MCP, memory, `CLAUDE.md`, plugins or hooks |
| Model | `gpt-6-sol`, reasoning `medium` | `claude-opus-5-5`, effort left at the default; the exact name and the Claude Code version are recorded in `agent.yaml` |
| Authentication | Local login | `ANTHROPIC_API_KEY` of a dedicated Console workspace with a spend limit, as a repository secret; deleted after the runs |
| Input check | Single root commit and exact `TASK.md` | Single commit, HEAD equal to the pinned one, exact `TASK.md` (blocking). The `input_sha256` recomputation is informational only |
| Patch capture | `git add -A` excluding `build*/`, `git diff --cached --binary` | The same commands, run in a separate container without network |
| Verdict | Unfix verifier, pinned revision | The same |

Consequences. The two agents built and tested in different environments (Windows with MSVC against Linux with GCC); the verifier builds both patches in its own Linux image. Whether Codex CLI could reach the network is not established; whether Claude Code could is excluded by the isolation proof. A single attempt per case measures that attempt, not a success rate.

## Candidate selection (BENCH-20)

Candidate cases are mined in GitHub Actions and kept as drafts in `candidates/<id>/`; they are not cases. Only the owner moves a draft to `cases/` and creates its private `bench-in-<id>` input. The plan is [docs/plans/bench-20-miner.md](plans/bench-20-miner.md).

A candidate is accepted only if all of these hold, and every other candidate is written to the append-only log `candidates/_rejected/<source>.jsonl` with a reason code (this is "not a candidate", never a public NOT_VERIFIABLE):

1. The upstream test fails on the parent 3 times out of 3 and passes with the fix 3 out of 3; the fix changes source files, not only tests or configuration.
2. Build and test run without hardware in a Linux container in ≤ 30 minutes, and **without network**: submodules are placed in the frozen snapshot at pinned commits recorded in `case.yaml` (`submodules`: path and commit), and `case.yaml` records `build_network: none`.
3. The project licence is on the SPDX allowlist (recorded in `case.yaml` and `meta.yaml`) and an issue or PR text exists from which solution hints can be removed.
4. The fix date is recorded (`fix_date`). `post_cutoff` is true when the fix is dated after 2026-06-30. This is only a date; nothing is claimed about any model's training data. Results of cases with `post_cutoff: true` are shown separately; the target is at least half of the new cases.
5. Backports of one change count once (`dedupe_key`).
6. No project, and no organisation family (all FreeRTOS repositories are one family), provides more than 30% of the 100 cases.
7. `fuzz_origin` is set only when the commit or issue directly refers to a fuzzer or OSS-Fuzz; otherwise it is `null`.

**Granularity of the reference test** (`bug_test_granularity` in `case.yaml`: `function` or `ctest_module`). If the project has a function-level filter (for example `unity_fixture -n/-g`), the filter is used and the granularity is `function`. Only when there is no such filter may the whole ctest test of a module be the reference (`ctest_module`), and then **all** of these must hold: on the base only the tests added or changed by the upstream diff fail in that module; every other test in the module passes 3/3 (`module_other_tests: "3/3 pass"`); otherwise the candidate is rejected with the code `noisy_module`. The granularity is stated in the case report and the README. This rule applies to cases added from BENCH-20 on; the ten existing cases are not changed and carry no such field.

Moving a draft to `cases/` follows the checklist in [candidates/README.md](../candidates/README.md), which includes updating `THIRD_PARTY_NOTICES.md`.

The shape of `candidates/` is checked by `python scripts/candidates.py check` (also run in CI); it also checks that every published `case.yaml` has the shared fields.

# Unfix benchmark: AI-agent fixes to real C/C++ bugs, independently verified

Verified by [Unfix](https://unfix.dev) — an independent verifier for C/C++ and firmware fixes. It doesn't write code; it reproduces the bug, applies the fix, removes it again and checks that the bug comes back.

**What this is.** Ten real bugs from open-source C/C++ projects. Two AI coding agents, Codex CLI and Claude Code, each got every bug once, with the same inputs, and made one fix attempt. Each patch was then judged by the same verifier against the maintainers' own upstream test. The tables below are the outcome: one verdict per agent and case, no ranking.

**How to check a verdict.** Open the case's report in [`results/`](results), take the patch from `cases/<case>/agents/<agent>/agent-fix.patch`, and follow [Check a verdict yourself](#check-a-verdict-yourself). The agents' environments differ; the differences are stated under [What the agent got](#what-the-agent-got).

## Results

<!-- results:start -->
| Case | Project | Bug | Codex CLI | Claude Code |
| --- | --- | --- | --- | --- |
| corehttp-210 | [coreHTTP](https://github.com/FreeRTOS/coreHTTP) | [#210: header field at a read boundary](https://github.com/FreeRTOS/coreHTTP/pull/210) | [VERIFIED](results/corehttp-210/codex-cli.md) | [VERIFIED](results/corehttp-210/claude-code.md) |
| coremqtt-331 | [coreMQTT](https://github.com/FreeRTOS/coreMQTT) | [#331: zero-length client identifier](https://github.com/FreeRTOS/coreMQTT/pull/331) | [VERIFIED](results/coremqtt-331/codex-cli.md) | [VERIFIED](results/coremqtt-331/claude-code.md) |
| cpp-peglib-121 | [cpp-peglib](https://github.com/yhirose/cpp-peglib) | [#121: start rule with ignore operator](https://github.com/yhirose/cpp-peglib/issues/121) | [REJECTED](results/cpp-peglib-121/codex-cli.md) | [REJECTED](results/cpp-peglib-121/claude-code.md) |
| fmt-4490 | [fmt](https://github.com/fmtlib/fmt) | [#4490: allocator move](https://github.com/fmtlib/fmt/pull/4490) | [REJECTED](results/fmt-4490/codex-cli.md) | [REJECTED](results/fmt-4490/claude-code.md)[^1] |
| fmt-4742 | [fmt](https://github.com/fmtlib/fmt) | [#4742: out-of-bounds read](https://github.com/fmtlib/fmt/pull/4742) | [REJECTED](results/fmt-4742/codex-cli.md) | [REJECTED](results/fmt-4742/claude-code.md) |
| fmt-4800 | [fmt](https://github.com/fmtlib/fmt) | [#4800: positional width and precision](https://github.com/fmtlib/fmt/pull/4800) | [VERIFIED](results/fmt-4800/codex-cli.md) | [VERIFIED](results/fmt-4800/claude-code.md) |
| fmt-4933 | [fmt](https://github.com/fmtlib/fmt) | [#4933: named argument count](https://github.com/fmtlib/fmt/pull/4933) | [REJECTED](results/fmt-4933/codex-cli.md) | [REJECTED](results/fmt-4933/claude-code.md) |
| fmt-4942 | [fmt](https://github.com/fmtlib/fmt) | [#4942: zero precision](https://github.com/fmtlib/fmt/pull/4942) | [VERIFIED](results/fmt-4942/codex-cli.md) | [REJECTED](results/fmt-4942/claude-code.md) |
| fmt-4960 | [fmt](https://github.com/fmtlib/fmt) | [#4960: floating-point precision](https://github.com/fmtlib/fmt/pull/4960) | [REJECTED](results/fmt-4960/codex-cli.md) | [VERIFIED](results/fmt-4960/claude-code.md) |
| fmt-4978 | [fmt](https://github.com/fmtlib/fmt) | [#4978: calendar formatting](https://github.com/fmtlib/fmt/pull/4978) | [VERIFIED](results/fmt-4978/codex-cli.md) | [VERIFIED](results/fmt-4978/claude-code.md) |
| freertos-plus-tcp-1018 | [FreeRTOS-Plus-TCP](https://github.com/FreeRTOS/FreeRTOS-Plus-TCP) | [#1018: TCP zero-copy send](https://github.com/FreeRTOS/FreeRTOS-Plus-TCP/pull/1018) | [PENDING](results/freertos-plus-tcp-1018/codex-cli.md) | [REJECTED](results/freertos-plus-tcp-1018/claude-code.md) |
| freertos-plus-tcp-1158 | [FreeRTOS-Plus-TCP](https://github.com/FreeRTOS/FreeRTOS-Plus-TCP) | [#1158: DNS reply over-read](https://github.com/FreeRTOS/FreeRTOS-Plus-TCP/pull/1158) | [REJECTED](results/freertos-plus-tcp-1158/codex-cli.md) | [PENDING](results/freertos-plus-tcp-1158/claude-code.md) |
| freertos-plus-tcp-1357 | [FreeRTOS-Plus-TCP](https://github.com/FreeRTOS/FreeRTOS-Plus-TCP) | [#1357: IPv6 address printing bounds](https://github.com/FreeRTOS/FreeRTOS-Plus-TCP/pull/1357) | [VERIFIED](results/freertos-plus-tcp-1357/codex-cli.md) | [VERIFIED](results/freertos-plus-tcp-1357/claude-code.md) |
| spdlog-3049 | [spdlog](https://github.com/gabime/spdlog) | [#3049: concurrent async flush](https://github.com/gabime/spdlog/pull/3049) | [REJECTED](results/spdlog-3049/codex-cli.md) | [REJECTED](results/spdlog-3049/claude-code.md) |
| zlibng-2465 | [zlib-ng](https://github.com/zlib-ng/zlib-ng) | [#2465: inflate boundary](https://github.com/zlib-ng/zlib-ng/pull/2465) | [VERIFIED](results/zlibng-2465/codex-cli.md) | [VERIFIED](results/zlibng-2465/claude-code.md) |

| Agent | VERIFIED | REJECTED | REVIEW | NOT_VERIFIABLE | NO_PATCH | ERROR | PENDING |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Codex CLI | 7 | 7 | 0 | 0 | 0 | 0 | 1 |
| Claude Code | 7 | 7 | 0 | 0 | 0 | 0 | 1 |
<!-- results:end -->

[^1]: По правилу анти-чита с cplus a69c652 этот патч получил бы REVIEW вместо FAIL на анти-чите; результат оставлен на исходной ревизии 81c0fda по протоколу (первые 20 результатов не перепроверяются).

The tables are generated from the files in [`results/`](results) by `scripts/render_readme.py`; each agent ran once per case.

## What the agent got

- A snapshot of the broken commit, with no later upstream history or fix.
- `ISSUE.md`: the original issue text with solution-revealing passages removed.
- The same `TASK.md` for every case: “Fix the bug described in ISSUE.md. Keep the change minimal. Run the existing tests.”
- One attempt per agent; the first patch was saved byte-for-byte, without human edits.
- Environment, which is not the same for the two agents:
  - Codex CLI ran locally on a Windows machine (MSVC 2019 Build Tools) under its own `workspace-write` sandbox setting. The network was not restricted or measured; whether it could reach the network is not established. For cpp-peglib-121 and fmt-4800 the recorded invocation is plain `codex exec` and the setting is noted only in the `sandbox` field of `agent.yaml`.
  - Claude Code ran in GitHub Actions, in a Docker container whose only reachable host is `api.anthropic.com`. An isolation proof in each run's log shows that other hosts, such as `github.com`, were unreachable, and the proxy's refusal counts are in each `agent.yaml` (`proxy`). For the first nine cases those counts were reconstructed from stored proxy logs, which the report says; token totals are recorded only for later runs.
  - The verifier is the same, in its own Linux image. The [conditions of both agents](docs/protocol.md#conditions-codex-cli-and-claude-code) are compared in the protocol.
- The input is a private snapshot of the broken commit, pinned in [`inputs/bench-in-heads.json`](inputs/bench-in-heads.json). `input_sha256` in each `case.yaml` identifies the frozen source archive, `ISSUE.md`, and `TASK.md` input; a recomputation from the upstream base is informational and matches for only some cases, so the pinned snapshot, not that hash, is what both agents received.

## How a verdict is decided

The reference test comes from the maintainers' upstream fix. Before the agent runs, the first test in the upstream diff that fails on the broken base three times out of three is selected and frozen. **VERIFIED** means that test passes with the agent patch and fails again when only the agent's source changes are reverted, with all required checks passing. Anti-cheat checks reject changes that evade the test or weaken its checks. **REJECTED** means a required check failed; **NOT_VERIFIABLE** means the available evidence cannot establish a reliable code verdict. See the [full protocol](docs/protocol.md).

## Check a verdict yourself

This example reproduces the [fmt-4800 VERIFIED report](results/fmt-4800/codex-cli.md) on Linux or WSL. You need Git, CMake, a C++ compiler and a shell. Start in the root of this benchmark repository. The commands use `repo`, `base`, `upstream_fix`, `bug_test`, `build`, and `test` from [case.yaml](cases/fmt-4800/case.yaml); the agent patch is [agent-fix.patch](cases/fmt-4800/agents/codex-cli/agent-fix.patch).

```sh
BENCH="$PWD"
BASE=e60274b29c0a748df2c6280d0a374e6eef3b6c73
FIX=128ba144ab85ddd0ad9ea39f2febdfb51802cb1b
git clone https://github.com/fmtlib/fmt.git ../fmt-4800-recheck
cd ../fmt-4800-recheck
git checkout "$BASE"

# Add only the maintainers' reference test, not their source fix.
git diff "$BASE" "$FIX" -- test/printf-test.cc | git apply
cmake -S . -B build -DFMT_TEST=ON
cmake --build build --target printf-test
./build/bin/printf-test --gtest_filter=printf_test.zero_positional_width_precision
# Expected: FAIL on the broken base.

# Apply the agent's first patch and rebuild.
git apply "$BENCH/cases/fmt-4800/agents/codex-cli/agent-fix.patch"
cmake --build build --target printf-test
./build/bin/printf-test --gtest_filter=printf_test.zero_positional_width_precision
# Expected: PASS.
ctest --test-dir build -R printf-test --output-on-failure
# Expected: the full printf-test target passes.

# Remove only the agent's source edit. Keep the reference test and agent test.
git restore --source="$BASE" -- include/fmt/base.h
cmake --build build --target printf-test
./build/bin/printf-test --gtest_filter=printf_test.zero_positional_width_precision
# Expected: FAIL again.
```

The focused command above runs the selected `bug_test`; the CTest command runs the full target named by `test`. Other cases may need a different build target or test filter: use that case's `build`, `test`, and `bug_test` fields.

## Limits

- Fifteen cases are a small sample; seven are from fmt. The four added last (corehttp-210, freertos-plus-tcp-1018, -1158 and -1357) are judged by cplus like coremqtt-331; six of their eight results are in (corehttp-210 and -1357 for both agents, -1018 for Claude Code, -1158 for Codex CLI) and two are still PENDING (-1018 for Codex CLI, -1158 for Claude Code). The eleventh, coremqtt-331, is the first Unity case and is judged by cplus; both agents ran once, and both patches were checked again after the verifier revision moved to `a69c652` (the agents were not rerun, see [DECISIONS](docs/DECISIONS.md)).
- Fix dates of the cases added from BENCH-20 on are recorded in the case (`meta.yaml`: `fix_date`, `post_cutoff`). coremqtt-331: fix 2025-10-30, **fix before 2026-06-30** (`post_cutoff: false`). corehttp-210: fix 2026-11-17, **fix after 2026-06-30** (`post_cutoff: true`). freertos-plus-tcp-1018: fix 2023-09-20, before (`false`). freertos-plus-tcp-1158: fix 2024-06-17, before (`false`). freertos-plus-tcp-1357: fix 2026-08-06, **after** (`true`). bench v1 takes fixes merged on or after 2023-01-01, so most of its cases are before that date; the goal of at least half cases after 2026-06-30 belongs to the way to 100 cases, not to v1. The first ten cases carry no such field.
- In fmt-4960, the reference test was chosen after the agent run. The selection rule was applied retrospectively and documented in [the case file](cases/fmt-4960/case.yaml); the patch was never edited.
- The verifier is not open source yet. Public reports contain the verdict, eight check statuses, and elapsed time.
- Each result names the verifier revision it was made with (the `Verifier:` line). All 20 results of the first ten cases were made with `81c0fda` and are not re-checked; cases added later are pinned to a newer revision, shown in their own results.
- One attempt per agent and case measures that attempt, not a success rate; the conditions of the two agents differ in the ways listed in the [protocol](docs/protocol.md#conditions-codex-cli-and-claude-code).

## Found a wrong verdict?

[Open an issue](https://github.com/u-pump/unfix-bench/issues) with the case ID. Corrections will be published. Contact: [hello@unfix.dev](mailto:hello@unfix.dev). More at [unfix.dev](https://unfix.dev).

## License

| Content | License |
| --- | --- |
| Code in `scripts/` and `.github/workflows/` | [MIT](LICENSES/MIT.txt) |
| Benchmark data and documentation in `cases/**/case.yaml`, `cases/**/agents/**/agent.yaml`, `results/`, `README.md`, `docs/`, and `CITATION.cff` | [Creative Commons Attribution 4.0 International (CC BY 4.0)](LICENSES/CC-BY-4.0.txt) |
| Agent patches in `cases/**/agents/**/agent-fix.patch` and reproduced upstream code | The [respective upstream project's license](THIRD_PARTY_NOTICES.md) |
| Candidate drafts in `candidates/**` (not yet published cases): benchmark data such as `case.yaml`, `meta.yaml`, the rejection logs and `baseline.log` | [Creative Commons Attribution 4.0 International (CC BY 4.0)](LICENSES/CC-BY-4.0.txt) |
| Upstream code, diffs and the upstream issue or pull-request text kept in `candidates/**` (for example `ISSUE.md`) | The [respective upstream project's license](THIRD_PARTY_NOTICES.md) |

To cite the benchmark, use [CITATION.cff](CITATION.cff). Recommended attribution for CC BY 4.0 material: “Unfix benchmark by U-Pump, https://github.com/u-pump/unfix-bench, licensed under CC BY 4.0”.

The license texts follow the [`LICENSES/<SPDX-ID>.txt` layout in the REUSE Specification](https://reuse.software/spec/). The root [LICENSE](LICENSE) is the same MIT text as [LICENSES/MIT.txt](LICENSES/MIT.txt); see [LICENSES/CC-BY-4.0.txt](LICENSES/CC-BY-4.0.txt) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for the other applicable terms.

The Unfix verifier is proprietary, is not included in this repository, and is not covered by these licenses.

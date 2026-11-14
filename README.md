# Unfix benchmark: AI-agent fixes to real C/C++ bugs, independently verified

Verified by [Unfix](https://unfix.dev) — an independent verifier for C/C++ and firmware fixes. It doesn't write code; it reproduces the bug, applies the fix, removes it again and checks that the bug comes back.

## Results

<!-- results:start -->
| Case | Project | Bug | Codex CLI | Claude Code |
| --- | --- | --- | --- | --- |
| cpp-peglib-121 | [cpp-peglib](https://github.com/yhirose/cpp-peglib) | [#121: start rule with ignore operator](https://github.com/yhirose/cpp-peglib/issues/121) | [REJECTED](results/cpp-peglib-121/codex-cli.md) | [REJECTED](results/cpp-peglib-121/claude-code.md) |
| fmt-4490 | [fmt](https://github.com/fmtlib/fmt) | [#4490: allocator move](https://github.com/fmtlib/fmt/pull/4490) | [REJECTED](results/fmt-4490/codex-cli.md) | [REJECTED](results/fmt-4490/claude-code.md) |
| fmt-4742 | [fmt](https://github.com/fmtlib/fmt) | [#4742: out-of-bounds read](https://github.com/fmtlib/fmt/pull/4742) | [REJECTED](results/fmt-4742/codex-cli.md) | [REJECTED](results/fmt-4742/claude-code.md) |
| fmt-4800 | [fmt](https://github.com/fmtlib/fmt) | [#4800: positional width and precision](https://github.com/fmtlib/fmt/pull/4800) | [VERIFIED](results/fmt-4800/codex-cli.md) | [VERIFIED](results/fmt-4800/claude-code.md) |
| fmt-4933 | [fmt](https://github.com/fmtlib/fmt) | [#4933: named argument count](https://github.com/fmtlib/fmt/pull/4933) | [REJECTED](results/fmt-4933/codex-cli.md) | [REJECTED](results/fmt-4933/claude-code.md) |
| fmt-4942 | [fmt](https://github.com/fmtlib/fmt) | [#4942: zero precision](https://github.com/fmtlib/fmt/pull/4942) | [VERIFIED](results/fmt-4942/codex-cli.md) | [REJECTED](results/fmt-4942/claude-code.md) |
| fmt-4960 | [fmt](https://github.com/fmtlib/fmt) | [#4960: floating-point precision](https://github.com/fmtlib/fmt/pull/4960) | [REJECTED](results/fmt-4960/codex-cli.md) | [VERIFIED](results/fmt-4960/claude-code.md) |
| fmt-4978 | [fmt](https://github.com/fmtlib/fmt) | [#4978: calendar formatting](https://github.com/fmtlib/fmt/pull/4978) | [VERIFIED](results/fmt-4978/codex-cli.md) | [VERIFIED](results/fmt-4978/claude-code.md) |
| spdlog-3049 | [spdlog](https://github.com/gabime/spdlog) | [#3049: concurrent async flush](https://github.com/gabime/spdlog/pull/3049) | [REJECTED](results/spdlog-3049/codex-cli.md) | [REJECTED](results/spdlog-3049/claude-code.md) |
| zlibng-2465 | [zlib-ng](https://github.com/zlib-ng/zlib-ng) | [#2465: inflate boundary](https://github.com/zlib-ng/zlib-ng/pull/2465) | [VERIFIED](results/zlibng-2465/codex-cli.md) | [VERIFIED](results/zlibng-2465/claude-code.md) |

| Agent | VERIFIED | REJECTED | REVIEW | NOT_VERIFIABLE | NO_PATCH | ERROR | PENDING |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Codex CLI | 4 | 6 | 0 | 0 | 0 | 0 | 0 |
| Claude Code | 4 | 6 | 0 | 0 | 0 | 0 | 0 |
<!-- results:end -->

The tables are generated from the files in [`results/`](results) by `scripts/render_readme.py`; each agent ran once per case.

## What the agent got

- A snapshot of the broken commit, with no later upstream history or fix.
- `ISSUE.md`: the original issue text with solution-revealing passages removed.
- The same `TASK.md` for every case: “Fix the bug described in ISSUE.md. Keep the change minimal. Run the existing tests.”
- One attempt per agent; the first patch was saved byte-for-byte, without human edits.
- Network: Codex CLI ran locally on Windows under its own sandbox setting (`--sandbox workspace-write` in 8 of 10 cases; the invocation recorded for cpp-peglib-121 and fmt-4800 names no sandbox flag). Whether it could reach the network was not independently verified. Claude Code runs in a container whose only reachable host is `api.anthropic.com`, proven in each run's log. The [conditions of both agents](docs/protocol.md#conditions-codex-cli-and-claude-code) are compared in the protocol.
- `input_sha256` in each `case.yaml` identifies the frozen source archive, `ISSUE.md`, and `TASK.md` input.

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

- Ten cases is a small sample; seven are from fmt.
- In fmt-4960, the reference test was chosen after the agent run. The selection rule was applied retrospectively and documented in [the case file](cases/fmt-4960/case.yaml); the patch was never edited.
- The verifier is not open source yet. Public reports contain the verdict, eight check statuses, and elapsed time.
- One attempt per agent and case measures that attempt, not a success rate; the conditions of the two agents differ in the ways listed in the [protocol](docs/protocol.md#conditions-codex-cli-and-claude-code).

## Found a wrong verdict?

[Open an issue](https://github.com/u-pump/unfix-bench/issues) with the case ID. Corrections will be published. Contact: [hello@unfix.dev](mailto:hello@unfix.dev). More at [unfix.dev](https://unfix.dev).

## License

| Content | License |
| --- | --- |
| Code in `scripts/` and `.github/workflows/` | [MIT](LICENSES/MIT.txt) |
| Benchmark data and documentation in `cases/**/case.yaml`, `cases/**/agents/**/agent.yaml`, `results/`, `README.md`, `docs/`, and `CITATION.cff` | [Creative Commons Attribution 4.0 International (CC BY 4.0)](LICENSES/CC-BY-4.0.txt) |
| Agent patches in `cases/**/agents/**/agent-fix.patch` and reproduced upstream code | The [respective upstream project's license](THIRD_PARTY_NOTICES.md) |

To cite the benchmark, use [CITATION.cff](CITATION.cff). Recommended attribution for CC BY 4.0 material: “Unfix benchmark by U-Pump, https://github.com/u-pump/unfix-bench, licensed under CC BY 4.0”.

The license texts follow the [`LICENSES/<SPDX-ID>.txt` layout in the REUSE Specification](https://reuse.software/spec/). The root [LICENSE](LICENSE) is the same MIT text as [LICENSES/MIT.txt](LICENSES/MIT.txt); see [LICENSES/CC-BY-4.0.txt](LICENSES/CC-BY-4.0.txt) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for the other applicable terms.

The Unfix verifier is proprietary, is not included in this repository, and is not covered by these licenses.

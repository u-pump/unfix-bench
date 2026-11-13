# spdlog-3049

Verdict: **REJECTED**

Reason: judged by upstream reference test 'multithread flush'; the patch did not eliminate the expected reproducer failure

Note: agent implemented the wait but broke the upstream discard_new behaviour (differs from expected upstream behaviour)

Input: bench-in-spdlog-3049 differs from the upstream base in 5 non-test files (.gitignore, INSTALL, LICENSE, README.md, cmake/spdlogConfig.cmake.in): CRLF line endings became LF. The executable bit of files is not preserved in the bench-in repositories (all cases). Both agents receive the same input; the patch is verified against the upstream base.

Elapsed: 87.1 s

Verifier: cplus 81c0fda242fef1daf55d3164e06127d372c81caa · 2026-10-24 14:16:42 UTC

Patch: sha256 11b110ea6489605ff9059e14688a48cfaeafa88b77fe1a9d60296b261978db27
Agent: Codex CLI · Version: 0.164.0

| Check | Status |
| --- | --- |
| anti_cheat | PASS |
| build:baseline | PASS |
| repro:baseline | PASS |
| build:patched | PASS |
| repro:patched | FAIL |
| repeat | SKIPPED |
| revert | SKIPPED |
| regression | SKIPPED |

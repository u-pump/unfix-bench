# spdlog-3049

Verdict: **NOT_VERIFIABLE**

Reason: upstream reference test lacks a complete three-run baseline

Input: bench-in-spdlog-3049 differs from the upstream base in 5 non-test files (.gitignore, INSTALL, LICENSE, README.md, cmake/spdlogConfig.cmake.in): CRLF line endings became LF. The executable bit of files is not preserved in the bench-in repositories (all cases). Both agents receive the same input; the patch is verified against the upstream base.

Elapsed: 0.7 s

Verifier: cplus 81c0fda242fef1daf55d3164e06127d372c81caa · 2026-11-13 21:32:36 UTC

Patch: sha256 3c77abce6693d4d558366a2ab6e795aa3bb82aff85165acefd422683907b1863

Agent: Claude Code · Version: 2.1.323 (Claude Code)

| Check | Status |
| --- | --- |
| anti_cheat | SKIPPED |
| build:baseline | SKIPPED |
| repro:baseline | SKIPPED |
| build:patched | SKIPPED |
| repro:patched | SKIPPED |
| repeat | SKIPPED |
| revert | SKIPPED |
| regression | SKIPPED |

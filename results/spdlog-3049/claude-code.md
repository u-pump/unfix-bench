# spdlog-3049

Verdict: **REJECTED**

Reason: judged by upstream reference test 'multithread flush'; the patch did not eliminate the expected reproducer failure

Input: bench-in-spdlog-3049 differs from the upstream base in 5 non-test files (.gitignore, INSTALL, LICENSE, README.md, cmake/spdlogConfig.cmake.in): CRLF line endings became LF. The executable bit of files is not preserved in the bench-in repositories (all cases). Both agents receive the same input; the patch is verified against the upstream base.

Network: the proxy refused 3 request(s) from the agent run (github.com x3); allowed hosts: api.anthropic.com. Reconstructed from the stored proxy log, proof requests subtracted by their known number.

Elapsed: 75.8 s

Verifier: cplus 81c0fda242fef1daf55d3164e06127d372c81caa · 2026-11-14 00:31:18 UTC

Patch: sha256 3c77abce6693d4d558366a2ab6e795aa3bb82aff85165acefd422683907b1863

Agent: Claude Code · Version: 2.1.323 (Claude Code)

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

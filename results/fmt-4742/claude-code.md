# fmt-4742

Verdict: **REJECTED**

Reason: judged by upstream reference test 'printf_test.trailing_percent'; the patch did not eliminate the expected reproducer failure

Elapsed: 41.5 s

Verifier: cplus 81c0fda242fef1daf55d3164e06127d372c81caa · 2026-11-13 21:20:46 UTC

Patch: sha256 a17a457bc7fc3b5124ccd590661eb8b0c6aceba9b204fbbc701807f9eace9d51

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

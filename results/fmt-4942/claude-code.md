# fmt-4942

Verdict: **REJECTED**

Reason: judged by upstream reference test 'printf_test.zero_int_with_zero_precision'; the patch did not eliminate the expected reproducer failure

Network: the proxy refused 0 request(s) from the agent run (none); allowed hosts: api.anthropic.com. Reconstructed from the stored proxy log, proof requests subtracted by their known number.

Elapsed: 41.4 s

Verifier: cplus 81c0fda242fef1daf55d3164e06127d372c81caa · 2026-11-13 21:26:16 UTC

Patch: sha256 aebf1e3c3900a648f5ff739f178b4e95fe75298b218d6a87b73bc8d267a54a0f

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

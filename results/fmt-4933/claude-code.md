# fmt-4933

Verdict: **REJECTED**

Reason: judged by upstream reference test 'args_test.named_arg_count'; the patch did not eliminate the expected reproducer failure

Network: the proxy refused 0 request(s) from the agent run (none); allowed hosts: api.anthropic.com. Reconstructed from the stored proxy log, proof requests subtracted by their known number.

Elapsed: 14.9 s

Verifier: cplus 81c0fda242fef1daf55d3164e06127d372c81caa · 2026-11-13 21:23:51 UTC

Patch: sha256 b401086bbda4ed9da5269fd310a894292d24f93a68dddbefc6fd055c56d398c0

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

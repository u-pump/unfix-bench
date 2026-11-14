# fmt-4960

Verdict: **VERIFIED**

Reason: judged by upstream reference test 'format_test.high_precision_trailing_zeros'; fix proven

Network: the proxy refused 0 request(s) from the agent run (none); allowed hosts: api.anthropic.com. Reconstructed from the stored proxy log, proof requests subtracted by their known number.

Elapsed: 48.5 s

Verifier: cplus 81c0fda242fef1daf55d3164e06127d372c81caa · 2026-11-13 21:29:21 UTC

Patch: sha256 98d0969ac59afc61592dc88b5fbe675b39fc7e0316ebbe55ace8a985708da505

Agent: Claude Code · Version: 2.1.323 (Claude Code)

| Check | Status |
| --- | --- |
| anti_cheat | PASS |
| build:baseline | PASS |
| repro:baseline | PASS |
| build:patched | PASS |
| repro:patched | PASS |
| repeat | PASS |
| revert | PASS |
| regression | PASS |

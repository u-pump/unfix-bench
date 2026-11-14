# fmt-4800

Verdict: **VERIFIED**

Reason: judged by upstream reference test 'printf_test.zero_positional_width_precision'; fix proven

Network: the proxy refused 0 request(s) from the agent run (none); allowed hosts: api.anthropic.com. Reconstructed from the stored proxy log, proof requests subtracted by their known number.

Elapsed: 36.3 s

Verifier: cplus 81c0fda242fef1daf55d3164e06127d372c81caa · 2026-11-13 20:10:18 UTC

Patch: sha256 d859792d6e479a6eaa35506001ed724268edde6a2135bcfc46098528c0cd0806

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

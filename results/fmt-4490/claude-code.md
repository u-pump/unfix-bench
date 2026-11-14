# fmt-4490

Verdict: **REJECTED**

Reason: the patch changes protected tests or check configuration; test/mock-allocator.h, line 48

Network: the proxy refused 0 request(s) from the agent run (none); allowed hosts: api.anthropic.com. Reconstructed from the stored proxy log, proof requests subtracted by their known number.

Elapsed: 0.8 s

Verifier: cplus 81c0fda242fef1daf55d3164e06127d372c81caa · 2026-11-13 21:18:35 UTC

Patch: sha256 6b26bc4d7f7ff56c2c9e63397af567bf63eb15f7f245ebf7d28a1e56623e50d6

Agent: Claude Code · Version: 2.1.323 (Claude Code)

| Check | Status |
| --- | --- |
| anti_cheat | FAIL |
| build:baseline | SKIPPED |
| repro:baseline | SKIPPED |
| build:patched | SKIPPED |
| repro:patched | SKIPPED |
| repeat | SKIPPED |
| revert | SKIPPED |
| regression | SKIPPED |

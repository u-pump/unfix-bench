# freertos-plus-tcp-1018

Verdict: **REJECTED**

Reason: the patch changes protected tests or check configuration; test/unit-test/FreeRTOS_Sockets/FreeRTOS_Sockets_TCP_API_utest.c, line 1261

Network: the proxy refused 0 request(s) from the agent run (none); allowed connections: api.anthropic.com x3. Counted from the proxy log; the isolation proof's own requests are excluded.

Elapsed: 0.8 s

Verifier: cplus a69c6524b9680dd349c511de32a628f40e7dc2a2 · 2026-11-20 17:44:56 UTC

Reference: ctest_module (module FreeRTOS_Sockets_TCP_API_utest; only tests added by the fix fail on the base)

Patch: sha256 796510137d474805dfbc87d8a76fc3021a332aefcb2c82e37e4b41a032601307

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

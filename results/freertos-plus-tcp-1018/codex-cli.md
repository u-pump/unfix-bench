# freertos-plus-tcp-1018

Verdict: **REJECTED**

Reason: the patch changes protected tests or check configuration; test/unit-test/FreeRTOS_Sockets/FreeRTOS_Sockets_TCP_API_utest.c, line 1261; the patch changes protected tests or check configuration; test/unit-test/FreeRTOS_Sockets/FreeRTOS_Socket

Network: the proxy refused 20 request(s) from the agent run (ab.chatgpt.com x5, chatgpt.com x15); allowed connections: api.openai.com x1. Counted from the proxy log; the isolation proof's own requests are excluded.

Elapsed: 1.0 s

Verifier: cplus dc84e98a80499b118ffb437ce722533fcde03af7 · 2026-11-26 19:13:56 UTC

Reference: ctest_module (module FreeRTOS_Sockets_TCP_API_utest; only tests added by the fix fail on the base)

Patch: sha256 724260f5d1ee2abb4b22aa3958e7fafcf1a473c2fc8a85cce4b0c473ec7c215e

Agent: Codex CLI · Version: 0.164.0

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

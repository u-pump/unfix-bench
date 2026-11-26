# freertos-plus-tcp-1158

Verdict: **REJECTED**

Reason: the patch changes protected tests or check configuration; test/unit-test/FreeRTOS_DNS_Parser/FreeRTOS_DNS_Parser_utest.c, line 3072; the patch changes protected tests or check configuration; test/unit-test/FreeRTOS_DNS_Parser/FreeRTOS_DNS_P

Network: the proxy refused 0 request(s) from the agent run (none); allowed connections: api.anthropic.com x3. Counted from the proxy log; the isolation proof's own requests are excluded.

Elapsed: 0.7 s

Verifier: cplus dc84e98a80499b118ffb437ce722533fcde03af7 · 2026-11-26 18:21:04 UTC

Reference: ctest_module (module FreeRTOS_DNS_Parser_utest; only tests added by the fix fail on the base)

Patch: sha256 9a73359e53d4b8f3c5e5358544a31afe68aeb7bd41f8fbc40358b402af11b01f

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

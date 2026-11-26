# freertos-plus-tcp-1158

Verdict: **REJECTED**

Reason: the patch changes protected tests or check configuration; test/unit-test/FreeRTOS_DNS_Parser/FreeRTOS_DNS_Parser_utest.c, line 3072; the patch changes protected tests or check configuration; test/unit-test/FreeRTOS_DNS_Parser/FreeRTOS_DNS_P

Attempt: Same patch (sha256 b747ce7a...), same single agent run (run 44784623261), not rerun. First verdict INFRASTRUCTURE_ERROR on cplus a69c652 (2026-11-20 17:44:50 UTC): cplus bug baseline: reference test did not reproduce, a limit of that verifier revision (FreeRTOS-Plus-TCP was configured twice, c-plus #113). Checked again on cplus dc84e98, the revision now set for this case: REJECTED, anti_cheat FAIL (the patch changes an existing protected test); the verdict above is the current one.

Network: the proxy refused 19 request(s) from the agent run (ab.chatgpt.com x4, chatgpt.com x15); allowed connections: api.openai.com x1. Counted from the proxy log; the isolation proof's own requests are excluded.

Elapsed: 0.9 s

Verifier: cplus dc84e98a80499b118ffb437ce722533fcde03af7 · 2026-11-26 17:39:37 UTC

Reference: ctest_module (module FreeRTOS_DNS_Parser_utest; only tests added by the fix fail on the base)

Patch: sha256 b747ce7ab7d12d489f15d2e74b7b097365bf5a0b3bf0df2b3c138912b7288c02

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

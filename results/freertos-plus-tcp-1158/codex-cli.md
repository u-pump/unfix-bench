# freertos-plus-tcp-1158

Verdict: **VERIFIED**

Attempt: Same patch (sha256 b747ce7a...), same single agent run (run 44784623261), not rerun. First verdict INFRASTRUCTURE_ERROR on cplus a69c652 (2026-11-20 17:44:50 UTC): cplus bug baseline: reference test did not reproduce, a limit of that verifier revision (FreeRTOS-Plus-TCP was configured twice, c-plus #113). Checked again on cplus dc84e98, the revision now set for this case: REJECTED, anti_cheat FAIL (the patch changes an existing protected test); the verdict above is the current one.

Network: the proxy refused 19 request(s) from the agent run (ab.chatgpt.com x4, chatgpt.com x15); allowed connections: api.openai.com x1. Counted from the proxy log; the isolation proof's own requests are excluded.

Elapsed: 79.2 s

Verifier: cplus 6121ef2a29edca936fdd9f16386782ca748e12fb · 2026-11-26 20:39:42 UTC

Reference: ctest_module (module FreeRTOS_DNS_Parser_utest; only tests added by the fix fail on the base)

Patch: sha256 b747ce7ab7d12d489f15d2e74b7b097365bf5a0b3bf0df2b3c138912b7288c02

Agent: Codex CLI · Version: 0.164.0

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

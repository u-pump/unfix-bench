# freertos-plus-tcp-1357

Verdict: **VERIFIED**

Attempt: Same patch (sha256 af8600f6...), same single agent run (run 44783997958), not rerun. First verdict INFRASTRUCTURE_ERROR on cplus a69c652 (2026-11-20 17:34:56 UTC): cplus bug baseline: reference test did not reproduce, a limit of that verifier revision (FreeRTOS-Plus-TCP was configured twice, c-plus #113). Checked again on cplus dc84e98, the revision now set for this case; the verdict above is the current one.

Network: the proxy refused 17 request(s) from the agent run (ab.chatgpt.com x2, chatgpt.com x15); allowed connections: api.openai.com x1. Counted from the proxy log; the isolation proof's own requests are excluded.

Elapsed: 80.4 s

Verifier: cplus dc84e98a80499b118ffb437ce722533fcde03af7 · 2026-11-26 17:31:37 UTC

Reference: ctest_module (module FreeRTOS_Sockets_IPv6_utest; only tests added by the fix fail on the base)

Patch: sha256 af8600f6bf498fd71a3db78e6b6ed37a9603ea9927f467513795d1cd8d092be9

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

# freertos-plus-tcp-1018

Verdict: **REJECTED**

Reason: the patch changes protected tests or check configuration; test/unit-test/FreeRTOS_Sockets/FreeRTOS_Sockets_TCP_API_utest.c, line 1261; the patch changes protected tests or check configuration; test/unit-test/FreeRTOS_Sockets/FreeRTOS_Socket

Attempt: Same patch (sha256 724260f5...), same single agent run (run 45881136727), not rerun. First verdict REJECTED on cplus dc84e98 (2026-11-26 19:13:56 UTC): anti_cheat FAIL, the patch changes an existing protected test. Checked again on cplus 6121ef2, the revision now set for this case (an agent edit that matches the reference hunk for hunk is not a violation, c-plus #114): REJECTED again for the same reason, because this edit does not match the reference hunk (the test is renamed and rewritten); the verdict above is the current one.

Network: the proxy refused 20 request(s) from the agent run (ab.chatgpt.com x5, chatgpt.com x15); allowed connections: api.openai.com x1. Counted from the proxy log; the isolation proof's own requests are excluded.

Elapsed: 0.7 s

Verifier: cplus 6121ef2a29edca936fdd9f16386782ca748e12fb · 2026-11-26 21:54:44 UTC

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

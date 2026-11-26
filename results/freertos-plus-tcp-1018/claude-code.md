# freertos-plus-tcp-1018

Verdict: **VERIFIED**

Attempt: Same patch (sha256 79651013...), same single agent run (run 44784613157), not rerun. First verdict REJECTED on cplus a69c652 (2026-11-20 17:44:56 UTC): anti_cheat FAIL, the patch changes an existing protected test. Checked again on cplus dc84e98, the revision now set for this case: REJECTED again for the same reason; the verdict above is the current one.

Network: the proxy refused 0 request(s) from the agent run (none); allowed connections: api.anthropic.com x3. Counted from the proxy log; the isolation proof's own requests are excluded.

Elapsed: 49.0 s

Verifier: cplus 6121ef2a29edca936fdd9f16386782ca748e12fb · 2026-11-26 20:45:48 UTC

Reference: ctest_module (module FreeRTOS_Sockets_TCP_API_utest; only tests added by the fix fail on the base)

Patch: sha256 796510137d474805dfbc87d8a76fc3021a332aefcb2c82e37e4b41a032601307

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

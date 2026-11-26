# freertos-plus-tcp-1357

Verdict: **VERIFIED**

Reason: judged by upstream reference test 'test_FreeRTOS_inet_ntop6_MaxAddressExactSize'; fix proven

Attempt: Same patch (sha256 bb5bd5a3...), same single agent run (run 44783989869), not rerun. First verdict INFRASTRUCTURE_ERROR on cplus a69c652 (2026-11-20 17:35:17 UTC): cplus bug baseline: reference test did not reproduce, a limit of that verifier revision (FreeRTOS-Plus-TCP was configured twice, c-plus #113). Checked again on cplus dc84e98, the revision now set for this case; the verdict above is the current one.

Network: the proxy refused 0 request(s) from the agent run (none); allowed connections: api.anthropic.com x3. Counted from the proxy log; the isolation proof's own requests are excluded.

Elapsed: 74.6 s

Verifier: cplus dc84e98a80499b118ffb437ce722533fcde03af7 · 2026-11-26 16:35:47 UTC

Reference: ctest_module (module FreeRTOS_Sockets_IPv6_utest; only tests added by the fix fail on the base)

Patch: sha256 bb5bd5a361f16cf8227c5c049182bbe88ff84f97fc1709250e7b729c4abc5523

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

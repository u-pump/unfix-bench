# freertos-plus-tcp-1158

Verdict: **VERIFIED**

Attempt: Same patch (sha256 9a73359e...), same single agent run (run 45874578333), not rerun. First verdict REJECTED on cplus dc84e98 (2026-11-26 18:21:04 UTC): anti_cheat FAIL for a changed protected test file (test/unit-test/FreeRTOS_DNS_Parser/FreeRTOS_DNS_Parser_utest.c, line 3072), a limit of that verifier revision (an agent edit identical to the upstream hunk of the reference was counted as a violation, c-plus #114). Checked again on cplus 6121ef2, the revision now set for this case; the verdict above is the current one.

Network: the proxy refused 0 request(s) from the agent run (none); allowed connections: api.anthropic.com x3. Counted from the proxy log; the isolation proof's own requests are excluded.

Elapsed: 48.5 s

Verifier: cplus 6121ef2a29edca936fdd9f16386782ca748e12fb · 2026-11-26 21:48:08 UTC

Reference: ctest_module (module FreeRTOS_DNS_Parser_utest; only tests added by the fix fail on the base)

Patch: sha256 9a73359e53d4b8f3c5e5358544a31afe68aeb7bd41f8fbc40358b402af11b01f

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

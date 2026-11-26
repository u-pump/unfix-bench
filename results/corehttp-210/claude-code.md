# corehttp-210

Verdict: **VERIFIED**

Reason: judged by upstream reference test 'test_HTTPClient_Send_parse_complete_header_field_at_read_boundary'; fix proven

Attempt: Same patch (sha256 79462f3a...), same single agent run (run 44794967422), not rerun. First verdict VERIFIED on cplus a69c652 (2026-11-20 18:43:50 UTC). Checked again on cplus dc84e98, the revision now set for this case: VERIFIED again with 8 of 8 gates PASS; the verdict above is the current one.

Network: the proxy refused 0 request(s) from the agent run (none); allowed connections: api.anthropic.com x3. Counted from the proxy log; the isolation proof's own requests are excluded.

Elapsed: 17.0 s

Verifier: cplus dc84e98a80499b118ffb437ce722533fcde03af7 · 2026-11-26 17:56:53 UTC

Reference: ctest_module (module core_http_send_utest; only tests added by the fix fail on the base)

Patch: sha256 79462f3a4cd2caddc9aebfd2dc07a88921bf6ec1128c9b1d6253341c7b905bc6

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

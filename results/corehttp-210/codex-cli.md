# corehttp-210

Verdict: **VERIFIED**

Attempt: Same patch (sha256 4aaf257b...), same single agent run (run 44794974954), not rerun. First verdict REJECTED on cplus a69c652 (2026-11-20 18:44:02 UTC): anti_cheat FAIL for a changed protected test file (test/unit-test/core_http_send_utest.c, line 111), a limit of that verifier revision (a new #define constant counted as a violation, c-plus #110). Checked again on cplus dc84e98, the revision now set for this case; the verdict above is the current one.

Network: the proxy refused 17 request(s) from the agent run (ab.chatgpt.com x2, chatgpt.com x15); allowed connections: api.openai.com x1. Counted from the proxy log; the isolation proof's own requests are excluded.

Elapsed: 17.7 s

Verifier: cplus dc84e98a80499b118ffb437ce722533fcde03af7 · 2026-11-26 18:06:52 UTC

Reference: ctest_module (module core_http_send_utest; only tests added by the fix fail on the base)

Patch: sha256 4aaf257b10967a42757c1ac12cc9c7d61eab549276d9ef2f310bb125a2976997

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

# corehttp-210

Verdict: **REJECTED**

Reason: the patch changes protected tests or check configuration; test/unit-test/core_http_send_utest.c, line 111

Network: the proxy refused 17 request(s) from the agent run (ab.chatgpt.com x2, chatgpt.com x15); allowed connections: api.openai.com x1. Counted from the proxy log; the isolation proof's own requests are excluded.

Elapsed: 0.7 s

Verifier: cplus a69c6524b9680dd349c511de32a628f40e7dc2a2 · 2026-11-20 18:44:02 UTC

Reference: ctest_module (module core_http_send_utest; only tests added by the fix fail on the base)

Patch: sha256 4aaf257b10967a42757c1ac12cc9c7d61eab549276d9ef2f310bb125a2976997

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

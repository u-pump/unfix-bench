# coremqtt-331

Verdict: **NOT_VERIFIABLE**

Reason: reference test conflicts with agent test edits

Network: the proxy refused 0 request(s) from the agent run (none); allowed connections: api.anthropic.com x3. Counted from the proxy log; the isolation proof's own requests are excluded.

Elapsed: 2.2 s

Verifier: cplus 6967f904db2659e61142591664c0508e81e262c6 · 2026-11-17 23:26:29 UTC

Reference: ctest_module (module core_mqtt_serializer_utest; only tests added by the fix fail on the base)

Patch: sha256 669b364daae0e3525c93012d298824461a10a188381a3728c7148e1f6e57949a

Agent: Claude Code · Version: 2.1.323 (Claude Code)

| Check | Status |
| --- | --- |
| anti_cheat | SKIPPED |
| build:baseline | SKIPPED |
| repro:baseline | SKIPPED |
| build:patched | SKIPPED |
| repro:patched | SKIPPED |
| repeat | SKIPPED |
| revert | SKIPPED |
| regression | SKIPPED |

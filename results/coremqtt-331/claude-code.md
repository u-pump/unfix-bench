# coremqtt-331

Verdict: **VERIFIED**

Attempt: Same patch (sha256 669b364d...), same single agent run (run 44198931220), not rerun. First verdict NOT_VERIFIABLE on cplus 6967f90 (2026-11-17 23:26:29 UTC): reference test conflicts with agent test edits, a limit of that verifier revision. Verified again with cplus dadf0588 (c-plus #97, #99); the verdict above is the current one.

Network: the proxy refused 0 request(s) from the agent run (none); allowed connections: api.anthropic.com x3. Counted from the proxy log; the isolation proof's own requests are excluded.

Elapsed: 17.1 s

Verifier: cplus dadf0588efee26730378c298fdddd212437aed86 · 2026-11-18 12:05:49 UTC

Reference: ctest_module (module core_mqtt_serializer_utest; only tests added by the fix fail on the base)

Patch: sha256 669b364daae0e3525c93012d298824461a10a188381a3728c7148e1f6e57949a

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

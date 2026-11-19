# coremqtt-331

Verdict: **REJECTED**

Reason: the patch changes protected tests or check configuration; test/unit-test/core_mqtt_serializer_utest.c, line 460

Attempt: Same patch (sha256 34f0e7b2...), same single agent run (run 44306825972), not rerun. First verdict REJECTED on cplus dadf0588 (2026-11-18 12:48:28 UTC): anti_cheat FAIL for a changed comment line (test/unit-test/core_mqtt_serializer_utest.c, line 460), the rule of that revision. Checked again on cplus a69c652 (c-plus #100, #101), which does not count comments; the verdict above is the current one.

Network: the proxy refused 16 request(s) from the agent run (ab.chatgpt.com x1, chatgpt.com x15); allowed connections: api.openai.com x1. Counted from the proxy log; the isolation proof's own requests are excluded.

Elapsed: 0.9 s

Verifier: cplus dadf0588efee26730378c298fdddd212437aed86 · 2026-11-18 12:48:28 UTC

Reference: ctest_module (module core_mqtt_serializer_utest; only tests added by the fix fail on the base)

Patch: sha256 34f0e7b2dd0845057eee4c78fd684faf9c8e4cb01141148c715cd7b0dd0bc2ef

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

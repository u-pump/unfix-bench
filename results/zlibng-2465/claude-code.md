# zlibng-2465

Verdict: **VERIFIED**

Reason: judged by upstream reference test 'inflate.mark_inside_match'; fix proven

Network: the proxy refused 3 request(s) from the agent run (github.com x3); allowed hosts: api.anthropic.com. Reconstructed from the stored proxy log, proof requests subtracted by their known number.

Elapsed: 44.9 s

Verifier: cplus 81c0fda242fef1daf55d3164e06127d372c81caa · 2026-11-13 21:36:08 UTC

Patch: sha256 c04fd9a7b955ab357ce46041e9c844b137e0517a3544f69f3707f833b7fbc204

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

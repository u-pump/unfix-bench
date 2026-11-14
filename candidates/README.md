# Candidates (drafts, not cases)

Mined candidate cases for BENCH-20. Nothing here is a published case: the owner reviews a draft, creates the private `bench-in-<id>` input and moves it to `cases/`. See [the selection rules](../docs/protocol.md#candidate-selection-bench-20) and [the plan](../docs/plans/bench-20-miner.md).

```
candidates/<id>/case.yaml     case fields as in cases/, plus bug_test_granularity, build_network, submodules
candidates/<id>/meta.yaml     source, spdx, fix_date, post_cutoff, upstream_pr, fuzz_origin, dedupe_key, mined_run_url, miner_version
candidates/<id>/ISSUE.md      draft issue text; removed hints may be listed in ISSUE.removals.md
candidates/<id>/baseline.log  three runs on the base (fail) and three with the fix (pass)
candidates/_rejected/*.jsonl  append-only log of rejected candidates, one JSON object per line, with a reason code
```

Check the shape with `python scripts/candidates.py check`.

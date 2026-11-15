# Candidates (drafts, not cases)

Mined candidate cases for BENCH-20. Nothing here is a published case: the owner reviews a draft, creates the private `bench-in-<id>` input and moves it to `cases/`. See [the selection rules](../docs/protocol.md#candidate-selection-bench-20) and [the plan](../docs/plans/bench-20-miner.md).

```
candidates/<id>/case.yaml     case fields as in cases/, plus bug_test_granularity, build_network, submodules
candidates/<id>/meta.yaml     source, spdx, fix_date, post_cutoff, upstream_pr, fuzz_origin, dedupe_key, mined_run_url, miner_version
candidates/<id>/ISSUE.md      draft issue text; removed hints may be listed in ISSUE.removals.md
candidates/<id>/baseline.log  three runs on the base (fail) and three with the fix (pass)
candidates/_rejected/*.jsonl  append-only log of rejected candidates, one JSON object per line, with a reason code
```

Drafts are produced by the `Mine candidates` workflow (manual run, owner only): `discover` (GitHub reads) -> `image` (builds `docker/miner-build`, no registry) -> `baseline` (clone with network, build and test in the image with `--network none`) -> `collect` (artifact policy) -> `record` (opens a pull request with `candidates/`). Only `record` can write; nothing is moved to `cases/` automatically, and `ISSUE.md` still holds the upstream text with its hints until the owner edits it.

**Checks on the miner's pull request.** The pull request is created with the workflow's `GITHUB_TOKEN`, and GitHub does not start other workflows for events caused by that token, so `verify.yml` does not run on it by itself. What did run: `record.py apply` ends with `candidates.check_candidates` over the whole tree and fails the job if anything is malformed, so a pull request that exists already passed the `candidates/` shape check. If the checks are required for merging, the owner starts them by hand: push any commit to the branch `mine-candidates-<run id>` from their own account, or close and reopen the pull request (standard GitHub behaviour; not tried in this repository yet). The branch is protected by nothing else, so look at the diff before merging.

Check the shape with `python scripts/candidates.py check`.

## Checklist: moving a candidate from `candidates/` to `cases/` (owner)

1. Review `case.yaml`, `meta.yaml`, `ISSUE.md` (and `ISSUE.removals.md`) and `baseline.log`.
2. Create the private `u-pump/bench-in-<id>` input (one root commit, submodules at the commits recorded in `case.yaml`) and add `agent_input_repo` and `input_sha256`; pin its HEAD in `inputs/bench-in-heads.json`.
3. Move `candidates/<id>/case.yaml` to `cases/<id>/case.yaml` and keep `meta.yaml` data (`fix_date`, `post_cutoff`) available for the README split.
4. **Update `THIRD_PARTY_NOTICES.md`**: add the upstream project and its licence file link at the case's `base` commit (add a row for a new project, add the case to the row of a known one).
5. Check that the project or family stays within the cap: at most 30 of the 100 cases (`scripts/mine/cap.py` counts published cases and accepted candidates).
6. Run `python scripts/candidates.py check` and `python scripts/render_readme.py --check`.

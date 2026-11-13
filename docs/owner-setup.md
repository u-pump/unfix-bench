# Owner setup for verification

The repository is safe to browse before this setup. Empty `agent-fix.patch` files produce `PENDING`; no AI agent has run.

1. On GitHub, open your profile picture → **Settings** → **Developer settings** → **Personal access tokens** → **Fine-grained tokens** → **Generate new token**. Set **Resource owner** to `u-pump`, **Repository access** to **Only select repositories**, and select only `u-pump/c-plus`. Under **Repository permissions**, set **Contents: Read-only** and leave other configurable permissions unset. Choose a short expiry, generate the token, and complete any organization approval required for private-repository access. The automatic Metadata read permission is normal.
2. In `u-pump/unfix-bench`, open **Settings** → **Secrets and variables** → **Actions** → **Secrets** → **New repository secret**. Name it `CPLUS_READ_TOKEN` and paste the token value. Do not place it in a file, issue, commit, or workflow input.
3. In `u-pump/unfix-bench`, open **Settings** → **Actions** → **General** → **Approval for running fork pull request workflows from contributors**. Select **Require approval for all external contributors** (the current GitHub wording for the requested outside-collaborator protection), then **Save**. The workflow itself has no `pull_request` or `pull_request_target` trigger.
4. If the organization policy permits it, leave Actions enabled and permit `actions/checkout`, `actions/setup-python`, `actions/upload-artifact`, and `actions/download-artifact`. When an agent patch has been submitted by the owner, push its unchanged file under `cases/` or run **Actions** → **Verify submitted patches** → **Run workflow** with its case ID. Review the generated report before making any benchmark claim.

The read-only token is used only in the install step. The separate publish job receives the standard `GITHUB_TOKEN` with `contents: write` to commit the public summary. The verification job receives `contents: read` only.

## Claude Code runs (BENCH-13)

The [Claude Code workflow](run-claude-code.md) needs three more repository secrets and two settings. None of them is ever written to a file, an issue, a commit or a workflow input.

1. **`CLAUDE_CODE_OAUTH_TOKEN`.** On a machine where you are logged in to the Claude subscription, run `claude setup-token`, copy the token it prints, and add it under **Settings** → **Secrets and variables** → **Actions** → **Secrets** → **New repository secret**. The token is valid for one year and can only make model requests.
2. **`BENCH_INPUT_TOKEN`.** A fine-grained personal access token: **Resource owner** `u-pump`, **Repository access** → **Only select repositories**, select exactly these ten repositories, **Repository permissions** → **Contents: Read-only**, nothing else, short expiry:
   `bench-in-cpp-peglib-121`, `bench-in-fmt-4490`, `bench-in-fmt-4742`, `bench-in-fmt-4800`, `bench-in-fmt-4933`, `bench-in-fmt-4942`, `bench-in-fmt-4960`, `bench-in-fmt-4978`, `bench-in-spdlog-3049`, `bench-in-zlibng-2465`.
3. **`CPLUS_READ_TOKEN`** already exists (see above) and is reused for the verdict.
4. **Pull requests from Actions.** **Settings** → **Actions** → **General** → **Workflow permissions** → tick **Allow GitHub Actions to create and approve pull requests**, then **Save**. The record job opens its pull request with the built-in `GITHUB_TOKEN`; GitHub does not start other workflows for such a pull request, so run the checks by hand if you want them on it.
5. If **Settings** → **Actions** → **General** restricts allowed actions, also permit `actions/checkout`, `actions/setup-python`, `actions/upload-artifact` and `actions/download-artifact` (already required by the verify workflow).

**After all ten runs are done, revoke the Claude token:** delete the `CLAUDE_CODE_OAUTH_TOKEN` secret and revoke the token in the settings of the Claude account that issued it (the account's list of Claude Code sessions and tokens); then check that it no longer works, for example by confirming that a `probe_only` run is unaffected and a new attempt fails authentication. Anthropic's [authentication documentation](https://code.claude.com/docs/en/iam) describes `claude setup-token`. Delete `BENCH_INPUT_TOKEN` as well. If a run ever reports `SECRET FOUND`, revoke the token immediately, whatever else happened.

Artifacts of this repository are downloadable by anyone who can see it, so a run uploads only files that passed the secret scan and keeps them seven days.

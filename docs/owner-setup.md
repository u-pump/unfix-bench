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

**After all ten runs: retire the Claude token on the same day.** Delete the `CLAUDE_CODE_OAUTH_TOKEN` and `BENCH_INPUT_TOKEN` secrets, and delete the token file or shell variable wherever you pasted it. Then read the next paragraph: deleting the secret does not make the token invalid.

**There is no documented way to revoke a `claude setup-token` token.** Anthropic's documentation says only that `claude setup-token` generates "a one-year OAuth token" that "can only make model requests" and is not saved anywhere ([authentication](https://code.claude.com/docs/en/authentication)); that "If you delete a secret, the credential it held stays valid" ([GitHub Actions](https://code.claude.com/docs/en/github-actions)); and that the token "is tied to the subscription of the person who ran `claude setup-token`". The documentation gives no page in claude.ai or the Console that lists or revokes such a token, and it does not say that `claude auth logout` or `/logout` revokes it. The exact interface path is therefore not stated here, because it is not documented. Choices that are open to you:
- ask Anthropic support (https://support.claude.com) how to revoke a `setup-token` token and keep the answer with the run records;
- run the benchmark from a Claude account (or a subscription) used only for it, so that an unrevoked token can reach nothing else, and stop the subscription afterwards;
- otherwise treat the token as live until it expires one year after the date printed by `claude setup-token`, and note that date.
The token can make model requests on that subscription, nothing else.

If a run ever reports `SECRET FOUND`, retire the token the same way at once, whatever else happened.

Artifacts of this repository are downloadable by anyone who can see it, so a run uploads only files that passed the secret scan and keeps them seven days.

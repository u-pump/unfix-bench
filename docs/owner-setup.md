# Owner setup for verification

The repository is safe to browse before this setup. Empty `agent-fix.patch` files produce `PENDING`; no AI agent has run.

1. On GitHub, open your profile picture → **Settings** → **Developer settings** → **Personal access tokens** → **Fine-grained tokens** → **Generate new token**. Set **Resource owner** to `u-pump`, **Repository access** to **Only select repositories**, and select only `u-pump/c-plus`. Under **Repository permissions**, set **Contents: Read-only** and leave other configurable permissions unset. Choose a short expiry, generate the token, and complete any organization approval required for private-repository access. The automatic Metadata read permission is normal.
2. In `u-pump/unfix-bench`, open **Settings** → **Secrets and variables** → **Actions** → **Secrets** → **New repository secret**. Name it `CPLUS_READ_TOKEN` and paste the token value. Do not place it in a file, issue, commit, or workflow input.
3. In `u-pump/unfix-bench`, open **Settings** → **Actions** → **General** → **Approval for running fork pull request workflows from contributors**. Select **Require approval for all external contributors** (the current GitHub wording for the requested outside-collaborator protection), then **Save**. The workflow itself has no `pull_request` or `pull_request_target` trigger.
4. If the organization policy permits it, leave Actions enabled and permit `actions/checkout`, `actions/setup-python`, `actions/upload-artifact`, and `actions/download-artifact`. When an agent patch has been submitted by the owner, push its unchanged file under `cases/` or run **Actions** → **Verify submitted patches** → **Run workflow** with its case ID. Review the generated report before making any benchmark claim.

The read-only token is used only in the install step. The separate publish job receives the standard `GITHUB_TOKEN` with `contents: write` to commit the public summary. The verification job receives `contents: read` only.

## Claude Code runs (BENCH-13)

The [Claude Code workflow](run-claude-code.md) authenticates with an Anthropic API key from a **dedicated Console workspace that has a spend limit**. The key is deleted after the ten runs. Nothing below is ever written to a file, an issue, a commit or a workflow input. Console paths are quoted from Anthropic's documentation ([workspaces](https://platform.claude.com/docs/en/build-with-claude/workspaces), [API key management](https://platform.claude.com/docs/en/manage-claude/authentication)); where the documentation gives no path, this page says so.

1. **Create the workspace.** In the Claude Console open **Workspaces** (`platform.claude.com/settings/workspaces`) and click **Create workspace**; enter a name (for example `unfix-bench`), choose a color, and click **Create workspace** again. Only organization admins can create workspaces. The Default Workspace cannot have a spend limit, so do not use it.
2. **Set the spend limit.** On the **Workspaces** page select the new workspace, and in the panel that opens click **Spend limits** to cap monthly spending and configure alerts. Choose a cap you are willing to lose; the key cannot spend more than this in the workspace. The documentation does not state what a run costs.
3. **Create the key.** Open **API keys** (`platform.claude.com/settings/keys`) and click **Create key**. Name it (for example `unfix-bench-claude-code`), choose an expiration (the presets are 3 hours, 1 day, 7 days and 30 days, or a custom duration; pick one that ends after the last run), and scope the key to the `unfix-bench` workspace. The documentation says a key can be scoped to a specific workspace but does not name the control; do not use an unscoped key, and if the form offers no way to scope it, ask Anthropic support before continuing. Copy the key once.
4. **Add the repository secret `ANTHROPIC_API_KEY`:** **Settings** → **Secrets and variables** → **Actions** → **Secrets** → **New repository secret**, paste the key. Never paste it anywhere else.
5. **`BENCH_INPUT_TOKEN`** (already added): a fine-grained personal access token, **Resource owner** `u-pump`, **Only select repositories**: exactly `bench-in-cpp-peglib-121`, `bench-in-fmt-4490`, `bench-in-fmt-4742`, `bench-in-fmt-4800`, `bench-in-fmt-4933`, `bench-in-fmt-4942`, `bench-in-fmt-4960`, `bench-in-fmt-4978`, `bench-in-spdlog-3049`, `bench-in-zlibng-2465`; **Contents: Read-only**; short expiry.
6. **`CPLUS_READ_TOKEN`** already exists (see above) and is reused for the verdict.
7. **Pull requests from Actions.** **Settings** → **Actions** → **General** → **Workflow permissions** → tick **Allow GitHub Actions to create and approve pull requests**, then **Save**. The record job opens its pull request with the built-in `GITHUB_TOKEN`; GitHub does not start other workflows for such a pull request, so run the checks by hand if you want them on it.
8. If **Settings** → **Actions** → **General** restricts allowed actions, also permit `actions/checkout`, `actions/setup-python`, `actions/upload-artifact` and `actions/download-artifact`.

**After the ten runs, on the same day:**
1. On **API keys** (`platform.claude.com/settings/keys`) click **Delete** on the key. The documentation says **Disable** is reversible and **Delete** is permanent; it does not say how fast either takes effect.
2. Delete the `ANTHROPIC_API_KEY` and `BENCH_INPUT_TOKEN` repository secrets. Deleting a secret does not make the credential invalid ("If you delete a secret, the credential it held stays valid"), which is why the key itself is deleted in step 1.
3. Check that the key is gone: it appears on the **API keys** page with the status archived (the documentation describes deleted keys as archived).
4. Optionally archive the workspace: the documentation says archiving "deactivates the workspace and archives every API key created for it" and cannot be undone.

If a run ever reports `SECRET FOUND`, delete the key at once, whatever else happened.

Artifacts of this repository are downloadable by anyone who can see it, so a run uploads only files that passed the secret scan and keeps them seven days.

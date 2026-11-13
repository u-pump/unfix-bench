# Running Codex CLI locally

Codex CLI is run by the owner on a local Windows machine. Claude Code runs in GitHub Actions instead: see [run-claude-code.md](run-claude-code.md).

The script takes only the private `u-pump/bench-in-<id>` snapshot, passes the unchanged `TASK.md` text, saves the first attempt, and refuses to overwrite a recorded one. In PowerShell 7, from the root of the benchmark repository, with `codex` installed and `gh` logged in as `u-pump`:

```powershell
pwsh -File scripts/run-agent-local.ps1 -Agent codex-cli <case-id>
```

The script runs `codex exec --sandbox workspace-write`, writes `agent-fix.patch` without `build*/` output, and records the Codex version, model, date and patch SHA-256 in `agent.yaml`. The log stays in `.tmp/agent-runs/logs/`. A failed CLI run or a run without a completed command changes no file. Submit the result in a separate pull request; do not edit the patch or repeat the attempt.

Whether the local Codex sandbox blocks network access depends on the CLI configuration and is not verified by this script; see the [conditions of both agents](protocol.md#conditions-codex-cli-and-claude-code).

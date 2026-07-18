# Local Codex Primary Automation

This runbook defines the unattended daily and Sunday workflow without copying any local
Codex credential into the repository, Windows Task Scheduler, GitHub Actions, or logs.

## Operating model

The automation has two independent layers:

| Layer | Default time (Asia/Shanghai) | Content backend | Purpose |
| --- | --- | --- | --- |
| Local daily primary | Every day 07:30 | Installed `codex exec` | Produce the review-ready daily copy and posters on time |
| Local weekly primary | Sunday 08:45 | Installed `codex exec` | Produce the Sunday weekly issue after the daily task |
| Actions daily fallback | Every day 09:17 | Deterministic | Generate only when no exact, complete local Codex report exists |
| Actions weekly fallback | Sunday 10:27 | Deterministic | Generate only when no exact, complete Sunday Codex report exists |

GitHub Actions cron can be delayed, so it is a continuity fallback rather than the
publication clock. The daily task also has a current-user logon trigger: if the scheduled
time was missed, the next sign-in runs the same idempotent transaction. The two local tasks
share one lock. If the daily task is still running when the Sunday task starts, Task Scheduler
retries instead of running both writers.

A normal local-user push triggers `pages.yml` through its `push` event. A push made with the
workflow `GITHUB_TOKEN` does not recursively trigger another workflow, so a successful daily
or weekly Actions fallback explicitly dispatches `pages.yml --ref main`. Failed or skipped
fallback publication does not dispatch Pages.

The project still generates drafts for human review. It does not sign in to Xiaohongshu or
publish a post.

## Credential boundary

The local runner:

- invokes the installed `codex` command as the current Windows user;
- lets Codex load its own user-level provider and authentication state;
- does not open or parse Codex credential, endpoint, provider, model, config, or auth files;
- does not put credentials in task arguments, Git commits, report metadata, or runtime logs;
- runs Codex only through the existing evidence-bound, read-only editorial adapter;
- never copies the local Codex credential to GitHub Actions.

The scheduled tasks use `Interactive` and `Limited` logon settings. They therefore run with
the same signed-in user profile as the verified Codex CLI and do not run as `SYSTEM` or an
administrator. If the computer is powered off or the user session is signed out, the local
LLM run is not guaranteed; the later deterministic Actions workflow remains available.

The local repository `HEAD` is the executable-code trust anchor. Fetching `origin/main` does
not make new remote code trusted. The runner requires the trusted local commit to be an
ancestor of the fetched commit and permits every intervening path only when it is a dated
snapshot, daily/weekly report, poster asset, or avatar. Any change to Python, PowerShell,
configuration, prompts, schemas, workflows, site code, or documentation stops the task before
the remote worktree is created or executed. Update and review the IDE checkout manually before
resuming after such a change.

Bundle verification for any temporary worktree uses the local trusted
`src/github_hotspots/automation.py` directly with `python -S`. It never imports a verifier from
the fetched worktree. The verified `origin/main` SHA is captured and used for worktree creation,
so a moving remote-tracking ref cannot bypass the path gate.

## Local transaction

`scripts/automation/run_scheduled.ps1` performs one transaction:

1. Acquire `%LOCALAPPDATA%\GitHubHotspots\run.lock` with exclusive file access. Once the lock
   is held, remove automation-named worktrees older than six hours and path manifests older
   than one day, with every deletion constrained below the state root.
2. Resolve the run date in `China Standard Time`. A delayed weekly task outside Sunday is
   skipped rather than labelled as a false Sunday snapshot.
3. Verify `git`, the project virtual environment, and the installed Codex CLI without
   reading credentials or configuration.
4. Fetch `origin/main`, record local `HEAD` as the trusted commit, require ancestor continuity,
   and validate the complete `trusted..remote` diff with the report-only remote path gate.
5. Create a detached temporary worktree at the exact verified remote SHA below
   `%LOCALAPPDATA%\GitHubHotspots\worktrees\`.
6. If the remote commit already contains a current, complete report for the exact date with
   both boards using Codex without fallback, also verify its indexed `publish/history` revision.
   Skip only when both are complete; if only history is missing, rebuild history without
   calling Codex or replacing the report.
7. Run pytest, Ruff lint, and Ruff format checks in the isolated worktree.
8. Run the daily or weekly pipeline with `--editorial-backend codex-cli`.
9. Strictly validate Prompt 4.1 / Schema 4.0, both non-empty boards, current publication issue
   metadata, renderer 4.0, `signal-broadsheet-v1`, Markdown copies, ranked identities, and each
   PNG chunk, CRC, dimension, IDAT, and IEND.
10. Build `publish/current/<period>` inside the temporary worktree as a complete preflight and
    write the thin revision below `publish/history/<period>/<year>/<stem>/<fingerprint>/`.
    A publication packaging or history verification failure happens before commit or push.
11. Reject any changed path outside the exact snapshot/report/history allowlist and scan staged
    text for high-confidence credential signatures. History may contain only its two indexes,
    revision manifests/checklists, and the two boards' title/caption/review text; PNG is rejected.
12. Create one `chore(hotspots): ...` report-only commit.
13. Fetch and rerun the trusted remote path gate before every rebase, remote publication read,
    or push-race decision. Only report-only remote movement may be rebased; code or configuration
    movement aborts and requires a fresh trusted local update. Never force push.
14. After a successful push or verified remote win, rebuild or idempotently reuse the package
    and copy it to the IDE workspace. Equality uses the publish `content_fingerprint`; copied
    images are recorded as `materialization: copy` in the final target manifest. A newer local
    `current` cannot be replaced by an older run date, and a damaged matching bundle is rebuilt.
15. Verify the Pages workflow for the resulting commit, then remove the temporary worktree.

The IDE checkout is never reset, cleaned, rebased, or used as the generation worktree.
Unrelated local edits remain untouched.

## Strict report gate

The standard-library validator can be run without installing project dependencies:

```powershell
.\.venv\Scripts\python.exe -S .\src\github_hotspots\automation.py verify `
  --root . `
  --period daily `
  --date 2026-07-12 `
  --require-codex
```

Every `verify` run rejects an older editorial/poster contract, empty board, wrong publication
issue, or incomplete/corrupt PNG. `--require-codex` additionally exits non-zero if either board
used deterministic writing or any fallback. This extra backend gate is required because the
interactive CLI intentionally treats deterministic fallback as a usable report and normally
exits successfully.

Verify the permanent thin-history record independently:

```powershell
.\.venv\Scripts\python.exe -S .\src\github_hotspots\automation.py verify-history `
  --root . `
  --period daily `
  --date 2026-07-13
```

`verify-history` requires a revision matching the current report and poster-manifest hashes,
checks every stored text hash and referenced PNG hash/dimension, rejects packaged PNG under
`publish/history`, and confirms that the revision appears in `INDEX.json`.

The path gate is also available independently:

```powershell
$pathsFile = Join-Path $env:TEMP "github-hotspots-paths.txt"
$paths = @(git -c core.quotepath=false diff --name-only)
[IO.File]::WriteAllLines($pathsFile, $paths, [Text.UTF8Encoding]::new($false))
.\.venv\Scripts\python.exe -S .\src\github_hotspots\automation.py validate-paths `
  --period daily `
  --date 2026-07-12 `
  --paths-file $pathsFile
Remove-Item $pathsFile
```

Remote movement is checked separately across every date and both periods:

```powershell
$pathsFile = Join-Path $env:TEMP "github-hotspots-remote-paths.txt"
$paths = @(git -c core.quotepath=false diff --name-only --no-renames HEAD..origin/main)
[IO.File]::WriteAllLines($pathsFile, $paths, [Text.UTF8Encoding]::new($false))
.\.venv\Scripts\python.exe -S .\src\github_hotspots\automation.py validate-remote-paths `
  --paths-file $pathsFile
Remove-Item $pathsFile
```

## Register the Windows tasks

Registration is explicit. The repository never registers or modifies a task merely because
tests or the application run.

Task Scheduler trigger times use the Windows system time zone. The registration script
therefore requires `[TimeZoneInfo]::Local.Id` to equal `China Standard Time`; it refuses to
register under any other zone rather than silently scheduling 07:30/08:45 in the wrong locale.

Preview first:

```powershell
.\scripts\automation\register_tasks.ps1 -WhatIf
```

Register the defaults:

```powershell
.\scripts\automation\register_tasks.ps1
```

Choose different local generation times when needed:

```powershell
.\scripts\automation\register_tasks.ps1 -DailyAt "07:15" -WeeklyAt "08:30"
```

The registered settings are:

- current Windows user, interactive logon, limited privileges;
- daily schedule plus a current-user logon catch-up trigger;
- wake from sleep when supported and start when available;
- no Task Scheduler network launch gate; the runner starts, records a log, and lets fetch or
  source collection fail visibly when connectivity is unavailable;
- ignore a duplicate instance of the same task;
- retry three times at 15-minute intervals;
- stop after 75 minutes;
- continue when using battery power.

Check status without changing anything:

```powershell
$names = @(
  "GitHub Hotspots Daily (Local Codex)",
  "GitHub Hotspots Weekly (Local Codex)"
)
Get-ScheduledTask -TaskName $names
Get-ScheduledTaskInfo -TaskName $names
```

If either task is missing, rerun `register_tasks.ps1`. A healthy daily task is `Ready`,
has one daily trigger plus one current-user logon trigger, and reports
`RunOnlyIfNetworkAvailable=False`.

Run one registered task manually:

```powershell
Start-ScheduledTask -TaskName "GitHub Hotspots Daily (Local Codex)"
```

Remove the tasks without touching reports or credentials:

```powershell
Unregister-ScheduledTask -TaskName "GitHub Hotspots Daily (Local Codex)" -Confirm:$false
Unregister-ScheduledTask -TaskName "GitHub Hotspots Weekly (Local Codex)" -Confirm:$false
```

## Logs and retention

Local runtime logs are written to:

```text
%LOCALAPPDATA%\GitHubHotspots\logs\
```

They contain operation names, safe program output, exit codes, commit SHA, and Pages URL.
They do not intentionally record environment variables, task XML, Codex prompts, raw Codex
responses, provider configuration, or credentials. Logs older than 30 days are removed by a
later run. Logs and temporary worktrees are outside Git. If PowerShell is force-killed or the
machine loses power before `finally`, the next lock owner safely removes automation-named state
worktrees older than six hours and `*.paths` manifests older than one day.

`publish/archive/` is intentionally not deleted automatically because a locally edited issue may
still be waiting for manual Xiaohongshu publication. It is not the permanent project archive:
Git-tracked generated baselines live in `publish/history/`, while `archive/` protects local human
edits and can grow over time. Weekly folders use the ISO week-year. Review local archive retention
manually before deletion. Persistent scheduler runtime logs are under
`%LOCALAPPDATA%\GitHubHotspots\logs`; the ignored `publish/logs` created in a temporary worktree is
not the authoritative unattended-run log.

## Failure behaviour

| Failure | Result |
| --- | --- |
| Daily or weekly task is missing | Re-run `register_tasks.ps1`, verify both tasks are `Ready`, then use an explicit reviewed recovery run for any missing current-date report |
| Lock already held | Exit `75`; Task Scheduler retries |
| Tests, lint, source collection, or report render fails | No commit and no push |
| Codex unavailable, times out, or falls back | Strict gate fails; no local commit; Actions may generate the deterministic fallback |
| Remote is force-pushed or contains code/config/prompt/workflow/doc changes after trusted `HEAD` | Abort before executing the remote worktree; manually review and update the local checkout |
| Current report uses an old prompt/schema/renderer/style, wrong issue metadata, empty board, or corrupt PNG | Strict gate fails; regenerate with the trusted current code |
| Publication package preflight fails | No commit and no push |
| Publication history is missing while the Codex report is valid | Rebuild and commit only the history; do not rerun Codex or replace report facts |
| Publication preflight changes the history index after a report-only rebase | Abort and retry from a fresh worktree instead of pushing a dirty tree |
| Unexpected or suspicious staged file | No commit and no push |
| Non-fast-forward with a valid remote Codex report | Remote wins; no duplicate commit and no force push |
| Non-fast-forward without a valid remote report | Clean rebase only; conflict fails and retries from a fresh worktree |
| Pages deployment fails or times out | Content commit remains; task reports failure for operator follow-up |
| Machine misses Sunday and starts on Monday | No inaccurate weekly backfill; use the Actions fallback or an explicit reviewed manual run |

Do not backdate a report merely to fill a gap. GitHub counters and Trending describe the
query time, so a later collection cannot truthfully reconstruct a missed earlier snapshot.

## Codex CLI references

- [Developer commands: `codex exec`](https://learn.chatgpt.com/docs/developer-commands#codex-exec)
- [Sandbox and approval combinations](https://learn.chatgpt.com/docs/agent-approvals-security#common-sandbox-and-approval-combinations)

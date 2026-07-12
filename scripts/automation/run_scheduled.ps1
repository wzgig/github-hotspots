[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("daily", "weekly")]
    [string]$Period,

    [ValidatePattern("^\d{4}-\d{2}-\d{2}$")]
    [string]$RunDate,

    [string]$StateRoot = (Join-Path $env:LOCALAPPDATA "GitHubHotspots"),

    [switch]$SkipPagesWait
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$AutomationScript = Join-Path $RepoRoot "src\github_hotspots\automation.py"
$StateRoot = [System.IO.Path]::GetFullPath($StateRoot)
$LogRoot = Join-Path $StateRoot "logs"
$WorktreeRoot = Join-Path $StateRoot "worktrees"
$RunId = "{0}-{1}-{2}" -f (Get-Date -Format "yyyyMMddTHHmmss"), $Period, ([guid]::NewGuid().ToString("N").Substring(0, 8))
$LogPath = Join-Path $LogRoot ("{0}.log" -f $RunId)
$LockPath = Join-Path $StateRoot "run.lock"
$WorktreePath = Join-Path $WorktreeRoot $RunId
$LockStream = $null
$WorktreeAdded = $false
$TrustedCommit = $null
$VerifiedRemoteCommit = $null

New-Item -ItemType Directory -Force -Path $LogRoot, $WorktreeRoot | Out-Null

function Write-RunLog {
    param([Parameter(Mandatory = $true)][string]$Message)

    $line = "{0} {1}" -f ([DateTimeOffset]::Now.ToString("o")), $Message
    Add-Content -LiteralPath $LogPath -Value $line -Encoding utf8
    Write-Host $line
}

function Assert-StateChild {
    param([Parameter(Mandatory = $true)][string]$Path)

    $fullPath = [System.IO.Path]::GetFullPath($Path)
    $rootWithSeparator = $StateRoot.TrimEnd('\') + '\'
    if (-not $fullPath.StartsWith($rootWithSeparator, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to operate outside the automation state root."
    }
}

function Invoke-Logged {
    param(
        [Parameter(Mandatory = $true)][string]$Label,
        [Parameter(Mandatory = $true)][string]$FilePath,
        [string[]]$ArgumentList = @(),
        [string]$WorkingDirectory = $RepoRoot,
        [switch]$AllowFailure
    )

    Write-RunLog "start $Label"
    Push-Location $WorkingDirectory
    $nativeErrorActionPreference = $ErrorActionPreference
    $exitCode = 1
    try {
        # Windows PowerShell 5.1 promotes native stderr to ErrorRecord objects when streams are
        # merged. Git and gh legitimately write progress to stderr on exit 0, so trust the native
        # exit code while still recording both streams instead of treating progress as a failure.
        $ErrorActionPreference = "Continue"
        & $FilePath @ArgumentList 2>&1 | ForEach-Object {
            $outputLine = "$_"
            Add-Content -LiteralPath $LogPath -Value $outputLine -Encoding utf8
            Write-Host $outputLine
        }
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $nativeErrorActionPreference
        Pop-Location
    }
    Write-RunLog "finish $Label exit=$exitCode"
    if ($exitCode -ne 0 -and -not $AllowFailure) {
        throw "$Label failed with exit code $exitCode."
    }
    return $exitCode
}

function Invoke-Captured {
    param(
        [Parameter(Mandatory = $true)][string]$Label,
        [Parameter(Mandatory = $true)][string]$FilePath,
        [string[]]$ArgumentList = @(),
        [string]$WorkingDirectory = $RepoRoot,
        [switch]$AllowFailure
    )

    Write-RunLog "start $Label"
    Push-Location $WorkingDirectory
    $nativeErrorActionPreference = $ErrorActionPreference
    $exitCode = 1
    $output = @()
    try {
        $ErrorActionPreference = "Continue"
        $output = @(& $FilePath @ArgumentList 2>&1)
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $nativeErrorActionPreference
        Pop-Location
    }
    foreach ($item in $output) {
        Add-Content -LiteralPath $LogPath -Value "$item" -Encoding utf8
    }
    Write-RunLog "finish $Label exit=$exitCode"
    if ($exitCode -ne 0 -and -not $AllowFailure) {
        throw "$Label failed with exit code $exitCode."
    }
    return $output
}

function Test-Bundle {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string]$Python,
        [Parameter(Mandatory = $true)][string]$TargetPeriod,
        [Parameter(Mandatory = $true)][string]$TargetDate
    )

    $exitCode = Invoke-Logged `
        -Label "verify bundle with trusted validator" `
        -FilePath $Python `
        -ArgumentList @(
            "-S", $AutomationScript, "verify",
            "--root", $Root,
            "--period", $TargetPeriod,
            "--date", $TargetDate,
            "--require-codex",
            "--quiet"
        ) `
        -WorkingDirectory $RepoRoot `
        -AllowFailure
    return $exitCode -eq 0
}

function Assert-PublishChild {
    param([Parameter(Mandatory = $true)][string]$Path)

    $publishRoot = [System.IO.Path]::GetFullPath((Join-Path $RepoRoot "publish"))
    $fullPath = [System.IO.Path]::GetFullPath($Path)
    $rootWithSeparator = $publishRoot.TrimEnd('\') + '\'
    if (
        $fullPath -ne $publishRoot -and
        -not $fullPath.StartsWith($rootWithSeparator, [System.StringComparison]::OrdinalIgnoreCase)
    ) {
        throw "Refusing to operate outside the repository publish directory."
    }
}

function Get-IsoWeekYear {
    param([Parameter(Mandatory = $true)][DateTime]$Date)

    $isoDay = (([int]$Date.DayOfWeek + 6) % 7)
    return $Date.AddDays(3 - $isoDay).Year
}

function Update-PublishTodayIndex {
    param(
        [Parameter(Mandatory = $true)][string]$SourceRoot,
        [Parameter(Mandatory = $true)][string]$Python
    )

    $publishRoot = Join-Path $RepoRoot "publish"
    $todayPath = Join-Path $publishRoot "current\TODAY.md"
    Assert-PublishChild $todayPath
    $previousPythonPath = $env:PYTHONPATH
    $previousPublishRoot = $env:GH_HOTSPOTS_PUBLISH_ROOT
    $env:PYTHONPATH = Join-Path $SourceRoot "src"
    $env:GH_HOTSPOTS_PUBLISH_ROOT = $publishRoot
    try {
        Invoke-Logged `
            -Label "refresh local publication index" `
            -FilePath $Python `
            -ArgumentList @(
                "-c",
                "import os; from github_hotspots.publish_bundle import refresh_publish_index; refresh_publish_index(os.environ['GH_HOTSPOTS_PUBLISH_ROOT'])"
            ) `
            -WorkingDirectory $SourceRoot | Out-Null
    }
    finally {
        $env:PYTHONPATH = $previousPythonPath
        if ($null -eq $previousPublishRoot) {
            Remove-Item Env:GH_HOTSPOTS_PUBLISH_ROOT -ErrorAction SilentlyContinue
        }
        else {
            $env:GH_HOTSPOTS_PUBLISH_ROOT = $previousPublishRoot
        }
    }
}

function Test-PublishManifestUsesCopies {
    param([Parameter(Mandatory = $true)]$Manifest)

    $boards = @($Manifest.boards)
    if ($boards.Count -lt 1) {
        return $false
    }
    foreach ($board in $boards) {
        $images = @($board.images)
        if ($images.Count -lt 1) {
            return $false
        }
        foreach ($image in $images) {
            if ($image.materialization -ne "copy") {
                return $false
            }
        }
    }
    return $true
}

function Set-PublishManifestMaterializationToCopy {
    param([Parameter(Mandatory = $true)][string]$ManifestPath)

    Assert-PublishChild $ManifestPath
    $manifest = Get-Content -LiteralPath $ManifestPath -Raw -Encoding utf8 | ConvertFrom-Json
    foreach ($board in @($manifest.boards)) {
        foreach ($image in @($board.images)) {
            $image.materialization = "copy"
        }
    }
    $json = ($manifest | ConvertTo-Json -Depth 100) + "`n"
    [System.IO.File]::WriteAllText(
        $ManifestPath,
        $json,
        [System.Text.UTF8Encoding]::new($false)
    )
}

function Sync-PublishDirectory {
    param(
        [Parameter(Mandatory = $true)][string]$SourceRoot,
        [Parameter(Mandatory = $true)][string]$Python
    )

    $source = Join-Path $SourceRoot "publish\current\$Period"
    if (-not (Test-Path -LiteralPath $source -PathType Container)) {
        throw "Generated publication folder is missing: $source"
    }
    $publishRoot = Join-Path $RepoRoot "publish"
    $target = Join-Path $publishRoot "current\$Period"
    $sourceManifestPath = Join-Path $source "MANIFEST.json"
    $sourceManifest = Get-Content -LiteralPath $sourceManifestPath -Raw -Encoding utf8 | ConvertFrom-Json
    Assert-PublishChild $target

    if (Test-Path -LiteralPath $target -PathType Container) {
        $targetManifestPath = Join-Path $target "MANIFEST.json"
        if (-not (Test-Path -LiteralPath $targetManifestPath -PathType Leaf)) {
            throw "Existing local publication folder has no MANIFEST.json: $target"
        }
        $targetManifest = Get-Content -LiteralPath $targetManifestPath -Raw -Encoding utf8 | ConvertFrom-Json
        $sourceFingerprint = "$($sourceManifest.content_fingerprint)"
        $targetFingerprint = "$($targetManifest.content_fingerprint)"
        if (
            $sourceFingerprint -match "^[0-9a-f]{64}$" -and
            $targetFingerprint -eq $sourceFingerprint -and
            (Test-PublishManifestUsesCopies -Manifest $targetManifest)
        ) {
            Write-RunLog "local publish folder already matches source report"
            Update-PublishTodayIndex -SourceRoot $SourceRoot -Python $Python
            return
        }
        $archiveDate = [DateTime]::ParseExact(
            "$($targetManifest.run_date)",
            "yyyy-MM-dd",
            [System.Globalization.CultureInfo]::InvariantCulture
        )
        $archiveYear = if ($Period -eq "weekly") {
            Get-IsoWeekYear -Date $archiveDate
        }
        else {
            $archiveDate.Year
        }
        $archiveBase = Join-Path $publishRoot "archive\$Period\$archiveYear\$($targetManifest.issue.stem)"
        $archive = $archiveBase
        if (Test-Path -LiteralPath $archive) {
            $archive = "$archiveBase-sync-$((Get-Date).ToString('yyyyMMddTHHmmss'))"
        }
        Assert-PublishChild $archive
        New-Item -ItemType Directory -Force -Path (Split-Path $archive -Parent) | Out-Null
        Move-Item -LiteralPath $target -Destination $archive
        Write-RunLog "archived previous local publish folder path=$archive"
    }

    New-Item -ItemType Directory -Force -Path (Split-Path $target -Parent) | Out-Null
    Copy-Item -LiteralPath $source -Destination $target -Recurse
    Set-PublishManifestMaterializationToCopy -ManifestPath (Join-Path $target "MANIFEST.json")
    Update-PublishTodayIndex -SourceRoot $SourceRoot -Python $Python
    Write-RunLog "synchronised local publish folder path=$target"
}

function Build-And-SyncPublication {
    param(
        [Parameter(Mandatory = $true)][string]$SourceRoot,
        [Parameter(Mandatory = $true)][string]$Python,
        [Parameter(Mandatory = $true)][string]$TargetPeriod,
        [Parameter(Mandatory = $true)][string]$TargetDate
    )

    $previousPythonPath = $env:PYTHONPATH
    $env:PYTHONPATH = Join-Path $SourceRoot "src"
    try {
        $stem = ((Invoke-Captured `
            -Label "calculate publication report stem" `
            -FilePath $Python `
            -ArgumentList @(
                "-S", $AutomationScript, "stem",
                "--period", $TargetPeriod,
                "--date", $TargetDate
            ) `
            -WorkingDirectory $RepoRoot) -join "").Trim()
        Invoke-Logged `
            -Label "prepare local publication folder" `
            -FilePath $Python `
            -ArgumentList @(
                "-m", "github_hotspots.cli", "publish",
                "reports/$TargetPeriod/$stem.json"
            ) `
            -WorkingDirectory $SourceRoot | Out-Null
        Sync-PublishDirectory -SourceRoot $SourceRoot -Python $Python
    }
    finally {
        $env:PYTHONPATH = $previousPythonPath
    }
}

function Invoke-PublicationPreflight {
    param(
        [Parameter(Mandatory = $true)][string]$SourceRoot,
        [Parameter(Mandatory = $true)][string]$Python,
        [Parameter(Mandatory = $true)][string]$TargetPeriod,
        [Parameter(Mandatory = $true)][string]$TargetDate
    )

    $previousPythonPath = $env:PYTHONPATH
    $env:PYTHONPATH = Join-Path $SourceRoot "src"
    try {
        $stem = ((Invoke-Captured `
            -Label "calculate publication preflight stem" `
            -FilePath $Python `
            -ArgumentList @(
                "-S", $AutomationScript, "stem",
                "--period", $TargetPeriod,
                "--date", $TargetDate
            ) `
            -WorkingDirectory $RepoRoot) -join "").Trim()
        Invoke-Logged `
            -Label "preflight local publication bundle" `
            -FilePath $Python `
            -ArgumentList @(
                "-m", "github_hotspots.cli", "publish",
                "reports/$TargetPeriod/$stem.json"
            ) `
            -WorkingDirectory $SourceRoot | Out-Null
    }
    finally {
        $env:PYTHONPATH = $previousPythonPath
    }
}

function Build-And-SyncRemotePublication {
    param(
        [Parameter(Mandatory = $true)][string]$Python,
        [Parameter(Mandatory = $true)][string]$TargetPeriod,
        [Parameter(Mandatory = $true)][string]$TargetDate
    )

    if (-not $VerifiedRemoteCommit) {
        throw "Remote commit has not passed the trusted update gate."
    }
    $remotePath = Join-Path $WorktreeRoot ("{0}-publish-{1}" -f $RunId, ([guid]::NewGuid().ToString("N").Substring(0, 8)))
    Assert-StateChild $remotePath
    $added = $false
    try {
        Invoke-Logged `
            -Label "add remote publication worktree" `
            -FilePath "git" `
            -ArgumentList @(
                "-C", $RepoRoot, "worktree", "add", "--detach", $remotePath, $VerifiedRemoteCommit
            ) | Out-Null
        $added = $true
        if (-not (Test-Bundle -Root $remotePath -Python $Python -TargetPeriod $TargetPeriod -TargetDate $TargetDate)) {
            throw "Remote publication bundle failed strict validation."
        }
        Build-And-SyncPublication `
            -SourceRoot $remotePath `
            -Python $Python `
            -TargetPeriod $TargetPeriod `
            -TargetDate $TargetDate
    }
    finally {
        if ($added) {
            Invoke-Logged `
                -Label "remove remote publication worktree" `
                -FilePath "git" `
                -ArgumentList @("-C", $RepoRoot, "worktree", "remove", "--force", $remotePath) `
                -AllowFailure | Out-Null
        }
    }
}

function Get-ChangedPaths {
    param([Parameter(Mandatory = $true)][string]$Root)

    $tracked = @(Invoke-Captured `
        -Label "list tracked changes" `
        -FilePath "git" `
        -ArgumentList @("-c", "core.quotepath=false", "diff", "--name-only") `
        -WorkingDirectory $Root)
    $untracked = @(Invoke-Captured `
        -Label "list untracked changes" `
        -FilePath "git" `
        -ArgumentList @("-c", "core.quotepath=false", "ls-files", "--others", "--exclude-standard") `
        -WorkingDirectory $Root)
    return @($tracked + $untracked | ForEach-Object { "$_".Trim() } | Where-Object { $_ } | Sort-Object -Unique)
}

function Write-PathFile {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][AllowEmptyCollection()][string[]]$Values
    )

    Assert-StateChild $Path
    [System.IO.File]::WriteAllLines(
        $Path,
        $Values,
        [System.Text.UTF8Encoding]::new($false)
    )
}

function Assert-TrustedRemoteState {
    param([Parameter(Mandatory = $true)][string]$Python)

    if (-not $TrustedCommit) {
        throw "Trusted local commit has not been recorded."
    }
    $remoteCommit = ((Invoke-Captured `
        -Label "read origin main commit" `
        -FilePath "git" `
        -ArgumentList @("-C", $RepoRoot, "rev-parse", "origin/main")) -join "").Trim()
    if ($remoteCommit -notmatch "^[0-9a-f]{40}$") {
        throw "origin/main did not resolve to a full commit SHA."
    }

    $ancestorExit = Invoke-Logged `
        -Label "verify trusted commit ancestry" `
        -FilePath "git" `
        -ArgumentList @(
            "-C", $RepoRoot,
            "merge-base", "--is-ancestor", $TrustedCommit, $remoteCommit
        ) `
        -AllowFailure
    if ($ancestorExit -ne 0) {
        throw "origin/main is not descended from the trusted local HEAD; review and update the local checkout."
    }

    $remotePaths = @(Invoke-Captured `
        -Label "list remote changes since trusted commit" `
        -FilePath "git" `
        -ArgumentList @(
            "-C", $RepoRoot,
            "-c", "core.quotepath=false",
            "diff", "--name-only", "--no-renames", "$TrustedCommit..$remoteCommit"
        ) | ForEach-Object { "$_".Trim() } | Where-Object { $_ })
    $remotePathFile = Join-Path $StateRoot ("{0}.remote.paths" -f $RunId)
    Write-PathFile -Path $remotePathFile -Values $remotePaths
    Invoke-Logged `
        -Label "validate remote report-only updates" `
        -FilePath $Python `
        -ArgumentList @(
            "-S", $AutomationScript, "validate-remote-paths",
            "--paths-file", $remotePathFile
        ) `
        -WorkingDirectory $RepoRoot | Out-Null

    $script:VerifiedRemoteCommit = $remoteCommit
    Write-RunLog "trusted remote verified commit=$remoteCommit path_count=$($remotePaths.Count)"
}

function Update-VerifiedOriginMain {
    param(
        [Parameter(Mandatory = $true)][string]$Python,
        [Parameter(Mandatory = $true)][string]$Label,
        [switch]$RecordTrustedCommit
    )

    Invoke-Logged `
        -Label $Label `
        -FilePath "git" `
        -ArgumentList @("-C", $RepoRoot, "fetch", "origin", "main") | Out-Null
    if ($RecordTrustedCommit) {
        $localCommit = ((Invoke-Captured `
            -Label "record trusted local HEAD" `
            -FilePath "git" `
            -ArgumentList @("-C", $RepoRoot, "rev-parse", "HEAD")) -join "").Trim()
        if ($localCommit -notmatch "^[0-9a-f]{40}$") {
            throw "Local HEAD did not resolve to a full commit SHA."
        }
        $script:TrustedCommit = $localCommit
        Write-RunLog "trusted local commit=$localCommit"
    }
    Assert-TrustedRemoteState -Python $Python
}

function Remove-StaleAutomationState {
    $worktreeCutoff = [DateTime]::UtcNow.AddHours(-6)
    $pathCutoff = [DateTime]::UtcNow.AddDays(-1)
    $worktreeNamePattern = "^\d{8}T\d{6}-(?:daily|weekly)-[0-9a-f]{8}(?:-(?:publish|remote)-[0-9a-f]{8})?$"
    $pathNamePattern = "^\d{8}T\d{6}-(?:daily|weekly)-[0-9a-f]{8}(?:\.remote)?\.paths$"

    foreach ($item in Get-ChildItem -LiteralPath $WorktreeRoot -Directory -Force -ErrorAction SilentlyContinue) {
        if ($item.Name -notmatch $worktreeNamePattern -or $item.LastWriteTimeUtc -ge $worktreeCutoff) {
            continue
        }
        Assert-StateChild $item.FullName
        Write-RunLog "removing stale automation worktree path=$($item.FullName)"
        Invoke-Logged `
            -Label "remove stale automation worktree" `
            -FilePath "git" `
            -ArgumentList @("-C", $RepoRoot, "worktree", "remove", "--force", $item.FullName) `
            -AllowFailure | Out-Null
        if (Test-Path -LiteralPath $item.FullName) {
            Assert-StateChild $item.FullName
            if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
                Remove-Item -LiteralPath $item.FullName -Force -ErrorAction Stop
            }
            else {
                Remove-Item -LiteralPath $item.FullName -Recurse -Force -ErrorAction Stop
            }
        }
    }

    foreach ($item in Get-ChildItem -LiteralPath $StateRoot -File -Force -ErrorAction SilentlyContinue) {
        if ($item.Name -notmatch $pathNamePattern -or $item.LastWriteTimeUtc -ge $pathCutoff) {
            continue
        }
        Assert-StateChild $item.FullName
        Remove-Item -LiteralPath $item.FullName -Force -ErrorAction Stop
        Write-RunLog "removed stale path manifest path=$($item.FullName)"
    }

    Invoke-Logged `
        -Label "prune stale worktree metadata" `
        -FilePath "git" `
        -ArgumentList @("-C", $RepoRoot, "worktree", "prune") `
        -AllowFailure | Out-Null
}

function Test-RemoteBundle {
    param(
        [Parameter(Mandatory = $true)][string]$Python,
        [Parameter(Mandatory = $true)][string]$TargetPeriod,
        [Parameter(Mandatory = $true)][string]$TargetDate
    )

    if (-not $VerifiedRemoteCommit) {
        throw "Remote commit has not passed the trusted update gate."
    }
    $remotePath = Join-Path $WorktreeRoot ("{0}-remote-{1}" -f $RunId, ([guid]::NewGuid().ToString("N").Substring(0, 8)))
    Assert-StateChild $remotePath
    $added = $false
    try {
        Invoke-Logged `
            -Label "add remote verification worktree" `
            -FilePath "git" `
            -ArgumentList @(
                "-C", $RepoRoot, "worktree", "add", "--detach", $remotePath, $VerifiedRemoteCommit
            ) | Out-Null
        $added = $true
        return Test-Bundle `
            -Root $remotePath `
            -Python $Python `
            -TargetPeriod $TargetPeriod `
            -TargetDate $TargetDate
    }
    finally {
        if ($added) {
            Invoke-Logged `
                -Label "remove remote verification worktree" `
                -FilePath "git" `
                -ArgumentList @("-C", $RepoRoot, "worktree", "remove", "--force", $remotePath) `
                -AllowFailure | Out-Null
        }
    }
}

function Wait-PagesDeployment {
    param(
        [Parameter(Mandatory = $true)][string]$Commit,
        [Parameter(Mandatory = $true)][string]$WorkingDirectory
    )

    if ($SkipPagesWait) {
        Write-RunLog "Pages verification skipped by option"
        return
    }
    if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
        throw "GitHub CLI is required to verify Pages deployment."
    }

    for ($attempt = 1; $attempt -le 40; $attempt++) {
        $raw = @(Invoke-Captured `
            -Label "query Pages run attempt $attempt" `
            -FilePath "gh" `
            -ArgumentList @(
                "run", "list",
                "--workflow", "pages.yml",
                "--commit", $Commit,
                "--limit", "1",
                "--json", "status,conclusion,url"
            ) `
            -WorkingDirectory $WorkingDirectory)
        $json = ($raw -join "`n").Trim()
        if ($json) {
            $runs = @($json | ConvertFrom-Json)
            if ($runs.Count -gt 0) {
                $run = $runs[0]
                if ($run.status -eq "completed" -and $run.conclusion -eq "success") {
                    Write-RunLog "Pages deployment succeeded url=$($run.url)"
                    return
                }
                if ($run.status -eq "completed" -and $run.conclusion -ne "success") {
                    throw "Pages deployment completed with $($run.conclusion)."
                }
            }
        }
        Start-Sleep -Seconds 15
    }
    throw "Timed out waiting for the Pages deployment."
}

try {
    try {
        $LockStream = [System.IO.File]::Open(
            $LockPath,
            [System.IO.FileMode]::OpenOrCreate,
            [System.IO.FileAccess]::ReadWrite,
            [System.IO.FileShare]::None
        )
    }
    catch [System.IO.IOException] {
        Write-RunLog "another scheduled run owns the shared lock"
        exit 75
    }

    $chinaTimeZone = [System.TimeZoneInfo]::FindSystemTimeZoneById("China Standard Time")
    $chinaNow = [System.TimeZoneInfo]::ConvertTime([DateTimeOffset]::UtcNow, $chinaTimeZone)
    if (-not $RunDate) {
        if ($Period -eq "weekly" -and $chinaNow.DayOfWeek -ne [System.DayOfWeek]::Sunday) {
            Write-RunLog "weekly task started outside Sunday; refusing inaccurate backfill"
            return
        }
        $RunDate = $chinaNow.ToString("yyyy-MM-dd")
    }
    [void][DateTime]::ParseExact(
        $RunDate,
        "yyyy-MM-dd",
        [System.Globalization.CultureInfo]::InvariantCulture
    )

    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        throw "Git is not available for the current user."
    }

    Write-RunLog "scheduled run start period=$Period date=$RunDate"
    Remove-StaleAutomationState
    $Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
    foreach ($requiredPath in ($Python, $AutomationScript)) {
        if (-not (Test-Path -LiteralPath $requiredPath -PathType Leaf)) {
            throw "Required automation file is missing: $requiredPath"
        }
    }
    if (-not (Get-Command codex -ErrorAction SilentlyContinue)) {
        throw "The installed Codex CLI is not available for the current user."
    }
    Invoke-Logged `
        -Label "Codex CLI preflight" `
        -FilePath "codex" `
        -ArgumentList @("--version") | Out-Null
    Update-VerifiedOriginMain `
        -Python $Python `
        -Label "fetch and validate origin main" `
        -RecordTrustedCommit

    Assert-StateChild $WorktreePath
    Invoke-Logged `
        -Label "add isolated worktree" `
        -FilePath "git" `
        -ArgumentList @(
            "-C", $RepoRoot, "worktree", "add", "--detach", $WorktreePath, $VerifiedRemoteCommit
        ) | Out-Null
    $WorktreeAdded = $true

    $env:PYTHONPATH = Join-Path $WorktreePath "src"
    Remove-Item Env:CI -ErrorAction SilentlyContinue
    Remove-Item Env:GITHUB_ACTIONS -ErrorAction SilentlyContinue

    if (Test-Bundle -Root $WorktreePath -Python $Python -TargetPeriod $Period -TargetDate $RunDate) {
        $currentCommit = (Invoke-Captured `
            -Label "read current commit" `
            -FilePath "git" `
            -ArgumentList @("rev-parse", "HEAD") `
            -WorkingDirectory $WorktreePath) -join ""
        Write-RunLog "valid Codex bundle already exists; no generation needed"
        Build-And-SyncPublication `
            -SourceRoot $WorktreePath `
            -Python $Python `
            -TargetPeriod $Period `
            -TargetDate $RunDate
        Wait-PagesDeployment -Commit $currentCommit.Trim() -WorkingDirectory $WorktreePath
        return
    }

    Invoke-Logged `
        -Label "pytest" `
        -FilePath $Python `
        -ArgumentList @("-m", "pytest") `
        -WorkingDirectory $WorktreePath | Out-Null
    Invoke-Logged `
        -Label "ruff check" `
        -FilePath $Python `
        -ArgumentList @("-m", "ruff", "check", ".") `
        -WorkingDirectory $WorktreePath | Out-Null
    Invoke-Logged `
        -Label "ruff format check" `
        -FilePath $Python `
        -ArgumentList @("-m", "ruff", "format", "--check", ".") `
        -WorkingDirectory $WorktreePath | Out-Null

    Invoke-Logged `
        -Label "generate $Period report with local Codex" `
        -FilePath $Python `
        -ArgumentList @(
            "-m", "github_hotspots.cli", "run",
            "--period", $Period,
            "--date", $RunDate,
            "--editorial-backend", "codex-cli"
        ) `
        -WorkingDirectory $WorktreePath | Out-Null

    if (-not (Test-Bundle -Root $WorktreePath -Python $Python -TargetPeriod $Period -TargetDate $RunDate)) {
        throw "Strict post-run bundle verification failed."
    }
    Invoke-PublicationPreflight `
        -SourceRoot $WorktreePath `
        -Python $Python `
        -TargetPeriod $Period `
        -TargetDate $RunDate

    $changedPaths = @(Get-ChangedPaths -Root $WorktreePath)
    if ($changedPaths.Count -eq 0) {
        Write-RunLog "generation produced no changes"
        Build-And-SyncPublication `
            -SourceRoot $WorktreePath `
            -Python $Python `
            -TargetPeriod $Period `
            -TargetDate $RunDate
        return
    }
    $pathFile = Join-Path $StateRoot ("{0}.paths" -f $RunId)
    Write-PathFile -Path $pathFile -Values $changedPaths
    Invoke-Logged `
        -Label "validate generated path allowlist" `
        -FilePath $Python `
        -ArgumentList @(
            "-S", $AutomationScript, "validate-paths",
            "--period", $Period,
            "--date", $RunDate,
            "--paths-file", $pathFile
        ) `
        -WorkingDirectory $RepoRoot | Out-Null

    $stem = ((Invoke-Captured `
        -Label "calculate report stem" `
        -FilePath $Python `
        -ArgumentList @(
            "-S", $AutomationScript, "stem",
            "--period", $Period,
            "--date", $RunDate
        ) `
        -WorkingDirectory $RepoRoot) -join "").Trim()
    $stageCandidates = @(
        "data/snapshots/$RunDate.json",
        "reports/$Period/$stem.md",
        "reports/$Period/$stem.json",
        "reports/$Period/$stem.xiaohongshu.md",
        "reports/$Period/$stem.ai.xiaohongshu.md",
        "reports/$Period/assets/$stem",
        "reports/$Period/avatars/$stem"
    )
    foreach ($relativePath in $stageCandidates) {
        if (Test-Path -LiteralPath (Join-Path $WorktreePath $relativePath)) {
            Invoke-Logged `
                -Label "stage $relativePath" `
                -FilePath "git" `
                -ArgumentList @("add", "--", $relativePath) `
                -WorkingDirectory $WorktreePath | Out-Null
        }
    }

    $remainingPaths = @(Get-ChangedPaths -Root $WorktreePath)
    if ($remainingPaths.Count -gt 0) {
        throw "Generated files remain unstaged after allowlisted staging."
    }
    $stagedPaths = @(Invoke-Captured `
        -Label "list staged paths" `
        -FilePath "git" `
        -ArgumentList @("-c", "core.quotepath=false", "diff", "--cached", "--name-only") `
        -WorkingDirectory $WorktreePath | ForEach-Object { "$_".Trim() } | Where-Object { $_ })
    Write-PathFile -Path $pathFile -Values $stagedPaths
    Invoke-Logged `
        -Label "validate staged path allowlist" `
        -FilePath $Python `
        -ArgumentList @(
            "-S", $AutomationScript, "validate-paths",
            "--period", $Period,
            "--date", $RunDate,
            "--paths-file", $pathFile
        ) `
        -WorkingDirectory $RepoRoot | Out-Null
    Invoke-Logged `
        -Label "scan staged artifacts" `
        -FilePath $Python `
        -ArgumentList @(
            "-S", $AutomationScript, "scan-paths",
            "--root", $WorktreePath,
            "--paths-file", $pathFile
        ) `
        -WorkingDirectory $RepoRoot | Out-Null
    Invoke-Logged `
        -Label "git diff check" `
        -FilePath "git" `
        -ArgumentList @("diff", "--cached", "--check") `
        -WorkingDirectory $WorktreePath | Out-Null

    $hasNoChanges = Invoke-Logged `
        -Label "check staged changes" `
        -FilePath "git" `
        -ArgumentList @("diff", "--cached", "--quiet") `
        -WorkingDirectory $WorktreePath `
        -AllowFailure
    if ($hasNoChanges -eq 0) {
        Write-RunLog "no staged artifact changes to commit"
        Build-And-SyncPublication `
            -SourceRoot $WorktreePath `
            -Python $Python `
            -TargetPeriod $Period `
            -TargetDate $RunDate
        return
    }

    Invoke-Logged `
        -Label "commit generated artifacts" `
        -FilePath "git" `
        -ArgumentList @("commit", "-m", "chore(hotspots): update $Period report for $RunDate") `
        -WorkingDirectory $WorktreePath | Out-Null

    Update-VerifiedOriginMain `
        -Python $Python `
        -Label "refresh and validate origin main before push"
    $remoteIsAncestor = Invoke-Logged `
        -Label "check remote ancestry" `
        -FilePath "git" `
        -ArgumentList @("merge-base", "--is-ancestor", $VerifiedRemoteCommit, "HEAD") `
        -WorkingDirectory $WorktreePath `
        -AllowFailure
    if ($remoteIsAncestor -ne 0) {
        if (Test-RemoteBundle -Python $Python -TargetPeriod $Period -TargetDate $RunDate) {
            $remoteCommit = $VerifiedRemoteCommit
            Write-RunLog "remote already contains a valid Codex bundle; local commit is superseded"
            Build-And-SyncRemotePublication `
                -Python $Python `
                -TargetPeriod $Period `
                -TargetDate $RunDate
            Wait-PagesDeployment -Commit $remoteCommit -WorkingDirectory $WorktreePath
            return
        }
        $rebaseExit = Invoke-Logged `
            -Label "rebase generated commit onto origin main" `
            -FilePath "git" `
            -ArgumentList @("rebase", $VerifiedRemoteCommit) `
            -WorkingDirectory $WorktreePath `
            -AllowFailure
        if ($rebaseExit -ne 0) {
            Invoke-Logged `
                -Label "abort conflicting rebase" `
                -FilePath "git" `
                -ArgumentList @("rebase", "--abort") `
                -WorkingDirectory $WorktreePath `
                -AllowFailure | Out-Null
            throw "Remote changed overlapping generated files; retry from a fresh worktree."
        }
        if (-not (Test-Bundle -Root $WorktreePath -Python $Python -TargetPeriod $Period -TargetDate $RunDate)) {
            throw "Strict bundle verification failed after the report-only rebase."
        }
        Invoke-PublicationPreflight `
            -SourceRoot $WorktreePath `
            -Python $Python `
            -TargetPeriod $Period `
            -TargetDate $RunDate
    }

    $pushExit = Invoke-Logged `
        -Label "push generated commit" `
        -FilePath "git" `
        -ArgumentList @("push", "origin", "HEAD:main") `
        -WorkingDirectory $WorktreePath `
        -AllowFailure
    if ($pushExit -ne 0) {
        Update-VerifiedOriginMain `
            -Python $Python `
            -Label "fetch and validate after rejected push"
        if (Test-RemoteBundle -Python $Python -TargetPeriod $Period -TargetDate $RunDate) {
            $remoteCommit = $VerifiedRemoteCommit
            Write-RunLog "remote won the push race with a valid Codex bundle"
            Build-And-SyncRemotePublication `
                -Python $Python `
                -TargetPeriod $Period `
                -TargetDate $RunDate
            Wait-PagesDeployment -Commit $remoteCommit -WorkingDirectory $WorktreePath
            return
        }
        throw "Push was rejected and no valid remote Codex bundle exists."
    }

    $commit = ((Invoke-Captured `
        -Label "read pushed commit" `
        -FilePath "git" `
        -ArgumentList @("rev-parse", "HEAD") `
        -WorkingDirectory $WorktreePath) -join "").Trim()
    Write-RunLog "scheduled run pushed commit=$commit"
    Build-And-SyncPublication `
        -SourceRoot $WorktreePath `
        -Python $Python `
        -TargetPeriod $Period `
        -TargetDate $RunDate
    Wait-PagesDeployment -Commit $commit -WorkingDirectory $WorktreePath
    Write-RunLog "scheduled run complete period=$Period date=$RunDate"
}
catch {
    Write-RunLog "scheduled run failed category=runtime_error message=$($_.Exception.Message)"
    throw
}
finally {
    if ($WorktreeAdded) {
        Assert-StateChild $WorktreePath
        Invoke-Logged `
            -Label "remove isolated worktree" `
            -FilePath "git" `
            -ArgumentList @("-C", $RepoRoot, "worktree", "remove", "--force", $WorktreePath) `
            -AllowFailure | Out-Null
        Invoke-Logged `
            -Label "prune worktree metadata" `
            -FilePath "git" `
            -ArgumentList @("-C", $RepoRoot, "worktree", "prune") `
            -AllowFailure | Out-Null
    }
    if ($LockStream) {
        $LockStream.Dispose()
    }
    Get-ChildItem -LiteralPath $LogRoot -File -Filter "*.log" -ErrorAction SilentlyContinue |
        Where-Object { $_.LastWriteTimeUtc -lt [DateTime]::UtcNow.AddDays(-30) } |
        Remove-Item -Force -ErrorAction SilentlyContinue
}

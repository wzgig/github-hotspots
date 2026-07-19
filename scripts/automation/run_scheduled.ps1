[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("daily", "weekly")]
    [string]$Period,

    [ValidatePattern("^\d{4}-\d{2}-\d{2}$")]
    [string]$RunDate,

    [string]$StateRoot = (Join-Path $env:LOCALAPPDATA "GitHubHotspots"),

    [switch]$SkipPagesWait,

    [switch]$LoadFunctionsOnly
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

function Test-PublicationHistory {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string]$Python,
        [Parameter(Mandatory = $true)][string]$TargetPeriod,
        [Parameter(Mandatory = $true)][string]$TargetDate
    )

    $exitCode = Invoke-Logged `
        -Label "verify publication history with trusted validator" `
        -FilePath $Python `
        -ArgumentList @(
            "-S", $AutomationScript, "verify-history",
            "--root", $Root,
            "--period", $TargetPeriod,
            "--date", $TargetDate,
            "--quiet"
        ) `
        -WorkingDirectory $RepoRoot `
        -AllowFailure
    return $exitCode -eq 0
}

function Test-CompleteBundle {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string]$Python,
        [Parameter(Mandatory = $true)][string]$TargetPeriod,
        [Parameter(Mandatory = $true)][string]$TargetDate
    )

    if (-not (Test-Bundle `
        -Root $Root `
        -Python $Python `
        -TargetPeriod $TargetPeriod `
        -TargetDate $TargetDate)) {
        return $false
    }
    return Test-PublicationHistory `
        -Root $Root `
        -Python $Python `
        -TargetPeriod $TargetPeriod `
        -TargetDate $TargetDate
}

function Assert-PublishChild {
    param([Parameter(Mandatory = $true)][string]$Path)

    Assert-ChildPath `
        -Path $Path `
        -Root (Join-Path $RepoRoot "publish") `
        -Label "repository publish directory"
}

function Assert-ChildPath {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string]$Label
    )

    $publishRoot = [System.IO.Path]::GetFullPath($Root)
    $fullPath = [System.IO.Path]::GetFullPath($Path)
    $rootWithSeparator = $publishRoot.TrimEnd('\') + '\'
    if (
        $fullPath -ne $publishRoot -and
        -not $fullPath.StartsWith($rootWithSeparator, [System.StringComparison]::OrdinalIgnoreCase)
    ) {
        throw "Refusing to operate outside the $Label."
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

    try {
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
    catch {
        return $false
    }
}

function Get-SafeManifestChildPath {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string]$RelativePath
    )

    if (-not $RelativePath.Trim()) {
        throw "Publication manifest contains an empty relative path."
    }
    $rootPath = [System.IO.Path]::GetFullPath($Root)
    $candidate = [System.IO.Path]::GetFullPath((Join-Path $rootPath $RelativePath))
    Assert-ChildPath -Path $candidate -Root $rootPath -Label "publication bundle"
    if ($candidate -eq $rootPath) {
        throw "Publication manifest path must identify a file below the bundle root."
    }
    return $candidate
}

function Test-PublishFileHash {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$ExpectedSha256
    )

    if (
        $ExpectedSha256 -notmatch "^[0-9a-fA-F]{64}$" -or
        -not (Test-Path -LiteralPath $Path -PathType Leaf)
    ) {
        return $false
    }
    $actual = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
    return $actual -eq $ExpectedSha256.ToLowerInvariant()
}

function Test-PublishManifestFiles {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)]$Manifest,
        [switch]$RequireCopies
    )

    try {
        if (-not (Test-Path -LiteralPath $Root -PathType Container)) {
            return $false
        }
        $checklist = Join-Path $Root "CHECKLIST.md"
        if (
            -not (Test-PublishFileHash `
                -Path $checklist `
                -ExpectedSha256 "$($Manifest.checklist_sha256)")
        ) {
            return $false
        }
        $boards = @($Manifest.boards)
        if ($boards.Count -lt 1) {
            return $false
        }
        foreach ($board in $boards) {
            $boardDirectory = Get-SafeManifestChildPath `
                -Root $Root `
                -RelativePath "$($board.directory)"
            if (-not (Test-Path -LiteralPath $boardDirectory -PathType Container)) {
                return $false
            }
            $textFiles = @(
                [pscustomobject]@{ Path = "$($board.title)"; Sha256 = "$($board.title_sha256)" }
                [pscustomobject]@{ Path = "$($board.caption)"; Sha256 = "$($board.caption_sha256)" }
                [pscustomobject]@{ Path = "$($board.review)"; Sha256 = "$($board.review_sha256)" }
            )
            foreach ($item in $textFiles) {
                $path = Get-SafeManifestChildPath -Root $Root -RelativePath $item.Path
                if (-not (Test-PublishFileHash -Path $path -ExpectedSha256 $item.Sha256)) {
                    return $false
                }
            }
            $images = @($board.images)
            if ($images.Count -lt 1) {
                return $false
            }
            foreach ($image in $images) {
                if ($RequireCopies -and $image.materialization -ne "copy") {
                    return $false
                }
                $path = Get-SafeManifestChildPath `
                    -Root $boardDirectory `
                    -RelativePath "$($image.path)"
                if (-not (Test-PublishFileHash -Path $path -ExpectedSha256 "$($image.sha256)")) {
                    return $false
                }
            }
        }
        return $true
    }
    catch {
        return $false
    }
}

function Set-PublishManifestMaterializationToCopy {
    param(
        [Parameter(Mandatory = $true)][string]$ManifestPath,
        [string]$AllowedRoot = (Join-Path $RepoRoot "publish")
    )

    Assert-ChildPath -Path $ManifestPath -Root $AllowedRoot -Label "publication bundle"
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

function Get-AvailablePublishArchivePath {
    param([Parameter(Mandatory = $true)][string]$BasePath)

    if (-not (Test-Path -LiteralPath $BasePath)) {
        return $BasePath
    }
    for ($revision = 2; $revision -lt 10000; $revision++) {
        $candidate = "{0}-r{1:d2}" -f $BasePath, $revision
        if (-not (Test-Path -LiteralPath $candidate)) {
            return $candidate
        }
    }
    throw "Unable to allocate a publication archive revision path."
}

function Get-PublishArchivePath {
    param(
        [Parameter(Mandatory = $true)][string]$PublishRoot,
        [Parameter(Mandatory = $true)][string]$TargetPeriod,
        $Manifest
    )

    $archiveRoot = Join-Path $PublishRoot "archive\$TargetPeriod"
    try {
        if ($null -eq $Manifest -or "$($Manifest.period)" -ne $TargetPeriod) {
            throw "invalid manifest period"
        }
        $archiveDate = [DateTime]::ParseExact(
            "$($Manifest.run_date)",
            "yyyy-MM-dd",
            [System.Globalization.CultureInfo]::InvariantCulture
        )
        $stem = "$($Manifest.issue.stem)"
        if ($stem -notmatch "^[A-Za-z0-9][A-Za-z0-9._-]*$") {
            throw "invalid manifest issue stem"
        }
        $archiveYear = if ($TargetPeriod -eq "weekly") {
            Get-IsoWeekYear -Date $archiveDate
        }
        else {
            $archiveDate.Year
        }
        $basePath = Join-Path $archiveRoot "$archiveYear\$stem"
    }
    catch {
        $recoveryStamp = Get-Date -Format "yyyyMMddTHHmmss"
        $recoveryId = [guid]::NewGuid().ToString("N").Substring(0, 8)
        $recoveryName = "$TargetPeriod-recovery-$recoveryStamp-$recoveryId"
        $basePath = Join-Path $archiveRoot "recovery\$recoveryName"
    }
    Assert-ChildPath -Path $basePath -Root $PublishRoot -Label "publication archive"
    return Get-AvailablePublishArchivePath -BasePath $basePath
}

function Switch-PublishStaging {
    param(
        [Parameter(Mandatory = $true)][string]$Staging,
        [Parameter(Mandatory = $true)][string]$Target,
        [Parameter(Mandatory = $true)][string]$PublishRoot,
        [Parameter(Mandatory = $true)][ValidateSet("daily", "weekly")][string]$TargetPeriod,
        $TargetManifest,
        [scriptblock]$Activation = {
            param($SourcePath, $DestinationPath)
            Move-Item -LiteralPath $SourcePath -Destination $DestinationPath -ErrorAction Stop
        }
    )

    $archive = $null
    if (Test-Path -LiteralPath $Target) {
        $archive = Get-PublishArchivePath `
            -PublishRoot $PublishRoot `
            -TargetPeriod $TargetPeriod `
            -Manifest $TargetManifest
        New-Item -ItemType Directory -Force -Path (Split-Path $archive -Parent) | Out-Null
        Move-Item -LiteralPath $Target -Destination $archive -ErrorAction Stop
    }
    try {
        & $Activation $Staging $Target
    }
    catch {
        if (
            $archive -and
            (Test-Path -LiteralPath $archive) -and
            -not (Test-Path -LiteralPath $Target)
        ) {
            try {
                Move-Item -LiteralPath $archive -Destination $Target -ErrorAction Stop
                Write-RunLog "publication activation failed; restored previous local publish folder"
                $archive = $null
            }
            catch {
                throw "Publication activation and rollback both failed. Preserved prior bundle: $archive"
            }
        }
        throw
    }
    if ($archive) {
        Write-RunLog "archived previous local publish folder path=$archive"
    }
    return $archive
}

function Install-PublishDirectory {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$PublishRoot,
        [Parameter(Mandatory = $true)][ValidateSet("daily", "weekly")][string]$TargetPeriod
    )

    $publishRootPath = [System.IO.Path]::GetFullPath($PublishRoot)
    $target = Join-Path $publishRootPath "current\$TargetPeriod"
    Assert-ChildPath -Path $target -Root $publishRootPath -Label "publication directory"
    if (-not (Test-Path -LiteralPath $Source -PathType Container)) {
        throw "Generated publication folder is missing: $Source"
    }
    $sourceManifestPath = Join-Path $Source "MANIFEST.json"
    if (-not (Test-Path -LiteralPath $sourceManifestPath -PathType Leaf)) {
        throw "Generated publication folder has no MANIFEST.json: $Source"
    }
    $sourceManifest = Get-Content -LiteralPath $sourceManifestPath -Raw -Encoding utf8 | ConvertFrom-Json
    $sourceFingerprint = "$($sourceManifest.content_fingerprint)"
    $sourceDate = [DateTime]::ParseExact(
        "$($sourceManifest.run_date)",
        "yyyy-MM-dd",
        [System.Globalization.CultureInfo]::InvariantCulture
    )
    if (
        $sourceFingerprint -notmatch "^[0-9a-f]{64}$" -or
        "$($sourceManifest.period)" -ne $TargetPeriod -or
        -not (Test-PublishManifestFiles -Root $Source -Manifest $sourceManifest)
    ) {
        throw "Generated publication folder failed manifest and file integrity validation: $Source"
    }

    $targetManifest = $null
    if (Test-Path -LiteralPath $target -PathType Container) {
        $targetManifestPath = Join-Path $target "MANIFEST.json"
        if (Test-Path -LiteralPath $targetManifestPath -PathType Leaf) {
            try {
                $targetManifest = Get-Content `
                    -LiteralPath $targetManifestPath `
                    -Raw `
                    -Encoding utf8 | ConvertFrom-Json
            }
            catch {
                Write-RunLog "existing local publication manifest is unreadable; preserving it in recovery archive"
            }
        }
        $targetFingerprint = ""
        if ($null -ne $targetManifest) {
            try {
                $targetFingerprint = "$($targetManifest.content_fingerprint)"
                $targetDate = [DateTime]::ParseExact(
                    "$($targetManifest.run_date)",
                    "yyyy-MM-dd",
                    [System.Globalization.CultureInfo]::InvariantCulture
                )
                if ("$($targetManifest.period)" -eq $TargetPeriod -and $targetDate -gt $sourceDate) {
                    throw (
                        "Refusing to replace newer $TargetPeriod publication " +
                        "$($targetDate.ToString('yyyy-MM-dd')) with older $($sourceDate.ToString('yyyy-MM-dd'))."
                    )
                }
            }
            catch {
                if ($_.Exception.Message -like "Refusing to replace newer*") {
                    throw
                }
                $targetFingerprint = ""
                $targetManifest = $null
                Write-RunLog "existing local publication manifest is incomplete; preserving it in recovery archive"
            }
        }
        if (
            $targetFingerprint -eq $sourceFingerprint -and
            (Test-PublishManifestUsesCopies -Manifest $targetManifest) -and
            (Test-PublishManifestFiles -Root $target -Manifest $targetManifest -RequireCopies)
        ) {
            Write-RunLog "local publish folder already matches source report"
            return [pscustomobject]@{
                Changed = $false
                Target = $target
                Archived = $null
            }
        }
    }

    $currentRoot = Split-Path $target -Parent
    New-Item -ItemType Directory -Force -Path $currentRoot | Out-Null
    $staging = Join-Path $currentRoot (".{0}-staging-{1}" -f $TargetPeriod, ([guid]::NewGuid().ToString("N")))
    Assert-ChildPath -Path $staging -Root $publishRootPath -Label "publication staging directory"
    $archive = $null
    try {
        Copy-Item -LiteralPath $Source -Destination $staging -Recurse -ErrorAction Stop
        $stagingManifestPath = Join-Path $staging "MANIFEST.json"
        Set-PublishManifestMaterializationToCopy `
            -ManifestPath $stagingManifestPath `
            -AllowedRoot $publishRootPath
        $stagingManifest = Get-Content `
            -LiteralPath $stagingManifestPath `
            -Raw `
            -Encoding utf8 | ConvertFrom-Json
        if (-not (Test-PublishManifestFiles -Root $staging -Manifest $stagingManifest -RequireCopies)) {
            throw "Staged publication folder failed manifest and file integrity validation."
        }

        $archive = Switch-PublishStaging `
            -Staging $staging `
            -Target $target `
            -PublishRoot $publishRootPath `
            -TargetPeriod $TargetPeriod `
            -TargetManifest $targetManifest
    }
    finally {
        if (Test-Path -LiteralPath $staging) {
            Assert-ChildPath -Path $staging -Root $publishRootPath -Label "publication staging directory"
            Remove-Item -LiteralPath $staging -Recurse -Force -ErrorAction SilentlyContinue
        }
    }

    return [pscustomobject]@{
        Changed = $true
        Target = $target
        Archived = $archive
    }
}

function Sync-PublishDirectory {
    param(
        [Parameter(Mandatory = $true)][string]$SourceRoot,
        [Parameter(Mandatory = $true)][string]$Python
    )

    $source = Join-Path $SourceRoot "publish\current\$Period"
    $publishRoot = Join-Path $RepoRoot "publish"
    $result = Install-PublishDirectory `
        -Source $source `
        -PublishRoot $publishRoot `
        -TargetPeriod $Period
    Update-PublishTodayIndex -SourceRoot $SourceRoot -Python $Python
    if ($result.Changed) {
        Write-RunLog "synchronised local publish folder path=$($result.Target)"
    }
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
        if (-not (Test-CompleteBundle -Root $remotePath -Python $Python -TargetPeriod $TargetPeriod -TargetDate $TargetDate)) {
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
        -ArgumentList @(
            "-c", "core.quotepath=false",
            "-c", "core.safecrlf=false",
            "diff", "--name-only"
        ) `
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
    param(
        [Parameter(Mandatory = $true)][string]$Python,
        [Parameter(Mandatory = $true)][string]$RemoteCommit
    )

    if (-not $TrustedCommit) {
        throw "Trusted local commit has not been recorded."
    }
    if ($RemoteCommit -notmatch "^[0-9a-f]{40}$") {
        throw "origin/main did not resolve to a full commit SHA."
    }

    $ancestorExit = Invoke-Logged `
        -Label "verify trusted commit ancestry" `
        -FilePath "git" `
        -ArgumentList @(
            "-C", $RepoRoot,
            "merge-base", "--is-ancestor", $TrustedCommit, $RemoteCommit
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
            "diff", "--name-only", "--no-renames", "$TrustedCommit..$RemoteCommit"
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

    $script:VerifiedRemoteCommit = $RemoteCommit
    Write-RunLog "trusted remote verified commit=$RemoteCommit path_count=$($remotePaths.Count)"
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
        -ArgumentList @(
            "-C", $RepoRoot,
            "fetch", "--no-tags", "origin",
            "+refs/heads/main:refs/remotes/origin/main"
        ) | Out-Null
    $remoteCommit = ((Invoke-Captured `
        -Label "read fetched origin main commit" `
        -FilePath "git" `
        -ArgumentList @(
            "-C", $RepoRoot,
            "rev-parse", "refs/remotes/origin/main^{commit}"
        )) -join "").Trim()
    if ($remoteCommit -notmatch "^[0-9a-f]{40}$") {
        throw "Fetched origin/main did not resolve to a full commit SHA."
    }
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
    Assert-TrustedRemoteState -Python $Python -RemoteCommit $remoteCommit
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
        return Test-CompleteBundle `
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

function ConvertFrom-PagesRunListJson {
    param([Parameter(Mandatory = $true)][AllowEmptyString()][string]$Json)

    if (-not $Json.Trim()) {
        return [pscustomobject]@{
            State = "malformed"
            Status = $null
            Conclusion = $null
            Url = $null
            Message = "GitHub CLI returned empty stdout."
        }
    }
    try {
        # Windows PowerShell 5.1 wraps ConvertFrom-Json's empty array output when the conversion
        # is nested directly inside @(...). Assign first, then enumerate, so [] remains Count=0.
        $parsed = $Json | ConvertFrom-Json
        $runs = @($parsed)
    }
    catch {
        return [pscustomobject]@{
            State = "malformed"
            Status = $null
            Conclusion = $null
            Url = $null
            Message = "GitHub CLI returned invalid JSON: $($_.Exception.Message)"
        }
    }
    if ($runs.Count -eq 0) {
        return [pscustomobject]@{
            State = "not_found"
            Status = $null
            Conclusion = $null
            Url = $null
            Message = "No matching Pages workflow run exists yet."
        }
    }

    $run = $runs[0]
    if ($null -eq $run) {
        return [pscustomobject]@{
            State = "malformed"
            Status = $null
            Conclusion = $null
            Url = $null
            Message = "GitHub CLI returned a null workflow run."
        }
    }
    $statusProperty = $run.PSObject.Properties["status"]
    $conclusionProperty = $run.PSObject.Properties["conclusion"]
    $urlProperty = $run.PSObject.Properties["url"]
    if ($null -eq $statusProperty -or $null -eq $conclusionProperty -or $null -eq $urlProperty) {
        return [pscustomobject]@{
            State = "malformed"
            Status = $null
            Conclusion = $null
            Url = $null
            Message = "GitHub CLI workflow run is missing status, conclusion, or url."
        }
    }

    $status = "$($statusProperty.Value)"
    $conclusion = "$($conclusionProperty.Value)"
    $url = "$($urlProperty.Value)"
    if (-not $status.Trim()) {
        return [pscustomobject]@{
            State = "malformed"
            Status = $status
            Conclusion = $conclusion
            Url = $url
            Message = "GitHub CLI workflow run has an empty status."
        }
    }
    if ($status -eq "completed") {
        if ($conclusion -eq "success") {
            return [pscustomobject]@{
                State = "success"
                Status = $status
                Conclusion = $conclusion
                Url = $url
                Message = "Pages deployment completed successfully."
            }
        }
        if (-not $conclusion.Trim()) {
            return [pscustomobject]@{
                State = "malformed"
                Status = $status
                Conclusion = $conclusion
                Url = $url
                Message = "Completed Pages workflow run has no conclusion."
            }
        }
        return [pscustomobject]@{
            State = "failure"
            Status = $status
            Conclusion = $conclusion
            Url = $url
            Message = "Pages deployment completed with $conclusion."
        }
    }
    return [pscustomobject]@{
        State = "pending"
        Status = $status
        Conclusion = $conclusion
        Url = $url
        Message = "Pages deployment is $status."
    }
}

function Invoke-PagesRunQuery {
    param(
        [Parameter(Mandatory = $true)][string]$Commit,
        [Parameter(Mandatory = $true)][string]$WorkingDirectory,
        [string]$GitHubCli = "gh"
    )

    $captureId = [guid]::NewGuid().ToString("N")
    $stdoutPath = Join-Path $StateRoot ("{0}.pages-{1}.stdout" -f $RunId, $captureId)
    $stderrPath = Join-Path $StateRoot ("{0}.pages-{1}.stderr" -f $RunId, $captureId)
    Assert-StateChild $stdoutPath
    Assert-StateChild $stderrPath
    $exitCode = 1
    $stdout = ""
    $stderr = ""
    $nativeErrorActionPreference = $ErrorActionPreference
    $pushed = $false
    try {
        Push-Location $WorkingDirectory
        $pushed = $true
        $ErrorActionPreference = "Continue"
        $global:LASTEXITCODE = 1
        & $GitHubCli @(
            "run", "list",
            "--workflow", "pages.yml",
            "--commit", $Commit,
            "--limit", "1",
            "--json", "status,conclusion,url"
        ) 1> $stdoutPath 2> $stderrPath
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $nativeErrorActionPreference
        if ($pushed) {
            Pop-Location
        }
        if (Test-Path -LiteralPath $stdoutPath -PathType Leaf) {
            $stdout = "$(Get-Content -LiteralPath $stdoutPath -Raw)"
        }
        if (Test-Path -LiteralPath $stderrPath -PathType Leaf) {
            $stderr = "$(Get-Content -LiteralPath $stderrPath -Raw)"
        }
        Remove-Item -LiteralPath $stdoutPath, $stderrPath -Force -ErrorAction SilentlyContinue
    }
    foreach ($line in @($stderr -split "`r?`n" | Where-Object { $_ })) {
        Write-RunLog "Pages query stderr: $line"
    }
    return [pscustomobject]@{
        ExitCode = $exitCode
        Stdout = $stdout.Trim()
    }
}

function Wait-PagesDeployment {
    param(
        [Parameter(Mandatory = $true)][string]$Commit,
        [Parameter(Mandatory = $true)][string]$WorkingDirectory,
        [ValidateRange(1, 1000)][int]$MaxAttempts = 40,
        [ValidateRange(0, 3600)][int]$PollSeconds = 15,
        [string]$GitHubCli = "gh"
    )

    if ($SkipPagesWait) {
        Write-RunLog "Pages verification skipped by option"
        return
    }
    if (-not (Get-Command $GitHubCli -ErrorAction SilentlyContinue)) {
        throw "GitHub CLI is required to verify Pages deployment."
    }

    $lastMessage = "No Pages query has completed."
    for ($attempt = 1; $attempt -le $MaxAttempts; $attempt++) {
        Write-RunLog "start query Pages run attempt $attempt"
        $query = Invoke-PagesRunQuery `
            -Commit $Commit `
            -WorkingDirectory $WorkingDirectory `
            -GitHubCli $GitHubCli
        Write-RunLog "finish query Pages run attempt $attempt exit=$($query.ExitCode)"
        if ($query.ExitCode -ne 0) {
            $lastMessage = "GitHub CLI query failed with exit code $($query.ExitCode)."
            Write-RunLog "$lastMessage Retrying within the Pages timeout."
        }
        else {
            $observation = ConvertFrom-PagesRunListJson -Json $query.Stdout
            $lastMessage = $observation.Message
            if ($observation.State -eq "success") {
                Write-RunLog "Pages deployment succeeded url=$($observation.Url)"
                return
            }
            if ($observation.State -eq "failure") {
                throw $observation.Message
            }
            Write-RunLog "Pages deployment not ready state=$($observation.State) message=$lastMessage"
        }
        if ($attempt -lt $MaxAttempts -and $PollSeconds -gt 0) {
            Start-Sleep -Seconds $PollSeconds
        }
    }
    throw "Timed out waiting for the Pages deployment. Last observation: $lastMessage"
}

if ($LoadFunctionsOnly) {
    return
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

    $reportAlreadyValid = Test-Bundle `
        -Root $WorktreePath `
        -Python $Python `
        -TargetPeriod $Period `
        -TargetDate $RunDate
    $historyAlreadyValid = $false
    if ($reportAlreadyValid) {
        $historyAlreadyValid = Test-PublicationHistory `
            -Root $WorktreePath `
            -Python $Python `
            -TargetPeriod $Period `
            -TargetDate $RunDate
    }
    if ($reportAlreadyValid -and $historyAlreadyValid) {
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

    if ($reportAlreadyValid) {
        Write-RunLog "valid Codex report exists but publication history needs repair; skipping regeneration"
    }
    else {
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
    }
    Invoke-PublicationPreflight `
        -SourceRoot $WorktreePath `
        -Python $Python `
        -TargetPeriod $Period `
        -TargetDate $RunDate
    if (-not (Test-PublicationHistory `
        -Root $WorktreePath `
        -Python $Python `
        -TargetPeriod $Period `
        -TargetDate $RunDate)) {
        throw "Publication history verification failed after preflight."
    }

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
    $historyDate = [DateTime]::ParseExact(
        $RunDate,
        "yyyy-MM-dd",
        [System.Globalization.CultureInfo]::InvariantCulture
    )
    $historyYear = if ($Period -eq "weekly") {
        Get-IsoWeekYear -Date $historyDate
    }
    else {
        $historyDate.Year
    }
    $stageCandidates = @(
        "data/snapshots/$RunDate.json",
        "reports/$Period/$stem.md",
        "reports/$Period/$stem.json",
        "reports/$Period/$stem.xiaohongshu.md",
        "reports/$Period/$stem.ai.xiaohongshu.md",
        "reports/$Period/assets/$stem",
        "reports/$Period/avatars/$stem",
        "publish/history/INDEX.json",
        "publish/history/INDEX.md",
        "publish/history/$Period/$historyYear/$stem"
    )
    foreach ($relativePath in $stageCandidates) {
        if (Test-Path -LiteralPath (Join-Path $WorktreePath $relativePath)) {
            Invoke-Logged `
                -Label "stage $relativePath" `
                -FilePath "git" `
                -ArgumentList @("-c", "core.safecrlf=false", "add", "--", $relativePath) `
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
        if (-not (Test-CompleteBundle -Root $WorktreePath -Python $Python -TargetPeriod $Period -TargetDate $RunDate)) {
            throw "Strict bundle verification failed after the report-only rebase."
        }
        Invoke-PublicationPreflight `
            -SourceRoot $WorktreePath `
            -Python $Python `
            -TargetPeriod $Period `
            -TargetDate $RunDate
        $postRebaseChanges = @(Get-ChangedPaths -Root $WorktreePath)
        if ($postRebaseChanges.Count -gt 0) {
            throw (
                "Publication preflight changed generated history after rebase; " +
                "retry from a fresh worktree before pushing."
            )
        }
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

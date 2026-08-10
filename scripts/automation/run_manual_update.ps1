[CmdletBinding()]
param(
    [switch]$SkipPagesWait,

    [switch]$LoadFunctionsOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Runner = Join-Path $PSScriptRoot "run_scheduled.ps1"
$PowerShell = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"

function Get-ManualUpdatePlan {
    param(
        [DateTimeOffset]$ChinaNow = (
            [System.TimeZoneInfo]::ConvertTime(
                [DateTimeOffset]::UtcNow,
                [System.TimeZoneInfo]::FindSystemTimeZoneById("China Standard Time")
            )
        )
    )

    $today = $ChinaNow.ToString("yyyy-MM-dd")
    $daysSinceSunday = [int]$ChinaNow.DayOfWeek
    $latestSunday = $ChinaNow.Date.AddDays(-$daysSinceSunday).ToString("yyyy-MM-dd")
    $daysUntilSunday = 7 - $daysSinceSunday
    $nextSunday = $ChinaNow.Date.AddDays($daysUntilSunday).ToString("yyyy-MM-dd")
    $weeklyDue = $ChinaNow.DayOfWeek -eq [System.DayOfWeek]::Sunday

    @(
        [pscustomobject]@{
            Period = "daily"
            CheckOnly = $false
            UpgradeFallback = $false
            RunDate = $today
            Status = "due"
            NextDueDate = $today
        }
        [pscustomobject]@{
            Period = "weekly"
            CheckOnly = -not $weeklyDue
            UpgradeFallback = $true
            RunDate = if ($weeklyDue) { $today } else { $latestSunday }
            Status = if ($weeklyDue) { "due" } else { "verify_or_upgrade" }
            NextDueDate = if ($weeklyDue) { $today } else { $nextSunday }
        }
    )
}

function Invoke-ManualPeriodUpdate {
    param(
        [Parameter(Mandatory = $true)]
        [ValidateSet("daily", "weekly")]
        [string]$Period,

        [Parameter(Mandatory = $true)]
        [ValidatePattern("^\d{4}-\d{2}-\d{2}$")]
        [string]$RunDate,

        [switch]$CheckOnly,

        [switch]$UpgradeFallback
    )

    $arguments = @(
        "-NoLogo",
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy", "RemoteSigned",
        "-File", $Runner,
        "-Period", $Period,
        "-RunDate", $RunDate,
        "-LockWaitSeconds", "0"
    )
    if ($CheckOnly) {
        $arguments += "-CheckOnly"
    }
    if ($UpgradeFallback) {
        $arguments += "-UpgradeFallback"
    }
    if ($SkipPagesWait) {
        $arguments += "-SkipPagesWait"
    }

    $nativeErrorActionPreference = $ErrorActionPreference
    $exitCode = 1
    try {
        $ErrorActionPreference = "Continue"
        & $PowerShell @arguments 2>&1 | ForEach-Object { Write-Host "$_" }
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $nativeErrorActionPreference
    }
    return $exitCode
}

if ($LoadFunctionsOnly) {
    return
}

foreach ($requiredPath in ($Runner, $PowerShell)) {
    if (-not (Test-Path -LiteralPath $requiredPath -PathType Leaf)) {
        throw "Required manual-update component is missing: $requiredPath"
    }
}

$chinaTimeZone = [System.TimeZoneInfo]::FindSystemTimeZoneById("China Standard Time")
$chinaNow = [System.TimeZoneInfo]::ConvertTime([DateTimeOffset]::UtcNow, $chinaTimeZone)
$plan = @(Get-ManualUpdatePlan -ChinaNow $chinaNow)
$failures = @()
$failureCodes = @()

Write-Host "GitHub Hotspots manual report check"
Write-Host "China time: $($chinaNow.ToString('yyyy-MM-dd HH:mm:ss zzz'))"
Write-Host "The current daily report and latest scheduled weekly report are both checked."
Write-Host "Missing reports are generated only on their truthful due date; frozen weekly fallbacks may be upgraded without recollecting history."

foreach ($item in $plan) {
    Write-Host ""
    $checkLabel = if ($item.UpgradeFallback -and $item.CheckOnly) { "VERIFY/UPGRADE" } elseif ($item.CheckOnly) { "VERIFY" } else { "CHECK" }
    Write-Host "[$checkLabel] $($item.Period) report for $($item.RunDate)"
    $exitCode = Invoke-ManualPeriodUpdate `
        -Period $item.Period `
        -RunDate $item.RunDate `
        -CheckOnly:$item.CheckOnly `
        -UpgradeFallback:$item.UpgradeFallback
    if ($exitCode -eq 0) {
        Write-Host "[OK] $($item.period) report is complete and synchronized."
        if ($item.Period -eq "weekly" -and $item.CheckOnly) {
            Write-Host "[NEXT] Next weekly generation date: $($item.NextDueDate)."
        }
        continue
    }

    if ($exitCode -eq 75) {
        Write-Host "[BUSY] Another local report run owns the shared lock. Run this launcher again after it finishes."
    }
    elseif ($exitCode -eq 76) {
        Write-Host ((
                "[MISSING] No complete frozen weekly report was found for {0}. " +
                "Automatic historical collection is disabled; use the reviewed recovery workflow."
            ) -f $item.RunDate)
    }
    else {
        Write-Host "[FAILED] $($item.period) report check returned exit code $exitCode."
    }
    $failures += $item.Period
    $failureCodes += $exitCode
}

if ($failures.Count -gt 0) {
    Write-Host ""
    Write-Host "Manual check did not complete for: $($failures -join ', ')"
    exit ([int]$failureCodes[0])
}

Write-Host ""
Write-Host "The current daily report and latest scheduled weekly report are complete and synchronized."

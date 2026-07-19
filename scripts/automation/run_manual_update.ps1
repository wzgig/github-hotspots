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
            ShouldRun = $true
            RunDate = $today
            Status = "due"
            NextDueDate = $today
        }
        [pscustomobject]@{
            Period = "weekly"
            ShouldRun = $weeklyDue
            RunDate = if ($weeklyDue) { $today } else { $latestSunday }
            Status = if ($weeklyDue) { "due" } else { "not_due" }
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
        [string]$RunDate
    )

    $arguments = @(
        "-NoLogo",
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy", "RemoteSigned",
        "-File", $Runner,
        "-Period", $Period,
        "-RunDate", $RunDate
    )
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

Write-Host "GitHub Hotspots manual report check"
Write-Host "China time: $($chinaNow.ToString('yyyy-MM-dd HH:mm:ss zzz'))"
Write-Host "Existing complete remote bundles are verified and reused; missing due bundles are generated and pushed."

foreach ($item in $plan) {
    if (-not $item.ShouldRun) {
        Write-Host ((
                "[SKIP] Weekly report is not due today. Latest scheduled Sunday: {0}; " +
                "next due Sunday: {1}. Historical weekly facts are not fabricated automatically."
            ) -f $item.RunDate, $item.NextDueDate)
        continue
    }

    Write-Host ""
    Write-Host "[CHECK] $($item.Period) report for $($item.RunDate)"
    $exitCode = Invoke-ManualPeriodUpdate -Period $item.Period -RunDate $item.RunDate
    if ($exitCode -eq 0) {
        Write-Host "[OK] $($item.period) report is complete and synchronized."
        continue
    }

    if ($exitCode -eq 75) {
        Write-Host "[BUSY] Another local report run owns the shared lock. Run this launcher again after it finishes."
    }
    else {
        Write-Host "[FAILED] $($item.period) report check returned exit code $exitCode."
    }
    $failures += $item.Period
}

if ($failures.Count -gt 0) {
    Write-Host ""
    Write-Host "Manual check did not complete for: $($failures -join ', ')"
    exit 1
}

Write-Host ""
Write-Host "All reports due at this time are complete and synchronized."

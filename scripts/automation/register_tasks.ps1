[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [ValidatePattern("^([01]\d|2[0-3]):[0-5]\d$")]
    [string]$DailyAt = "07:30",

    [ValidatePattern("^([01]\d|2[0-3]):[0-5]\d$")]
    [string]$WeeklyAt = "08:45"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Runner = Join-Path $PSScriptRoot "run_scheduled.ps1"
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$PowerShell = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
$DailyTaskName = "GitHub Hotspots Daily (Local Codex)"
$WeeklyTaskName = "GitHub Hotspots Weekly (Local Codex)"
$RequiredTimeZoneId = "China Standard Time"

$currentTimeZoneId = [System.TimeZoneInfo]::Local.Id
if ($currentTimeZoneId -ne $RequiredTimeZoneId) {
    throw (
        "Windows time zone must be '$RequiredTimeZoneId' before registering the 07:30/08:45 " +
        "Asia/Shanghai tasks. Current time zone: '$currentTimeZoneId'. Change the system time " +
        "zone, then rerun this script."
    )
}

foreach ($requiredPath in ($Runner, $Python, $PowerShell)) {
    if (-not (Test-Path -LiteralPath $requiredPath -PathType Leaf)) {
        throw "Required executable or script is missing: $requiredPath"
    }
}
foreach ($command in ("codex", "git", "gh")) {
    if (-not (Get-Command $command -ErrorAction SilentlyContinue)) {
        throw "Required command is unavailable for the current user: $command"
    }
}

$dailyTime = [DateTime]::ParseExact(
    $DailyAt,
    "HH:mm",
    [System.Globalization.CultureInfo]::InvariantCulture
)
$weeklyTime = [DateTime]::ParseExact(
    $WeeklyAt,
    "HH:mm",
    [System.Globalization.CultureInfo]::InvariantCulture
)
$principal = New-ScheduledTaskPrincipal `
    -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) `
    -LogonType Interactive `
    -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -WakeToRun `
    -RunOnlyIfNetworkAvailable `
    -MultipleInstances IgnoreNew `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 15) `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 75) `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries

function New-HotspotsAction {
    param([Parameter(Mandatory = $true)][string]$Period)

    $arguments = @(
        "-NoLogo",
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy", "RemoteSigned",
        "-File", ('"{0}"' -f $Runner),
        "-Period", $Period
    ) -join " "
    return New-ScheduledTaskAction `
        -Execute $PowerShell `
        -Argument $arguments `
        -WorkingDirectory $RepoRoot
}

$dailyTask = New-ScheduledTask `
    -Action (New-HotspotsAction -Period "daily") `
    -Trigger (New-ScheduledTaskTrigger -Daily -At $dailyTime) `
    -Principal $principal `
    -Settings $settings `
    -Description "Generate and push the daily GitHub Hotspots bundle with the current user's local Codex CLI."
$weeklyTask = New-ScheduledTask `
    -Action (New-HotspotsAction -Period "weekly") `
    -Trigger (New-ScheduledTaskTrigger -Weekly -WeeksInterval 1 -DaysOfWeek Sunday -At $weeklyTime) `
    -Principal $principal `
    -Settings $settings `
    -Description "Generate and push the Sunday GitHub Hotspots weekly bundle with the current user's local Codex CLI."

if ($PSCmdlet.ShouldProcess($DailyTaskName, "Register scheduled task at $DailyAt every day")) {
    Register-ScheduledTask -TaskName $DailyTaskName -InputObject $dailyTask -Force | Out-Null
}
if ($PSCmdlet.ShouldProcess($WeeklyTaskName, "Register scheduled task at $WeeklyAt every Sunday")) {
    Register-ScheduledTask -TaskName $WeeklyTaskName -InputObject $weeklyTask -Force | Out-Null
}

if ($WhatIfPreference) {
    [pscustomobject]@{ TaskName = $DailyTaskName; State = "Planned"; RunAs = $principal.UserId }
    [pscustomobject]@{ TaskName = $WeeklyTaskName; State = "Planned"; RunAs = $principal.UserId }
    return
}

Get-ScheduledTask -TaskName $DailyTaskName, $WeeklyTaskName |
    Select-Object TaskName, State, @{Name = "RunAs"; Expression = { $_.Principal.UserId } }

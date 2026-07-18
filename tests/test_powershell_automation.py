from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "automation" / "run_scheduled.ps1"
REGISTER = ROOT / "scripts" / "automation" / "register_tasks.ps1"
POWERSHELL = shutil.which("powershell.exe") if os.name == "nt" else None
requires_windows_powershell = pytest.mark.skipif(
    POWERSHELL is None,
    reason="Windows PowerShell 5.1 is unavailable",
)


def _ps_quote(value: str | Path) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _run_powershell(script: str) -> subprocess.CompletedProcess[str]:
    assert POWERSHELL is not None
    encoding_setup = (
        "$utf8 = New-Object System.Text.UTF8Encoding($false); "
        "[Console]::OutputEncoding = $utf8; $OutputEncoding = $utf8; "
    )
    return subprocess.run(
        [
            POWERSHELL,
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            encoding_setup + script,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def _load_functions(state_root: Path, *, period: str = "daily") -> str:
    return (
        "$ErrorActionPreference = 'Stop'; "
        f". {_ps_quote(RUNNER)} -Period {period} "
        f"-StateRoot {_ps_quote(state_root)} -LoadFunctionsOnly; "
    )


def _last_json(stdout: str) -> object:
    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    for line in reversed(lines):
        if line.startswith(("[", "{")):
            return json.loads(line)
    raise AssertionError(f"PowerShell produced no JSON output:\n{stdout}")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_publish_bundle(root: Path) -> None:
    board = root / "01-comprehensive"
    images = board / "images"
    images.mkdir(parents=True)
    checklist = root / "CHECKLIST.md"
    checklist.write_text("ready\n", encoding="utf-8")
    title = board / "TITLE.txt"
    caption = board / "CAPTION.txt"
    review = board / "REVIEW.md"
    image = images / "01-cover.png"
    title.write_text("title\n", encoding="utf-8")
    caption.write_text("caption\n", encoding="utf-8")
    review.write_text("review\n", encoding="utf-8")
    image.write_bytes(b"test-image")
    manifest = {
        "schema_version": 1,
        "content_fingerprint": "a" * 64,
        "checklist_sha256": _sha256(checklist),
        "period": "daily",
        "run_date": "2026-07-13",
        "issue": {"stem": "D002-2026-07-13"},
        "boards": [
            {
                "directory": "01-comprehensive",
                "title": "01-comprehensive/TITLE.txt",
                "title_sha256": _sha256(title),
                "caption": "01-comprehensive/CAPTION.txt",
                "caption_sha256": _sha256(caption),
                "review": "01-comprehensive/REVIEW.md",
                "review_sha256": _sha256(review),
                "images": [
                    {
                        "path": "images/01-cover.png",
                        "sha256": _sha256(image),
                        "materialization": "copy",
                    }
                ],
            }
        ],
    }
    (root / "MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")


@requires_windows_powershell
def test_pages_json_states_are_safe_in_powershell_51(tmp_path: Path) -> None:
    cases = {
        "empty": "[]",
        "queued": '[{"status":"queued","conclusion":null,"url":"queued"}]',
        "success": ('[{"status":"completed","conclusion":"success","url":"success"}]'),
        "failure": ('[{"status":"completed","conclusion":"failure","url":"failure"}]'),
        "missing": '[{"status":"queued"}]',
    }
    encoded_cases = json.dumps(cases).replace("'", "''")
    script = (
        _load_functions(tmp_path / "state")
        + f"""
$cases = '{encoded_cases}' | ConvertFrom-Json
$results = @()
foreach ($property in $cases.PSObject.Properties) {{
    $observation = ConvertFrom-PagesRunListJson -Json "$($property.Value)"
    $results += [pscustomobject]@{{ Name = $property.Name; State = $observation.State }}
}}
$results | ConvertTo-Json -Compress
"""
    )

    result = _run_powershell(script)

    assert result.returncode == 0, result.stderr
    states = {item["Name"]: item["State"] for item in _last_json(result.stdout)}
    assert states == {
        "empty": "not_found",
        "queued": "pending",
        "success": "success",
        "failure": "failure",
        "missing": "malformed",
    }


@requires_windows_powershell
def test_pages_wait_retries_and_keeps_stderr_out_of_json(tmp_path: Path) -> None:
    counter = tmp_path / "counter.txt"
    counter.write_text("0\n", encoding="ascii")
    fake_gh = tmp_path / "fake-gh.cmd"
    fake_gh.write_text(
        """@echo off
set /p COUNT=<"%GH_FAKE_COUNTER%"
set /a COUNT+=1
>"%GH_FAKE_COUNTER%" echo %COUNT%
if "%COUNT%"=="1" (
  echo transient query failure 1>&2
  exit /b 1
)
if "%COUNT%"=="2" (
  echo harmless stderr warning 1>&2
  echo [{"status":"queued","conclusion":null,"url":"queued"}]
  exit /b 0
)
echo [{"status":"completed","conclusion":"success","url":"success"}]
exit /b 0
""",
        encoding="ascii",
    )
    state_root = tmp_path / "state"
    script = (
        _load_functions(state_root)
        + f"""
$env:GH_FAKE_COUNTER = {_ps_quote(counter)}
Wait-PagesDeployment -Commit ('a' * 40) -WorkingDirectory {_ps_quote(ROOT)} `
    -GitHubCli {_ps_quote(fake_gh)} -MaxAttempts 3 -PollSeconds 0
Write-Output 'DONE'
"""
    )

    result = _run_powershell(script)

    assert result.returncode == 0, result.stderr
    assert "DONE" in result.stdout
    assert counter.read_text(encoding="ascii").strip() == "3"
    logs = "\n".join(path.read_text(encoding="utf-8-sig") for path in state_root.rglob("*.log"))
    assert "transient query failure" in logs
    assert "harmless stderr warning" in logs
    assert "invalid JSON" not in logs


@requires_windows_powershell
def test_publish_install_repairs_corrupt_matching_current_and_is_idempotent(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    publish_root = tmp_path / "publish"
    target = publish_root / "current" / "daily"
    _write_publish_bundle(source)
    shutil.copytree(source, target)
    missing_image = target / "01-comprehensive" / "images" / "01-cover.png"
    missing_image.unlink()
    state_root = tmp_path / "state"
    script = (
        _load_functions(state_root)
        + f"""
$first = Install-PublishDirectory -Source {_ps_quote(source)} `
    -PublishRoot {_ps_quote(publish_root)} -TargetPeriod daily
$second = Install-PublishDirectory -Source {_ps_quote(source)} `
    -PublishRoot {_ps_quote(publish_root)} -TargetPeriod daily
[pscustomobject]@{{ FirstChanged = $first.Changed; SecondChanged = $second.Changed }} |
    ConvertTo-Json -Compress
"""
    )

    result = _run_powershell(script)

    assert result.returncode == 0, result.stderr
    payload = _last_json(result.stdout)
    assert payload == {"FirstChanged": True, "SecondChanged": False}
    repaired = target / "01-comprehensive" / "images" / "01-cover.png"
    assert repaired.read_bytes() == b"test-image"
    archived = publish_root / "archive" / "daily" / "2026" / "D002-2026-07-13"
    assert archived.is_dir()
    assert not (archived / "01-comprehensive" / "images" / "01-cover.png").exists()


@requires_windows_powershell
def test_publish_manifest_integrity_checks_checklist_hash(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    _write_publish_bundle(bundle)
    (bundle / "CHECKLIST.md").write_text("changed\n", encoding="utf-8")
    state_root = tmp_path / "state"
    script = (
        _load_functions(state_root)
        + f"""
$manifest = Get-Content -LiteralPath {_ps_quote(bundle / "MANIFEST.json")} -Raw |
    ConvertFrom-Json
[pscustomobject]@{{ Valid = Test-PublishManifestFiles `
    -Root {_ps_quote(bundle)} -Manifest $manifest }} | ConvertTo-Json -Compress
"""
    )

    result = _run_powershell(script)

    assert result.returncode == 0, result.stderr
    assert _last_json(result.stdout) == {"Valid": False}


@requires_windows_powershell
def test_publish_install_refuses_to_downgrade_newer_current(tmp_path: Path) -> None:
    source = tmp_path / "source"
    publish_root = tmp_path / "publish"
    target = publish_root / "current" / "daily"
    _write_publish_bundle(source)
    shutil.copytree(source, target)
    manifest_path = target / "MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["content_fingerprint"] = "b" * 64
    manifest["run_date"] = "2026-07-14"
    manifest["issue"]["stem"] = "D003-2026-07-14"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    state_root = tmp_path / "state"
    script = (
        _load_functions(state_root)
        + f"""
$blocked = $false
try {{
    Install-PublishDirectory -Source {_ps_quote(source)} `
        -PublishRoot {_ps_quote(publish_root)} -TargetPeriod daily | Out-Null
}}
catch {{
    $blocked = $_.Exception.Message -like 'Refusing to replace newer*'
}}
$current = Get-Content -LiteralPath {_ps_quote(manifest_path)} -Raw | ConvertFrom-Json
[pscustomobject]@{{
    Blocked = $blocked
    RunDate = $current.run_date
    ArchiveExists = Test-Path -LiteralPath {_ps_quote(publish_root / "archive")}
}} | ConvertTo-Json -Compress
"""
    )

    result = _run_powershell(script)

    assert result.returncode == 0, result.stderr
    assert _last_json(result.stdout) == {
        "Blocked": True,
        "RunDate": "2026-07-14",
        "ArchiveExists": False,
    }


@requires_windows_powershell
def test_publish_install_replaces_matching_current_with_invalid_manifest(tmp_path: Path) -> None:
    source = tmp_path / "source"
    publish_root = tmp_path / "publish"
    target = publish_root / "current" / "daily"
    _write_publish_bundle(source)
    shutil.copytree(source, target)
    manifest_path = target / "MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    del manifest["run_date"]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    state_root = tmp_path / "state"
    script = (
        _load_functions(state_root)
        + f"""
$result = Install-PublishDirectory -Source {_ps_quote(source)} `
    -PublishRoot {_ps_quote(publish_root)} -TargetPeriod daily
$current = Get-Content -LiteralPath {_ps_quote(manifest_path)} -Raw | ConvertFrom-Json
[pscustomobject]@{{
    Changed = $result.Changed
    RunDate = $current.run_date
    RecoveryExists = Test-Path -LiteralPath {_ps_quote(publish_root / "archive" / "daily" / "recovery")}
}} | ConvertTo-Json -Compress
"""
    )

    result = _run_powershell(script)

    assert result.returncode == 0, result.stderr
    assert _last_json(result.stdout) == {
        "Changed": True,
        "RunDate": "2026-07-13",
        "RecoveryExists": True,
    }


@requires_windows_powershell
def test_publish_activation_failure_rolls_back_previous_current(tmp_path: Path) -> None:
    publish_root = tmp_path / "publish"
    target = publish_root / "current" / "daily"
    staging = publish_root / "current" / ".daily-staging-test"
    _write_publish_bundle(target)
    _write_publish_bundle(staging)
    state_root = tmp_path / "state"
    script = (
        _load_functions(state_root)
        + f"""
$manifest = Get-Content -LiteralPath {_ps_quote(target / "MANIFEST.json")} -Raw |
    ConvertFrom-Json
$failed = $false
try {{
    Switch-PublishStaging -Staging {_ps_quote(staging)} -Target {_ps_quote(target)} `
        -PublishRoot {_ps_quote(publish_root)} -TargetPeriod daily -TargetManifest $manifest `
        -Activation {{ param($sourcePath, $destinationPath) throw 'simulated activation failure' }}
}}
catch {{
    $failed = $true
}}
[pscustomobject]@{{
    Failed = $failed
    TargetRestored = Test-Path -LiteralPath {_ps_quote(target / "MANIFEST.json")} -PathType Leaf
    StagingPreserved = Test-Path -LiteralPath {_ps_quote(staging)} -PathType Container
    ArchiveCount = @(Get-ChildItem -LiteralPath {_ps_quote(publish_root / "archive")} `
        -Recurse -Filter MANIFEST.json -ErrorAction SilentlyContinue).Count
}} | ConvertTo-Json -Compress
"""
    )

    result = _run_powershell(script)

    assert result.returncode == 0, result.stderr
    assert _last_json(result.stdout) == {
        "Failed": True,
        "TargetRestored": True,
        "StagingPreserved": True,
        "ArchiveCount": 0,
    }


def test_runner_fetches_origin_main_with_an_explicit_tracking_ref() -> None:
    source = RUNNER.read_text(encoding="utf-8")

    assert "+refs/heads/main:refs/remotes/origin/main" in source
    assert 'rev-parse", "refs/remotes/origin/main^{commit}"' in source
    assert '"publish/history/INDEX.json"' in source
    assert '"publish/history/INDEX.md"' in source
    assert '"publish/history/$Period/$historyYear/$stem"' in source


def test_task_registration_has_logon_catchup_without_network_launch_gate() -> None:
    source = REGISTER.read_text(encoding="utf-8")

    assert "New-ScheduledTaskTrigger -AtLogOn -User $CurrentUser" in source
    assert "-Trigger $dailyTriggers" in source
    assert "-StartWhenAvailable" in source
    assert "-RunOnlyIfNetworkAvailable" not in source

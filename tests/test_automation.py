from __future__ import annotations

import json
import struct
from datetime import date
from pathlib import Path

import pytest
from PIL import Image

from github_hotspots.automation import (
    AutomationValidationError,
    main,
    report_stem,
    scan_generated_files,
    validate_generated_paths,
    validate_remote_update_paths,
    validate_report_bundle,
)


def _write_png(path: Path, size: tuple[int, int] = (1200, 1600)) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, "white").save(path)


def _build_bundle(root: Path, *, fallback: bool = False) -> Path:
    stem = "2026-07-12"
    report_dir = root / "reports" / "daily"
    asset_dir = report_dir / "assets" / stem
    report_dir.mkdir(parents=True)
    for suffix in ("md", "xiaohongshu.md", "ai.xiaohongshu.md"):
        (report_dir / f"{stem}.{suffix}").write_text("ready\n", encoding="utf-8")

    boards: dict[str, dict[str, object]] = {}
    manifest_boards: dict[str, dict[str, object]] = {}
    for board_key in ("comprehensive", "ai"):
        cover = asset_dir / f"{stem}.{board_key}.cover.png"
        project = asset_dir / f"{stem}.{board_key}.01.acme--tool.png"
        _write_png(cover)
        _write_png(project)
        repositories = [{"rank": 1, "full_name": "acme/tool"}]
        boards[board_key] = {"repositories": repositories}
        manifest_boards[board_key] = {
            "cover": cover.relative_to(root).as_posix(),
            "projects": [
                {
                    "rank": 1,
                    "full_name": "acme/tool",
                    "path": project.relative_to(root).as_posix(),
                }
            ],
        }

    publication = {
        "issue_number": 1,
        "issue_code": "D001",
        "issue_label": "\u7b2c1\u671f",
        "status": "official",
    }
    manifest_path = asset_dir / "manifest.json"
    manifest = {
        "schema_version": 2,
        "period": "daily",
        "run_date": stem,
        "source_report": f"reports/daily/{stem}.json",
        "width": 1200,
        "height": 1600,
        "renderer": {"name": "github-hotspots-pillow", "version": "4.0"},
        "style_version": "signal-broadsheet-v1",
        "publication": publication,
        "boards": manifest_boards,
    }
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    report = {
        "schema_version": 3,
        "period": "daily",
        "run_date": stem,
        "publication": publication,
        "editorial": {
            "boards": {
                key: {
                    "prompt_version": "4.1",
                    "schema_version": "4.0",
                    "used_backend": "codex-cli",
                    "fallback_used": fallback,
                }
                for key in ("comprehensive", "ai")
            }
        },
        "assets": {
            "enabled": True,
            "width": 1200,
            "height": 1600,
            "manifest": manifest_path.relative_to(root).as_posix(),
            "publication": publication,
        },
        "boards": boards,
    }
    report_path = report_dir / f"{stem}.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    return report_path


def test_report_stem_uses_iso_week() -> None:
    assert report_stem("daily", date(2026, 7, 12)) == "2026-07-12"
    assert report_stem("weekly", "2026-07-12") == "2026-W28"


def test_validate_report_bundle_accepts_complete_codex_bundle(tmp_path: Path) -> None:
    _build_bundle(tmp_path)

    result = validate_report_bundle(tmp_path, "daily", "2026-07-12", require_codex=True)

    assert result.stem == "2026-07-12"
    assert result.used_backends == ("codex-cli", "codex-cli")
    assert len(result.poster_paths) == 4


def test_validate_report_bundle_rejects_editorial_fallback(tmp_path: Path) -> None:
    _build_bundle(tmp_path, fallback=True)

    with pytest.raises(AutomationValidationError, match="both boards") as error:
        validate_report_bundle(tmp_path, "daily", "2026-07-12", require_codex=True)

    assert error.value.category == "editorial_fallback"


def test_validate_report_bundle_accepts_current_deterministic_bundle_without_codex_gate(
    tmp_path: Path,
) -> None:
    report_path = _build_bundle(tmp_path)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    for board in report["editorial"]["boards"].values():
        board["used_backend"] = "deterministic"
    report_path.write_text(json.dumps(report), encoding="utf-8")

    result = validate_report_bundle(tmp_path, "daily", "2026-07-12")
    assert result.used_backends == ("deterministic", "deterministic")

    with pytest.raises(AutomationValidationError) as error:
        validate_report_bundle(tmp_path, "daily", "2026-07-12", require_codex=True)
    assert error.value.category == "editorial_fallback"


@pytest.mark.parametrize(
    ("field", "old_value"),
    (("prompt_version", "4.0"), ("schema_version", "3.0")),
)
def test_validate_report_bundle_rejects_old_editorial_contract(
    tmp_path: Path, field: str, old_value: str
) -> None:
    report_path = _build_bundle(tmp_path)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["editorial"]["boards"]["comprehensive"][field] = old_value
    report_path.write_text(json.dumps(report), encoding="utf-8")

    with pytest.raises(AutomationValidationError) as error:
        validate_report_bundle(tmp_path, "daily", "2026-07-12")

    assert error.value.category == "editorial_version"


@pytest.mark.parametrize(
    ("manifest_key", "old_value"),
    (
        ("renderer", {"name": "github-hotspots-pillow", "version": "3.0"}),
        ("style_version", "legacy-v3"),
    ),
)
def test_validate_report_bundle_rejects_old_poster_contract(
    tmp_path: Path, manifest_key: str, old_value: object
) -> None:
    report_path = _build_bundle(tmp_path)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    manifest_path = tmp_path / report["assets"]["manifest"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest[manifest_key] = old_value
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(AutomationValidationError) as error:
        validate_report_bundle(tmp_path, "daily", "2026-07-12")

    assert error.value.category == "poster_version"


def test_validate_report_bundle_rejects_wrong_publication_issue(tmp_path: Path) -> None:
    report_path = _build_bundle(tmp_path)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["publication"]["issue_code"] = "D000"
    report_path.write_text(json.dumps(report), encoding="utf-8")

    with pytest.raises(AutomationValidationError) as error:
        validate_report_bundle(tmp_path, "daily", "2026-07-12")

    assert error.value.category == "report_publication"


def test_validate_report_bundle_rejects_wrong_poster_dimensions(tmp_path: Path) -> None:
    _build_bundle(tmp_path)
    poster = next((tmp_path / "reports" / "daily" / "assets").rglob("*.png"))
    _write_png(poster, (600, 800))

    with pytest.raises(AutomationValidationError) as error:
        validate_report_bundle(tmp_path, "daily", "2026-07-12")

    assert error.value.category == "poster_dimensions"


def test_validate_report_bundle_rejects_truncated_png_header(tmp_path: Path) -> None:
    _build_bundle(tmp_path)
    poster = next((tmp_path / "reports" / "daily" / "assets").rglob("*.png"))
    poster.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + struct.pack(">II", 1200, 1600))

    with pytest.raises(AutomationValidationError) as error:
        validate_report_bundle(tmp_path, "daily", "2026-07-12")

    assert error.value.category == "poster_invalid"


def test_validate_report_bundle_rejects_empty_board(tmp_path: Path) -> None:
    report_path = _build_bundle(tmp_path)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["boards"]["comprehensive"]["repositories"] = []
    manifest_path = tmp_path / report["assets"]["manifest"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["boards"]["comprehensive"]["projects"] = []
    report_path.write_text(json.dumps(report), encoding="utf-8")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(AutomationValidationError) as error:
        validate_report_bundle(tmp_path, "daily", "2026-07-12")

    assert error.value.category == "board_projects"


def test_validate_report_bundle_rejects_manifest_path_escape(tmp_path: Path) -> None:
    report_path = _build_bundle(tmp_path)
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    payload["assets"]["manifest"] = "../outside.json"
    report_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(AutomationValidationError) as error:
        validate_report_bundle(tmp_path, "daily", "2026-07-12")

    assert error.value.category == "manifest_path"


def test_validate_generated_paths_accepts_only_current_bundle() -> None:
    paths = [
        "data/snapshots/2026-07-12.json",
        "reports/daily/2026-07-12.json",
        "reports/daily/assets/2026-07-12/cover.png",
        "reports/daily/avatars/2026-07-12/acme.png",
        "publish/daily/2026-07-12/综合主榜/文案.md",
    ]

    assert validate_generated_paths(paths, "daily", "2026-07-12") == tuple(paths)

    with pytest.raises(AutomationValidationError) as error:
        validate_generated_paths(["PROJECT_LOG.md"], "daily", "2026-07-12")
    assert error.value.category == "unexpected_path"


def test_validate_remote_update_paths_accepts_only_dated_report_artifacts() -> None:
    paths = [
        "data/snapshots/2026-07-12.json",
        "reports/daily/2026-07-12.json",
        "reports/daily/2026-07-12.xiaohongshu.md",
        "reports/daily/assets/2026-07-12/manifest.json",
        "reports/daily/assets/2026-07-12/cover.png",
        "reports/daily/avatars/2026-07-12/owner.png",
        "reports/weekly/2026-W28.ai.xiaohongshu.md",
        "reports/weekly/assets/2026-W28/cover.png",
        "reports/weekly/avatars/2026-W28/owner.png",
    ]

    assert validate_remote_update_paths(paths) == tuple(paths)


@pytest.mark.parametrize(
    "path",
    (
        "src/github_hotspots/automation.py",
        "config/hotspots.yaml",
        ".github/workflows/daily.yml",
        "docs/AUTOMATION.md",
        "reports/daily/2026-02-30.json",
        "reports/weekly/2026-W54.json",
        "reports/daily/assets/2026-07-12/payload.py",
        "publish/current/TODAY.md",
    ),
)
def test_validate_remote_update_paths_rejects_untrusted_remote_change(path: str) -> None:
    with pytest.raises(AutomationValidationError) as error:
        validate_remote_update_paths([path])

    assert error.value.category == "remote_update_path"


def test_scan_generated_files_rejects_high_confidence_secret(tmp_path: Path) -> None:
    safe = tmp_path / "reports" / "daily" / "2026-07-12.md"
    safe.parent.mkdir(parents=True)
    safe.write_text("ordinary report", encoding="utf-8")
    scan_generated_files(tmp_path, ["reports/daily/2026-07-12.md"])

    safe.write_text("Authorization: Bearer " + "a" * 32, encoding="utf-8")
    with pytest.raises(AutomationValidationError) as error:
        scan_generated_files(tmp_path, ["reports/daily/2026-07-12.md"])
    assert error.value.category == "suspected_secret"


def test_main_verify_and_stem_commands(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _build_bundle(tmp_path)

    assert main(["stem", "--period", "weekly", "--date", "2026-07-12"]) == 0
    assert capsys.readouterr().out.strip() == "2026-W28"

    assert (
        main(
            [
                "verify",
                "--root",
                str(tmp_path),
                "--period",
                "daily",
                "--date",
                "2026-07-12",
                "--require-codex",
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["poster_count"] == 4


def test_main_verify_quiet_returns_nonzero_for_missing_bundle(tmp_path: Path) -> None:
    assert (
        main(
            [
                "verify",
                "--root",
                str(tmp_path),
                "--period",
                "daily",
                "--date",
                "2026-07-12",
                "--require-codex",
                "--quiet",
            ]
        )
        == 1
    )


def test_main_validate_remote_paths_command(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert (
        main(
            [
                "validate-remote-paths",
                "data/snapshots/2026-07-12.json",
                "reports/weekly/2026-W28.json",
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["path_count"] == 2

    assert main(["validate-remote-paths", "prompts/repository_summary_zh.md"]) == 1
    assert json.loads(capsys.readouterr().err)["category"] == "remote_update_path"

    empty_paths = tmp_path / "remote.paths"
    empty_paths.write_text("", encoding="utf-8")
    assert main(["validate-remote-paths", "--paths-file", str(empty_paths)]) == 0
    assert json.loads(capsys.readouterr().out)["path_count"] == 0

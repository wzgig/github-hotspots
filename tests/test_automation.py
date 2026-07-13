from __future__ import annotations

import hashlib
import json
import struct
from datetime import date
from pathlib import Path

import pytest
from PIL import Image

from github_hotspots import automation as automation_module
from github_hotspots.automation import (
    AutomationValidationError,
    main,
    report_stem,
    scan_generated_files,
    validate_generated_paths,
    validate_publication_history,
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


def _sha256_text(path: Path) -> str:
    return hashlib.sha256(path.read_text(encoding="utf-8").encode("utf-8")).hexdigest()


def _sha256_binary(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _build_history(root: Path) -> Path:
    stem = "2026-07-12"
    report_path = root / "reports" / "daily" / f"{stem}.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    poster_manifest_path = root / report["assets"]["manifest"]
    poster_manifest = json.loads(poster_manifest_path.read_text(encoding="utf-8"))
    temporary = root / "publish" / ".history-fixture"
    temporary.mkdir(parents=True)
    checklist = temporary / "CHECKLIST.md"
    checklist.write_text("ready\n", encoding="utf-8")

    boards: list[dict[str, object]] = []
    for position, board_key in enumerate(("comprehensive", "ai"), start=1):
        directory = f"{position:02d}-{board_key}"
        board_root = temporary / directory
        board_root.mkdir()
        text_paths = {
            "title": board_root / "TITLE.txt",
            "caption": board_root / "CAPTION.txt",
            "review": board_root / "REVIEW.md",
        }
        for field, path in text_paths.items():
            path.write_text(f"{field}\n", encoding="utf-8")
        manifest_board = poster_manifest["boards"][board_key]
        raw_images = [
            ("cover", manifest_board["cover"]),
            *[("project", item["path"]) for item in manifest_board["projects"]],
        ]
        images = []
        for order, (role, source_value) in enumerate(raw_images, start=1):
            source = root / source_value
            images.append(
                {
                    "order": order,
                    "role": role,
                    "publication_path": f"images/{order:02d}.png",
                    "source": source.relative_to(root).as_posix(),
                    "sha256": _sha256_binary(source),
                    "width": 1200,
                    "height": 1600,
                }
            )
        boards.append(
            {
                "key": board_key,
                "directory": directory,
                "title": f"{directory}/TITLE.txt",
                "title_sha256": _sha256_text(text_paths["title"]),
                "caption": f"{directory}/CAPTION.txt",
                "caption_sha256": _sha256_text(text_paths["caption"]),
                "review": f"{directory}/REVIEW.md",
                "review_sha256": _sha256_text(text_paths["review"]),
                "images": images,
            }
        )

    history_manifest = {
        "schema_version": 1,
        "generator": {
            "name": "github-hotspots-publish-bundle",
            "version": "1.1",
        },
        "checklist_sha256": _sha256_text(checklist),
        "status": "draft",
        "period": "daily",
        "run_date": stem,
        "generated_at": "2026-07-12T09:01:00+08:00",
        "issue": {
            "number": 1,
            "code": "D001",
            "stem": "D001-2026-07-12",
            "label": "第1期",
            "status": "official",
        },
        "source": {
            "report": report_path.relative_to(root).as_posix(),
            "report_sha256": _sha256_text(report_path),
            "poster_manifest": poster_manifest_path.relative_to(root).as_posix(),
            "poster_manifest_sha256": _sha256_text(poster_manifest_path),
        },
        "editorial": {
            "policy": "facts-locked-batch-editing",
            "boards": {
                "comprehensive": {"used_backend": "codex-cli"},
                "ai": {"used_backend": "codex-cli"},
            },
        },
        "history": {
            "schema_version": 1,
            "kind": "thin-publication-history",
            "report_stem": stem,
            "revision": "pending",
            "image_policy": "repository-source-reference",
        },
        "boards": boards,
    }
    fingerprint = automation_module._publication_history_fingerprint(history_manifest)
    history_manifest["content_fingerprint"] = fingerprint
    history_manifest["history"]["revision"] = fingerprint[:12]
    revision = root / "publish" / "history" / "daily" / "2026" / stem / fingerprint[:12]
    revision.parent.mkdir(parents=True)
    temporary.replace(revision)
    (revision / "MANIFEST.json").write_text(json.dumps(history_manifest), encoding="utf-8")
    history_root = root / "publish" / "history"
    index = automation_module._expected_publication_history_index(history_root)
    (history_root / "INDEX.json").write_text(
        json.dumps(index),
        encoding="utf-8",
    )
    (history_root / "INDEX.md").write_text(
        automation_module._render_publication_history_index(index),
        encoding="utf-8",
    )
    return revision


def test_report_stem_uses_iso_week() -> None:
    assert report_stem("daily", date(2026, 7, 12)) == "2026-07-12"
    assert report_stem("weekly", "2026-07-12") == "2026-W28"


def test_validate_report_bundle_accepts_complete_codex_bundle(tmp_path: Path) -> None:
    _build_bundle(tmp_path)

    result = validate_report_bundle(tmp_path, "daily", "2026-07-12", require_codex=True)

    assert result.stem == "2026-07-12"
    assert result.used_backends == ("codex-cli", "codex-cli")
    assert len(result.poster_paths) == 4


def test_validate_publication_history_accepts_indexed_current_revision(tmp_path: Path) -> None:
    _build_bundle(tmp_path)
    revision = _build_history(tmp_path)

    assert validate_publication_history(tmp_path, "daily", "2026-07-12") == revision.parent

    (revision / "01-comprehensive" / "CAPTION.txt").write_text(
        "changed\n",
        encoding="utf-8",
    )
    with pytest.raises(AutomationValidationError) as error:
        validate_publication_history(tmp_path, "daily", "2026-07-12")
    assert error.value.category == "history_text"


def test_validate_publication_history_recomputes_fingerprint_and_full_index(tmp_path: Path) -> None:
    _build_bundle(tmp_path)
    revision = _build_history(tmp_path)
    manifest_path = revision / "MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["status"] = "preview"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(AutomationValidationError) as fingerprint_error:
        validate_publication_history(tmp_path, "daily", "2026-07-12")
    assert fingerprint_error.value.category == "history_manifest"

    _build_bundle(tmp_path / "index-case")
    _build_history(tmp_path / "index-case")
    index_path = tmp_path / "index-case" / "publish" / "history" / "INDEX.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    index["issues"][0]["latest"]["revision"] = "000000000000"
    index_path.write_text(json.dumps(index), encoding="utf-8")

    with pytest.raises(AutomationValidationError) as index_error:
        validate_publication_history(tmp_path / "index-case", "daily", "2026-07-12")
    assert index_error.value.category == "history_index"


def test_validate_report_bundle_uses_configured_publication_anchor(tmp_path: Path) -> None:
    report_path = _build_bundle(tmp_path)
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "hotspots.yaml").write_text(
        "publication:\n"
        "  daily_first_issue_date: 2026-07-11\n"
        "  weekly_first_issue_date: 2026-07-12\n",
        encoding="utf-8",
    )
    expected = {
        "issue_number": 2,
        "issue_code": "D002",
        "issue_label": "第2期",
        "status": "official",
    }
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["publication"] = expected
    report["assets"]["publication"] = expected
    report_path.write_text(json.dumps(report), encoding="utf-8")
    manifest_path = tmp_path / report["assets"]["manifest"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["publication"] = expected
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = validate_report_bundle(tmp_path, "daily", "2026-07-12", require_codex=True)

    assert result.run_date.isoformat() == "2026-07-12"


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
        "publish/history/INDEX.json",
        "publish/history/INDEX.md",
        "publish/history/daily/2026/2026-07-12/0123456789ab/MANIFEST.json",
        "publish/history/daily/2026/2026-07-12/0123456789ab/01-comprehensive/CAPTION.txt",
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
        "publish/history/INDEX.json",
        "publish/history/INDEX.md",
        "publish/history/daily/2026/2026-07-12/0123456789ab/MANIFEST.json",
        "publish/history/weekly/2026/2026-W28/abcdef012345/02-ai/REVIEW.md",
    ]

    assert validate_remote_update_paths(paths) == tuple(paths)


def test_scheduled_workflows_repair_and_stage_publication_history() -> None:
    for workflow in ("daily.yml", "weekly.yml"):
        source = (Path(".github/workflows") / workflow).read_text(encoding="utf-8")
        assert "verify-history" in source
        assert "should_backfill_history" in source
        assert '"publish/history/INDEX.json"' in source
        assert '"publish/history/INDEX.md"' in source
        assert '"publish/history/${PERIOD}/${HISTORY_YEAR}/${STEM}"' in source
        assert "+refs/heads/main:refs/remotes/origin/main" in source


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
        "publish/history/daily/2026/2026-07-12/0123456789ab/images/cover.png",
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
    _build_history(tmp_path)

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

    assert (
        main(
            [
                "verify-history",
                "--root",
                str(tmp_path),
                "--period",
                "daily",
                "--date",
                "2026-07-12",
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["history"].startswith(
        "publish/history/daily/2026/2026-07-12"
    )


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

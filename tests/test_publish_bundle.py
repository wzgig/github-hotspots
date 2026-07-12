import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest
import yaml
from PIL import Image

from github_hotspots import publish_bundle
from github_hotspots.config import Settings, load_settings
from github_hotspots.publish_bundle import build_publish_bundle, publication_issue


def _settings(tmp_path: Path, *, prefer_hardlinks: bool = True) -> Settings:
    document = yaml.safe_load(Path("config/hotspots.yaml").read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    publication = document["publication"]
    assert isinstance(publication, dict)
    publication["root_dir"] = "publish"
    publication["prefer_hardlinks"] = prefer_hardlinks
    config_path = tmp_path / "config" / "hotspots.yaml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        yaml.safe_dump(document, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return load_settings(config_path)


def _write_png(path: Path, *, size: tuple[int, int] = (1200, 1600), color: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color).save(path, format="PNG")


def _repository(board: str) -> dict[str, Any]:
    name = "toolkit" if board == "comprehensive" else "agent-kit"
    owner = "example" if board == "comprehensive" else "ai-lab"
    return {
        "rank": 1,
        "full_name": f"{owner}/{name}",
        "name": name,
        "html_url": f"https://github.com/{owner}/{name}",
        "stars": 1234,
        "forks": 88,
        "star_delta": 42,
        "delta_source": "snapshot",
        "summary": {
            "one_line": (
                "把重复开发任务整理成可复用工作流"
                if board == "comprehensive"
                else "让多个 AI Agent 分工执行并汇总任务结果"
            ),
            "capabilities": ["执行具体任务", "保存可复用结果"],
            "license_label": "MIT",
        },
    }


def _write_report(
    tmp_path: Path,
    *,
    period: str,
    run_date: date,
    image_size: tuple[int, int] = (1200, 1600),
    cover_override: str | None = None,
    editorial_override: dict[str, Any] | None = None,
) -> Path:
    stem = (
        run_date.isoformat()
        if period == "daily"
        else f"{run_date.isocalendar().year}-W{run_date.isocalendar().week:02d}"
    )
    report_dir = tmp_path / "reports" / period
    asset_dir = report_dir / "assets" / stem
    report_path = report_dir / f"{stem}.json"
    manifest_path = asset_dir / "manifest.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)

    report_boards: dict[str, Any] = {}
    manifest_boards: dict[str, Any] = {}
    colors = {"comprehensive": "#335577", "ai": "#774477"}
    for board in ("comprehensive", "ai"):
        repository = _repository(board)
        cover = asset_dir / f"{stem}.{board}.cover.png"
        project = asset_dir / f"{stem}.{board}.01.{board}.png"
        _write_png(cover, size=image_size, color=colors[board])
        _write_png(project, color="#F5F0E8")
        cover_path = cover.relative_to(tmp_path).as_posix()
        if board == "comprehensive" and cover_override is not None:
            cover_path = cover_override
        report_boards[board] = {
            "label": "综合主榜" if board == "comprehensive" else "AI 专题榜",
            "top_n": 1,
            "repositories": [repository],
        }
        manifest_boards[board] = {
            "enabled": True,
            "top_n": 1,
            "cover": cover_path,
            "projects": [
                {
                    "rank": 1,
                    "full_name": repository["full_name"],
                    "path": project.relative_to(tmp_path).as_posix(),
                }
            ],
        }

    editorial_board = {
        "prompt_version": "4.0",
        "schema_version": "4.0",
        "requested_backend": "codex-cli",
        "used_backend": "codex-cli",
        "fallback_used": False,
        "error_category": None,
    }
    editorial = {
        "policy": "facts-locked-batch-editing",
        "boards": {
            "comprehensive": dict(editorial_board),
            "ai": dict(editorial_board),
        },
    }
    if editorial_override is not None:
        editorial = editorial_override

    report = {
        "schema_version": 3,
        "period": period,
        "run_date": run_date.isoformat(),
        "generated_at": f"{run_date.isoformat()}T09:00:00+08:00",
        "assets": {"manifest": manifest_path.relative_to(tmp_path).as_posix()},
        "editorial": editorial,
        "boards": report_boards,
    }
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    manifest = {
        "schema_version": 2,
        "period": period,
        "run_date": run_date.isoformat(),
        "source_report": report_path.relative_to(tmp_path).as_posix(),
        "renderer": {"name": "github-hotspots-pillow", "version": "test"},
        "style_version": "original-editorial-v4",
        "enabled": True,
        "format": "png",
        "width": 1200,
        "height": 1600,
        "boards": manifest_boards,
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report_path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_publication_issue_starts_daily_and_weekly_at_one(tmp_path: Path) -> None:
    publication = _settings(tmp_path).publication_settings()

    daily = publication_issue(publication, "daily", date(2026, 7, 12))
    weekly = publication_issue(publication, "weekly", date(2026, 7, 12))
    preview = publication_issue(publication, "daily", date(2026, 7, 11))

    assert (daily.code, daily.number, daily.stem) == ("D001", 1, "D001-2026-07-12")
    assert (weekly.code, weekly.number, weekly.stem) == ("W001", 1, "W001-2026-W28")
    assert publication_issue(publication, "daily", date(2026, 7, 13)).code == "D002"
    assert publication_issue(publication, "weekly", date(2026, 7, 19)).code == "W002"
    assert preview.status == "preview"
    assert preview.number is None
    assert preview.code == "D-PREVIEW"


def test_build_publish_bundle_creates_four_ready_board_packages(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    daily_report = _write_report(tmp_path, period="daily", run_date=date(2026, 7, 12))
    weekly_report = _write_report(tmp_path, period="weekly", run_date=date(2026, 7, 12))

    daily = build_publish_bundle(settings, daily_report)
    weekly = build_publish_bundle(settings, weekly_report)

    assert daily.issue_code == "D001"
    assert weekly.issue_code == "W001"
    assert len(daily.board_dirs) == 2
    assert len(weekly.board_dirs) == 2
    for board_dir in (*daily.board_dirs, *weekly.board_dirs):
        assert (board_dir / "TITLE.txt").is_file()
        assert (board_dir / "CAPTION.txt").is_file()
        assert (board_dir / "REVIEW.md").is_file()
        caption = (board_dir / "CAPTION.txt").read_text(encoding="utf-8")
        assert "# 标题" not in caption
        assert "# 正文" not in caption
        assert "# 配图清单" not in caption
        assert "reports/" not in caption
        assert "发布前人工审核" not in caption
        assert "AI 辅助整理｜人工发布" in caption
        assert len(caption.rstrip()) <= 1000
        assert [path.name for path in sorted((board_dir / "images").glob("*.png"))] == [
            "01-cover.png",
            next(path.name for path in (board_dir / "images").glob("02-rank-01-*.png")),
        ]

    daily_caption = (daily.current_dir / "01-comprehensive" / "CAPTION.txt").read_text(
        encoding="utf-8"
    )
    weekly_caption = (weekly.current_dir / "01-comprehensive" / "CAPTION.txt").read_text(
        encoding="utf-8"
    )
    assert "今天把 1 个上榜项目翻译成人话" in daily_caption
    assert "example/toolkit" in daily_caption
    assert "把这一周的 1 个热点压缩成一组" in weekly_caption
    assert daily_caption != weekly_caption
    assert (daily.current_dir / "01-comprehensive" / "TITLE.txt").read_text(
        encoding="utf-8"
    ).strip() == "GitHub日报第1期｜1个开源项目讲明白"
    assert (weekly.current_dir / "02-ai" / "TITLE.txt").read_text(
        encoding="utf-8"
    ).strip() == "GitHub AI周报第1期｜1个AI项目值得收藏"

    manifest = json.loads(daily.manifest.read_text(encoding="utf-8"))
    assert manifest["status"] == "draft"
    assert manifest["generator"] == {
        "name": "github-hotspots-publish-bundle",
        "version": "1.0",
    }
    assert len(manifest["content_fingerprint"]) == 64
    assert manifest["issue"] == {
        "number": 1,
        "code": "D001",
        "stem": "D001-2026-07-12",
        "label": "第1期",
        "status": "official",
    }
    assert manifest["editorial"]["boards"]["comprehensive"]["used_backend"] == "codex-cli"
    assert manifest["editorial"]["boards"]["ai"]["fallback_used"] is False
    for board in manifest["boards"]:
        review = daily.current_dir / board["review"]
        assert board["review_sha256"] == _sha256(review)
        assert [image["order"] for image in board["images"]] == [1, 2]
        for image in board["images"]:
            packaged = daily.current_dir / board["directory"] / image["path"]
            source = tmp_path / image["source"]
            assert packaged.is_file()
            assert image["sha256"] == _sha256(packaged) == _sha256(source)
            assert (image["width"], image["height"]) == (1200, 1600)
            assert image["materialization"] in {"hardlink", "copy"}

    today = daily.today.read_text(encoding="utf-8")
    assert "日报 · D001" in today
    assert "周报 · W001" in today
    assert "D001-C" in today and "D001-A" in today
    assert "W001-C" in today and "W001-A" in today
    assert (tmp_path / "publish" / "logs" / "publication.jsonl").is_file()


def test_build_publish_bundle_archives_previous_current_without_overwrite(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    first = _write_report(tmp_path, period="daily", run_date=date(2026, 7, 12))
    second = _write_report(tmp_path, period="daily", run_date=date(2026, 7, 13))

    build_publish_bundle(settings, first)
    current = build_publish_bundle(settings, second)

    expected_archive = tmp_path / "publish" / "archive" / "daily" / "2026" / "D001-2026-07-12"
    assert current.issue_code == "D002"
    assert current.archived_dir == expected_archive
    assert (expected_archive / "MANIFEST.json").is_file()
    assert (
        json.loads((expected_archive / "MANIFEST.json").read_text(encoding="utf-8"))["issue"][
            "code"
        ]
        == "D001"
    )
    assert json.loads(current.manifest.read_text(encoding="utf-8"))["issue"]["code"] == "D002"
    today = current.today.read_text(encoding="utf-8")
    assert "今天优先发布最新日报综合榜" in today
    assert "晚些时候再发布周报综合榜" not in today


def test_build_publish_bundle_marks_prelaunch_report_as_preview(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    report = _write_report(tmp_path, period="daily", run_date=date(2026, 7, 11))

    artifacts = build_publish_bundle(settings, report)
    manifest = json.loads(artifacts.manifest.read_text(encoding="utf-8"))

    assert artifacts.issue_code == "D-PREVIEW"
    assert manifest["status"] == "preview"
    assert manifest["issue"]["number"] is None
    assert all(board["status"] == "preview" for board in manifest["boards"])


def test_build_publish_bundle_falls_back_to_copy_when_hardlink_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    settings = _settings(tmp_path, prefer_hardlinks=True)
    report = _write_report(tmp_path, period="daily", run_date=date(2026, 7, 12))

    def fail_link(*_args, **_kwargs):
        raise OSError("hardlinks unavailable")

    monkeypatch.setattr(publish_bundle.os, "link", fail_link)
    artifacts = build_publish_bundle(settings, report)
    manifest = json.loads(artifacts.manifest.read_text(encoding="utf-8"))

    assert {
        image["materialization"] for board in manifest["boards"] for image in board["images"]
    } == {"copy"}


def test_publish_fingerprint_is_independent_of_hardlink_or_copy(tmp_path: Path) -> None:
    linked_root = tmp_path / "linked"
    copied_root = tmp_path / "copied"
    linked_root.mkdir()
    copied_root.mkdir()
    linked_report = _write_report(linked_root, period="daily", run_date=date(2026, 7, 12))
    copied_report = _write_report(copied_root, period="daily", run_date=date(2026, 7, 12))

    linked = build_publish_bundle(_settings(linked_root, prefer_hardlinks=True), linked_report)
    linked_manifest = json.loads(linked.manifest.read_text(encoding="utf-8"))

    copied = build_publish_bundle(_settings(copied_root, prefer_hardlinks=False), copied_report)
    copied_manifest = json.loads(copied.manifest.read_text(encoding="utf-8"))

    assert linked_manifest["content_fingerprint"] == copied_manifest["content_fingerprint"]
    assert {
        image["materialization"] for board in copied_manifest["boards"] for image in board["images"]
    } == {"copy"}


def test_build_publish_bundle_rejects_unsafe_or_unpublishable_inputs(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    unsafe = _write_report(
        tmp_path,
        period="daily",
        run_date=date(2026, 7, 12),
        cover_override="../outside.png",
    )
    with pytest.raises(ValueError, match="must stay inside the repository"):
        build_publish_bundle(settings, unsafe)

    wrong_size = _write_report(
        tmp_path,
        period="daily",
        run_date=date(2026, 7, 13),
        image_size=(600, 800),
    )
    with pytest.raises(ValueError, match="must be 1200x1600"):
        build_publish_bundle(settings, wrong_size)

    invalid_editorial = {
        "policy": "facts-locked-batch-editing",
        "boards": {
            board: {
                "prompt_version": "4.0",
                "schema_version": "4.0",
                "requested_backend": "codex-cli",
                "used_backend": "deterministic",
                "fallback_used": False,
                "error_category": None,
            }
            for board in ("comprehensive", "ai")
        },
    }
    bad_editorial_report = _write_report(
        tmp_path,
        period="daily",
        run_date=date(2026, 7, 14),
        editorial_override=invalid_editorial,
    )
    with pytest.raises(ValueError, match="backend mismatch without fallback"):
        build_publish_bundle(settings, bad_editorial_report)

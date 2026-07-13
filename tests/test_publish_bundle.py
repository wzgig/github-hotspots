import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest
import yaml
from PIL import Image

import github_hotspots.publish_bundle as publish_bundle_module
from github_hotspots.config import Settings, load_settings
from github_hotspots.publish_bundle import (
    build_publish_bundle,
    publication_issue,
    refresh_history_index,
)


def _settings(tmp_path: Path) -> Settings:
    document = yaml.safe_load(Path("config/hotspots.yaml").read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    publication = document["publication"]
    assert isinstance(publication, dict)
    publication["root_dir"] = "publish"
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
        _write_png(project, size=image_size, color="#F5F0E8")
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
        "assets": {
            "enabled": True,
            "width": image_size[0],
            "height": image_size[1],
            "manifest": manifest_path.relative_to(tmp_path).as_posix(),
        },
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
        "width": image_size[0],
        "height": image_size[1],
        "boards": manifest_boards,
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report_path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rewrite_with_crlf(path: Path) -> None:
    value = path.read_text(encoding="utf-8")
    normalized = value.replace("\r\n", "\n").replace("\r", "\n")
    path.write_bytes(normalized.replace("\n", "\r\n").encode("utf-8"))


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
        "version": "1.1",
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
            assert image["materialization"] == "copy"

    today = daily.today.read_text(encoding="utf-8")
    assert "日报 · D001" in today
    assert "周报 · W001" in today
    assert "D001-C" in today and "D001-A" in today
    assert "W001-C" in today and "W001-A" in today
    assert (tmp_path / "publish" / "logs" / "publication.jsonl").is_file()

    daily_history = daily.history_dir
    assert daily_history == (
        tmp_path
        / "publish"
        / "history"
        / "daily"
        / "2026"
        / "2026-07-12"
        / manifest["content_fingerprint"][:12]
    )
    history_manifest = json.loads(daily.history_manifest.read_text(encoding="utf-8"))
    assert history_manifest["history"] == {
        "schema_version": 1,
        "kind": "thin-publication-history",
        "report_stem": "2026-07-12",
        "revision": manifest["content_fingerprint"][:12],
        "image_policy": "repository-source-reference",
    }
    assert not list(daily_history.rglob("*.png"))
    assert {
        path.relative_to(daily_history).as_posix()
        for path in daily_history.rglob("*")
        if path.is_file()
    } == {
        "MANIFEST.json",
        "CHECKLIST.md",
        "01-comprehensive/TITLE.txt",
        "01-comprehensive/CAPTION.txt",
        "01-comprehensive/REVIEW.md",
        "02-ai/TITLE.txt",
        "02-ai/CAPTION.txt",
        "02-ai/REVIEW.md",
    }
    for board in history_manifest["boards"]:
        for image in board["images"]:
            assert "path" not in image
            assert "materialization" not in image
            assert image["source"].startswith("reports/daily/assets/2026-07-12/")
            assert _sha256(tmp_path / image["source"]) == image["sha256"]

    history_index = json.loads(daily.history_index_json.read_text(encoding="utf-8"))
    assert [(item["period"], item["issue"]["code"]) for item in history_index["issues"]] == [
        ("daily", "D001"),
        ("weekly", "W001"),
    ]
    assert all(item["latest"] in item["revisions"] for item in history_index["issues"])
    history_markdown = daily.history_index_markdown.read_text(encoding="utf-8")
    assert "D001" in history_markdown
    assert "W001" in history_markdown
    assert "/01-comprehensive/CAPTION.txt)" in history_markdown
    assert "/02-ai/CAPTION.txt)" in history_markdown


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


def test_same_fingerprint_reuses_intact_current_and_history(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    report = _write_report(tmp_path, period="daily", run_date=date(2026, 7, 12))

    first = build_publish_bundle(settings, report)
    first_index = first.history_index_json.read_bytes()
    second = build_publish_bundle(settings, report)

    assert second.current_dir == first.current_dir
    assert second.history_dir == first.history_dir
    assert second.archived_dir is None
    assert second.history_index_json.read_bytes() == first_index
    assert not (tmp_path / "publish" / "archive").exists()
    revisions = list((tmp_path / "publish" / "history" / "daily" / "2026" / "2026-07-12").iterdir())
    assert revisions == [first.history_dir]


def test_publish_hashes_are_stable_across_lf_and_crlf_checkouts(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    report = _write_report(tmp_path, period="daily", run_date=date(2026, 7, 12))
    first = build_publish_bundle(settings, report)
    assert first.current_dir is not None

    poster_manifest = tmp_path / "reports" / "daily" / "assets" / "2026-07-12" / "manifest.json"
    for path in (report, poster_manifest):
        _rewrite_with_crlf(path)
    for root in (first.current_dir, first.history_dir):
        for path in root.rglob("*"):
            if path.is_file() and path.suffix.casefold() in {".json", ".md", ".txt"}:
                _rewrite_with_crlf(path)

    rebuilt = build_publish_bundle(settings, report)

    assert rebuilt.history_dir == first.history_dir
    assert rebuilt.archived_dir is None
    assert not (tmp_path / "publish" / "archive").exists()


@pytest.mark.parametrize("damage", ["caption", "image"])
def test_same_fingerprint_does_not_reuse_modified_or_missing_current(
    tmp_path: Path,
    damage: str,
) -> None:
    settings = _settings(tmp_path)
    report = _write_report(tmp_path, period="daily", run_date=date(2026, 7, 12))
    first = build_publish_bundle(settings, report)
    assert first.current_dir is not None
    original_caption = (first.current_dir / "01-comprehensive" / "CAPTION.txt").read_text(
        encoding="utf-8"
    )
    if damage == "caption":
        (first.current_dir / "01-comprehensive" / "CAPTION.txt").write_text(
            "人工修改后的待发布文案\n",
            encoding="utf-8",
        )
    else:
        next((first.current_dir / "01-comprehensive" / "images").glob("*.png")).unlink()

    rebuilt = build_publish_bundle(settings, report)

    assert rebuilt.archived_dir is not None
    assert rebuilt.current_dir is not None
    assert (rebuilt.current_dir / "01-comprehensive" / "CAPTION.txt").read_text(
        encoding="utf-8"
    ) == original_caption
    assert len(list(rebuilt.history_dir.parent.iterdir())) == 1
    if damage == "caption":
        assert (rebuilt.archived_dir / "01-comprehensive" / "CAPTION.txt").read_text(
            encoding="utf-8"
        ) == "人工修改后的待发布文案\n"


def test_changed_fingerprint_creates_revision_without_overwriting_history(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    report = _write_report(tmp_path, period="daily", run_date=date(2026, 7, 12))
    first = build_publish_bundle(settings, report)
    report_data = json.loads(report.read_text(encoding="utf-8"))
    report_data["boards"]["comprehensive"]["repositories"][0]["summary"]["one_line"] = (
        "把重复开发任务变成可检查的自动化流水线"
    )
    report.write_text(
        json.dumps(report_data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    revised = build_publish_bundle(settings, report)

    assert revised.history_dir != first.history_dir
    assert first.history_dir.is_dir()
    assert revised.history_dir.is_dir()
    assert len(list(revised.history_dir.parent.iterdir())) == 2
    index = json.loads(revised.history_index_json.read_text(encoding="utf-8"))
    daily = next(item for item in index["issues"] if item["period"] == "daily")
    assert len(daily["revisions"]) == 2
    assert (
        daily["latest"]["fingerprint"]
        == json.loads(revised.history_manifest.read_text(encoding="utf-8"))["content_fingerprint"]
    )


def test_history_only_repairs_corrupt_existing_revision(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    report = _write_report(tmp_path, period="daily", run_date=date(2026, 7, 12))
    first = build_publish_bundle(settings, report)
    damaged = first.history_dir / "01-comprehensive" / "CAPTION.txt"
    expected = damaged.read_text(encoding="utf-8")
    damaged.write_text("corrupt history\n", encoding="utf-8")

    repaired = build_publish_bundle(settings, report, activate_current=False)

    assert repaired.history_dir == first.history_dir
    assert damaged.read_text(encoding="utf-8") == expected
    assert [path.name for path in repaired.history_dir.parent.iterdir()] == [
        repaired.history_dir.name
    ]


def test_history_repair_survives_locked_quarantine_cleanup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(tmp_path)
    report = _write_report(tmp_path, period="daily", run_date=date(2026, 7, 12))
    first = build_publish_bundle(settings, report)
    damaged = first.history_dir / "01-comprehensive" / "CAPTION.txt"
    expected = damaged.read_text(encoding="utf-8")
    damaged.write_text("corrupt history\n", encoding="utf-8")
    original_rmtree = publish_bundle_module.shutil.rmtree

    def locked_quarantine(path: Path, *args: Any, **kwargs: Any) -> None:
        candidate = Path(path)
        if "history-recovery" in candidate.parts:
            raise OSError("simulated Windows file lock")
        original_rmtree(path, *args, **kwargs)

    monkeypatch.setattr(publish_bundle_module.shutil, "rmtree", locked_quarantine)

    repaired = build_publish_bundle(settings, report, activate_current=False)

    assert repaired.history_dir == first.history_dir
    assert damaged.read_text(encoding="utf-8") == expected
    refresh_history_index(tmp_path / "publish")
    assert [path.name for path in repaired.history_dir.parent.iterdir()] == [
        repaired.history_dir.name
    ]
    recovery_root = (
        tmp_path / "publish" / "archive" / "history-recovery" / "daily" / "2026" / "2026-07-12"
    )
    assert len(list(recovery_root.iterdir())) == 1


def test_history_only_backfill_does_not_downgrade_current(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    older_report = _write_report(tmp_path, period="daily", run_date=date(2026, 7, 12))
    newer_report = _write_report(tmp_path, period="daily", run_date=date(2026, 7, 13))
    current = build_publish_bundle(settings, newer_report)
    assert current.current_dir is not None

    with pytest.raises(ValueError, match="refusing to activate older daily report"):
        build_publish_bundle(settings, older_report)

    history = build_publish_bundle(settings, older_report, activate_current=False)
    assert history.activated_current is False
    assert history.current_dir is None
    assert history.manifest is None
    assert history.board_dirs == ()
    assert history.history_dir.is_dir()
    assert (
        json.loads((current.current_dir / "MANIFEST.json").read_text(encoding="utf-8"))["issue"][
            "code"
        ]
        == "D002"
    )

    activated = build_publish_bundle(
        settings,
        older_report,
        allow_older_current=True,
    )
    assert activated.activated_current is True
    assert activated.archived_dir is not None
    assert activated.manifest is not None
    assert json.loads(activated.manifest.read_text(encoding="utf-8"))["issue"]["code"] == "D001"


def test_history_indexes_can_be_rebuilt_from_revision_manifests(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    report = _write_report(tmp_path, period="daily", run_date=date(2026, 7, 12))
    artifacts = build_publish_bundle(settings, report, activate_current=False)
    expected_json = artifacts.history_index_json.read_bytes()
    expected_markdown = artifacts.history_index_markdown.read_bytes()
    artifacts.history_index_json.unlink()
    artifacts.history_index_markdown.unlink()

    json_path, markdown_path = refresh_history_index(tmp_path / "publish")

    assert json_path.read_bytes() == expected_json
    assert markdown_path.read_bytes() == expected_markdown


def test_build_publish_bundle_marks_prelaunch_report_as_preview(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    report = _write_report(tmp_path, period="daily", run_date=date(2026, 7, 11))

    artifacts = build_publish_bundle(settings, report)
    manifest = json.loads(artifacts.manifest.read_text(encoding="utf-8"))

    assert artifacts.issue_code == "D-PREVIEW"
    assert manifest["status"] == "preview"
    assert manifest["issue"]["number"] is None
    assert all(board["status"] == "preview" for board in manifest["boards"])


def test_publish_workbench_images_are_independent_copies(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    report = _write_report(tmp_path, period="daily", run_date=date(2026, 7, 12))
    artifacts = build_publish_bundle(settings, report)
    manifest = json.loads(artifacts.manifest.read_text(encoding="utf-8"))
    board = manifest["boards"][0]
    image = board["images"][0]
    packaged = artifacts.current_dir / board["directory"] / image["path"]
    source = tmp_path / image["source"]
    source_hash = _sha256(source)

    assert {
        image["materialization"] for board in manifest["boards"] for image in board["images"]
    } == {"copy"}
    packaged.write_bytes(b"human-edited-working-copy")
    assert _sha256(source) == source_hash

    rebuilt = build_publish_bundle(settings, report)

    assert rebuilt.archived_dir is not None
    assert _sha256(source) == source_hash
    assert _sha256(rebuilt.current_dir / board["directory"] / image["path"]) == source_hash


def test_build_publish_bundle_accepts_configured_legal_poster_dimensions(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    report = _write_report(
        tmp_path,
        period="daily",
        run_date=date(2026, 7, 12),
        image_size=(600, 800),
    )

    artifacts = build_publish_bundle(settings, report)
    manifest = json.loads(artifacts.manifest.read_text(encoding="utf-8"))

    assert {
        (image["width"], image["height"])
        for board in manifest["boards"]
        for image in board["images"]
    } == {(600, 800)}


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
        image_size=(601, 800),
    )
    with pytest.raises(ValueError, match="3:4"):
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

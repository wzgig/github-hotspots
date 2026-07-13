from pathlib import Path
from types import SimpleNamespace

from typer.testing import CliRunner

from github_hotspots import cli
from github_hotspots.config import load_settings
from github_hotspots.report import ReportArtifacts


def test_run_command_reports_both_boards_and_review_files(monkeypatch) -> None:
    settings = load_settings(Path("config/hotspots.yaml"))
    artifacts = ReportArtifacts(
        markdown=Path("reports/daily/2026-07-11.md"),
        json=Path("reports/daily/2026-07-11.json"),
        xiaohongshu=Path("reports/daily/2026-07-11.xiaohongshu.md"),
        ai_xiaohongshu=Path("reports/daily/2026-07-11.ai.xiaohongshu.md"),
        posters_dir=Path("reports/daily/assets/2026-07-11"),
        poster_manifest=Path("reports/daily/assets/2026-07-11/manifest.json"),
        poster_files=(Path("reports/daily/assets/2026-07-11/cover.png"),),
        warnings=(),
    )
    result = SimpleNamespace(
        period="daily",
        candidate_count=20,
        ranked_count=3,
        ai_ranked_count=3,
        snapshot=Path("data/snapshots/2026-07-11.json"),
        artifacts=artifacts,
        warnings=(),
    )
    monkeypatch.setattr(cli, "load_settings", lambda _: settings)
    monkeypatch.setattr(cli, "run_pipeline", lambda *_, **__: result)

    response = CliRunner().invoke(cli.app, ["run", "--date", "2026-07-11"])

    assert response.exit_code == 0
    assert "综合主榜: Top 3" in response.output
    assert "AI 专题榜: Top 3" in response.output
    assert "2026-07-11.xiaohongshu.md" in response.output
    assert "2026-07-11.ai.xiaohongshu.md" in response.output
    assert "Poster PNG files: 1" in response.output


def test_rerender_command_can_refresh_readme_and_avatar_evidence(monkeypatch) -> None:
    settings = load_settings(Path("config/hotspots.yaml"))
    artifacts = ReportArtifacts(
        markdown=Path("reports/daily/2026-07-11.md"),
        json=Path("reports/daily/2026-07-11.json"),
        xiaohongshu=Path("reports/daily/2026-07-11.xiaohongshu.md"),
        ai_xiaohongshu=Path("reports/daily/2026-07-11.ai.xiaohongshu.md"),
        posters_dir=Path("reports/daily/assets/2026-07-11"),
        poster_manifest=None,
        poster_files=(),
        warnings=(),
    )
    captured = {}

    monkeypatch.setattr(cli, "load_settings", lambda _: settings)

    def fake_rerender(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return artifacts

    monkeypatch.setattr(cli, "rerender_report", fake_rerender)

    response = CliRunner().invoke(
        cli.app,
        [
            "rerender",
            "reports/daily/2026-07-11.json",
            "--editorial-backend",
            "codex-cli",
            "--refresh-evidence",
        ],
    )

    assert response.exit_code == 0
    assert captured["kwargs"]["editorial_backend"] == "codex-cli"
    assert captured["kwargs"]["refresh_evidence"] is True


def test_publish_command_reports_local_board_packages(monkeypatch) -> None:
    settings = load_settings(Path("config/hotspots.yaml"))
    artifacts = SimpleNamespace(
        period="daily",
        issue_code="D001",
        current_dir=Path("publish/current/daily"),
        manifest=Path("publish/current/daily/MANIFEST.json"),
        checklist=Path("publish/current/daily/CHECKLIST.md"),
        today=Path("publish/current/TODAY.md"),
        board_dirs=(
            Path("publish/current/daily/01-comprehensive"),
            Path("publish/current/daily/02-ai"),
        ),
        archived_dir=None,
        history_dir=Path("publish/history/daily/2026/2026-07-12/abcdef123456"),
        history_manifest=Path("publish/history/daily/2026/2026-07-12/abcdef123456/MANIFEST.json"),
        history_index_json=Path("publish/history/INDEX.json"),
        history_index_markdown=Path("publish/history/INDEX.md"),
        activated_current=True,
    )
    captured = {}

    monkeypatch.setattr(cli, "load_settings", lambda _: settings)

    def fake_build(settings_arg, report_arg, **kwargs):
        captured["settings"] = settings_arg
        captured["report"] = report_arg
        captured["kwargs"] = kwargs
        return artifacts

    monkeypatch.setattr(cli, "build_publish_bundle", fake_build)

    response = CliRunner().invoke(
        cli.app,
        ["publish", "reports/daily/2026-07-12.json"],
    )

    assert response.exit_code == 0
    assert captured["settings"] is settings
    assert captured["report"] == Path("reports/daily/2026-07-12.json")
    assert captured["kwargs"] == {
        "activate_current": True,
        "allow_older_current": False,
    }
    assert "Prepared D001 daily publication bundle" in response.output
    assert "History revision:" in response.output
    normalized_output = response.output.replace("\\", "/")
    assert "publish/history/INDEX.json" in normalized_output
    assert "Board packages: 2" in response.output
    assert "Today index:" in response.output
    assert "TODAY.md" in response.output


def test_publish_command_history_only_does_not_activate_current(monkeypatch) -> None:
    settings = load_settings(Path("config/hotspots.yaml"))
    artifacts = SimpleNamespace(
        period="daily",
        issue_code="D001",
        current_dir=None,
        manifest=None,
        checklist=None,
        today=Path("publish/current/TODAY.md"),
        board_dirs=(),
        archived_dir=None,
        history_dir=Path("publish/history/daily/2026/2026-07-12/abcdef123456"),
        history_manifest=Path("publish/history/daily/2026/2026-07-12/abcdef123456/MANIFEST.json"),
        history_index_json=Path("publish/history/INDEX.json"),
        history_index_markdown=Path("publish/history/INDEX.md"),
        activated_current=False,
    )
    captured = {}
    monkeypatch.setattr(cli, "load_settings", lambda _: settings)

    def fake_build(settings_arg, report_arg, **kwargs):
        captured["kwargs"] = kwargs
        return artifacts

    monkeypatch.setattr(cli, "build_publish_bundle", fake_build)

    response = CliRunner().invoke(
        cli.app,
        ["publish", "reports/daily/2026-07-12.json", "--history-only"],
    )

    assert response.exit_code == 0
    assert captured["kwargs"] == {
        "activate_current": False,
        "allow_older_current": False,
    }
    assert "History-only mode: publish/current was not changed." in response.output
    assert "Current folder:" not in response.output


def test_publish_command_rejects_conflicting_history_options(monkeypatch) -> None:
    monkeypatch.setattr(cli, "load_settings", lambda _: None)

    response = CliRunner().invoke(
        cli.app,
        [
            "publish",
            "reports/daily/2026-07-12.json",
            "--history-only",
            "--activate-older",
        ],
    )

    assert response.exit_code == 1
    assert "cannot be combined" in response.output


def test_publish_history_index_command_rebuilds_indexes(monkeypatch) -> None:
    settings = load_settings(Path("config/hotspots.yaml"))
    captured = {}
    monkeypatch.setattr(cli, "load_settings", lambda _: settings)

    def fake_refresh(root):
        captured["root"] = root
        return Path("publish/history/INDEX.json"), Path("publish/history/INDEX.md")

    monkeypatch.setattr(cli, "refresh_history_index", fake_refresh)

    response = CliRunner().invoke(cli.app, ["publish-history-index"])

    assert response.exit_code == 0
    assert captured["root"] == settings.publication_settings().root_dir
    normalized_output = response.output.replace("\\", "/")
    assert "publish/history/INDEX.json" in normalized_output
    assert "publish/history/INDEX.md" in normalized_output

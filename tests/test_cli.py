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

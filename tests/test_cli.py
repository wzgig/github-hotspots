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
    monkeypatch.setattr(cli, "run_pipeline", lambda *_: result)

    response = CliRunner().invoke(cli.app, ["run", "--date", "2026-07-11"])

    assert response.exit_code == 0
    assert "综合主榜: Top 3" in response.output
    assert "AI 专题榜: Top 3" in response.output
    assert "2026-07-11.xiaohongshu.md" in response.output
    assert "2026-07-11.ai.xiaohongshu.md" in response.output

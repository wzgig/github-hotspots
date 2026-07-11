import json
from datetime import date
from pathlib import Path

from github_hotspots.config import Settings
from github_hotspots.models import RankedRepository, Repository
from github_hotspots.report import render_reports


def _settings(tmp_path: Path) -> Settings:
    config_path = tmp_path / "config" / "hotspots.yaml"
    config_path.parent.mkdir(parents=True)
    return Settings(
        path=config_path,
        timezone="Asia/Shanghai",
        github={},
        outputs={
            "snapshots_dir": "data/snapshots",
            "daily_reports_dir": "reports/daily",
            "weekly_reports_dir": "reports/weekly",
        },
        runs={
            "daily": {"period": "daily", "top_n": 3, "lookback_days": 1},
            "weekly": {"period": "weekly", "top_n": 7, "lookback_days": 7},
        },
        sources={},
        filters={},
        ranking={"weights": {}},
    )


def test_render_reports_writes_markdown_json_and_xhs_copy(tmp_path: Path) -> None:
    repository = Repository(
        repository_id=42,
        full_name="example/hot-repo",
        html_url="https://github.com/example/hot-repo",
        description="A practical developer automation toolkit.",
        language="Python",
        stars=1_200,
        forks=80,
        topics=("automation", "developer-tools"),
    )
    ranked = RankedRepository(
        repository=repository,
        rank=1,
        score=91.5,
        star_delta=125,
        fork_delta=4,
        delta_source="snapshot",
        component_percentiles={"star_growth": 100.0},
    )

    artifacts = render_reports(
        settings=_settings(tmp_path),
        period="daily",
        run_date=date(2026, 7, 11),
        rankings=[ranked],
        template_dir=Path("templates"),
    )

    payload = json.loads(artifacts.json.read_text(encoding="utf-8"))
    markdown = artifacts.markdown.read_text(encoding="utf-8")
    xhs = artifacts.xiaohongshu.read_text(encoding="utf-8")
    assert payload["repositories"][0]["full_name"] == "example/hot-repo"
    assert payload["repositories"][0]["summary"]["highlights"]
    assert "快照净增 Star" in markdown
    assert "https://github.com/example/hot-repo" in xhs


def test_estimated_delta_is_explicitly_labeled(tmp_path: Path) -> None:
    ranked = RankedRepository(
        repository=Repository(
            full_name="example/first-run",
            html_url="https://github.com/example/first-run",
            description="Example repository.",
            stars=100,
            forks=5,
        ),
        rank=1,
        score=50,
        star_delta=3,
        delta_source="estimate",
    )

    artifacts = render_reports(
        settings=_settings(tmp_path),
        period="daily",
        run_date=date(2026, 7, 11),
        rankings=[ranked],
        template_dir=Path("templates"),
    )

    markdown = artifacts.markdown.read_text(encoding="utf-8")
    xhs = artifacts.xiaohongshu.read_text(encoding="utf-8")
    assert "估算周期 Star" in markdown
    assert "约 +3" in xhs

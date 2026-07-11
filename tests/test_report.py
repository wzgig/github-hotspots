import json
from datetime import date
from pathlib import Path

from github_hotspots.config import Settings
from github_hotspots.models import RankedRepository, Repository
from github_hotspots.report import render_reports


def _settings(tmp_path: Path, *, ai_enabled: bool = True) -> Settings:
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
        boards={
            "comprehensive": {
                "enabled": True,
                "label": "综合主榜",
                "daily_top_n": 3,
                "weekly_top_n": 7,
            },
            "ai": {
                "enabled": ai_enabled,
                "label": "AI 专题榜",
                "daily_top_n": 3,
                "weekly_top_n": 7,
                "topics": ["machine-learning"],
                "keywords": ["ai", "machine learning"],
            },
        },
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
    ai_ranked = RankedRepository(
        repository=Repository(
            repository_id=43,
            full_name="example/ai-lab",
            html_url="https://github.com/example/ai-lab",
            description="A machine learning experimentation toolkit.",
            language="Python",
            stars=900,
            forks=40,
            topics=("machine-learning",),
        ),
        rank=1,
        score=88.0,
        star_delta=80,
        fork_delta=3,
        delta_source="trending",
        component_percentiles={"star_growth": 100.0},
    )

    artifacts = render_reports(
        settings=_settings(tmp_path),
        period="daily",
        run_date=date(2026, 7, 11),
        rankings=[ranked],
        ai_rankings=[ai_ranked],
        template_dir=Path("templates"),
    )

    payload = json.loads(artifacts.json.read_text(encoding="utf-8"))
    markdown = artifacts.markdown.read_text(encoding="utf-8")
    xhs = artifacts.xiaohongshu.read_text(encoding="utf-8")
    ai_xhs = artifacts.ai_xiaohongshu.read_text(encoding="utf-8")
    assert payload["schema_version"] == 2
    assert payload["repositories"][0]["full_name"] == "example/hot-repo"
    assert payload["repositories"][0]["summary"]["highlights"]
    assert payload["repositories"] == payload["boards"]["comprehensive"]["repositories"]
    assert payload["boards"]["comprehensive"]["label"] == "综合主榜"
    assert payload["boards"]["ai"]["repositories"][0]["full_name"] == "example/ai-lab"
    assert "## 综合主榜 Top 3" in markdown
    assert "## AI 专题榜 Top 3" in markdown
    assert "快照净增 Star" in markdown
    assert "https://github.com/example/hot-repo" in xhs
    assert "https://github.com/example/ai-lab" in ai_xhs
    assert artifacts.ai_xiaohongshu.name == "2026-07-11.ai.xiaohongshu.md"


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
    assert "本期没有符合 AI 专题口径的候选项目" in markdown
    assert "约 +3" in xhs


def test_disabled_ai_board_has_no_missing_candidate_warning(tmp_path: Path) -> None:
    ranked = RankedRepository(
        repository=Repository(
            full_name="example/general-tool",
            html_url="https://github.com/example/general-tool",
            description="General developer tooling.",
            stars=100,
        ),
        rank=1,
        score=50,
        star_delta=10,
        delta_source="trending",
    )

    artifacts = render_reports(
        settings=_settings(tmp_path, ai_enabled=False),
        period="daily",
        run_date=date(2026, 7, 11),
        rankings=[ranked],
        template_dir=Path("templates"),
    )

    markdown = artifacts.markdown.read_text(encoding="utf-8")
    payload = json.loads(artifacts.json.read_text(encoding="utf-8"))
    assert "当前配置已停用 AI 专题榜" in markdown
    assert "AI 专题榜：没有仓库通过当前筛选条件" not in markdown
    assert payload["boards"]["ai"]["repositories"] == []

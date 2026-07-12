import json
from datetime import date
from pathlib import Path

import pytest

from github_hotspots import report as report_module
from github_hotspots.config import Settings
from github_hotspots.evidence import (
    CachedAvatar,
    RepositoryEvidence,
    RepositoryMetadataEvidence,
)
from github_hotspots.models import RankedRepository, Repository
from github_hotspots.poster import (
    POSTER_RENDERER_NAME,
    POSTER_RENDERER_VERSION,
    POSTER_STYLE_VERSION,
    PosterArtifacts,
)
from github_hotspots.publication_evidence import PublicationEvidenceBundle
from github_hotspots.report import render_reports
from github_hotspots.summarizer import RepositorySummary


def _settings(
    tmp_path: Path,
    *,
    ai_enabled: bool = True,
    posters_enabled: bool = False,
) -> Settings:
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
        posters={
            "enabled": posters_enabled,
            "width": 600,
            "height": 800,
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
        run_date=date(2026, 7, 12),
        rankings=[ranked],
        ai_rankings=[ai_ranked],
        template_dir=Path("templates"),
    )

    payload = json.loads(artifacts.json.read_text(encoding="utf-8"))
    markdown = artifacts.markdown.read_text(encoding="utf-8")
    xhs = artifacts.xiaohongshu.read_text(encoding="utf-8")
    ai_xhs = artifacts.ai_xiaohongshu.read_text(encoding="utf-8")
    assert payload["schema_version"] == 3
    assert payload["publication"] == {
        "issue_number": 1,
        "issue_code": "D001",
        "issue_label": "第1期",
        "status": "official",
    }
    assert payload["editorial"]["boards"]["comprehensive"]["used_backend"] == ("deterministic")
    assert payload["assets"]["enabled"] is False
    assert payload["repositories"][0]["full_name"] == "example/hot-repo"
    assert payload["repositories"][0]["summary"]["highlights"]
    assert payload["repositories"] == payload["boards"]["comprehensive"]["repositories"]
    assert payload["boards"]["comprehensive"]["label"] == "综合主榜"
    assert payload["boards"]["ai"]["repositories"][0]["full_name"] == "example/ai-lab"
    assert "## 综合主榜 Top 3" in markdown
    assert "## AI 专题榜 Top 3" in markdown
    assert "快照净增 Star" in markdown
    assert "GitHub 日报 D001｜3 个项目到底能做什么" in xhs
    assert "GitHub AI 日报 D001｜3 个项目到底能做什么" in ai_xhs
    assert "它能做什么：" in xhs
    assert "为什么本期上榜：过去 24 小时净增 +125 Star" in xhs
    assert "GitHub 搜索：example/hot-repo" in xhs
    assert "GitHub 搜索：example/ai-lab" in ai_xhs
    assert "https://github.com/" not in xhs
    assert "https://github.com/" not in ai_xhs
    assert "AI 辅助整理，发布前需人工审核" in xhs
    assert artifacts.ai_xiaohongshu.name == "2026-07-12.ai.xiaohongshu.md"


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
    assert "过去 24 小时估算约 +3 Star（待后续快照核验）" in xhs


def test_rich_evidence_copy_and_avatar_metadata_flow_into_publication(tmp_path: Path) -> None:
    repository = Repository(
        repository_id=42,
        full_name="example/research-kit",
        html_url="https://github.com/example/research-kit",
        description="Research workflows for Claude Code.",
        language="Python",
        stars=3_000,
        forks=240,
    )
    ranked = RankedRepository(
        repository=repository,
        rank=1,
        score=92.0,
        star_delta=180,
        delta_source="snapshot",
    )
    summary = RepositorySummary(
        one_line="一套把调研、写作、评审和返修串起来的研究工作流。",
        highlights=("检索并梳理文献", "规划和撰写论文", "从多个视角审查初稿"),
        audience="需要完成综述、初稿审查或返修的研究人员与学生",
        capabilities=(
            "完成快速研究与事实核查",
            "整理普通或系统性文献综述",
            "规划论文结构并生成初稿",
            "从多个角色审查论文质量",
            "串联修订、复核与最终定稿",
        ),
        core_title="有人把关的研究流程",
        core_summary="它把多个研究技能串成阶段化流程，并在关键节点保留人工确认。",
        prerequisites="需要 Claude Code 和可用的模型 API Key",
        limitations="不是一键代写工具，研究方法、数据和结论仍需使用者确认",
        license_label="CC BY-NC 4.0",
        license_restrictions="署名，禁止商业使用",
        content_status="readme_enriched",
    )
    report_root = tmp_path / "reports" / "daily"
    avatar_path = report_root / "avatars" / "2026-07-11" / "owner.png"
    bundle = PublicationEvidenceBundle(
        repository_evidence=RepositoryEvidence(
            metadata=RepositoryMetadataEvidence(
                repository_id=42,
                full_name=repository.full_name,
                html_url=repository.html_url,
                owner_avatar_url="https://avatars.githubusercontent.com/u/42?v=4",
                license_spdx_id="NOASSERTION",
                default_branch="main",
                source_url="https://api.github.com/repos/example/research-kit",
            ),
            readme=None,
        ),
        avatar=CachedAvatar(
            path=avatar_path,
            sha256="a" * 64,
            width=96,
            height=96,
            source_url="https://avatars.githubusercontent.com/u/42?v=4",
        ),
        avatar_relative_path="avatars/2026-07-11/owner.png",
    )

    artifacts = render_reports(
        settings=_settings(tmp_path),
        period="daily",
        run_date=date(2026, 7, 11),
        rankings=[ranked],
        template_dir=Path("templates"),
        publication_evidence={repository.full_name: bundle},
        summary_overrides={"comprehensive": (summary,)},
        editorial_metadata_overrides={
            "comprehensive": {
                "prompt_version": "4.0",
                "schema_version": "4.0",
                "requested_backend": "codex-cli",
                "used_backend": "codex-cli",
                "fallback_used": False,
                "error_category": None,
            }
        },
    )

    payload = json.loads(artifacts.json.read_text(encoding="utf-8"))
    xhs = artifacts.xiaohongshu.read_text(encoding="utf-8")
    published = payload["repositories"][0]
    assert published["avatar_path"] == "avatars/2026-07-11/owner.png"
    assert published["license_spdx"] == "CC BY-NC 4.0"
    assert published["summary"]["capabilities"] == list(summary.capabilities)
    assert payload["editorial"]["boards"]["comprehensive"]["used_backend"] == "codex-cli"
    assert payload["editorial"]["boards"]["comprehensive"]["reused_existing_summary"] is True
    assert "串联修订、复核与最终定稿" in xhs
    assert "核心亮点：有人把关的研究流程" in xhs
    assert "许可证：CC BY-NC 4.0（署名，禁止商业使用）" in xhs
    assert "数据来自 GitHub 公开信息与本地快照" not in xhs


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


def test_render_reports_creates_manifest_and_per_repository_posters(tmp_path: Path) -> None:
    ranked = RankedRepository(
        repository=Repository(
            repository_id=42,
            full_name="example/poster-tool",
            html_url="https://github.com/example/poster-tool",
            description="A deterministic poster workflow.",
            language="Python",
            stars=1_200,
            forks=80,
            topics=("automation",),
        ),
        rank=1,
        score=91.5,
        star_delta=125,
        delta_source="snapshot",
    )

    stale = tmp_path / "reports" / "daily" / "assets" / "2026-07-11" / "stale.png"
    stale.parent.mkdir(parents=True)
    stale.write_bytes(b"old-poster")

    artifacts = render_reports(
        settings=_settings(tmp_path, posters_enabled=True),
        period="daily",
        run_date=date(2026, 7, 11),
        rankings=[ranked],
        template_dir=Path("templates"),
    )

    payload = json.loads(artifacts.json.read_text(encoding="utf-8"))
    manifest = json.loads(artifacts.poster_manifest.read_text(encoding="utf-8"))
    xhs = artifacts.xiaohongshu.read_text(encoding="utf-8")
    poster = payload["repositories"][0]["assets"]["poster"]
    assert artifacts.poster_manifest is not None
    assert artifacts.poster_manifest.is_file()
    assert len(artifacts.poster_files) == 3
    assert not stale.exists()
    assert (tmp_path / poster).is_file()
    assert payload["assets"]["width"] == 600
    assert payload["assets"]["manifest"] == ("reports/daily/assets/2026-07-11/manifest.json")
    assert payload["boards"]["comprehensive"]["top_n"] == 3
    assert payload["window_start"] == "2026-07-10"
    assert payload["window_end"] == "2026-07-11"
    assert payload["window_label"] == "2026-07-10 至 2026-07-11"
    assert manifest["schema_version"] == 2
    assert manifest["source_report"] == "reports/daily/2026-07-11.json"
    assert manifest["renderer"] == {
        "name": POSTER_RENDERER_NAME,
        "version": POSTER_RENDERER_VERSION,
    }
    assert manifest["style_version"] == POSTER_STYLE_VERSION
    assert manifest["publication"]["issue_code"] == "D-PREVIEW"
    assert manifest["window"] == {"start": "2026-07-10", "end": "2026-07-11"}
    assert manifest["boards"]["comprehensive"]["top_n"] == 3
    assert "# 配图清单（发布前人工审核）" in xhs
    assert poster in xhs


def test_failed_second_board_keeps_previous_poster_directory(
    tmp_path: Path,
    monkeypatch,
) -> None:
    target = tmp_path / "reports" / "daily" / "assets" / "2026-07-11"
    target.mkdir(parents=True)
    marker = target / "previous-manifest.json"
    marker.write_text('{"status":"complete"}\n', encoding="utf-8")

    ranked = RankedRepository(
        repository=Repository(
            full_name="example/atomic",
            html_url="https://github.com/example/atomic",
            description="Atomic poster test.",
            stars=100,
        ),
        rank=1,
        score=50,
        star_delta=10,
        delta_source="trending",
    )

    def fake_render_board_posters(**kwargs) -> PosterArtifacts:
        assert kwargs["issue_code"] == "D-PREVIEW"
        if kwargs["board_key"] == "ai":
            raise RuntimeError("simulated second-board failure")
        output_dir = Path(kwargs["output_dir"])
        output_dir.mkdir(parents=True, exist_ok=True)
        cover = output_dir / "2026-07-11.comprehensive.cover.png"
        cover.write_bytes(b"complete-cover")
        repositories = kwargs["repositories"]
        projects = []
        project_keys = []
        for repository in repositories:
            project = output_dir / "2026-07-11.comprehensive.01.example--atomic.png"
            project.write_bytes(b"complete-project")
            projects.append(project)
            project_keys.append((repository["rank"], repository["full_name"]))
        return PosterArtifacts(cover, tuple(projects), tuple(project_keys))

    monkeypatch.setattr(report_module, "render_board_posters", fake_render_board_posters)

    with pytest.raises(RuntimeError, match="simulated second-board failure"):
        render_reports(
            settings=_settings(tmp_path, posters_enabled=True),
            period="daily",
            run_date=date(2026, 7, 11),
            rankings=[ranked],
            ai_rankings=[ranked],
            template_dir=Path("templates"),
        )

    assert marker.read_text(encoding="utf-8") == '{"status":"complete"}\n'
    assert list(target.parent.glob(".2026-07-11.*.tmp")) == []


def test_report_matches_poster_paths_by_rank_and_repository_not_input_order(
    tmp_path: Path,
) -> None:
    first = RankedRepository(
        repository=Repository(
            full_name="example/first",
            html_url="https://github.com/example/first",
            description="First tool.",
            stars=200,
        ),
        rank=1,
        score=90,
        star_delta=20,
        delta_source="trending",
    )
    second = RankedRepository(
        repository=Repository(
            full_name="example/second",
            html_url="https://github.com/example/second",
            description="Second tool.",
            stars=100,
        ),
        rank=2,
        score=80,
        star_delta=10,
        delta_source="trending",
    )

    artifacts = render_reports(
        settings=_settings(tmp_path, posters_enabled=True),
        period="daily",
        run_date=date(2026, 7, 11),
        rankings=[second, first],
        template_dir=Path("templates"),
    )

    payload = json.loads(artifacts.json.read_text(encoding="utf-8"))
    paths = {
        repository["full_name"]: repository["assets"]["poster"]
        for repository in payload["repositories"]
    }
    assert paths["example/first"].endswith("01.example--first.png")
    assert paths["example/second"].endswith("02.example--second.png")

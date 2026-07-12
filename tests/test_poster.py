import json
import socket
from datetime import date
from pathlib import Path

import pytest
from PIL import Image

from github_hotspots import poster as poster_module
from github_hotspots.poster import (
    DEFAULT_POSTER_SIZE,
    PosterRepository,
    format_cover_growth_status,
    format_cover_selection_label,
    format_cover_window_label,
    format_delta_label,
    render_report_posters,
)


def _repository(rank: int, name: str, source: str) -> dict[str, object]:
    return {
        "rank": rank,
        "full_name": f"example/{name}",
        "html_url": f"https://github.com/example/{name}",
        "description": f"A deterministic workflow toolkit named {name}.",
        "language": "Python",
        "stars": 12_345 + rank,
        "forks": 678 + rank,
        "star_delta": 90 + rank,
        "delta_source": source,
        "summary": {
            "one_line": f"{name} 把重复开发步骤整理成可复用流程",
            "highlights": [
                "组合并重复执行常用开发任务",
                "保留本地可核对的执行结果",
                "让团队复用一致的工作流程",
            ],
            "audience": "需要减少重复操作的 Python 开发者与自动化团队",
        },
    }


def test_render_report_creates_cover_and_one_png_per_project_without_network(
    tmp_path: Path,
    monkeypatch,
) -> None:
    report_path = tmp_path / "2026-07-11.json"
    report_path.write_text(
        json.dumps(
            {
                "period": "daily",
                "run_date": "2026-07-11",
                "boards": {
                    "comprehensive": {
                        "label": "综合主榜",
                        "repositories": [
                            _repository(1, "alpha-tool", "snapshot"),
                            _repository(2, "beta-tool", "trending"),
                        ],
                    },
                    "ai": {
                        "label": "AI 专题榜",
                        "repositories": [_repository(1, "model-lab", "estimate")],
                    },
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    def reject_network(*args, **kwargs):
        raise AssertionError("poster rendering must not use the network")

    monkeypatch.setattr(socket, "create_connection", reject_network)
    output_dir = tmp_path / "posters"
    artifacts = render_report_posters(report_path, output_dir=output_dir)

    assert set(artifacts) == {"comprehensive", "ai"}
    assert len(artifacts["comprehensive"].projects) == 2
    assert len(artifacts["ai"].projects) == 1
    assert artifacts["comprehensive"].cover.name == "2026-07-11.comprehensive.cover.png"
    assert artifacts["comprehensive"].projects[0].name == (
        "2026-07-11.comprehensive.01.example--alpha-tool.png"
    )
    assert artifacts["ai"].projects[0].name == "2026-07-11.ai.01.example--model-lab.png"

    all_paths = [path for board in artifacts.values() for path in board.all_paths]
    assert len(all_paths) == 5
    for path in all_paths:
        assert path.is_file()
        with Image.open(path) as image:
            assert image.format == "PNG"
            assert image.size == DEFAULT_POSTER_SIZE


def test_delta_labels_keep_snapshot_trending_and_estimate_distinct() -> None:
    assert format_delta_label(120, "snapshot", "daily") == "已核验净增 Star +120"
    assert format_delta_label(-2, "snapshot", "weekly") == "快照差值 -2 Star（待核验）"
    assert format_delta_label(88, "trending", "daily") == "Trending 日周期 Star +88"
    assert format_delta_label(701, "trending", "weekly") == "Trending 周期 Star +701"
    assert format_delta_label(12, "estimate", "daily") == "估算日周期 Star +12"


def test_cover_contract_names_top_n_window_and_snapshot_quality() -> None:
    verified = PosterRepository.from_mapping(_repository(1, "verified", "snapshot"))
    pending_value = _repository(2, "pending", "snapshot")
    pending_value["star_delta"] = -2
    pending = PosterRepository.from_mapping(pending_value)
    trending = PosterRepository.from_mapping(_repository(3, "trending", "trending"))

    assert format_cover_selection_label(7, 3) == "Top 7 · 本期收录 3 个项目"
    assert format_cover_window_label(date(2026, 7, 4), date(2026, 7, 11)) == (
        "统计窗口 2026.07.04 — 2026.07.11"
    )
    assert format_cover_growth_status((verified, pending, trending)) == (
        "已核验净增 Star · 1 项使用历史快照；另 1 项待核验"
    )
    assert format_cover_growth_status((trending,)) == ("净增基线积累中 · 当前不标记精确新增")
    assert format_cover_growth_status((pending,)) == ("快照差值待核验 · 1 项暂不标记精确新增")


def test_renderer_fails_fast_when_no_cjk_font_is_available(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(poster_module, "_resolve_font_path", lambda *, bold: None)

    with pytest.raises(RuntimeError, match="No CJK-capable regular font"):
        poster_module.render_board_posters(
            board_key="comprehensive",
            board_label="综合主榜",
            period="daily",
            run_date="2026-07-11",
            repositories=[_repository(1, "alpha", "snapshot")],
            output_dir=tmp_path / "posters",
        )

    assert not (tmp_path / "posters").exists()


def test_renderer_rejects_existing_font_without_chinese_glyphs(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        poster_module,
        "_resolve_font_path",
        lambda *, bold: Path("DejaVuSans.ttf"),
    )

    with pytest.raises(RuntimeError, match="does not provide required Chinese glyphs"):
        poster_module.render_board_posters(
            board_key="comprehensive",
            board_label="综合主榜",
            period="daily",
            run_date="2026-07-11",
            repositories=[_repository(1, "alpha", "snapshot")],
            output_dir=tmp_path / "posters",
        )

    assert not (tmp_path / "posters").exists()


def test_weekly_filenames_use_iso_week_and_custom_portrait_size(tmp_path: Path) -> None:
    report_path = tmp_path / "weekly.json"
    report_path.write_text(
        json.dumps(
            {
                "period": "weekly",
                "run_date": "2026-07-11",
                "boards": {
                    "ai": {
                        "label": "AI 专题榜",
                        "repositories": [_repository(1, "agent-kit", "snapshot")],
                    }
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    artifacts = render_report_posters(
        report_path,
        output_dir=tmp_path / "posters",
        size=(1200, 1600),
    )["ai"]

    assert artifacts.cover.name == "2026-W28.ai.cover.png"
    assert artifacts.projects[0].name == "2026-W28.ai.01.example--agent-kit.png"
    with Image.open(artifacts.projects[0]) as image:
        assert image.size == (1200, 1600)


def test_v2_repository_prefers_explainer_fields_for_knowledge_card() -> None:
    value = _repository(1, "explainable-tool", "snapshot")
    value.update(
        {
            "plain_summary": "用普通中文说清项目解决的问题",
            "capabilities": [
                "把输入整理成结构化结果",
                "重复执行固定的处理步骤",
                "保留便于人工核对的输出",
            ],
            "core_value": "把复杂流程变成可重复任务",
            "why_hot": "过去 24 小时净增 +91 Star，来自快照核验",
        }
    )

    repository = PosterRepository.from_mapping(value)

    assert repository.short_description == "用普通中文说清项目解决的问题"
    assert repository.capabilities == (
        "把输入整理成结构化结果",
        "重复执行固定的处理步骤",
        "保留便于人工核对的输出",
    )
    assert repository.core_value == "把复杂流程变成可重复任务"
    assert repository.why_hot == "过去 24 小时净增 +91 Star，来自快照核验"


def test_v2_identity_block_is_deterministic_and_not_board_specific() -> None:
    assert poster_module._identity_token("catchorg/Catch2") == "C2"
    assert poster_module._identity_token("example/hermes-agent") == "HA"
    assert poster_module._identity_colours("example/hermes-agent") == (
        poster_module._identity_colours("example/hermes-agent")
    )


def test_v2_fixed_layout_keeps_regions_separate_and_long_name_fits() -> None:
    scale = 1200 / 1080
    layout = poster_module._project_layout(scale, size=(1200, 1600))

    assert layout.stats[1] > layout.hero[3]
    assert layout.capabilities[2] < layout.core[0]
    assert layout.core[3] < layout.audience[1]
    assert layout.why_hot[1] > layout.capabilities[3]

    image = Image.new("RGB", (1200, 1600), "white")
    draw = poster_module.ImageDraw.Draw(image)
    fonts = poster_module._FontBook(scale)
    long_name = "enterprise-agent-workflow-orchestration-toolkit"
    lines, truncated = poster_module._wrap_text_with_status(
        draw,
        long_name,
        fonts.get(40, bold=True),
        round(704 * scale),
        2,
    )

    assert len(lines) == 2
    assert truncated is False

    summary_lines, summary_truncated = poster_module._wrap_text_with_status(
        draw,
        (
            "这类任务可以交给 codex-plugin-cc：在 Claude Code 中调用 Codex "
            "审查代码或委派任务，并让两个编程助手在同一开发流程中分工"
        ),
        fonts.get(23, bold=True),
        round(704 * scale),
        3,
    )
    assert len(summary_lines) <= 3
    assert summary_truncated is False


def test_v2_card_uses_warm_paper_and_source_honest_growth(tmp_path: Path) -> None:
    report_path = tmp_path / "2026-07-11.json"
    report_path.write_text(
        json.dumps(
            {
                "period": "daily",
                "run_date": "2026-07-11",
                "boards": {
                    "comprehensive": {
                        "label": "综合主榜",
                        "repositories": [_repository(1, "knowledge-card", "snapshot")],
                    }
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    artifact = render_report_posters(report_path, output_dir=tmp_path / "posters")["comprehensive"]
    with Image.open(artifact.projects[0]) as image:
        assert image.getpixel((10, 10)) == poster_module._hex_to_rgb(
            poster_module._BOARD_THEMES["comprehensive"].header
        )
        assert image.getpixel((10, 800)) == poster_module._hex_to_rgb(
            poster_module._WARM_BACKGROUND
        )

    repository = PosterRepository.from_mapping(_repository(1, "verified", "snapshot"))
    assert poster_module._cover_growth_summary((repository,), "daily") == (
        "1 个项目均有快照基线，过去 24 小时合计净增 +91 Star。"
    )
    trending = PosterRepository.from_mapping(_repository(2, "trending", "trending"))
    assert poster_module._cover_growth_summary((repository, trending), "daily").startswith(
        "1/2 个项目具备可核验快照基线"
    )
    assert poster_module._why_hot_text(repository, "daily") == (
        "过去 24 小时净增 +91 Star（相邻快照核验）｜累计 12,346 Star"
    )
    assert poster_module._why_hot_text(trending, "weekly") == (
        "本期 GitHub Trending 显示 +92 Star｜不是快照净增"
    )
    assert poster_module._short_repository_link(repository) == "example/verified"

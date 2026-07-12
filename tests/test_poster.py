import json
import socket
from datetime import date
from pathlib import Path

import pytest
from PIL import Image, ImageChops

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


def test_v4_repository_accepts_editorial_fields_and_five_capabilities(
    tmp_path: Path,
) -> None:
    avatar_dir = tmp_path / "avatars"
    avatar_dir.mkdir()
    Image.new("RGB", (160, 100), "#176B54").save(avatar_dir / "owner.png")
    value = _repository(1, "explainable-tool", "snapshot")
    value.update(
        {
            "plain_summary": "用普通中文说清项目解决的问题",
            "capabilities": [
                "把输入整理成结构化结果",
                "重复执行固定的处理步骤",
                "保留便于人工核对的输出",
                "让团队复用同一套任务模板",
                "把结果导出给后续流程继续处理",
                "第六条应被安全裁掉",
            ],
            "core_title": "把复杂流程变成可重复任务",
            "core_summary": "把分散的操作步骤集中成一套可重复、可核对的处理流程。",
            "why_hot": "过去 24 小时净增 +91 Star，来自快照核验",
            "license": {"spdx_id": "Apache-2.0"},
            "avatar_path": "avatars/owner.png",
            "audience": "需要稳定复用复杂工作流的开发者与内容团队",
        }
    )

    repository = PosterRepository.from_mapping(value, avatar_root=tmp_path)

    assert repository.short_description == "用普通中文说清项目解决的问题"
    assert repository.capabilities == (
        "把输入整理成结构化结果",
        "重复执行固定的处理步骤",
        "保留便于人工核对的输出",
        "让团队复用同一套任务模板",
        "把结果导出给后续流程继续处理",
    )
    assert repository.core_title == "把复杂流程变成可重复任务"
    assert repository.core_summary == "把分散的操作步骤集中成一套可重复、可核对的处理流程。"
    assert repository.core_value == repository.core_title
    assert repository.why_hot == "过去 24 小时净增 +91 Star，来自快照核验"
    assert repository.license_spdx == "Apache-2.0"
    assert repository.avatar_path == (avatar_dir / "owner.png").resolve()
    assert repository.audience == "需要稳定复用复杂工作流的开发者与内容团队"


def test_v4_identity_block_is_deterministic_and_not_board_specific() -> None:
    assert poster_module._identity_token("catchorg/Catch2") == "C2"
    assert poster_module._identity_token("example/hermes-agent") == "HA"
    assert poster_module._identity_colours("example/hermes-agent") == (
        poster_module._identity_colours("example/hermes-agent")
    )


def test_v4_layout_stays_in_safe_single_column_flow() -> None:
    scale = 1200 / 1080
    layout = poster_module._project_layout(scale, size=(1200, 1600))

    regions = (
        layout.masthead,
        layout.identity,
        layout.signal_bar,
        layout.capabilities,
        layout.core,
        layout.audience,
    )
    for left, top, right, bottom in regions:
        assert 0 <= left < right <= 1200
        assert 0 <= top < bottom <= 1600

    assert layout.masthead[3] < layout.identity[1]
    assert layout.identity[3] < layout.signal_bar[1]
    assert layout.signal_bar[3] < layout.capabilities[1]
    assert layout.capabilities[3] < layout.core[1]
    assert layout.core[3] < layout.audience[1]
    assert layout.capabilities[0] == layout.core[0] == layout.audience[0]
    assert layout.capabilities[2] == layout.core[2] == layout.audience[2]
    assert layout.footer_y > layout.audience[3]
    assert layout.footer_y < 1600

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


def test_wrap_text_avoids_leading_closing_punctuation() -> None:
    image = Image.new("RGB", (600, 300), "white")
    draw = poster_module.ImageDraw.Draw(image)
    font = poster_module._FontBook(1.0).get(36, bold=True)
    max_width = round(draw.textlength("甲乙丙", font=font))

    lines, truncated = poster_module._wrap_text_with_status(
        draw,
        "甲乙丙，丁",
        font,
        max_width,
        2,
    )

    assert lines == ["甲乙", "丙，丁"]
    assert truncated is False
    assert all(line[0] not in poster_module._FORBIDDEN_LINE_START for line in lines)
    assert all(draw.textlength(line, font=font) <= max_width for line in lines)


def test_wrap_text_avoids_trailing_opening_punctuation() -> None:
    image = Image.new("RGB", (600, 300), "white")
    draw = poster_module.ImageDraw.Draw(image)
    font = poster_module._FontBook(1.0).get(36, bold=True)
    max_width = round(draw.textlength("甲乙“", font=font))

    lines, truncated = poster_module._wrap_text_with_status(
        draw,
        "甲乙“丙",
        font,
        max_width,
        2,
    )

    assert lines == ["甲乙", "“丙"]
    assert truncated is False
    assert all(line[-1] not in poster_module._FORBIDDEN_LINE_END for line in lines)
    assert all(draw.textlength(line, font=font) <= max_width for line in lines)


def test_wrap_quality_rejects_orphaned_han_character_before_punctuation() -> None:
    assert poster_module._has_orphaned_punctuation_lead(["词，方便查阅"]) is True
    assert poster_module._has_orphaned_punctuation_lead(["提示词，方便查阅"]) is False
    assert poster_module._has_orphaned_punctuation_lead(["方便集中查阅"]) is False


@pytest.mark.parametrize(
    "unsafe_path",
    (
        "https://example.com/avatar.png",
        "../outside.png",
        "avatars/../../outside.png",
    ),
)
def test_v4_avatar_path_rejects_urls_and_directory_escape(
    tmp_path: Path,
    unsafe_path: str,
) -> None:
    value = _repository(1, "unsafe-avatar", "snapshot")
    value["avatar_path"] = unsafe_path

    with pytest.raises(ValueError, match="avatar_path"):
        PosterRepository.from_mapping(value, avatar_root=tmp_path)


def test_v4_avatar_path_rejects_absolute_missing_and_unsupported_files(tmp_path: Path) -> None:
    value = _repository(1, "unsafe-avatar", "snapshot")
    absolute = tmp_path / "absolute.png"
    Image.new("RGB", (20, 20), "red").save(absolute)
    value["avatar_path"] = str(absolute)
    with pytest.raises(ValueError, match="avatar_path"):
        PosterRepository.from_mapping(value, avatar_root=tmp_path)

    value["avatar_path"] = "missing.png"
    with pytest.raises(ValueError, match="cached local file"):
        PosterRepository.from_mapping(value, avatar_root=tmp_path)

    unsupported = tmp_path / "avatar.txt"
    unsupported.write_text("not an image", encoding="utf-8")
    value["avatar_path"] = "avatar.txt"
    with pytest.raises(ValueError, match="PNG, JPG, JPEG, or WebP"):
        PosterRepository.from_mapping(value, avatar_root=tmp_path)


def test_v4_avatar_thumbnail_centre_crops_and_rounds_local_image(tmp_path: Path) -> None:
    source = Image.new("RGB", (200, 100), "red")
    for x in range(100, 200):
        for y in range(100):
            source.putpixel((x, y), (0, 0, 255))
    path = tmp_path / "wide.png"
    source.save(path)

    thumbnail = poster_module._load_avatar_thumbnail(path, (80, 80), radius=16)

    assert thumbnail.size == (80, 80)
    assert thumbnail.getpixel((0, 0))[3] == 0
    assert thumbnail.getpixel((20, 40))[:3] == (255, 0, 0)
    assert thumbnail.getpixel((60, 40))[:3] == (0, 0, 255)
    thumbnail.close()


def test_v4_card_uses_site_brand_palette_and_source_honest_growth(tmp_path: Path) -> None:
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
        theme = poster_module._BOARD_THEMES["comprehensive"]
        assert image.getpixel((10, 10)) == poster_module._hex_to_rgb(theme.page)
        assert image.getpixel((970, 48)) == poster_module._hex_to_rgb(theme.accent)
        assert image.getpixel((1100, 1350)) == poster_module._hex_to_rgb(theme.inverse)

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
    assert "数据来自 GitHub 公开信息与本地快照" not in Path(poster_module.__file__).read_text(
        encoding="utf-8"
    )


def test_v4_boards_and_cadences_are_visually_distinct_and_legacy_style_is_removed(
    tmp_path: Path,
) -> None:
    repository = _repository(1, "signal-tool", "snapshot")
    comprehensive_daily = poster_module.render_board_posters(
        board_key="comprehensive",
        board_label="综合主榜",
        period="daily",
        run_date="2026-07-12",
        repositories=[repository],
        output_dir=tmp_path / "comprehensive-daily",
    )
    comprehensive_weekly = poster_module.render_board_posters(
        board_key="comprehensive",
        board_label="综合主榜",
        period="weekly",
        run_date="2026-07-12",
        repositories=[repository],
        output_dir=tmp_path / "comprehensive-weekly",
    )
    ai_daily = poster_module.render_board_posters(
        board_key="ai",
        board_label="AI 专题榜",
        period="daily",
        run_date="2026-07-12",
        repositories=[repository],
        output_dir=tmp_path / "ai-daily",
    )

    with (
        Image.open(comprehensive_daily.cover) as daily,
        Image.open(comprehensive_weekly.cover) as weekly,
        Image.open(ai_daily.cover) as ai,
    ):
        board_difference = ImageChops.difference(daily, ai).convert("L").histogram()
        cadence_difference = ImageChops.difference(daily, weekly).convert("L").histogram()
        pixel_count = daily.width * daily.height
        assert 1 - board_difference[0] / pixel_count > 0.75
        assert 1 - cadence_difference[0] / pixel_count > 0.01
        assert daily.getpixel((10, 10)) == poster_module._hex_to_rgb(poster_module._PAPER)
        assert ai.getpixel((10, 10)) == poster_module._hex_to_rgb(poster_module._INK)

    source = Path(poster_module.__file__).read_text(encoding="utf-8")
    assert poster_module.POSTER_RENDERER_VERSION == "4.0"
    assert poster_module.POSTER_STYLE_VERSION == "signal-broadsheet-v1"
    for legacy in (
        "xiaohongshu-reference-card-v3",
        "#173F38",
        "#24574D",
        "#169B72",
        "#23A77B",
        "#D9F4E8",
        "#DDF4EA",
    ):
        assert legacy not in source


def test_public_issue_codes_start_from_first_release_date() -> None:
    assert poster_module._issue_code("daily", date(2026, 7, 11)) == "PREVIEW"
    assert poster_module._issue_code("daily", date(2026, 7, 12)) == "D001"
    assert poster_module._issue_code("daily", date(2026, 7, 13)) == "D002"
    assert poster_module._issue_code("weekly", date(2026, 7, 12)) == "W001"
    assert poster_module._issue_code("weekly", date(2026, 7, 19)) == "W002"


def test_explicit_issue_code_keeps_configured_weekly_series_identity() -> None:
    run_date = date(2026, 7, 13)

    assert poster_module._resolved_issue_code("weekly", run_date, "W001") == "W001"
    with pytest.raises(ValueError, match="weekly publication series"):
        poster_module._resolved_issue_code("weekly", run_date, "D002")


def test_v4_renders_long_explainer_copy_five_capabilities_and_cached_avatar(
    tmp_path: Path,
) -> None:
    avatar_dir = tmp_path / "cache"
    avatar_dir.mkdir()
    Image.new("RGB", (260, 180), "#2A6F5B").save(avatar_dir / "owner.webp")
    value = _repository(
        1,
        "enterprise-agent-workflow-orchestration-toolkit",
        "snapshot",
    )
    value.update(
        {
            "plain_summary": (
                "把多个编程助手放进同一套工作流中，让它们分别处理规划、实现、检查和结果整理。"
            ),
            "capabilities": [
                "同时管理多个编程助手的任务和会话",
                "把规划、编码与检查步骤分配给不同助手",
                "集中查看每个任务的执行状态和结果",
                "复用已经验证过的开发流程和任务模板",
                "把最终结果整理后交给人工继续审核",
            ],
            "core_title": "多助手并行协作",
            "core_summary": (
                "它把原本分散在多个终端和会话里的开发任务集中起来，便于分工、跟踪进度并保留可审核的结果。"
            ),
            "audience": "适合需要协调多个编程助手完成复杂研发任务的开发者与技术团队",
            "license_spdx": "Apache-2.0",
            "avatar_path": "cache/owner.webp",
        }
    )
    report_path = tmp_path / "long-copy.json"
    report_path.write_text(
        json.dumps(
            {
                "period": "weekly",
                "run_date": "2026-07-11",
                "boards": {
                    "comprehensive": {
                        "label": "综合主榜",
                        "repositories": [value],
                    }
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    artifacts = render_report_posters(report_path, output_dir=tmp_path / "posters")

    with Image.open(artifacts["comprehensive"].projects[0]) as image:
        assert image.size == DEFAULT_POSTER_SIZE
        assert image.format == "PNG"

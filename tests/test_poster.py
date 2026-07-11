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
        "description": f"A deterministic toolkit named {name}.",
        "language": "Python",
        "stars": 12_345 + rank,
        "forks": 678 + rank,
        "star_delta": 90 + rank,
        "delta_source": source,
        "summary": {
            "one_line": f"{name} helps developers ship repeatable workflows.",
            "highlights": [
                "Clear command-line workflow",
                "Deterministic local output",
                "Repository facts remain traceable",
            ],
            "audience": "Python developers and automation teams",
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

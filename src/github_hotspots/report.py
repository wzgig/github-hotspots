"""Render machine-readable, human-readable, and Xiaohongshu-ready reports."""

from __future__ import annotations

import json
import os
import re
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from .config import Settings
from .models import RankedRepository
from .summarizer import summarize_repository


@dataclass(frozen=True, slots=True)
class ReportArtifacts:
    markdown: Path
    json: Path
    xiaohongshu: Path
    ai_xiaohongshu: Path


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent, text=True
    )
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
        Path(temporary_name).replace(path)
    except Exception:
        Path(temporary_name).unlink(missing_ok=True)
        raise


def _environment(template_dir: Path) -> Environment:
    return Environment(
        loader=FileSystemLoader(str(template_dir)),
        undefined=StrictUndefined,
        autoescape=select_autoescape(default_for_string=False, default=False),
        trim_blocks=False,
        lstrip_blocks=False,
    )


def _compact_rendered_text(value: str) -> str:
    """Keep deliberate paragraph breaks without template-control whitespace."""

    return re.sub(r"\n{3,}", "\n\n", value).rstrip() + "\n"


def _window_label(period: str, run_date: date) -> str:
    if period == "daily":
        return run_date.isoformat()
    start = run_date - timedelta(days=6)
    return f"{start.isoformat()} 至 {run_date.isoformat()}"


def _report_stem(period: str, run_date: date) -> str:
    if period == "daily":
        return run_date.isoformat()
    iso_year, iso_week, _ = run_date.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"


def _quality(rankings: Sequence[RankedRepository]) -> tuple[str, list[str]]:
    sources = {item.delta_source for item in rankings}
    warnings: list[str] = []
    if not rankings:
        return "无可用候选", ["没有仓库通过当前筛选条件"]
    if any(item.star_delta < 0 or item.fork_delta < 0 for item in rankings):
        warnings.append("部分快照差值为负，可能来自撤销 Star、仓库迁移或计数修正")
    if sources == {"snapshot"}:
        return "高：历史快照增量", warnings
    if sources == {"trending"}:
        warnings.append("历史快照尚未覆盖上榜项目，周期 Star 来自 GitHub Trending")
        return "中高：GitHub Trending 周期信号", warnings
    if sources == {"estimate"}:
        warnings.append("当前没有可用快照或 Trending 增量，榜单仅使用估算与活跃度信号")
        return "低：首次运行估算", warnings
    if "estimate" in sources:
        warnings.append("部分项目缺少历史快照或 Trending 增量，使用估算信号")
        return "中：混合数据源，含估算", warnings
    warnings.append("部分项目使用历史快照，部分使用 GitHub Trending 周期信号")
    return "中高：快照与 Trending 混合", warnings


def _prepared_items(rankings: Sequence[RankedRepository]) -> list[dict[str, Any]]:
    prepared: list[dict[str, Any]] = []
    for item in rankings:
        prepared.append(
            {
                "repository": item.repository,
                "rank": item.rank,
                "score": item.score,
                "star_delta": item.star_delta,
                "fork_delta": item.fork_delta,
                "delta_source": item.delta_source,
                "component_percentiles": item.component_percentiles,
                "summary": summarize_repository(
                    item.repository, item.star_delta, item.delta_source
                ),
            }
        )
    return prepared


def _repository_payload(
    rankings: Sequence[RankedRepository], items: Sequence[dict[str, Any]]
) -> list[dict[str, Any]]:
    return [
        {**ranked.to_dict(), "summary": summary["summary"].to_dict()}
        for ranked, summary in zip(rankings, items, strict=True)
    ]


def _prefixed_warnings(label: str, warnings: Sequence[str]) -> list[str]:
    return [f"{label}：{warning}" for warning in warnings]


def render_reports(
    *,
    settings: Settings,
    period: str,
    run_date: date,
    rankings: Sequence[RankedRepository],
    ai_rankings: Sequence[RankedRepository] = (),
    extra_warnings: Sequence[str] = (),
    template_dir: Path | None = None,
) -> ReportArtifacts:
    """Render the dual-board Markdown, JSON, and two review-ready copies."""

    if period not in {"daily", "weekly"}:
        raise ValueError("period must be 'daily' or 'weekly'")

    templates = template_dir or Path(__file__).resolve().parents[2] / "templates"
    environment = _environment(templates)
    now = datetime.now(ZoneInfo(settings.timezone))
    comprehensive_board = settings.board("comprehensive")
    ai_board = settings.board("ai")
    quality, quality_warnings = (
        _quality(rankings) if comprehensive_board.enabled else ("已停用", [])
    )
    ai_quality, ai_quality_warnings = _quality(ai_rankings) if ai_board.enabled else ("已停用", [])
    warnings = [
        *_prefixed_warnings(comprehensive_board.label, quality_warnings),
        *_prefixed_warnings(ai_board.label, ai_quality_warnings),
        *extra_warnings,
    ]
    items = _prepared_items(rankings)
    ai_items = _prepared_items(ai_rankings)
    comprehensive_top_n = comprehensive_board.top_n(period)
    ai_top_n = ai_board.top_n(period)
    label = _window_label(period, run_date)
    title = (
        f"GitHub 每日热点双榜（{run_date.isoformat()}）"
        if period == "daily"
        else f"GitHub 每周热点双榜（{_report_stem(period, run_date)}）"
    )
    methodology = (
        "候选项目由 GitHub Trending 与 REST Search 共同发现；排名优先使用最接近目标窗口的"
        "本地快照计算 Star/Fork 净增量，基线缺失时使用 Trending 页面展示的周期 Star，"
        "再结合相对增长、最近推送、累计 Star 与 Trending 名次生成可解释分数。综合主榜对"
        "全部合格候选独立排名；AI 专题榜先按精确 Topic 和名称、描述、Topic 中的完整 token/"
        "短语筛选，再在 AI 候选池内独立排名。两个榜单允许出现同一仓库。"
    )

    common = {
        "title": title,
        "generated_at": now.isoformat(timespec="seconds"),
        "window_label": label,
        "data_quality": f"{comprehensive_board.label}：{quality}；{ai_board.label}：{ai_quality}",
        "warnings": warnings,
        "methodology": methodology,
    }
    markdown = _compact_rendered_text(
        environment.get_template("dual_digest.md.j2").render(
            **common,
            boards=[
                {
                    "label": comprehensive_board.label,
                    "top_n": comprehensive_top_n,
                    "data_quality": quality,
                    "items": items,
                    "empty_message": (
                        "本期没有通过综合筛选条件的候选项目。"
                        if comprehensive_board.enabled
                        else "当前配置已停用综合主榜。"
                    ),
                },
                {
                    "label": ai_board.label,
                    "top_n": ai_top_n,
                    "data_quality": ai_quality,
                    "items": ai_items,
                    "empty_message": (
                        "本期没有符合 AI 专题口径的候选项目。"
                        if ai_board.enabled
                        else "当前配置已停用 AI 专题榜。"
                    ),
                },
            ],
        )
    )

    comprehensive_common = {**common, "items": items}
    ai_common = {
        **common,
        "data_quality": ai_quality,
        "warnings": _prefixed_warnings(ai_board.label, ai_quality_warnings),
        "items": ai_items,
    }

    xhs_title = (
        f"今日 GitHub {comprehensive_board.label} Top {comprehensive_top_n} | {run_date.isoformat()}"
        if period == "daily"
        else (
            f"本周 GitHub {comprehensive_board.label} Top {comprehensive_top_n} | "
            f"{_report_stem(period, run_date)}"
        )
    )
    xhs = _compact_rendered_text(
        environment.get_template("xiaohongshu.md.j2").render(
            **comprehensive_common,
            xhs_title=xhs_title,
            intro="从全部合格候选中按周期热度、相对增长和代码活跃度独立筛选，数据与链接均可核验。",
            data_note=f"{quality}；窗口为 {label}",
            hashtags=["#GitHub", "#开源项目", "#程序员", "#开发者工具"],
        )
    )
    ai_xhs_title = (
        f"今日 GitHub {ai_board.label} Top {ai_top_n} | {run_date.isoformat()}"
        if period == "daily"
        else f"本周 GitHub {ai_board.label} Top {ai_top_n} | {_report_stem(period, run_date)}"
    )
    ai_xhs = _compact_rendered_text(
        environment.get_template("xiaohongshu.md.j2").render(
            **ai_common,
            xhs_title=ai_xhs_title,
            intro="从 AI 相关候选中独立计算热度排名，项目可能同时出现在综合主榜，发布前请人工审核。",
            data_note=f"{ai_quality}；窗口为 {label}",
            hashtags=["#GitHub", "#开源项目", "#AI", "#AI工具", "#机器学习"],
        )
    )

    comprehensive_payload = _repository_payload(rankings, items)
    ai_payload = _repository_payload(ai_rankings, ai_items)

    payload = {
        "schema_version": 2,
        "period": period,
        "run_date": run_date.isoformat(),
        "generated_at": now.isoformat(timespec="seconds"),
        "timezone": settings.timezone,
        "window_label": label,
        "data_quality": quality,
        "warnings": warnings,
        "methodology": methodology,
        "repositories": comprehensive_payload,
        "boards": {
            "comprehensive": {
                "label": comprehensive_board.label,
                "repositories": comprehensive_payload,
            },
            "ai": {"label": ai_board.label, "repositories": ai_payload},
        },
    }

    output_dir = settings.report_dir(period)
    stem = _report_stem(period, run_date)
    artifacts = ReportArtifacts(
        markdown=output_dir / f"{stem}.md",
        json=output_dir / f"{stem}.json",
        xiaohongshu=output_dir / f"{stem}.xiaohongshu.md",
        ai_xiaohongshu=output_dir / f"{stem}.ai.xiaohongshu.md",
    )
    _atomic_write(artifacts.markdown, markdown)
    _atomic_write(
        artifacts.json,
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
    )
    _atomic_write(artifacts.xiaohongshu, xhs)
    _atomic_write(artifacts.ai_xiaohongshu, ai_xhs)
    return artifacts

"""Render machine-readable, human-readable, and Xiaohongshu-ready reports."""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from .config import Settings
from .editorial import EditorialBatchResult, edit_summary_batch
from .models import RankedRepository
from .poster import (
    POSTER_RENDERER_NAME,
    POSTER_RENDERER_VERSION,
    POSTER_STYLE_VERSION,
    PosterArtifacts,
    render_board_posters,
)
from .summarizer import RepositorySummary, summarize_repository


@dataclass(frozen=True, slots=True)
class ReportArtifacts:
    markdown: Path
    json: Path
    xiaohongshu: Path
    ai_xiaohongshu: Path
    posters_dir: Path
    poster_manifest: Path | None
    poster_files: tuple[Path, ...]
    warnings: tuple[str, ...]


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


def _replace_directory(staging: Path, target: Path) -> None:
    """Swap a complete sibling staging directory into place with rollback."""

    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        staging.replace(target)
        return
    if not target.is_dir():
        raise RuntimeError(f"poster asset target is not a directory: {target}")

    backup = Path(tempfile.mkdtemp(prefix=f".{target.name}.backup.", dir=target.parent))
    backup.rmdir()
    target.replace(backup)
    try:
        staging.replace(target)
    except Exception:
        if not target.exists() and backup.exists():
            backup.replace(target)
        raise
    else:
        shutil.rmtree(backup, ignore_errors=True)


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


def _window_label(period: str, run_date: date, lookback_days: int | None = None) -> str:
    days = lookback_days if lookback_days is not None else (1 if period == "daily" else 7)
    start = run_date - timedelta(days=days)
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


def _draft_summaries(
    rankings: Sequence[RankedRepository],
) -> tuple[RepositorySummary, ...]:
    return tuple(
        summarize_repository(
            item.repository,
            item.star_delta,
            item.delta_source,
            narrative_index=narrative_index,
        )
        for narrative_index, item in enumerate(rankings)
    )


def _prepared_items(
    rankings: Sequence[RankedRepository],
    summaries: Sequence[RepositorySummary] | None = None,
) -> list[dict[str, Any]]:
    selected_summaries = tuple(summaries) if summaries is not None else _draft_summaries(rankings)
    if len(rankings) != len(selected_summaries):
        raise ValueError("rankings and summaries must have the same length")
    prepared: list[dict[str, Any]] = []
    for item, summary in zip(rankings, selected_summaries, strict=True):
        prepared.append(
            {
                "repository": item.repository,
                "rank": item.rank,
                "score": item.score,
                "star_delta": item.star_delta,
                "fork_delta": item.fork_delta,
                "delta_source": item.delta_source,
                "component_percentiles": item.component_percentiles,
                "summary": summary,
            }
        )
    return prepared


def _prepare_editorial_items(
    rankings: Sequence[RankedRepository],
    *,
    settings: Settings,
    period: str,
    run_date: date,
    backend_override: str | None,
) -> tuple[list[dict[str, Any]], EditorialBatchResult]:
    drafts = _draft_summaries(rankings)
    editorial = edit_summary_batch(
        rankings,
        drafts,
        period=period,
        period_start=run_date - timedelta(days=settings.run(period).lookback_days),
        period_end=run_date,
        settings=settings.editorial_settings(backend_override),
    )
    return _prepared_items(rankings, editorial.summaries), editorial


def _repository_payload(
    rankings: Sequence[RankedRepository], items: Sequence[dict[str, Any]]
) -> list[dict[str, Any]]:
    return [
        {**ranked.to_dict(), "summary": summary["summary"].to_dict()}
        for ranked, summary in zip(rankings, items, strict=True)
    ]


def _prefixed_warnings(label: str, warnings: Sequence[str]) -> list[str]:
    return [f"{label}：{warning}" for warning in warnings]


def _relative_path(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _poster_review_block(board_assets: dict[str, Any]) -> str:
    if not board_assets.get("enabled"):
        return ""
    lines = ["# 配图清单（发布前人工审核）", "", f"- 封面：`{board_assets['cover']}`"]
    for project in board_assets.get("projects", []):
        lines.append(f"- {int(project['rank']):02d} {project['full_name']}：`{project['path']}`")
    return "\n".join(lines) + "\n"


def _render_poster_assets(
    *,
    settings: Settings,
    period: str,
    run_date: date,
    window_start: date,
    stem: str,
    output_dir: Path,
    boards: Sequence[tuple[str, str, int, list[dict[str, Any]]]],
) -> tuple[dict[str, Any], tuple[Path, ...], Path | None]:
    poster_settings = settings.poster_settings()
    posters_dir = output_dir / "assets" / stem
    if not poster_settings.enabled:
        return (
            {
                "enabled": False,
                "format": "png",
                "width": poster_settings.width,
                "height": poster_settings.height,
                "boards": {},
            },
            (),
            None,
        )

    posters_dir.parent.mkdir(parents=True, exist_ok=True)
    staging_dir = Path(
        tempfile.mkdtemp(prefix=f".{posters_dir.name}.", suffix=".tmp", dir=posters_dir.parent)
    )
    manifest_path = posters_dir / "manifest.json"

    root = settings.path.parent.parent
    board_metadata: dict[str, Any] = {}
    all_paths: list[Path] = []
    try:
        for board_key, board_label, top_n, repositories in boards:
            rendered: PosterArtifacts = render_board_posters(
                board_key=board_key,
                board_label=board_label,
                period=period,
                run_date=run_date,
                repositories=repositories,
                output_dir=staging_dir,
                size=(poster_settings.width, poster_settings.height),
                top_n=top_n,
                window_start=window_start,
            )
            final_cover = posters_dir / rendered.cover.name
            final_projects = tuple(posters_dir / path.name for path in rendered.projects)
            all_paths.extend((final_cover, *final_projects))
            projects: list[dict[str, Any]] = []
            paths_by_repository = dict(zip(rendered.project_keys, final_projects, strict=True))
            for repository in repositories:
                project_path = paths_by_repository[(repository["rank"], repository["full_name"])]
                relative = _relative_path(project_path, root)
                repository["assets"] = {
                    "poster": relative,
                    "format": "png",
                    "width": poster_settings.width,
                    "height": poster_settings.height,
                }
                projects.append(
                    {
                        "rank": repository["rank"],
                        "full_name": repository["full_name"],
                        "path": relative,
                    }
                )
            board_metadata[board_key] = {
                "enabled": True,
                "top_n": top_n,
                "cover": _relative_path(final_cover, root),
                "projects": projects,
            }

        metadata = {
            "enabled": True,
            "format": "png",
            "width": poster_settings.width,
            "height": poster_settings.height,
            "directory": _relative_path(posters_dir, root),
            "manifest": _relative_path(manifest_path, root),
            "boards": board_metadata,
        }
        manifest = {
            "schema_version": 2,
            "period": period,
            "run_date": run_date.isoformat(),
            "window": {
                "start": window_start.isoformat(),
                "end": run_date.isoformat(),
            },
            "source_report": _relative_path(output_dir / f"{stem}.json", root),
            "renderer": {
                "name": POSTER_RENDERER_NAME,
                "version": POSTER_RENDERER_VERSION,
            },
            "style_version": POSTER_STYLE_VERSION,
            **metadata,
        }
        _atomic_write(
            staging_dir / "manifest.json",
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        )
        _replace_directory(staging_dir, posters_dir)
    finally:
        shutil.rmtree(staging_dir, ignore_errors=True)
    return metadata, tuple(all_paths), manifest_path


def render_reports(
    *,
    settings: Settings,
    period: str,
    run_date: date,
    rankings: Sequence[RankedRepository],
    ai_rankings: Sequence[RankedRepository] = (),
    extra_warnings: Sequence[str] = (),
    template_dir: Path | None = None,
    editorial_backend: str | None = None,
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
    items, comprehensive_editorial = _prepare_editorial_items(
        rankings,
        settings=settings,
        period=period,
        run_date=run_date,
        backend_override=editorial_backend,
    )
    ai_items, ai_editorial = _prepare_editorial_items(
        ai_rankings,
        settings=settings,
        period=period,
        run_date=run_date,
        backend_override=editorial_backend,
    )
    editorial_warnings = []
    for board_label, result in (
        (comprehensive_board.label, comprehensive_editorial),
        (ai_board.label, ai_editorial),
    ):
        if result.fallback_used:
            editorial_warnings.append(
                f"{board_label}：本地 Codex 受控选稿不可用（{result.error_category}），"
                "已整榜回退到确定性编辑"
            )
    warnings = [
        *_prefixed_warnings(comprehensive_board.label, quality_warnings),
        *_prefixed_warnings(ai_board.label, ai_quality_warnings),
        *editorial_warnings,
        *extra_warnings,
    ]
    comprehensive_top_n = comprehensive_board.top_n(period)
    ai_top_n = ai_board.top_n(period)
    poster_window_start = run_date - timedelta(days=settings.run(period).lookback_days)
    label = _window_label(period, run_date, settings.run(period).lookback_days)
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
        "中文文案先由确定性规则生成；仅在本地显式启用时，Codex CLI 才会在事实冻结后"
        "从受控候选中整榜选稿，并经过仓库身份、URL、数字、增量口径和禁用套话回查。"
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

    output_dir = settings.report_dir(period)
    stem = _report_stem(period, run_date)
    poster_assets, poster_files, poster_manifest = _render_poster_assets(
        settings=settings,
        period=period,
        run_date=run_date,
        window_start=poster_window_start,
        stem=stem,
        output_dir=output_dir,
        boards=(
            (
                "comprehensive",
                comprehensive_board.label,
                comprehensive_top_n,
                comprehensive_payload,
            ),
            ("ai", ai_board.label, ai_top_n, ai_payload),
        ),
    )
    comprehensive_assets = poster_assets.get("boards", {}).get("comprehensive", {"enabled": False})
    ai_assets = poster_assets.get("boards", {}).get("ai", {"enabled": False})
    xhs += "\n" + _poster_review_block(comprehensive_assets)
    ai_xhs += "\n" + _poster_review_block(ai_assets)

    payload = {
        "schema_version": 3,
        "period": period,
        "run_date": run_date.isoformat(),
        "window_start": poster_window_start.isoformat(),
        "window_end": run_date.isoformat(),
        "generated_at": now.isoformat(timespec="seconds"),
        "timezone": settings.timezone,
        "window_label": label,
        "data_quality": quality,
        "warnings": warnings,
        "methodology": methodology,
        "editorial": {
            "policy": "facts-locked-batch-editing",
            "boards": {
                "comprehensive": comprehensive_editorial.metadata(),
                "ai": ai_editorial.metadata(),
            },
        },
        "assets": poster_assets,
        "repositories": comprehensive_payload,
        "boards": {
            "comprehensive": {
                "label": comprehensive_board.label,
                "top_n": comprehensive_top_n,
                "assets": comprehensive_assets,
                "repositories": comprehensive_payload,
            },
            "ai": {
                "label": ai_board.label,
                "top_n": ai_top_n,
                "assets": ai_assets,
                "repositories": ai_payload,
            },
        },
    }

    artifacts = ReportArtifacts(
        markdown=output_dir / f"{stem}.md",
        json=output_dir / f"{stem}.json",
        xiaohongshu=output_dir / f"{stem}.xiaohongshu.md",
        ai_xiaohongshu=output_dir / f"{stem}.ai.xiaohongshu.md",
        posters_dir=output_dir / "assets" / stem,
        poster_manifest=poster_manifest,
        poster_files=poster_files,
        warnings=tuple(warnings),
    )
    _atomic_write(artifacts.markdown, markdown)
    _atomic_write(
        artifacts.json,
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
    )
    _atomic_write(artifacts.xiaohongshu, xhs)
    _atomic_write(artifacts.ai_xiaohongshu, ai_xhs)
    return artifacts

#!/usr/bin/env python3
"""Build deterministic data files for the static GitHub Pages dashboard."""

from __future__ import annotations

import argparse
import configparser
import json
import os
import re
from pathlib import Path
from typing import Any

DATA_VARIABLE = "GITHUB_HOTSPOTS_DATA"
REPORT_LIMITS = {"daily": 3, "weekly": 7}
BOARD_LABELS = {
    "comprehensive": "综合主榜",
    "ai": "AI 专题榜",
}

METRICS = [
    {
        "code": "Δ★",
        "name": "周期增星",
        "weight": "50%",
        "detail": "优先采用 1 日或 7 日快照净增；基线不足时使用 Trending 周期信号。",
    },
    {
        "code": "Δ%",
        "name": "相对增长",
        "weight": "20%",
        "detail": "让快速升温的新项目有机会越过长期积累的大仓库。",
    },
    {
        "code": "Δ⑂",
        "name": "Fork 增量",
        "weight": "10%",
        "detail": "观察开发者是否真正开始复制、试用和二次开发。",
    },
    {
        "code": "PUSH",
        "name": "近期活跃",
        "weight": "10%",
        "detail": "根据最近推送时间衰减计分，减少历史明星项目的惯性优势。",
    },
    {
        "code": "Σ★",
        "name": "累计规模",
        "weight": "5%",
        "detail": "以对数尺度保留社区规模信号，不让体量完全主导榜单。",
    },
    {
        "code": "TREND",
        "name": "趋势位次",
        "weight": "5%",
        "detail": "吸收 GitHub Trending 的即时热度，并保留信号来源说明。",
    },
]

PIPELINE = [
    {
        "step": "01",
        "name": "发现",
        "detail": "并行扫描 GitHub Trending 与 REST Search 候选池。",
    },
    {
        "step": "02",
        "name": "补全",
        "detail": "读取 Star、Fork、语言、主题与最近推送等公开元数据。",
    },
    {
        "step": "03",
        "name": "快照",
        "detail": "保存每日计数，为后续 1 日与 7 日真实增量建立基线。",
    },
    {
        "step": "04",
        "name": "排名",
        "detail": "六因子百分位加权，输出分数、增量和信号来源。",
    },
    {
        "step": "05",
        "name": "出版",
        "detail": "生成 Markdown、JSON、小红书文案与本项目数据页。",
    },
]


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read report JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"Report root must be an object: {path}")
    return payload


def _latest_report(report_dir: Path, period: str) -> tuple[Path, dict[str, Any]]:
    candidates: list[tuple[tuple[str, str, str], Path, dict[str, Any]]] = []
    for path in sorted(report_dir.glob("*.json")):
        payload = _load_json(path)
        if payload.get("period") != period:
            continue
        key = (
            str(payload.get("run_date") or ""),
            str(payload.get("generated_at") or ""),
            path.name,
        )
        candidates.append((key, path, payload))
    if not candidates:
        raise FileNotFoundError(f"No {period} JSON report found in {report_dir}")
    _, path, payload = max(candidates, key=lambda item: item[0])
    return path, payload


def _safe_int(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalise_repository(repository: dict[str, Any], fallback_rank: int) -> dict[str, Any]:
    summary = repository.get("summary")
    summary = summary if isinstance(summary, dict) else {}
    highlights = summary.get("highlights")
    topics = repository.get("topics")
    percentiles = repository.get("component_percentiles")
    delta_source = str(repository.get("delta_source") or "unknown")
    delta_labels = {
        "snapshot": "快照净增",
        "trending": "Trending 周期增星",
        "estimate": "历史均值估算",
    }
    description = str(repository.get("description") or "暂无仓库简介。")
    return {
        "rank": _safe_int(repository.get("rank"), fallback_rank),
        "full_name": str(repository.get("full_name") or "unknown/unknown"),
        "html_url": str(repository.get("html_url") or ""),
        "description": description,
        "language": str(repository.get("language") or "未标注"),
        "stars": _safe_int(repository.get("stars")),
        "forks": _safe_int(repository.get("forks")),
        "score": round(_safe_float(repository.get("score")), 2),
        "star_delta": _safe_int(repository.get("star_delta")),
        "fork_delta": _safe_int(repository.get("fork_delta")),
        "delta_source": delta_source,
        "delta_label": delta_labels.get(delta_source, "来源未标注"),
        "pushed_at": repository.get("pushed_at"),
        "topics": [str(item) for item in topics[:5]] if isinstance(topics, list) else [],
        "one_line": str(summary.get("one_line") or description),
        "highlights": (
            [str(item) for item in highlights[:3]] if isinstance(highlights, list) else []
        ),
        "audience": str(summary.get("audience") or "开源项目关注者"),
        "component_percentiles": (
            {str(key): round(_safe_float(value), 2) for key, value in percentiles.items()}
            if isinstance(percentiles, dict)
            else {}
        ),
    }


def _normalise_repositories(repositories: Any, period: str) -> list[dict[str, Any]]:
    if not isinstance(repositories, list):
        return []
    ordered = sorted(
        (item for item in repositories if isinstance(item, dict)),
        key=lambda item: _safe_int(item.get("rank"), 10_000),
    )[: REPORT_LIMITS[period]]
    return [
        _normalise_repository(repository, index)
        for index, repository in enumerate(ordered, start=1)
    ]


def _normalise_board(
    payload: dict[str, Any],
    board_name: str,
    period: str,
    fallback_repositories: Any = None,
) -> dict[str, Any]:
    boards = payload.get("boards")
    board = boards.get(board_name) if isinstance(boards, dict) else None
    board = board if isinstance(board, dict) else {}
    repositories = board.get("repositories")
    if not isinstance(repositories, list):
        repositories = fallback_repositories
    label = str(board.get("label") or BOARD_LABELS[board_name])
    return {
        "label": label,
        "repositories": _normalise_repositories(repositories, period),
    }


def _normalise_report(
    path: Path, payload: dict[str, Any], period: str, root: Path
) -> dict[str, Any]:
    legacy_repositories = payload.get("repositories")
    comprehensive = _normalise_board(
        payload,
        "comprehensive",
        period,
        fallback_repositories=legacy_repositories,
    )
    ai = _normalise_board(payload, "ai", period)
    warnings = payload.get("warnings")
    return {
        "period": period,
        "run_date": str(payload.get("run_date") or ""),
        "generated_at": str(payload.get("generated_at") or ""),
        "window_label": str(payload.get("window_label") or payload.get("run_date") or ""),
        "data_quality": str(payload.get("data_quality") or "数据质量未标注"),
        "warnings": [str(item) for item in warnings] if isinstance(warnings, list) else [],
        "methodology": str(payload.get("methodology") or ""),
        "source_path": path.relative_to(root).as_posix(),
        # Keep the historical field as a stable alias for the comprehensive board.
        "repositories": comprehensive["repositories"],
        "boards": {
            "comprehensive": comprehensive,
            "ai": ai,
        },
    }


def _github_url(value: str) -> str:
    value = value.strip()
    patterns = (
        r"https?://github\.com/(?P<repo>[^/\s]+/[^/\s]+?)(?:\.git)?/?$",
        r"git@github\.com:(?P<repo>[^/\s]+/[^/\s]+?)(?:\.git)?$",
        r"ssh://git@github\.com/(?P<repo>[^/\s]+/[^/\s]+?)(?:\.git)?/?$",
    )
    for pattern in patterns:
        match = re.fullmatch(pattern, value)
        if match:
            return f"https://github.com/{match.group('repo').removesuffix('.git')}"
    return ""


def _discover_repository_url(root: Path, explicit: str | None) -> str:
    if explicit:
        return _github_url(explicit)
    github_repository = os.getenv("GITHUB_REPOSITORY", "").strip()
    if re.fullmatch(r"[^/\s]+/[^/\s]+", github_repository):
        return f"https://github.com/{github_repository}"
    config_path = root / ".git" / "config"
    if not config_path.exists():
        return ""
    parser = configparser.ConfigParser()
    try:
        parser.read(config_path, encoding="utf-8")
        remote = parser.get('remote "origin"', "url", fallback="")
    except (configparser.Error, OSError):
        return ""
    return _github_url(remote)


def _write_if_changed(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return
    path.write_text(content, encoding="utf-8", newline="\n")


def build_site(root: Path, repository_url: str | None = None) -> dict[str, Any]:
    """Build site data from the latest daily and weekly reports under *root*."""

    root = root.resolve()
    daily_path, daily_payload = _latest_report(root / "reports" / "daily", "daily")
    weekly_path, weekly_payload = _latest_report(root / "reports" / "weekly", "weekly")
    daily = _normalise_report(daily_path, daily_payload, "daily", root)
    weekly = _normalise_report(weekly_path, weekly_payload, "weekly", root)
    generated_values = [daily["generated_at"], weekly["generated_at"]]
    warnings = list(dict.fromkeys([*daily["warnings"], *weekly["warnings"]]))
    resolved_repository_url = _discover_repository_url(root, repository_url)
    payload = {
        "schema_version": 2,
        "generated_at": max((value for value in generated_values if value), default=""),
        "site": {
            "title": "GitHub Hotspots",
            "tagline": "追踪开源世界真正发生的增量",
            "repository_url": resolved_repository_url,
        },
        "daily": daily,
        "weekly": weekly,
        "methodology": {
            "summary": weekly["methodology"] or daily["methodology"],
            "quality": weekly["data_quality"] or daily["data_quality"],
            "warnings": warnings,
            "metrics": METRICS,
        },
        "pipeline": PIPELINE,
    }
    json_text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    data_dir = root / "site" / "data"
    _write_if_changed(data_dir / "site-data.json", json_text)
    js_text = f'"use strict";\nwindow.{DATA_VARIABLE} = {json_text.rstrip()};\n'
    _write_if_changed(data_dir / "site-data.js", js_text)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Project root containing reports/ and site/ (default: repository root).",
    )
    parser.add_argument(
        "--repository-url",
        help="Canonical GitHub repository URL; defaults to Actions env or git origin.",
    )
    args = parser.parse_args()
    payload = build_site(args.root, args.repository_url)
    print(
        "Built site data: "
        f"daily={len(payload['daily']['repositories'])} comprehensive / "
        f"{len(payload['daily']['boards']['ai']['repositories'])} AI, "
        f"weekly={len(payload['weekly']['repositories'])} comprehensive / "
        f"{len(payload['weekly']['boards']['ai']['repositories'])} AI"
    )


if __name__ == "__main__":
    main()

"""Fact-bound summaries suitable for reports and social cards."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class RepositorySummary:
    one_line: str
    highlights: tuple[str, ...]
    audience: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "one_line": self.one_line,
            "highlights": list(self.highlights),
            "audience": self.audience,
        }


_CATEGORY_RULES: tuple[tuple[tuple[str, ...], str, str], ...] = (
    (
        ("llm", "agent", "ai", "machine-learning", "deep-learning"),
        "AI 与智能体开发",
        "AI 应用开发者、算法工程师、技术研究者",
    ),
    (
        ("security", "cybersecurity", "vulnerability"),
        "软件安全与风险治理",
        "安全工程师、运维团队、后端开发者",
    ),
    (
        ("cli", "developer-tools", "devtools", "automation"),
        "开发工具与自动化",
        "软件工程师、个人开发者、效率工具用户",
    ),
    (
        ("frontend", "react", "vue", "web", "css"),
        "Web 与前端工程",
        "前端开发者、设计工程师、独立开发者",
    ),
    (("data", "database", "analytics"), "数据处理与分析", "数据工程师、分析师、后端开发者"),
)


def _clip(text: str, limit: int) -> str:
    compact = " ".join(text.split())
    return compact if len(compact) <= limit else compact[: limit - 1].rstrip() + "…"


def _category(repository: Any) -> tuple[str, str]:
    haystack = " ".join(
        [
            str(getattr(repository, "description", "") or ""),
            " ".join(getattr(repository, "topics", ()) or ()),
        ]
    ).lower()
    for keywords, label, audience in _CATEGORY_RULES:
        if any(keyword in haystack for keyword in keywords):
            return label, audience
    return "开源软件与工程实践", "软件开发者、开源爱好者、技术团队"


def summarize_repository(
    repository: Any,
    star_delta: int | None = None,
    delta_source: str = "estimate",
) -> RepositorySummary:
    """Create a deterministic Chinese wrapper without inventing project claims."""

    name = getattr(repository, "name", None) or str(repository.full_name).rsplit("/", 1)[-1]
    category, audience = _category(repository)
    description = _clip(str(getattr(repository, "description", "") or "暂无仓库简介"), 82)
    language = getattr(repository, "language", None) or "未标注主要语言"
    stars = int(getattr(repository, "stars", 0) or 0)
    forks = int(getattr(repository, "forks", 0) or 0)

    one_line = _clip(f"{name} 是一个近期升温、聚焦“{category}”的开源项目：{description}", 96)
    if star_delta is None:
        growth = "首次运行尚无完整增量基线，当前结果属于估算榜单"
    elif delta_source == "snapshot" and star_delta < 0:
        growth = f"快照差值为 {star_delta:,} Star，属于待核验的数据异常，不计作新增"
    elif delta_source == "snapshot":
        growth = f"本地历史快照显示本期净增 {star_delta:,} Star"
    elif delta_source == "trending":
        growth = f"GitHub Trending 页面显示本期获得 {star_delta:,} Star"
    else:
        growth = f"按项目历史平均速度估算本期约 {star_delta:,} Star，并非实际增量"
    highlights = (
        _clip(f"仓库定位：{description}", 96),
        f"主要语言：{language}；累计 {stars:,} Star、{forks:,} Fork",
        growth,
    )
    return RepositorySummary(one_line=one_line, highlights=highlights, audience=audience)

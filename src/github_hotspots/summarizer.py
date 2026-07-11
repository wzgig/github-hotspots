"""Fact-bound summaries suitable for reports and social cards."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
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

_AUDIENCE_RULES: tuple[tuple[tuple[str, ...], str], ...] = (
    (
        ("security",),
        "安全工程师、渗透测试人员、应用开发团队",
    ),
    (
        ("office",),
        "Office 工具开发者、数据与文档工作者",
    ),
    (
        ("prompt-engineering",),
        "提示词工程师、AI 产品研究者、模型应用开发者",
    ),
    (
        ("ai-gateway",),
        "AI 应用开发者、平台工程师、工具集成者",
    ),
    (
        ("agent-ide",),
        "AI 编程工具开发者、Agent 工作流设计者、研发团队",
    ),
    (
        ("agent-orchestration",),
        "多智能体开发者、技术负责人、终端工具用户",
    ),
    (
        ("code-review",),
        "代码审查参与者、软件工程师、研发团队",
    ),
    (
        ("mcp",),
        "MCP 集成开发者、工具集成者、协议实现者",
    ),
)

_POSITIONING_RULES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("mcp", "terminal-automation"), "MCP 终端自动化项目"),
    (("terminal-automation",), "终端自动化项目"),
    (("ai-gateway",), "AI 网关项目"),
    (("llm-gateway",), "LLM 网关项目"),
    (("model-routing",), "模型路由项目"),
    (("ai-meeting-assistant",), "AI 会议助手项目"),
    (("meeting-minutes",), "会议纪要项目"),
    (("meeting-notes",), "会议记录项目"),
    (("transcription",), "语音转写项目"),
    (("ai-penetration-testing",), "AI 渗透测试项目"),
    (("penetration-testing",), "渗透测试项目"),
    (("agent-ide",), "智能体 IDE 项目"),
    (("agent-orchestration", "multiplexer"), "智能体编排与多路复用项目"),
    (("agent-orchestration",), "智能体编排项目"),
    (("code-review",), "代码审查项目"),
    (("office", "cli"), "Office 命令行项目"),
    (("office",), "Office 相关项目"),
    (("postgresql",), "PostgreSQL 相关项目"),
    (("postgres",), "PostgreSQL 相关项目"),
    (("skills", "sdlc"), "软件开发技能与流程项目"),
    (("prompt-engineering",), "提示词工程相关项目"),
    (("bundler", "javascript"), "JavaScript 打包工具项目"),
    (("developer-tools", "automation"), "开发工具与自动化项目"),
)

NARRATIVE_ANGLES = (
    "positioning",
    "growth_signal",
    "tech_stack",
    "scale",
    "topics",
    "activity",
    "source",
)
_NARRATIVE_VARIANT_COUNT = len(NARRATIVE_ANGLES)


def _clip(text: str, limit: int) -> str:
    compact = " ".join(text.split())
    return compact if len(compact) <= limit else compact[: limit - 1].rstrip() + "…"


def _category(repository: Any) -> tuple[str, str]:
    topics = _topic_set(repository)
    for keywords, label, audience in _CATEGORY_RULES:
        if topics.intersection(keywords):
            return label, audience
    return "开源软件与工程实践", "软件开发者、开源爱好者、技术团队"


def _audience(repository: Any) -> str:
    topics = _topic_set(repository)
    for keywords, audience in _AUDIENCE_RULES:
        if set(keywords).issubset(topics):
            return audience
    return _category(repository)[1]


def _positioning(repository: Any) -> str:
    topics = _topic_set(repository)
    for keywords, positioning in _POSITIONING_RULES:
        if set(keywords).issubset(topics):
            return positioning
    category, _ = _category(repository)
    return f"面向{category}方向的开源项目"


def _topic_set(repository: Any) -> frozenset[str]:
    return frozenset(
        str(topic).strip().casefold()
        for topic in (getattr(repository, "topics", ()) or ())
        if str(topic).strip()
    )


def _narrative_variant(repository: Any, narrative_index: int | None) -> int:
    """Choose a reproducible angle, with report order taking precedence."""

    if narrative_index is not None:
        return narrative_index % _NARRATIVE_VARIANT_COUNT
    identity = str(getattr(repository, "full_name", "") or getattr(repository, "name", ""))
    digest = sha256(identity.encode("utf-8")).digest()
    return digest[0] % _NARRATIVE_VARIANT_COUNT


def _growth_statement(star_delta: int | None, delta_source: str) -> str:
    if star_delta is None:
        return "首次运行尚无完整增量基线，当前结果属于估算榜单"
    if delta_source == "snapshot" and star_delta < 0:
        return f"快照差值为 {star_delta:,} Star，属于待核验的数据异常，不计作新增"
    if delta_source == "snapshot":
        return f"本地历史快照显示本期净增 {star_delta:,} Star"
    if delta_source == "trending":
        return f"GitHub Trending 页面显示本期获得 {star_delta:,} Star"
    return f"按项目历史平均速度估算本期约 {star_delta:,} Star，并非实际增量"


def _growth_lead(name: str, star_delta: int | None, delta_source: str) -> str:
    if star_delta is None:
        return f"{name} 暂无完整增量基线"
    if delta_source == "snapshot" and star_delta < 0:
        return f"{name} 的快照差值为 {star_delta:,} Star，当前需要核验"
    if delta_source == "snapshot":
        return f"本地快照记录 {name} 本期净增 {star_delta:,} Star"
    if delta_source == "trending":
        return f"Trending 页面记录 {name} 本期获得 {star_delta:,} Star"
    return f"{name} 本期约 {star_delta:,} Star 的变化来自估算信号"


def _topics_statement(repository: Any) -> str:
    topics = tuple(
        str(topic).strip()
        for topic in (getattr(repository, "topics", ()) or ())
        if str(topic).strip()
    )
    if not topics:
        return "公开 Topics：仓库未标注"
    return _clip(f"公开 Topics：{'、'.join(topics[:4])}", 96)


def _topics_lead(repository: Any, name: str, positioning: str) -> str:
    topics = tuple(
        str(topic).strip()
        for topic in (getattr(repository, "topics", ()) or ())
        if str(topic).strip()
    )
    if topics:
        return _clip(
            f"公开 Topics 包括 {'、'.join(topics[:3])}；{name} 的公开定位：{positioning}",
            96,
        )
    return _clip(f"{name} 未标注 Topics；公开定位：{positioning}", 96)


def _activity_lead(repository: Any, name: str, positioning: str) -> str:
    pushed_at = str(getattr(repository, "pushed_at", "") or "").strip()
    if pushed_at:
        return _clip(
            f"GitHub 记录的最近推送日期为 {pushed_at[:10]}；{name} 的公开定位：{positioning}",
            96,
        )
    return _clip(f"{name} 暂无可用的最近推送日期；公开定位：{positioning}", 96)


def _source_lead(repository: Any, name: str, positioning: str) -> str:
    sources = tuple(
        str(source).strip()
        for source in (getattr(repository, "sources", ()) or ())
        if str(source).strip()
    )
    if sources:
        source_labels = {
            "trending": "GitHub Trending",
            "trending_daily": "GitHub Trending 日榜",
            "trending_weekly": "GitHub Trending 周榜",
            "github_api": "GitHub API",
            "search": "GitHub Search",
        }
        labels = [source_labels.get(source.casefold(), source) for source in sources[:3]]
        return _clip(
            f"本榜候选信号来自 {'、'.join(labels)}；{name} 的公开定位：{positioning}",
            96,
        )
    return _clip(f"榜单保留了 {name} 的公开仓库事实；公开定位：{positioning}", 96)


def summarize_repository(
    repository: Any,
    star_delta: int | None = None,
    delta_source: str = "estimate",
    narrative_index: int | None = None,
) -> RepositorySummary:
    """Create a deterministic, fact-bound summary with varied narrative angles."""

    name = getattr(repository, "name", None) or str(repository.full_name).rsplit("/", 1)[-1]
    audience = _audience(repository)
    positioning = _positioning(repository)
    language = getattr(repository, "language", None) or "未标注主要语言"
    stars = int(getattr(repository, "stars", 0) or 0)
    forks = int(getattr(repository, "forks", 0) or 0)

    growth = _growth_statement(star_delta, delta_source)
    language_fact = f"GitHub 标注的主要语言：{language}"
    scale_fact = f"当前累计 {stars:,} Star、{forks:,} Fork"
    topics_fact = _topics_statement(repository)
    variant = _narrative_variant(repository, narrative_index)

    if variant == 0:
        one_line = _clip(f"{name} 的公开简介与 Topics 显示其定位：{positioning}", 96)
        highlights = (
            f"{language_fact}；{scale_fact}",
            growth,
            topics_fact,
        )
    elif variant == 1:
        one_line = _clip(
            f"{_growth_lead(name, star_delta, delta_source)}；公开定位：{positioning}", 96
        )
        highlights = (
            language_fact,
            scale_fact,
            topics_fact,
        )
    elif variant == 2:
        one_line = _clip(f"以 {language} 为主要语言，{name} 的公开定位：{positioning}", 96)
        highlights = (
            scale_fact,
            growth,
            topics_fact,
        )
    elif variant == 3:
        one_line = _clip(
            f"当前累计 {stars:,} Star、{forks:,} Fork；{name} 的公开定位：{positioning}",
            96,
        )
        highlights = (
            language_fact,
            growth,
            topics_fact,
        )
    elif variant == 4:
        one_line = _topics_lead(repository, name, positioning)
        highlights = (
            growth,
            language_fact,
            scale_fact,
        )
    elif variant == 5:
        one_line = _activity_lead(repository, name, positioning)
        highlights = (
            topics_fact,
            scale_fact,
            growth,
        )
    else:
        one_line = _source_lead(repository, name, positioning)
        highlights = (
            language_fact,
            topics_fact,
            growth,
        )
    return RepositorySummary(one_line=one_line, highlights=highlights, audience=audience)


def summary_candidates(
    repository: Any,
    star_delta: int | None = None,
    delta_source: str = "estimate",
) -> tuple[tuple[str, RepositorySummary], ...]:
    """Return every controlled narrative candidate for editorial selection."""

    return tuple(
        (
            angle,
            summarize_repository(
                repository,
                star_delta,
                delta_source,
                narrative_index=index,
            ),
        )
        for index, angle in enumerate(NARRATIVE_ANGLES)
    )

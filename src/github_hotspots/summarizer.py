"""Deterministic, fact-bound explanations for reports and social cards."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from hashlib import sha256
from typing import Any

_SUMMARY_TEXT_FIELDS = (
    "one_line",
    "highlights",
    "audience",
    "capabilities",
    "core_title",
    "core_summary",
    "prerequisites",
    "limitations",
    "license_label",
    "license_restrictions",
)
_LICENSE_POINTER_PATTERN = re.compile(
    r"(?:\bsee\b.{0,80}\blicen[cs]e\b|\blicen[cs]e file for details\b|"
    r"(?:详见|查看).{0,20}(?:LICENSE|许可))",
    re.IGNORECASE,
)


def _normalise_license_restriction(label: str, restriction: str) -> str:
    """Remove README navigation prose that is not an actual license condition."""

    if not restriction:
        return ""
    plain = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", restriction).strip()
    comparable = re.sub(r"[^a-z0-9]+", " ", plain.casefold()).strip()
    label_comparable = re.sub(r"[^a-z0-9]+", " ", label.casefold()).strip()
    if label_comparable and comparable in {label_comparable, f"{label_comparable} license"}:
        return ""
    return "" if _LICENSE_POINTER_PATTERN.search(plain) else restriction


def _default_evidence_ids(
    *,
    highlights: tuple[str, ...],
    capabilities: tuple[str, ...],
    prerequisites: str,
    limitations: str,
    license_label: str,
    license_restrictions: str,
) -> dict[str, Any]:
    reference = ("deterministic_draft",)
    return {
        "one_line": reference,
        "highlights": tuple(reference for _ in highlights),
        "audience": reference,
        "capabilities": tuple(reference for _ in capabilities),
        "core_title": reference,
        "core_summary": reference,
        "prerequisites": reference if prerequisites else (),
        "limitations": reference if limitations else (),
        "license_label": reference if license_label else (),
        "license_restrictions": reference if license_restrictions else (),
    }


def _normalise_evidence_ids(value: Mapping[str, Any], defaults: dict[str, Any]) -> dict[str, Any]:
    normalised = dict(defaults)
    for field_name in _SUMMARY_TEXT_FIELDS:
        if field_name not in value:
            continue
        references = value[field_name]
        if field_name in {"highlights", "capabilities"}:
            if isinstance(references, (str, bytes)) or not isinstance(references, (list, tuple)):
                normalised[field_name] = ()
                continue
            normalised[field_name] = tuple(
                tuple(str(reference) for reference in group)
                if isinstance(group, (list, tuple)) and not isinstance(group, (str, bytes))
                else ()
                for group in references
            )
            continue
        if isinstance(references, (list, tuple)) and not isinstance(references, (str, bytes)):
            normalised[field_name] = tuple(str(reference) for reference in references)
        else:
            normalised[field_name] = ()
    return normalised


def _serialise_evidence_ids(value: Mapping[str, Any]) -> dict[str, Any]:
    serialised: dict[str, Any] = {}
    for field_name, references in value.items():
        if field_name in {"highlights", "capabilities"}:
            serialised[field_name] = [list(group) for group in references]
        else:
            serialised[field_name] = list(references)
    return serialised


@dataclass(frozen=True, slots=True)
class RepositorySummary:
    """Reader-facing repository copy with traceable evidence references.

    ``one_line``, ``highlights`` and ``audience`` remain the compatibility
    surface used by existing reports.  The richer fields are optional for
    callers constructing legacy summaries and receive deterministic defaults.
    """

    one_line: str
    highlights: tuple[str, ...]
    audience: str
    capabilities: tuple[str, ...] = ()
    core_title: str = ""
    core_summary: str = ""
    prerequisites: str = ""
    limitations: str = ""
    license_label: str = ""
    license_restrictions: str = ""
    readme_sha: str | None = None
    content_status: str = "metadata_only"
    evidence_ids: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        highlights = tuple(str(value).strip() for value in self.highlights if str(value).strip())
        capabilities = tuple(
            str(value).strip() for value in self.capabilities if str(value).strip()
        )
        if not capabilities:
            capabilities = highlights[:5]
        if len(capabilities) > 5:
            raise ValueError("capabilities cannot contain more than five items")

        one_line = str(self.one_line).strip()
        audience = str(self.audience).strip()
        core_title = str(self.core_title).strip() or (capabilities[0] if capabilities else one_line)
        core_summary = str(self.core_summary).strip() or one_line
        prerequisites = str(self.prerequisites).strip()
        limitations = str(self.limitations).strip()
        license_label = str(self.license_label).strip()
        license_restrictions = _normalise_license_restriction(
            license_label,
            str(self.license_restrictions).strip(),
        )
        content_status = str(self.content_status).strip() or "metadata_only"
        readme_sha = str(self.readme_sha).strip() if self.readme_sha else None

        defaults = _default_evidence_ids(
            highlights=highlights,
            capabilities=capabilities,
            prerequisites=prerequisites,
            limitations=limitations,
            license_label=license_label,
            license_restrictions=license_restrictions,
        )
        evidence_ids = _normalise_evidence_ids(self.evidence_ids, defaults)
        if not license_restrictions:
            evidence_ids["license_restrictions"] = ()

        object.__setattr__(self, "one_line", one_line)
        object.__setattr__(self, "highlights", highlights)
        object.__setattr__(self, "audience", audience)
        object.__setattr__(self, "capabilities", capabilities)
        object.__setattr__(self, "core_title", core_title)
        object.__setattr__(self, "core_summary", core_summary)
        object.__setattr__(self, "prerequisites", prerequisites)
        object.__setattr__(self, "limitations", limitations)
        object.__setattr__(self, "license_label", license_label)
        object.__setattr__(self, "license_restrictions", license_restrictions)
        object.__setattr__(self, "readme_sha", readme_sha)
        object.__setattr__(self, "content_status", content_status)
        object.__setattr__(self, "evidence_ids", evidence_ids)

    def to_dict(self) -> dict[str, Any]:
        return {
            "one_line": self.one_line,
            "highlights": list(self.highlights),
            "audience": self.audience,
            "capabilities": list(self.capabilities),
            "core_title": self.core_title,
            "core_summary": self.core_summary,
            "prerequisites": self.prerequisites,
            "limitations": self.limitations,
            "license_label": self.license_label,
            "license_restrictions": self.license_restrictions,
            "readme_sha": self.readme_sha,
            "content_status": self.content_status,
            "evidence_ids": _serialise_evidence_ids(self.evidence_ids),
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RepositorySummary:
        """Parse a persisted summary while accepting the legacy three-field shape."""

        if not isinstance(value, Mapping):
            raise TypeError("repository summary must be a mapping")

        def required_text(field_name: str) -> str:
            field_value = value.get(field_name)
            if not isinstance(field_value, str) or not field_value.strip():
                raise ValueError(f"repository summary {field_name} must be non-empty text")
            return field_value

        def optional_text(field_name: str) -> str:
            field_value = value.get(field_name, "")
            if not isinstance(field_value, str):
                raise ValueError(f"repository summary {field_name} must be text")
            return field_value

        def text_items(field_name: str, *, required: bool) -> tuple[str, ...]:
            field_value = value.get(field_name)
            if field_value is None and not required:
                return ()
            if (
                isinstance(field_value, (str, bytes))
                or not isinstance(field_value, (list, tuple))
                or (required and not field_value)
                or any(not isinstance(item, str) or not item.strip() for item in field_value)
            ):
                raise ValueError(f"repository summary {field_name} must be a text array")
            return tuple(field_value)

        readme_sha = value.get("readme_sha")
        if readme_sha is not None and not isinstance(readme_sha, str):
            raise ValueError("repository summary readme_sha must be text or null")
        content_status = value.get("content_status", "metadata_only")
        if not isinstance(content_status, str) or not content_status.strip():
            raise ValueError("repository summary content_status must be non-empty text")
        evidence_ids = value.get("evidence_ids", {})
        if not isinstance(evidence_ids, Mapping):
            raise ValueError("repository summary evidence_ids must be a mapping")

        return cls(
            one_line=required_text("one_line"),
            highlights=text_items("highlights", required=True),
            audience=required_text("audience"),
            capabilities=text_items("capabilities", required=False),
            core_title=optional_text("core_title"),
            core_summary=optional_text("core_summary"),
            prerequisites=optional_text("prerequisites"),
            limitations=optional_text("limitations"),
            license_label=optional_text("license_label"),
            license_restrictions=optional_text("license_restrictions"),
            readme_sha=readme_sha,
            content_status=content_status,
            evidence_ids=evidence_ids,
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> RepositorySummary:
        """Compatibility alias for callers loading JSON dictionaries."""

        return cls.from_mapping(value)


@dataclass(frozen=True, slots=True)
class _CapabilityProfile:
    """A small, reusable explanation built only from controlled public clues."""

    task: str
    benefit: str
    highlights: tuple[str, str, str]
    audience: str
    review_required: bool = False


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

_NEGATION_PATTERN = re.compile(
    r"(?:\b(?:not|no|never|without|cannot|cant|can't|isnt|isn't|doesnt|doesn't)\b|"
    r"不是|并非|不支持|不能|无法|没有)"
)


def _clip(text: str, limit: int) -> str:
    compact = " ".join(text.split())
    return compact if len(compact) <= limit else compact[: limit - 1].rstrip() + "…"


def _topic_set(repository: Any) -> frozenset[str]:
    return frozenset(
        str(topic).strip().casefold()
        for topic in (getattr(repository, "topics", ()) or ())
        if str(topic).strip()
    )


def _normalised_description(repository: Any) -> str:
    return " ".join(str(getattr(repository, "description", "") or "").casefold().split())


def _normalised_identity(repository: Any) -> str:
    full_name = str(getattr(repository, "full_name", "") or "").casefold()
    return re.sub(r"[^a-z0-9]+", "-", full_name).strip("-")


def _description_has_positive_phrase(description: str, *phrases: str) -> bool:
    """Match a narrow phrase unless a nearby negation reverses its meaning."""

    for phrase in phrases:
        normalised_phrase = " ".join(phrase.casefold().split())
        start = 0
        while (index := description.find(normalised_phrase, start)) >= 0:
            prefix = description[max(0, index - 36) : index]
            boundary = max(prefix.rfind("."), prefix.rfind(";"), prefix.rfind(","))
            local_prefix = prefix[boundary + 1 :]
            if not _NEGATION_PATTERN.search(local_prefix):
                return True
            start = index + len(normalised_phrase)
    return False


def _has_all(topics: frozenset[str], *required: str) -> bool:
    return set(required).issubset(topics)


def _has_any(topics: frozenset[str], *candidates: str) -> bool:
    return bool(topics.intersection(candidates))


def _profile(
    task: str,
    benefit: str,
    highlights: tuple[str, str, str],
    audience: str,
    *,
    review_required: bool = False,
) -> _CapabilityProfile:
    return _CapabilityProfile(
        task=task,
        benefit=benefit,
        highlights=highlights,
        audience=audience,
        review_required=review_required,
    )


def _capability_profile(repository: Any) -> _CapabilityProfile:
    """Choose the most specific capability profile supported by exact clues."""

    topics = _topic_set(repository)
    description = _normalised_description(repository)
    identity = _normalised_identity(repository)

    if _has_any(topics, "test-framework", "unit-testing") and _has_any(
        topics, "cpp", "cpp14", "cpp17", "c-plus-plus"
    ):
        return _profile(
            "为 C++ 项目编写和运行单元测试",
            "支持用 TDD 或 BDD 方式组织测试",
            (
                "为 C++ 代码编写并运行单元测试",
                "用断言检查代码行为和预期是否一致",
                "支持按 TDD 或 BDD 方式组织测试",
            ),
            "需要给 C++ 库或应用补充自动化测试的开发者",
        )

    if (
        "firecrawl" in identity
        or _has_any(topics, "ai-crawler", "ai-scraping")
        or _has_all(topics, "crawler", "data-extraction")
    ):
        return _profile(
            "搜索、抓取并整理网页内容",
            "把网页数据交给程序或 AI 工作流继续处理",
            (
                "通过接口搜索并抓取公开网页",
                "从页面中提取正文和结构化内容",
                "把网页整理成更易处理的文本数据",
            ),
            "需要为 AI 应用、搜索或数据流程接入网页内容的开发者",
        )

    if _has_all(topics, "office", "cli"):
        return _profile(
            "用命令行读取、修改和批量处理 Office 文件",
            "让脚本或 AI Agent 接手文档工作",
            (
                "读取和修改 Word、Excel 与 PowerPoint 文件",
                "通过命令行批量执行常见文档操作",
                "把 Office 文件处理接入 Agent 工作流",
            ),
            "需要用脚本或 AI Agent 批量处理办公文件的开发者与知识工作者",
        )

    if "office" in topics:
        return _profile(
            "读取、修改和整理常见 Office 文件",
            "把重复的文档处理步骤集中完成",
            (
                "读取并整理办公文档中的内容",
                "修改表格、文档或演示文件",
                "把重复的文件处理步骤组成工作流",
            ),
            "需要批量整理文档、表格或演示文件的办公与开发人员",
        )

    if _description_has_positive_phrase(description, "use codex from claude code") and (
        _description_has_positive_phrase(description, "review code")
        or _description_has_positive_phrase(description, "delegate tasks")
    ):
        return _profile(
            "在 Claude Code 中调用 Codex 审查代码或委派任务",
            "让两个编程助手在同一开发流程中分工",
            (
                "从 Claude Code 会话直接调用 Codex",
                "让 Codex 对代码变更提供审查意见",
                "把适合的开发任务委派给 Codex 执行",
            ),
            "同时使用 Claude Code 与 Codex 协作开发的工程师",
        )

    if _has_any(topics, "ai-penetration-testing", "ai-pentesting") or _has_all(
        topics, "security", "pentest"
    ):
        return _profile(
            "自动检查应用中的安全漏洞",
            "把发现的问题整理成可修复的线索",
            (
                "对应用执行自动化渗透测试",
                "定位可能被攻击者利用的漏洞",
                "给出需要优先检查和修复的问题",
            ),
            "需要在发布前检查应用攻击面和漏洞的安全与开发团队",
        )

    meeting_clues = _has_any(
        topics,
        "ai-meeting-assistant",
        "meeting-minutes",
        "meeting-notes",
    )
    transcription_clues = "transcription" in topics or _description_has_positive_phrase(
        description, "live transcription", "meeting transcription"
    )
    if meeting_clues and transcription_clues:
        local = _has_any(topics, "local-ai", "offline-first", "on-device")
        local_task = "在本地转写会议并整理会议记录" if local else "转写会议并整理会议记录"
        local_highlight = "在本地整理会议摘要和纪要" if local else "整理会议摘要和可回看的纪要"
        return _profile(
            local_task,
            "保留说话内容并生成便于回看的摘要",
            (
                "把会议语音转换成文字记录",
                "按发言内容整理会议讨论脉络",
                local_highlight,
            ),
            "需要会后快速获得文字记录和会议纪要的团队与个人",
        )

    if "system-prompts" in identity or _description_has_positive_phrase(
        description, "extracted system prompts", "system prompt collection"
    ):
        return _profile(
            "集中检索和对照不同 AI 产品的系统提示词",
            "帮助研究模型指令和产品交互设计",
            (
                "按模型和工具整理系统提示词样本",
                "对照不同产品的指令结构与约束",
                "持续汇总可用于研究的提示词资料",
            ),
            "研究模型行为、提示词设计或 AI 产品交互的读者",
        )

    if "agent-orchestration" in topics:
        return _profile(
            "组织和切换多个编程 Agent",
            "让不同 Agent 分工处理开发任务",
            (
                "同时管理多个编程 Agent 会话",
                "把不同开发任务分配给合适的 Agent",
                "切换并复用已经建立的 Agent 工作流",
            ),
            "需要让多个编程 Agent 并行协作的开发者与技术负责人",
        )

    if "agent-ide" in topics:
        return _profile(
            "集中运行和管理多个编程 Agent",
            "让开发任务可以并行推进",
            (
                "在同一界面启动多个编程 Agent",
                "把任务拆给不同 Agent 并行执行",
                "集中查看各个 Agent 的执行状态",
            ),
            "需要统一管理多个编程 Agent 和并行任务的研发团队",
        )

    if _has_any(topics, "ai-gateway", "llm-gateway", "model-routing"):
        return _profile(
            "统一接入并路由多个 AI 模型服务",
            "把模型选择和供应商配置集中管理",
            (
                "用统一入口连接不同模型服务",
                "按配置把请求路由到目标模型",
                "集中管理模型供应商和调用方式",
            ),
            "需要接入多个模型供应商或维护统一调用层的 AI 开发者",
        )

    if _has_all(topics, "skills", "sdlc"):
        return _profile(
            "给编程 Agent 提供可复用的软件开发技能",
            "让需求、编码和验证按固定流程推进",
            (
                "把常用开发方法封装成可复用技能",
                "按规划、实现和验证步骤组织任务",
                "在不同项目中复用同一套开发流程",
            ),
            "希望让编程 Agent 按固定方法完成研发任务的开发者",
        )

    if _has_all(topics, "mcp", "terminal-automation"):
        return _profile(
            "通过 MCP 让模型操作终端和本地工具",
            "把命令执行接入 Agent 工作流",
            (
                "向 MCP 客户端暴露终端操作能力",
                "让 Agent 运行命令并读取执行结果",
                "把本地工具接入可组合的自动化流程",
            ),
            "需要把终端工具接入 MCP 或 Agent 工作流的开发者",
        )

    if "terminal-automation" in topics:
        return _profile(
            "在终端中执行并串联重复操作",
            "把命令行任务整理成自动化流程",
            (
                "批量运行常用命令行操作",
                "把多个终端步骤串成固定流程",
                "减少重复输入命令和手动切换",
            ),
            "需要批量执行命令或维护终端工作流的开发者与运维人员",
        )

    if "code-review" in topics:
        return _profile(
            "检查代码变更并整理审查意见",
            "帮助团队发现问题和统一修改建议",
            (
                "逐项检查提交中的代码变更",
                "标出潜在缺陷和需要确认的实现",
                "把审查意见整理成可跟进的建议",
            ),
            "需要审查合并请求或统一代码质量标准的研发团队",
        )

    if "transcription" in topics:
        return _profile(
            "把语音内容转换成可编辑文字",
            "方便检索、整理和继续加工",
            (
                "将录音或实时语音转换为文字",
                "生成便于复制和编辑的文本记录",
                "为摘要、搜索和归档准备文字材料",
            ),
            "需要整理访谈、课程、会议或录音内容的用户",
        )

    if "prompt-engineering" in topics:
        return _profile(
            "整理和复用提示词设计方法",
            "帮助测试不同指令结构和模型表现",
            (
                "收集可复用的提示词模式和示例",
                "对照不同指令结构带来的输出差异",
                "把提示词设计过程整理成可重复方法",
            ),
            "需要设计、测试和维护模型提示词的产品与开发人员",
        )

    if (
        _has_all(topics, "bundler", "javascript")
        and _description_has_positive_phrase(description, "javascript runtime")
        and _description_has_positive_phrase(description, "package manager")
    ):
        return _profile(
            "运行、打包和测试 JavaScript 或 TypeScript 项目",
            "把运行时、包管理和构建工具放在同一套工具中",
            (
                "直接运行 JavaScript 和 TypeScript 程序",
                "打包项目代码并管理依赖",
                "执行测试并生成可发布的构建结果",
            ),
            "希望用一套工具完成 JavaScript 开发、测试和构建的开发者",
        )

    if _has_all(topics, "bundler", "javascript"):
        return _profile(
            "打包 JavaScript 或 TypeScript 项目代码",
            "生成便于部署和分发的构建产物",
            (
                "把多个源码模块合并成可发布文件",
                "处理项目构建所需的依赖和资源",
                "为开发和发布流程生成打包结果",
            ),
            "需要构建前端应用、库或 JavaScript 工具的开发者",
        )

    if (
        _has_any(topics, "postgres", "postgresql")
        and "rust" in topics
        and _description_has_positive_phrase(description, "postgres rewritten in rust")
    ):
        return _profile(
            "用 Rust 实现并验证兼容 PostgreSQL 的数据库核心",
            "帮助研究数据库内核和 Rust 系统开发",
            (
                "用 Rust 重写 PostgreSQL 的核心实现",
                "运行 PostgreSQL 回归测试检查兼容性",
                "为数据库内核实验提供可研究的实现",
            ),
            "研究 PostgreSQL 内核、Rust 或数据库系统实现的开发者",
        )

    if _has_any(topics, "developer-tools", "devtools", "automation"):
        return _profile(
            "把重复的开发操作整理成自动化流程",
            "减少手动执行和重复配置",
            (
                "把常用开发步骤组合成可复用任务",
                "通过脚本重复执行同一套操作",
                "让团队共享一致的自动化工作流",
            ),
            "需要减少重复操作并统一研发流程的软件团队",
        )

    if "mcp" in topics:
        return _profile(
            "把外部工具和数据接入支持 MCP 的模型应用",
            "用统一协议建立工具调用连接",
            (
                "为模型应用提供标准化工具接口",
                "连接外部数据源和可调用工具",
                "把工具能力暴露给兼容 MCP 的客户端",
            ),
            "需要开发 MCP 服务或集成外部工具的应用开发者",
        )

    if _has_any(topics, "ai-agent", "ai-agents", "agentic-ai", "agent"):
        return _profile(
            "搭建能够连续执行多步任务的 AI Agent",
            "把模型能力接入可重复的任务流程",
            (
                "把复杂任务拆成连续的执行步骤",
                "让 Agent 围绕目标推进任务流程",
                "为工具调用和工作流扩展提供基础",
            ),
            "需要搭建自动化智能体或多步骤 AI 工作流的开发者",
        )

    return _profile(
        "核对这个仓库的具体用途和使用方式",
        "在信息补全前保留人工审核门槛",
        (
            "需要查看仓库 README 确认主要任务",
            "需要核对实际输入、输出和使用方式",
            "需要人工确认适用场景后再发布",
        ),
        "公开信息不足，需人工确认后再发布",
        review_required=True,
    )


def _narrative_variant(repository: Any, narrative_index: int | None) -> int:
    """Choose a reproducible wording variant, with report order taking precedence."""

    if narrative_index is not None:
        return narrative_index % _NARRATIVE_VARIANT_COUNT
    identity = str(getattr(repository, "full_name", "") or getattr(repository, "name", ""))
    digest = sha256(identity.encode("utf-8")).digest()
    return digest[0] % _NARRATIVE_VARIANT_COUNT


def _one_line(name: str, profile: _CapabilityProfile, variant: int) -> str:
    if profile.review_required:
        review_variants = (
            f"公开信息不足，暂不能准确说明 {name} 的具体用途",
            f"{name} 的用途证据不足，需要先查看仓库 README",
            f"目前无法从公开字段确认 {name} 能完成哪些任务",
            f"在补充 README 证据前，{name} 需要人工核对用途",
            f"{name} 暂无足够功能证据，不应直接进入发布稿",
            f"这次只能确认 {name} 的仓库身份，具体功能仍待核对",
            f"要解释 {name} 的用途，还需要补充可核验的 README 信息",
        )
        return _clip(review_variants[variant], 96)

    task = profile.task
    benefit = profile.benefit
    variants = (
        f"{name} 可以{task}，同时{benefit}",
        f"想要{task}，可以用 {name}；它能{benefit}",
        f"主要任务是{task}；{name} 还能{benefit}",
        f"用 {name} 可以{task}，还会{benefit}",
        f"这类任务可以交给 {name}：{task}，并{benefit}",
        f"当你需要{task}，{name} 可以接手，同时{benefit}",
        f"如果工作流里要{task}，可以交给 {name}，同时{benefit}",
    )
    return _clip(variants[variant], 96)


def summarize_repository(
    repository: Any,
    star_delta: int | None = None,
    delta_source: str = "estimate",
    narrative_index: int | None = None,
) -> RepositorySummary:
    """Explain what a repository does without turning metadata into features."""

    del star_delta, delta_source
    name = getattr(repository, "name", None) or str(repository.full_name).rsplit("/", 1)[-1]
    profile = _capability_profile(repository)
    variant = _narrative_variant(repository, narrative_index)
    one_line = _one_line(name, profile, variant)
    return RepositorySummary(
        one_line=one_line,
        highlights=profile.highlights,
        audience=profile.audience,
        capabilities=profile.highlights,
        core_title=_clip(profile.task, 60),
        core_summary=one_line,
        content_status="needs_review" if profile.review_required else "metadata_only",
    )


def summary_candidates(
    repository: Any,
    star_delta: int | None = None,
    delta_source: str = "estimate",
) -> tuple[tuple[str, RepositorySummary], ...]:
    """Return every controlled purpose-first candidate for editorial selection."""

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

import pytest

from github_hotspots.models import Repository
from github_hotspots.summarizer import (
    NARRATIVE_ANGLES,
    summarize_repository,
    summary_candidates,
)

FORBIDDEN_PHRASES = (
    "是一个近期升温",
    "聚焦“",
    "值得关注",
    "不容错过",
    "宝藏项目",
    "面向开源软件与工程实践",
)

METADATA_MARKERS = (
    " Star",
    " Fork",
    "主要语言",
    "公开 Topics",
    "快照",
    "Trending",
    "最近推送",
    "候选信号",
)


def _repository(owner: str = "example") -> Repository:
    return Repository(
        full_name=f"{owner}/shared-tool",
        html_url=f"https://github.com/{owner}/shared-tool",
        description="A practical developer automation toolkit.",
        language="Python",
        stars=12_345,
        forks=678,
        topics=("automation", "developer-tools"),
    )


def _rendered(summary) -> str:
    return "\n".join((summary.one_line, *summary.highlights, summary.audience))


def test_summary_explains_purpose_and_capabilities_without_metadata() -> None:
    for narrative_index in range(len(NARRATIVE_ANGLES)):
        summary = summarize_repository(
            _repository(),
            star_delta=125,
            delta_source="snapshot",
            narrative_index=narrative_index,
        )
        rendered = _rendered(summary)

        assert "自动化流程" in summary.one_line
        assert len(summary.highlights) == 3
        assert len(set(summary.highlights)) == 3
        assert "重复操作" in summary.audience
        assert all(phrase not in rendered for phrase in FORBIDDEN_PHRASES)
        assert all(marker not in rendered for marker in METADATA_MARKERS)
        assert "12,345" not in rendered
        assert "678" not in rendered
        assert "125" not in rendered


def test_summary_is_deterministic_for_the_same_repository() -> None:
    first = summarize_repository(_repository(), star_delta=125, delta_source="snapshot")
    second = summarize_repository(_repository(), star_delta=125, delta_source="snapshot")

    assert first == second


def test_weekly_candidates_keep_seven_distinct_purpose_first_openings() -> None:
    candidates = summary_candidates(_repository(), star_delta=125, delta_source="snapshot")

    assert tuple(angle for angle, _summary in candidates) == NARRATIVE_ANGLES
    assert len(candidates) == 7
    assert len({summary.one_line[:12] for _angle, summary in candidates}) == 7
    assert all("自动化流程" in summary.one_line for _angle, summary in candidates)
    assert all(summary.highlights == candidates[0][1].highlights for _angle, summary in candidates)


@pytest.mark.parametrize(
    ("repository", "one_line_term", "highlight_term", "audience_term"),
    [
        (
            Repository(
                full_name="catchorg/Catch2",
                description=("A modern, C++-native, test framework for unit-tests, TDD and BDD."),
                topics=("bdd", "cpp", "cpp14", "tdd", "test-framework", "testing"),
            ),
            "C++ 项目编写和运行单元测试",
            "TDD 或 BDD",
            "C++ 库或应用",
        ),
        (
            Repository(
                full_name="firecrawl/firecrawl",
                description="The API to search, scrape, and interact with the web at scale.",
                topics=(
                    "ai-crawler",
                    "ai-scraping",
                    "crawler",
                    "data-extraction",
                    "html-to-markdown",
                ),
            ),
            "抓取并整理网页内容",
            "结构化内容",
            "接入网页内容",
        ),
        (
            Repository(
                full_name="iOfficeAI/OfficeCLI",
                description=(
                    "AI agents can read, edit, and automate Word, Excel, and PowerPoint files."
                ),
                topics=("agent", "ai", "cli", "docx", "excel", "office", "powerpoint"),
            ),
            "命令行读取、修改和批量处理 Office 文件",
            "Word、Excel 与 PowerPoint",
            "办公文件",
        ),
        (
            Repository(
                full_name="openai/codex-plugin-cc",
                description="Use Codex from Claude Code to review code or delegate tasks.",
                topics=(),
            ),
            "Claude Code 中调用 Codex",
            "代码变更提供审查意见",
            "Claude Code 与 Codex",
        ),
        (
            Repository(
                full_name="usestrix/strix",
                description=(
                    "Open-source AI penetration testing tool to find and fix app vulnerabilities."
                ),
                topics=("ai-penetration-testing", "ai-pentesting", "security"),
            ),
            "检查应用中的安全漏洞",
            "自动化渗透测试",
            "检查应用攻击面",
        ),
        (
            Repository(
                full_name="Zackriya-Solutions/meetily",
                description=(
                    "AI meeting assistant with live transcription, speaker diarization, "
                    "and local summarization."
                ),
                topics=(
                    "ai-meeting-assistant",
                    "local-ai",
                    "meeting-minutes",
                    "meeting-notes",
                    "offline-first",
                ),
            ),
            "本地转写会议",
            "会议摘要和纪要",
            "文字记录和会议纪要",
        ),
        (
            Repository(
                full_name="asgeirtj/system_prompts_leaks",
                description="Extracted system prompts from Claude, ChatGPT, Gemini, and more.",
                topics=("ai", "anthropic", "chatgpt", "claude"),
            ),
            "对照不同 AI 产品的系统提示词",
            "指令结构与约束",
            "模型行为",
        ),
        (
            Repository(
                full_name="ogulcancelik/herdr",
                description="Agent multiplexer that lives in your terminal.",
                topics=("agent", "agent-orchestration", "coding-agents", "multiplexer"),
            ),
            "组织和切换多个编程 Agent",
            "分配给合适的 Agent",
            "多个编程 Agent 并行协作",
        ),
        (
            Repository(
                full_name="stablyai/orca",
                description="An environment for working with a fleet of parallel agents.",
                topics=("agent-ide", "ai-agents", "devtools"),
            ),
            "管理多个编程 Agent",
            "并行执行",
            "统一管理多个编程 Agent",
        ),
        (
            Repository(
                full_name="diegosouzapw/OmniRoute",
                description="AI gateway with provider routing.",
                topics=("ai-gateway", "model-routing", "ai-agents"),
            ),
            "路由多个 AI 模型服务",
            "统一入口",
            "多个模型供应商",
        ),
        (
            Repository(
                full_name="obra/superpowers",
                description="An agentic skills framework and development methodology.",
                topics=("ai", "coding", "sdlc", "skills", "subagent-driven-development"),
            ),
            "可复用的软件开发技能",
            "规划、实现和验证",
            "固定方法完成研发任务",
        ),
        (
            Repository(
                full_name="wonderwhy-er/DesktopCommanderMCP",
                description=(
                    "MCP server that gives Claude terminal control and file system tools."
                ),
                topics=("agent", "mcp", "terminal-ai", "terminal-automation"),
            ),
            "通过 MCP 让模型操作终端",
            "读取执行结果",
            "终端工具接入 MCP",
        ),
        (
            Repository(
                full_name="example/prompt-workbench",
                description="A prompt design workbench.",
                topics=("prompt-engineering",),
            ),
            "提示词设计方法",
            "指令结构带来的输出差异",
            "维护模型提示词",
        ),
        (
            Repository(
                full_name="oven-sh/bun",
                description=(
                    "JavaScript runtime, bundler, test runner, and package manager in one."
                ),
                topics=("bun", "bundler", "javascript", "typescript"),
            ),
            "运行、打包和测试 JavaScript",
            "打包项目代码并管理依赖",
            "JavaScript 开发、测试和构建",
        ),
        (
            Repository(
                full_name="malisper/pgrust",
                description="Postgres rewritten in Rust and running Postgres regression tests.",
                topics=("database", "postgres", "postgresql", "rust"),
            ),
            "Rust 实现并验证兼容 PostgreSQL",
            "PostgreSQL 回归测试",
            "数据库系统实现",
        ),
        (
            Repository(
                full_name="NousResearch/hermes-agent",
                description="The agent that grows with you.",
                topics=("ai", "ai-agent", "ai-agents", "llm"),
            ),
            "多步任务的 AI Agent",
            "连续的执行步骤",
            "多步骤 AI 工作流",
        ),
    ],
    ids=(
        "catch2",
        "firecrawl",
        "office-cli",
        "codex-plugin-cc",
        "ai-pentest",
        "local-meeting-transcription",
        "system-prompt-library",
        "agent-orchestration",
        "agent-ide",
        "ai-gateway",
        "agent-skills",
        "mcp-terminal-automation",
        "prompt-engineering",
        "bun-toolchain",
        "postgres-in-rust",
        "generic-agent",
    ),
)
def test_supported_categories_explain_real_tasks(
    repository: Repository,
    one_line_term: str,
    highlight_term: str,
    audience_term: str,
) -> None:
    summary = summarize_repository(repository, narrative_index=0)
    rendered = _rendered(summary)

    assert one_line_term in summary.one_line
    assert highlight_term in " ".join(summary.highlights)
    assert audience_term in summary.audience
    assert len(summary.highlights) == 3
    assert len(set(summary.highlights)) == 3
    assert all(marker not in rendered for marker in METADATA_MARKERS)


def test_free_description_negation_cannot_create_capability_claims() -> None:
    repository = Repository(
        full_name="example/not-a-meeting-tool",
        description=(
            "This is not a meeting assistant and has no live transcription or "
            "system prompt collection."
        ),
        topics=(),
    )

    summary = summarize_repository(repository, narrative_index=0)
    rendered = _rendered(summary)

    assert "会议" not in rendered
    assert "转写" not in rendered
    assert "系统提示词" not in rendered
    assert "公开信息不足" in summary.one_line
    assert "人工确认" in summary.audience


def test_negated_codex_description_does_not_trigger_plugin_profile() -> None:
    repository = Repository(
        full_name="example/not-codex-plugin",
        description="Do not use Codex from Claude Code to review code or delegate tasks.",
        topics=(),
    )

    summary = summarize_repository(repository, narrative_index=0)

    assert "Claude Code 中调用 Codex" not in summary.one_line
    assert "用途证据不足" in summary.one_line or "公开信息不足" in summary.one_line


@pytest.mark.parametrize(
    ("topic", "expected_term", "forbidden_term", "audience_term"),
    [
        ("transcription", "语音内容转换", "AI", "访谈、课程、会议或录音"),
        ("terminal-automation", "终端中执行", "MCP", "终端工作流"),
        ("code-review", "检查代码变更", "AI", "合并请求"),
        ("office", "Office 文件", "命令行", "文档、表格或演示文件"),
        ("mcp", "支持 MCP", "终端", "MCP 服务"),
    ],
)
def test_single_topic_does_not_gain_unproven_modifiers(
    topic: str,
    expected_term: str,
    forbidden_term: str,
    audience_term: str,
) -> None:
    repository = Repository(
        full_name=f"example/{topic}",
        description="Untrusted free-form description.",
        topics=(topic,),
    )

    summary = summarize_repository(repository, narrative_index=0)

    assert expected_term in summary.one_line
    assert forbidden_term not in _rendered(summary)
    assert audience_term in summary.audience


def test_unknown_repository_is_marked_for_human_review() -> None:
    repository = Repository(
        full_name="example/unknown-tool",
        description="A thing for modern teams.",
        topics=(),
    )

    summary = summarize_repository(repository, narrative_index=0)

    assert summary.one_line == "公开信息不足，暂不能准确说明 unknown-tool 的具体用途"
    assert summary.highlights == (
        "需要查看仓库 README 确认主要任务",
        "需要核对实际输入、输出和使用方式",
        "需要人工确认适用场景后再发布",
    )
    assert summary.audience == "公开信息不足，需人工确认后再发布"

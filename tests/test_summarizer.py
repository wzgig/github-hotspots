from itertools import pairwise

import pytest

from github_hotspots.models import Repository
from github_hotspots.summarizer import summarize_repository

FORBIDDEN_PHRASES = (
    "是一个近期升温",
    "聚焦“",
    "值得关注",
    "不容错过",
    "宝藏项目",
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


def test_summary_avoids_forbidden_cliches() -> None:
    for narrative_index in range(7):
        summary = summarize_repository(
            _repository(),
            star_delta=125,
            delta_source="snapshot",
            narrative_index=narrative_index,
        )
        rendered = "\n".join((summary.one_line, *summary.highlights, summary.audience))
        assert all(phrase not in rendered for phrase in FORBIDDEN_PHRASES)
        assert "A practical developer automation toolkit" not in summary.one_line
        assert "开发工具与自动化项目" in summary.one_line


def test_summary_is_deterministic_for_the_same_repository() -> None:
    first = summarize_repository(_repository(), star_delta=125, delta_source="snapshot")
    second = summarize_repository(_repository(), star_delta=125, delta_source="snapshot")

    assert first == second
    assert "12,345 Star" in " ".join((first.one_line, *first.highlights))
    assert "678 Fork" in " ".join((first.one_line, *first.highlights))


def test_report_order_produces_distinct_neighboring_narratives() -> None:
    summaries = [
        summarize_repository(
            _repository(owner=f"owner-{index}"),
            star_delta=125,
            delta_source="snapshot",
            narrative_index=index,
        )
        for index in range(4)
    ]

    one_lines = [summary.one_line for summary in summaries]
    assert len(set(one_lines)) == len(one_lines)
    assert all(left != right for left, right in pairwise(one_lines))
    assert any(line.startswith("本地快照记录") for line in one_lines)
    assert any(line.startswith("以 Python 为主要语言") for line in one_lines)


def test_weekly_board_uses_seven_distinct_opening_patterns() -> None:
    repository = _repository()
    repository.pushed_at = "2026-07-11T00:00:00Z"
    repository.sources = ("trending", "search")

    summaries = [
        summarize_repository(
            repository,
            star_delta=125,
            delta_source="snapshot",
            narrative_index=index,
        )
        for index in range(7)
    ]

    openings = [summary.one_line[:12] for summary in summaries]
    assert len(set(openings)) == 7


def test_specific_audience_rules_beat_generic_ai_category() -> None:
    security = Repository(
        full_name="example/ai-pentest",
        description="An AI penetration testing tool for application vulnerabilities.",
        topics=("ai", "security", "pentest"),
    )
    office = Repository(
        full_name="example/office-agent",
        description="An agent for Office document automation.",
        topics=("ai", "office", "automation"),
    )

    assert summarize_repository(security).audience.startswith("安全工程师")
    assert summarize_repository(office).audience.startswith("Office 工具开发者")


def test_specific_positioning_rules_turn_public_clues_into_chinese_copy() -> None:
    gateway = Repository(
        full_name="example/model-gateway",
        description="Free AI gateway with one endpoint and provider routing.",
        topics=("ai-gateway", "model-routing", "mcp"),
    )
    meeting = Repository(
        full_name="example/meeting-helper",
        description="Privacy first AI meeting assistant and meeting notes.",
        topics=("ai-meeting-assistant",),
    )
    agent_ide = Repository(
        full_name="example/agent-ide",
        description="An agent development environment for a fleet of parallel agents.",
        topics=("agent-ide", "claude-code"),
    )

    assert "AI 网关项目" in summarize_repository(gateway, narrative_index=0).one_line
    assert "AI 会议助手项目" in summarize_repository(meeting, narrative_index=0).one_line
    assert "智能体 IDE 项目" in summarize_repository(agent_ide, narrative_index=0).one_line


def test_free_description_negation_cannot_create_a_strong_positioning_claim() -> None:
    repository = Repository(
        full_name="example/not-a-meeting-tool",
        description="This is not a meeting assistant and has no privacy features.",
        topics=(),
    )

    summary = summarize_repository(repository, narrative_index=0)

    assert "会议" not in summary.one_line
    assert "隐私" not in summary.one_line
    assert "开源软件与工程实践" in summary.one_line


@pytest.mark.parametrize(
    (
        "topic",
        "expected_positioning",
        "forbidden_positioning",
        "expected_audience",
        "forbidden_audience",
    ),
    [
        ("transcription", "语音转写项目", "AI", "软件开发者", ("AI",)),
        ("terminal-automation", "终端自动化项目", "MCP", "软件开发者", ("MCP",)),
        ("code-review", "代码审查项目", "AI", "代码审查参与者", ("AI",)),
        ("office", "Office 相关项目", "命令行", "Office 工具开发者", ("自动化",)),
        (
            "mcp",
            "开源软件与工程实践",
            "终端自动化",
            "MCP 集成开发者",
            ("终端自动化", "AI 工具作者"),
        ),
    ],
)
def test_single_topic_does_not_gain_unproven_modifiers(
    topic: str,
    expected_positioning: str,
    forbidden_positioning: str,
    expected_audience: str,
    forbidden_audience: tuple[str, ...],
) -> None:
    repository = Repository(
        full_name=f"example/{topic}",
        description="Untrusted free-form description.",
        topics=(topic,),
    )

    summary = summarize_repository(repository, narrative_index=0)

    assert expected_positioning in summary.one_line
    assert forbidden_positioning not in summary.one_line
    assert expected_audience in summary.audience
    assert all(term not in summary.audience for term in forbidden_audience)

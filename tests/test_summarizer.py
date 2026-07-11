from itertools import pairwise

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
        assert "开发流程自动化" in summary.one_line


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
    assert summarize_repository(office).audience.startswith("Office 自动化开发者")


def test_specific_positioning_rules_turn_public_clues_into_chinese_copy() -> None:
    gateway = Repository(
        full_name="example/model-gateway",
        description="Free AI gateway with one endpoint and provider routing.",
        topics=("ai-gateway", "model-routing"),
    )
    meeting = Repository(
        full_name="example/meeting-helper",
        description="Privacy first AI meeting assistant and meeting notes.",
        topics=("meeting-assistant",),
    )
    agent_ide = Repository(
        full_name="example/agent-ide",
        description="An agent development environment for a fleet of parallel agents.",
        topics=("agent-ide", "claude-code"),
    )

    assert "统一接入与路由多种 AI 模型" in summarize_repository(gateway, narrative_index=0).one_line
    assert "注重隐私的 AI 会议记录助手" in summarize_repository(meeting, narrative_index=0).one_line
    assert (
        "面向并行智能体协作的开发环境"
        in summarize_repository(agent_ide, narrative_index=0).one_line
    )

from github_hotspots.boards import select_ai_repositories
from github_hotspots.config import BoardSettings
from github_hotspots.models import Repository


def _ai_settings() -> BoardSettings:
    return BoardSettings(
        key="ai",
        label="AI 专题榜",
        enabled=True,
        daily_top_n=3,
        weekly_top_n=7,
        topics=("machine-learning",),
        keywords=("ai", "machine learning", "openai"),
    )


def test_ai_selection_matches_exact_topics_tokens_and_phrases() -> None:
    repositories = [
        Repository(full_name="acme/topic-match", topics=("Machine-Learning",)),
        Repository(
            full_name="acme/phrase-match",
            description="A practical machine-learning toolkit.",
        ),
        Repository(full_name="acme/awesome-ai", description="Developer toolkit."),
        Repository(full_name="acme/openai-client", description="Typed SDK."),
    ]

    selected = select_ai_repositories(repositories, _ai_settings())

    assert [repository.name for repository in selected] == [
        "topic-match",
        "phrase-match",
        "awesome-ai",
        "openai-client",
    ]


def test_ai_selection_does_not_use_naive_ai_substrings() -> None:
    repositories = [
        Repository(
            full_name="acme/rails-maintainer",
            description="Email and training workflow utilities.",
        ),
        Repository(full_name="acme/airflow-tools", description="Data orchestration."),
    ]

    assert select_ai_repositories(repositories, _ai_settings()) == []


def test_disabled_ai_board_returns_no_candidates() -> None:
    settings = _ai_settings()
    disabled = BoardSettings(
        key=settings.key,
        label=settings.label,
        enabled=False,
        daily_top_n=settings.daily_top_n,
        weekly_top_n=settings.weekly_top_n,
        topics=settings.topics,
        keywords=settings.keywords,
    )

    repositories = [Repository(full_name="acme/ai", description="AI toolkit")]

    assert select_ai_repositories(repositories, disabled) == []

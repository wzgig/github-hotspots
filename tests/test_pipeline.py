from datetime import date
from pathlib import Path

from github_hotspots.config import load_settings
from github_hotspots.models import Repository
from github_hotspots.pipeline import _apply_filters, _rank_boards, _search_qualifiers


def test_filters_remove_low_star_missing_description_and_excluded_owner() -> None:
    repositories = [
        Repository(full_name="good/project", description="Useful", stars=500),
        Repository(full_name="small/project", description="Useful", stars=2),
        Repository(full_name="empty/project", description=None, stars=500),
        Repository(full_name="blocked/project", description="Useful", stars=500),
    ]
    filters = {
        "min_stars": 50,
        "require_description": True,
        "excluded_languages": [],
        "excluded_owners": ["blocked"],
        "excluded_repositories": [],
    }

    result = _apply_filters(repositories, filters)

    assert [repository.full_name for repository in result] == ["good/project"]


def test_search_qualifiers_reflect_filter_policy() -> None:
    qualifiers = _search_qualifiers(
        {
            "exclude_archived": True,
            "exclude_forks": True,
            "exclude_mirrors": True,
            "min_stars": 50,
        }
    )

    assert qualifiers == "archived:false fork:false mirror:false stars:>=50"


def test_comprehensive_and_ai_candidates_are_ranked_independently() -> None:
    settings = load_settings(Path("config/hotspots.yaml"))
    repositories = [
        Repository(
            full_name="acme/database-engine",
            description="A fast database engine.",
            stars=10_000,
            daily_stars=500,
            pushed_at="2026-07-11T00:00:00Z",
        ),
        Repository(
            full_name="acme/model-lab",
            description="A machine learning experimentation toolkit.",
            stars=1_000,
            daily_stars=50,
            pushed_at="2026-07-11T00:00:00Z",
        ),
    ]

    comprehensive, ai = _rank_boards(
        repositories,
        settings=settings,
        period="daily",
        as_of=date(2026, 7, 11),
    )

    assert [item.repository.name for item in comprehensive] == ["database-engine", "model-lab"]
    assert comprehensive[1].rank == 2
    assert [item.repository.name for item in ai] == ["model-lab"]
    assert ai[0].rank == 1

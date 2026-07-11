from github_hotspots.models import Repository
from github_hotspots.pipeline import _apply_filters, _search_qualifiers


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

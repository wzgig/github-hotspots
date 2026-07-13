from __future__ import annotations

from datetime import date

import pytest

from github_hotspots.models import Repository, RepositorySnapshot
from github_hotspots.ranking import DEFAULT_WEIGHTS, percentile_ranks, rank_repositories


def test_rank_repositories_prefers_snapshot_then_trending_then_estimate() -> None:
    # Arrange
    repositories = [
        Repository(
            repository_id=1,
            full_name="acme/alpha",
            stars=150,
            forks=20,
            daily_stars=500,
            trending_rank_daily=2,
            pushed_at="2026-07-11T08:00:00Z",
        ),
        Repository(
            repository_id=2,
            full_name="acme/beta",
            stars=1_000,
            forks=200,
            daily_stars=40,
            trending_rank_daily=1,
            pushed_at="2026-07-01T08:00:00Z",
        ),
        Repository(
            repository_id=3,
            full_name="acme/gamma",
            stars=100,
            forks=10,
            created_at="2026-07-01T00:00:00Z",
        ),
    ]
    baseline = [
        RepositorySnapshot(
            captured_on=date(2026, 7, 10),
            repository_id=1,
            full_name="old-owner/alpha",
            stars=100,
            forks=10,
        )
    ]

    # Act
    ranked = rank_repositories(
        repositories,
        baseline_1d=baseline,
        period="daily",
        as_of=date(2026, 7, 11),
    )
    by_name = {item.repository.name: item for item in ranked}

    # Assert
    assert ranked[0].repository.full_name == "acme/alpha"
    assert [item.rank for item in ranked] == [1, 2, 3]
    assert (by_name["alpha"].star_delta, by_name["alpha"].fork_delta) == (50, 10)
    assert by_name["alpha"].delta_source == "snapshot"
    assert by_name["beta"].star_delta == 40
    assert by_name["beta"].delta_source == "trending"
    assert (by_name["gamma"].star_delta, by_name["gamma"].fork_delta) == (10, 1)
    assert by_name["gamma"].delta_source == "estimate"
    assert set(by_name["alpha"].component_percentiles) == set(DEFAULT_WEIGHTS)
    assert by_name["alpha"].component_percentiles["activity"] == 100.0
    assert by_name["beta"].component_percentiles["trending_signal"] == 100.0


def test_weekly_ranking_uses_seven_day_baseline_and_weekly_signal() -> None:
    # Arrange
    repositories = [
        Repository(
            repository_id=7,
            full_name="acme/snapshot",
            stars=100,
            forks=30,
            weekly_stars=999,
        ),
        Repository(
            repository_id=8,
            full_name="acme/trending",
            stars=500,
            forks=50,
            weekly_stars=70,
            trending_rank_weekly=4,
        ),
    ]
    baseline_1d = [
        RepositorySnapshot(
            captured_on=date(2026, 7, 10),
            repository_id=7,
            full_name="acme/snapshot",
            stars=90,
            forks=29,
        )
    ]
    baseline_7d = [
        RepositorySnapshot(
            captured_on=date(2026, 7, 4),
            repository_id=7,
            full_name="acme/snapshot",
            stars=50,
            forks=20,
        )
    ]

    # Act
    ranked = rank_repositories(
        repositories,
        baseline_1d,
        baseline_7d,
        period="weekly",
        as_of=date(2026, 7, 11),
    )
    by_name = {item.repository.name: item for item in ranked}

    # Assert
    assert by_name["snapshot"].star_delta == 50
    assert by_name["snapshot"].fork_delta == 10
    assert by_name["snapshot"].delta_source == "snapshot"
    assert by_name["trending"].star_delta == 70
    assert by_name["trending"].fork_delta == 0
    assert by_name["trending"].delta_source == "trending"
    assert by_name["trending"].component_percentiles["trending_signal"] == 43.07


def test_activity_score_uses_report_timezone_before_taking_the_date() -> None:
    # Arrange: these timestamps describe the same instant, shortly after midnight in Shanghai.
    repositories = [
        Repository(
            full_name="acme/utc-timestamp",
            stars=100,
            daily_stars=10,
            pushed_at="2026-07-12T23:30:00Z",
        ),
        Repository(
            full_name="acme/local-timestamp",
            stars=100,
            daily_stars=10,
            pushed_at="2026-07-13T07:30:00+08:00",
        ),
    ]

    # Act
    ranked = rank_repositories(
        repositories,
        period="daily",
        as_of=date(2026, 7, 13),
        timezone="Asia/Shanghai",
    )

    # Assert
    activity = {item.repository.name: item.component_percentiles["activity"] for item in ranked}
    assert activity == {"local-timestamp": 100.0, "utc-timestamp": 100.0}


def test_rank_repositories_rejects_unknown_report_timezone() -> None:
    with pytest.raises(ValueError, match="unknown report timezone"):
        rank_repositories(
            [Repository(full_name="acme/timezone", daily_stars=1)],
            period="daily",
            timezone="Mars/Olympus_Mons",
        )


def test_percentile_ranks_are_tie_aware_and_explainable() -> None:
    # Arrange
    values = [1, 2, 2, 4]

    # Act
    result = percentile_ranks(values)

    # Assert
    assert result == [0.0, 50.0, 50.0, 100.0]
    assert percentile_ranks([9]) == [100.0]
    assert percentile_ranks([]) == []


def test_custom_weights_must_match_six_component_contract() -> None:
    # Arrange
    repositories = [Repository(full_name="acme/only", daily_stars=1)]
    invalid_weights = {"star_growth": 1.0}

    # Act / Assert
    with pytest.raises(ValueError, match="weights must contain exactly"):
        rank_repositories(repositories, period="daily", weights=invalid_weights)


def test_ranked_repository_to_dict_is_flat_and_json_ready() -> None:
    # Arrange
    repository = Repository(
        repository_id=11,
        full_name="acme/json",
        stars=25,
        daily_stars=5,
        topics=("python", "automation"),
    )

    # Act
    payload = rank_repositories([repository], period="daily")[0].to_dict()

    # Assert
    assert payload["repository_id"] == 11
    assert payload["owner"] == "acme"
    assert payload["name"] == "json"
    assert payload["topics"] == ["python", "automation"]
    assert payload["delta_source"] == "trending"
    assert payload["component_percentiles"]["star_growth"] == 100.0

"""Explainable percentile ranking for collected repositories."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime

from .github_client import deduplicate_repositories
from .models import RankedRepository, Repository, RepositorySnapshot

DEFAULT_WEIGHTS: dict[str, float] = {
    "star_growth": 0.50,
    "relative_growth": 0.20,
    "fork_growth": 0.10,
    "activity": 0.10,
    "total_stars": 0.05,
    "trending_signal": 0.05,
}


@dataclass(slots=True)
class _GrowthSignal:
    repository: Repository
    star_delta: int
    fork_delta: int
    delta_source: str
    baseline_stars: int


def rank_repositories(
    repositories: Iterable[Repository],
    baseline_1d: Iterable[RepositorySnapshot] | None = None,
    baseline_7d: Iterable[RepositorySnapshot] | None = None,
    *,
    period: str = "daily",
    weights: Mapping[str, float] | None = None,
    as_of: date | None = None,
) -> list[RankedRepository]:
    """Rank repositories with a transparent weighted-percentile formula.

    The daily run uses a 1-day snapshot and the weekly run a 7-day snapshot.
    For each repository, growth is selected in this order:

    1. exact snapshot counter delta (``delta_source='snapshot'``),
    2. GitHub Trending period stars (``'trending'``),
    3. historical average since creation (``'estimate'``).

    Growth and total-star components are converted to 0..100 percentiles;
    recent activity and Trending rank are already 0..100 signals.  The final
    score is their weighted sum using :data:`DEFAULT_WEIGHTS`.
    """

    if period not in {"daily", "weekly"}:
        raise ValueError("period must be 'daily' or 'weekly'")
    repositories_list = deduplicate_repositories(repositories)
    if not repositories_list:
        return []

    selected_baseline = baseline_1d if period == "daily" else baseline_7d
    baseline_index = _BaselineIndex(selected_baseline or [])
    run_date = as_of or date.today()
    signals = [
        _growth_signal(repository, baseline_index, period, run_date)
        for repository in repositories_list
    ]

    normalised_weights = _normalise_weights(weights)
    window_days = 1 if period == "daily" else 7
    scored_star_deltas = [
        max(signal.star_delta, 0) if signal.delta_source != "estimate" else 0 for signal in signals
    ]
    scored_fork_deltas = [
        max(signal.fork_delta, 0) if signal.delta_source != "estimate" else 0 for signal in signals
    ]
    percentile_inputs: dict[str, list[float]] = {
        "star_growth": [math.log1p(delta / window_days) for delta in scored_star_deltas],
        "relative_growth": [
            math.log1p(delta / math.sqrt(max(signal.baseline_stars, 25)))
            for signal, delta in zip(signals, scored_star_deltas, strict=True)
        ],
        "fork_growth": [math.log1p(delta / window_days) for delta in scored_fork_deltas],
        "total_stars": [math.log1p(max(signal.repository.stars, 0)) for signal in signals],
    }
    percentiles = {
        component: percentile_ranks(values) for component, values in percentile_inputs.items()
    }
    direct_signals = {
        "activity": [
            _activity_score(signal.repository.pushed_at, window_days, run_date)
            for signal in signals
        ],
        "trending_signal": [_trending_score(signal.repository, period) for signal in signals],
    }

    unranked: list[RankedRepository] = []
    for index, signal in enumerate(signals):
        component_percentiles: dict[str, float] = {
            component: round(values[index], 2) for component, values in percentiles.items()
        }
        component_percentiles.update(
            {component: round(values[index], 2) for component, values in direct_signals.items()}
        )
        score = sum(
            component_percentiles[component] * weight
            for component, weight in normalised_weights.items()
        )
        unranked.append(
            RankedRepository(
                repository=signal.repository,
                rank=0,
                score=round(score, 2),
                star_delta=signal.star_delta,
                fork_delta=signal.fork_delta,
                delta_source=signal.delta_source,
                component_percentiles=component_percentiles,
            )
        )

    ordered = sorted(
        unranked,
        key=lambda item: (
            -item.score,
            -item.star_delta,
            -item.repository.stars,
            item.repository.full_name.casefold(),
        ),
    )
    for rank, item in enumerate(ordered, start=1):
        item.rank = rank
    return ordered


def percentile_ranks(values: Sequence[int | float]) -> list[float]:
    """Return tie-aware percentiles in input order.

    Formula for ``n > 1``::

        100 * (count_lower + (count_equal - 1) / 2) / (n - 1)

    A one-item collection is assigned 100 because it is both the minimum and
    maximum of its comparison set.
    """

    if not values:
        return []
    if len(values) == 1:
        return [100.0]
    result: list[float] = []
    for value in values:
        lower = sum(candidate < value for candidate in values)
        equal = sum(candidate == value for candidate in values)
        percentile = 100.0 * (lower + (equal - 1) / 2) / (len(values) - 1)
        result.append(percentile)
    return result


class _BaselineIndex:
    def __init__(self, snapshots: Iterable[RepositorySnapshot]) -> None:
        self._by_id: dict[int, RepositorySnapshot] = {}
        self._by_name: dict[str, RepositorySnapshot] = {}
        for snapshot in snapshots:
            if snapshot.repository_id is not None:
                self._by_id[snapshot.repository_id] = snapshot
            self._by_name[snapshot.full_name.casefold()] = snapshot

    def find(self, repository: Repository) -> RepositorySnapshot | None:
        if repository.repository_id is not None:
            by_id = self._by_id.get(repository.repository_id)
            if by_id is not None:
                return by_id
        return self._by_name.get(repository.full_name.casefold())


def _growth_signal(
    repository: Repository,
    baseline_index: _BaselineIndex,
    period: str,
    as_of: date,
) -> _GrowthSignal:
    baseline = baseline_index.find(repository)
    if baseline is not None:
        return _GrowthSignal(
            repository=repository,
            star_delta=repository.stars - baseline.stars,
            fork_delta=repository.forks - baseline.forks,
            delta_source="snapshot",
            baseline_stars=baseline.stars,
        )

    trending_stars = repository.period_stars(period)
    if trending_stars is not None:
        return _GrowthSignal(
            repository=repository,
            star_delta=max(0, trending_stars),
            fork_delta=0,
            delta_source="trending",
            baseline_stars=max(repository.stars - max(trending_stars, 0), 0),
        )

    window_days = 1 if period == "daily" else 7
    star_delta, fork_delta = _historical_average_estimate(repository, window_days, as_of)
    return _GrowthSignal(
        repository=repository,
        star_delta=star_delta,
        fork_delta=fork_delta,
        delta_source="estimate",
        baseline_stars=max(repository.stars - star_delta, 0),
    )


def _activity_score(pushed_at: str | None, window_days: int, as_of: date) -> float:
    pushed_on = _parse_date(pushed_at)
    if pushed_on is None:
        return 0.0
    days_since_push = max((as_of - pushed_on).days, 0)
    return math.exp(-days_since_push / (2 * window_days + 1)) * 100.0


def _trending_score(repository: Repository, period: str) -> float:
    rank = repository.trending_rank_daily if period == "daily" else repository.trending_rank_weekly
    if rank is None or rank < 1:
        return 0.0
    return min(100.0, 100.0 / math.log2(rank + 1))


def _historical_average_estimate(
    repository: Repository, window_days: int, as_of: date
) -> tuple[int, int]:
    created_on = _parse_date(repository.created_at)
    if created_on is None:
        return 0, 0
    age_days = max((as_of - created_on).days, 1)
    estimated_stars = round(max(repository.stars, 0) * window_days / age_days)
    estimated_forks = round(max(repository.forks, 0) * window_days / age_days)
    return estimated_stars, estimated_forks


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _normalise_weights(
    weights: Mapping[str, float] | None,
) -> dict[str, float]:
    values = dict(DEFAULT_WEIGHTS if weights is None else weights)
    unknown = set(values) - set(DEFAULT_WEIGHTS)
    missing = set(DEFAULT_WEIGHTS) - set(values)
    if unknown or missing:
        expected = ", ".join(DEFAULT_WEIGHTS)
        raise ValueError(f"weights must contain exactly: {expected}")
    if any(
        not isinstance(value, (int, float)) or not math.isfinite(float(value)) or value < 0
        for value in values.values()
    ):
        raise ValueError("weights must be finite non-negative numbers")
    total = sum(float(value) for value in values.values())
    if total <= 0:
        raise ValueError("at least one weight must be positive")
    return {component: float(value) / total for component, value in values.items()}

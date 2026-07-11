"""End-to-end collection, ranking, snapshot, and report orchestration."""

from __future__ import annotations

import os
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from .config import Settings
from .github_client import GitHubClient, deduplicate_repositories
from .models import Repository
from .ranking import rank_repositories
from .report import ReportArtifacts, render_reports
from .snapshot import SnapshotStore
from .trending import fetch_trending


@dataclass(frozen=True, slots=True)
class PipelineResult:
    period: str
    run_date: date
    candidate_count: int
    ranked_count: int
    snapshot: Path
    artifacts: ReportArtifacts
    warnings: tuple[str, ...]


def run_pipeline(settings: Settings, period: str, run_date: date) -> PipelineResult:
    """Run one daily or weekly workflow with graceful source degradation."""

    run = settings.run(period)
    warnings: list[str] = []
    token_name = str(settings.github.get("token_env", "GITHUB_TOKEN"))
    token = os.getenv(token_name) or None
    timeout = float(settings.github.get("request_timeout_seconds", 30))
    base_url = str(settings.github.get("api_base_url", "https://api.github.com"))

    trending_candidates = _collect_trending(settings, period)
    if settings.sources.get("trending", {}).get("enabled", True) and not trending_candidates:
        warnings.append("GitHub Trending 未返回候选，已降级使用 REST Search")

    with GitHubClient(token=token, base_url=base_url, timeout=timeout) as client:
        search_candidates = _collect_search(settings, client, run_date, run.lookback_days)
        if settings.sources.get("search", {}).get("enabled", True) and not search_candidates:
            warnings.append("GitHub REST Search 未返回候选，可能受到限流或筛选条件影响")

        # Search results already contain REST metadata.  Enrich only the small
        # Trending set to keep an unauthenticated run below the hourly limit.
        enriched_trending = client.enrich_repositories(trending_candidates)

    candidates = deduplicate_repositories([*enriched_trending, *search_candidates])
    candidates = _apply_filters(candidates, settings.filters)
    if not candidates:
        raise RuntimeError("No repositories remained after collection and filtering")

    store = SnapshotStore(settings.snapshots_dir)
    baseline_1d, baseline_7d = store.baselines(run_date)
    rankings = rank_repositories(
        candidates,
        baseline_1d=baseline_1d,
        baseline_7d=baseline_7d,
        period=period,
        weights=settings.ranking_weights,
        as_of=run_date,
    )
    selected = rankings[: run.top_n]
    snapshot_path = store.save(run_date, candidates)
    artifacts = render_reports(
        settings=settings,
        period=period,
        run_date=run_date,
        rankings=selected,
        extra_warnings=warnings,
    )
    return PipelineResult(
        period=period,
        run_date=run_date,
        candidate_count=len(candidates),
        ranked_count=len(selected),
        snapshot=snapshot_path,
        artifacts=artifacts,
        warnings=tuple(warnings),
    )


def _collect_trending(settings: Settings, period: str) -> list[Repository]:
    source = settings.sources.get("trending", {})
    if not source.get("enabled", True):
        return []
    languages = list(source.get("languages") or [None])
    spoken_language = source.get("spoken_language") or None
    timeout = float(settings.github.get("request_timeout_seconds", 30))
    maximum = max(1, int(source.get("max_repositories", 25)))

    repositories: list[Repository] = []
    for language in languages:
        repositories.extend(
            fetch_trending(
                period,
                language=language,
                spoken_language=spoken_language,
                timeout=timeout,
                headers={
                    "User-Agent": str(settings.github.get("user_agent", "github-hotspots/0.1"))
                },
            )[:maximum]
        )
    return deduplicate_repositories(repositories)[:maximum]


def _collect_search(
    settings: Settings,
    client: GitHubClient,
    run_date: date,
    lookback_days: int,
) -> list[Repository]:
    source = settings.sources.get("search", {})
    if not source.get("enabled", True):
        return []

    since = (run_date - timedelta(days=lookback_days)).isoformat()
    qualifiers = _search_qualifiers(settings.filters)
    repositories: list[Repository] = []
    for template in source.get("queries", []):
        query = str(template).format(since=since)
        if qualifiers:
            query = f"{query} {qualifiers}"
        repositories.extend(
            client.search_repositories(
                query,
                sort=str(source.get("sort", "stars")),
                order=str(source.get("order", "desc")),
                per_page=int(source.get("per_page", 50)),
            )
        )
    return deduplicate_repositories(repositories)


def _search_qualifiers(filters: dict | object) -> str:
    values = filters if isinstance(filters, dict) else dict(filters)  # type: ignore[arg-type]
    qualifiers: list[str] = []
    if values.get("exclude_archived", True):
        qualifiers.append("archived:false")
    if values.get("exclude_forks", True):
        qualifiers.append("fork:false")
    if values.get("exclude_mirrors", True):
        qualifiers.append("mirror:false")
    minimum = int(values.get("min_stars", 0) or 0)
    if minimum > 0:
        qualifiers.append(f"stars:>={minimum}")
    return " ".join(qualifiers)


def _apply_filters(repositories: Iterable[Repository], filters: object) -> list[Repository]:
    values = filters if isinstance(filters, dict) else dict(filters)  # type: ignore[arg-type]
    minimum = int(values.get("min_stars", 0) or 0)
    require_description = bool(values.get("require_description", False))
    excluded_languages = _casefold_set(values.get("excluded_languages", []))
    excluded_owners = _casefold_set(values.get("excluded_owners", []))
    excluded_repositories = _casefold_set(values.get("excluded_repositories", []))

    filtered: list[Repository] = []
    for repository in deduplicate_repositories(repositories):
        if repository.stars < minimum:
            continue
        if require_description and not (repository.description or "").strip():
            continue
        if (repository.language or "").casefold() in excluded_languages:
            continue
        if repository.owner.casefold() in excluded_owners:
            continue
        if repository.full_name.casefold() in excluded_repositories:
            continue
        filtered.append(repository)
    return filtered


def _casefold_set(values: object) -> set[str]:
    if not isinstance(values, (list, tuple, set)):
        return set()
    return {str(value).casefold() for value in values}

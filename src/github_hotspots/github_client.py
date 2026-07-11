"""Small GitHub REST client and repository merge helpers."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import replace
from typing import Any
from urllib.parse import quote

import httpx

from .models import Repository

GITHUB_API_URL = "https://api.github.com"


class GitHubClient:
    """Read repository metadata from GitHub's REST API.

    HTTP failures degrade to ``None`` or an empty list.  This allows a pipeline
    to keep Trending-only records when API access is temporarily unavailable or
    rate-limited.
    """

    def __init__(
        self,
        token: str | None = None,
        *,
        client: Any | None = None,
        base_url: str = GITHUB_API_URL,
        timeout: float = 20.0,
    ) -> None:
        self._owns_client = client is None
        self._client = client or httpx.Client(
            base_url=base_url,
            timeout=timeout,
            follow_redirects=True,
            headers=_github_headers(token),
        )

    def __enter__(self) -> GitHubClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        """Close an internally-created HTTP client."""

        if self._owns_client:
            self._client.close()

    def search_repositories(
        self,
        query: str,
        *,
        sort: str = "stars",
        order: str = "desc",
        per_page: int = 30,
        page: int = 1,
    ) -> list[Repository]:
        """Search GitHub repositories and parse the returned metadata."""

        params = {
            "q": query,
            "sort": sort,
            "order": order,
            "per_page": max(1, min(int(per_page), 100)),
            "page": max(1, int(page)),
        }
        payload = self._get_json("/search/repositories", params=params)
        items = payload.get("items", []) if payload else []
        if not isinstance(items, list):
            return []
        repositories = [
            repository
            for item in items
            if isinstance(item, Mapping)
            if (repository := repository_from_api(item)) is not None
        ]
        return deduplicate_repositories(repositories)

    def get_repository(self, full_name: str) -> Repository | None:
        """Fetch one repository by ``owner/name``."""

        if full_name.count("/") != 1:
            return None
        path = f"/repos/{quote(full_name.strip(), safe='/')}"
        payload = self._get_json(path)
        return repository_from_api(payload) if payload else None

    def enrich_repositories(self, repositories: Iterable[Repository]) -> list[Repository]:
        """Add REST metadata while preserving all Trending signals."""

        enriched: list[Repository] = []
        for repository in deduplicate_repositories(repositories):
            metadata = self.get_repository(repository.full_name)
            enriched.append(
                _overlay_api_metadata(repository, metadata) if metadata is not None else repository
            )
        return deduplicate_repositories(enriched)

    def _get_json(
        self, path: str, *, params: Mapping[str, Any] | None = None
    ) -> dict[str, Any] | None:
        try:
            response = self._client.get(path, params=dict(params or {}))
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, OSError, ValueError, TypeError):
            return None
        return dict(payload) if isinstance(payload, Mapping) else None


def repository_from_api(payload: Mapping[str, Any]) -> Repository | None:
    """Convert one GitHub REST repository object into a model."""

    full_name = payload.get("full_name")
    if not isinstance(full_name, str) or full_name.count("/") != 1:
        return None
    repository_id = _optional_int(payload.get("id"))
    topics = payload.get("topics")
    topic_values = (
        tuple(str(topic) for topic in topics if isinstance(topic, str))
        if isinstance(topics, list)
        else ()
    )
    return Repository(
        repository_id=repository_id,
        full_name=full_name,
        html_url=str(payload.get("html_url") or f"https://github.com/{full_name}"),
        description=_optional_string(payload.get("description")),
        language=_optional_string(payload.get("language")),
        stars=_int_or_zero(payload.get("stargazers_count")),
        forks=_int_or_zero(payload.get("forks_count")),
        open_issues=_int_or_zero(payload.get("open_issues_count")),
        watchers=_int_or_zero(payload.get("subscribers_count", payload.get("watchers_count"))),
        topics=topic_values,
        created_at=_optional_string(payload.get("created_at")),
        updated_at=_optional_string(payload.get("updated_at")),
        pushed_at=_optional_string(payload.get("pushed_at")),
        sources=("github_api",),
    )


def deduplicate_repositories(
    repositories: Iterable[Repository],
) -> list[Repository]:
    """Deduplicate by repository ID or case-insensitive ``full_name``.

    The small O(n²) merge is intentional: input lists are normally tens or
    hundreds of rows, and this approach correctly collapses a bridging record
    where one duplicate shares an ID and another only shares a name.
    """

    result: list[Repository] = []
    for repository in repositories:
        matching_indexes = [
            index for index, existing in enumerate(result) if _same_repository(existing, repository)
        ]
        if not matching_indexes:
            result.append(repository)
            continue

        target = matching_indexes[0]
        merged = merge_repositories(result[target], repository)
        for duplicate_index in reversed(matching_indexes[1:]):
            merged = merge_repositories(merged, result[duplicate_index])
            del result[duplicate_index]
        result[target] = merged
    return result


def merge_repositories(left: Repository, right: Repository) -> Repository:
    """Merge duplicate collector records without losing period signals."""

    return Repository(
        repository_id=right.repository_id or left.repository_id,
        full_name=right.full_name or left.full_name,
        html_url=right.html_url or left.html_url,
        description=right.description or left.description,
        language=right.language or left.language,
        stars=max(left.stars, right.stars),
        forks=max(left.forks, right.forks),
        open_issues=max(left.open_issues, right.open_issues),
        watchers=max(left.watchers, right.watchers),
        topics=_ordered_union(left.topics, right.topics),
        created_at=_earlier(left.created_at, right.created_at),
        updated_at=_later(left.updated_at, right.updated_at),
        pushed_at=_later(left.pushed_at, right.pushed_at),
        daily_stars=_max_optional(left.daily_stars, right.daily_stars),
        weekly_stars=_max_optional(left.weekly_stars, right.weekly_stars),
        trending_rank_daily=_min_optional(left.trending_rank_daily, right.trending_rank_daily),
        trending_rank_weekly=_min_optional(left.trending_rank_weekly, right.trending_rank_weekly),
        sources=_ordered_union(left.sources, right.sources),
    )


def _overlay_api_metadata(collected: Repository, metadata: Repository) -> Repository:
    # REST counters are the current source of truth; Trending-only fields are
    # copied back explicitly rather than using a generic, ambiguous merge rule.
    return replace(
        metadata,
        html_url=metadata.html_url or collected.html_url,
        description=metadata.description or collected.description,
        language=metadata.language or collected.language,
        topics=metadata.topics or collected.topics,
        daily_stars=collected.daily_stars,
        weekly_stars=collected.weekly_stars,
        trending_rank_daily=collected.trending_rank_daily,
        trending_rank_weekly=collected.trending_rank_weekly,
        sources=_ordered_union(collected.sources, metadata.sources),
    )


def _same_repository(left: Repository, right: Repository) -> bool:
    ids_match = (
        left.repository_id is not None
        and right.repository_id is not None
        and left.repository_id == right.repository_id
    )
    names_match = left.full_name.casefold() == right.full_name.casefold()
    return ids_match or names_match


def _github_headers(token: str | None) -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "github-hotspots/1.0",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _optional_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _int_or_zero(value: Any) -> int:
    return _optional_int(value) or 0


def _optional_string(value: Any) -> str | None:
    return str(value) if value is not None and str(value).strip() else None


def _ordered_union(left: tuple[str, ...], right: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys((*left, *right)))


def _max_optional(left: int | None, right: int | None) -> int | None:
    values = [value for value in (left, right) if value is not None]
    return max(values) if values else None


def _min_optional(left: int | None, right: int | None) -> int | None:
    values = [value for value in (left, right) if value is not None]
    return min(values) if values else None


def _later(left: str | None, right: str | None) -> str | None:
    values = [value for value in (left, right) if value]
    return max(values) if values else None


def _earlier(left: str | None, right: str | None) -> str | None:
    values = [value for value in (left, right) if value]
    return min(values) if values else None

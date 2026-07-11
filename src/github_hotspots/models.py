"""Shared data models for the GitHub Hotspots core.

The models intentionally contain no I/O.  They are small transfer objects that
can be used by collectors, snapshot storage, ranking, reporting, and a CLI.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any


@dataclass(slots=True)
class Repository:
    """A repository enriched with optional GitHub Trending signals."""

    full_name: str
    repository_id: int | None = None
    html_url: str = ""
    description: str | None = None
    language: str | None = None
    stars: int = 0
    forks: int = 0
    open_issues: int = 0
    watchers: int = 0
    topics: tuple[str, ...] = field(default_factory=tuple)
    created_at: str | None = None
    updated_at: str | None = None
    pushed_at: str | None = None
    daily_stars: int | None = None
    weekly_stars: int | None = None
    trending_rank_daily: int | None = None
    trending_rank_weekly: int | None = None
    sources: tuple[str, ...] = field(default_factory=tuple)

    @property
    def owner(self) -> str:
        """Return the owner component of ``owner/name``."""

        owner, separator, _ = self.full_name.partition("/")
        return owner if separator else ""

    @property
    def name(self) -> str:
        """Return the repository name component of ``owner/name``."""

        _, separator, name = self.full_name.partition("/")
        return name if separator else self.full_name

    def period_stars(self, period: str) -> int | None:
        """Return the Trending star count associated with a period."""

        if period == "daily":
            return self.daily_stars
        if period == "weekly":
            return self.weekly_stars
        raise ValueError("period must be 'daily' or 'weekly'")

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible representation."""

        return {
            "repository_id": self.repository_id,
            "full_name": self.full_name,
            "owner": self.owner,
            "name": self.name,
            "html_url": self.html_url,
            "description": self.description,
            "language": self.language,
            "stars": self.stars,
            "forks": self.forks,
            "open_issues": self.open_issues,
            "watchers": self.watchers,
            "topics": list(self.topics),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "pushed_at": self.pushed_at,
            "daily_stars": self.daily_stars,
            "weekly_stars": self.weekly_stars,
            "trending_rank_daily": self.trending_rank_daily,
            "trending_rank_weekly": self.trending_rank_weekly,
            "sources": list(self.sources),
        }


@dataclass(slots=True, frozen=True)
class RepositorySnapshot:
    """The counters needed to calculate growth for one repository and day."""

    captured_on: date
    full_name: str
    stars: int
    repository_id: int | None = None
    forks: int = 0
    open_issues: int = 0

    @classmethod
    def from_repository(cls, repository: Repository, captured_on: date) -> RepositorySnapshot:
        """Build a compact snapshot from a repository."""

        return cls(
            captured_on=captured_on,
            repository_id=repository.repository_id,
            full_name=repository.full_name,
            stars=repository.stars,
            forks=repository.forks,
            open_issues=repository.open_issues,
        )

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> RepositorySnapshot:
        """Parse a JSON object written by :meth:`to_dict`."""

        repository_id = value.get("repository_id")
        return cls(
            captured_on=date.fromisoformat(str(value["captured_on"])),
            repository_id=int(repository_id) if repository_id is not None else None,
            full_name=str(value["full_name"]),
            stars=int(value.get("stars", 0)),
            forks=int(value.get("forks", 0)),
            open_issues=int(value.get("open_issues", 0)),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible representation."""

        return {
            "captured_on": self.captured_on.isoformat(),
            "repository_id": self.repository_id,
            "full_name": self.full_name,
            "stars": self.stars,
            "forks": self.forks,
            "open_issues": self.open_issues,
        }


@dataclass(slots=True)
class RankedRepository:
    """A repository plus an explainable ranking result."""

    repository: Repository
    rank: int
    score: float
    star_delta: int
    delta_source: str
    fork_delta: int = 0
    component_percentiles: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a flat JSON-compatible representation for reports."""

        return {
            **self.repository.to_dict(),
            "rank": self.rank,
            "score": self.score,
            "star_delta": self.star_delta,
            "fork_delta": self.fork_delta,
            "delta_source": self.delta_source,
            "component_percentiles": dict(self.component_percentiles),
        }

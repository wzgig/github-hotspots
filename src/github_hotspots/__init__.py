"""Core collectors, snapshots, and ranking for GitHub Hotspots."""

from .github_client import (
    GitHubClient,
    deduplicate_repositories,
    merge_repositories,
    repository_from_api,
)
from .models import RankedRepository, Repository, RepositorySnapshot
from .ranking import DEFAULT_WEIGHTS, percentile_ranks, rank_repositories
from .snapshot import SnapshotStore
from .trending import fetch_trending, parse_count, parse_trending_html

__all__ = [
    "DEFAULT_WEIGHTS",
    "GitHubClient",
    "RankedRepository",
    "Repository",
    "RepositorySnapshot",
    "SnapshotStore",
    "deduplicate_repositories",
    "fetch_trending",
    "merge_repositories",
    "parse_count",
    "parse_trending_html",
    "percentile_ranks",
    "rank_repositories",
    "repository_from_api",
]

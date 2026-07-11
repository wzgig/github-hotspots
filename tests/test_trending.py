from __future__ import annotations

import httpx

from github_hotspots.github_client import GitHubClient, deduplicate_repositories
from github_hotspots.models import Repository
from github_hotspots.trending import fetch_trending, parse_count, parse_trending_html


def test_parse_daily_trending_extracts_repository_and_period_stars() -> None:
    # Arrange
    html = """
    <main>
      <article class="Box-row">
        <h2><a href="/octo/example"> octo / example </a></h2>
        <p class="col-9">A resilient parser fixture.</p>
        <span itemprop="programmingLanguage">Python</span>
        <a href="/octo/example/stargazers">12,345</a>
        <a href="/octo/example/forks">678</a>
        <span class="d-inline-block float-sm-right">321 stars today</span>
      </article>
      <article class="Box-row"><h2>missing link</h2></article>
    </main>
    """

    # Act
    repositories = parse_trending_html(html, "daily")

    # Assert
    assert len(repositories) == 1
    repository = repositories[0]
    assert repository.full_name == "octo/example"
    assert repository.owner == "octo"
    assert repository.name == "example"
    assert repository.html_url == "https://github.com/octo/example"
    assert repository.description == "A resilient parser fixture."
    assert repository.language == "Python"
    assert repository.stars == 12_345
    assert repository.forks == 678
    assert repository.daily_stars == 321
    assert repository.weekly_stars is None
    assert repository.trending_rank_daily == 1
    assert repository.sources == ("trending_daily",)


def test_parse_weekly_trending_supports_compact_counts_and_missing_fields() -> None:
    # Arrange
    html = """
    <article class="Box-row">
      <h2><a href="/acme/toolkit">acme / toolkit</a></h2>
      <a href="/acme/toolkit/stargazers">1.2k</a>
      <span>2,004 stars this week</span>
    </article>
    """

    # Act
    repositories = parse_trending_html(html, "weekly")

    # Assert
    assert len(repositories) == 1
    assert repositories[0].stars == 1_200
    assert repositories[0].forks == 0
    assert repositories[0].description is None
    assert repositories[0].weekly_stars == 2_004
    assert repositories[0].trending_rank_weekly == 1
    assert parse_count("3.5M") == 3_500_000
    assert parse_count("not available") == 0


def test_fetch_trending_uses_injected_client_without_network() -> None:
    # Arrange
    html = """
    <article class="Box-row">
      <h2><a href="/owner/repo">owner/repo</a></h2>
      <span>42 stars today</span>
    </article>
    """

    class FakeResponse:
        text = html

        @staticmethod
        def raise_for_status() -> None:
            return None

    class FakeClient:
        def __init__(self) -> None:
            self.request: tuple[str, dict[str, str], dict[str, str]] | None = None

        def get(self, url: str, *, params: dict[str, str], headers: dict[str, str]) -> FakeResponse:
            self.request = (url, params, headers)
            return FakeResponse()

    client = FakeClient()

    # Act
    repositories = fetch_trending("daily", language="python", client=client)

    # Assert
    assert repositories[0].daily_stars == 42
    assert client.request is not None
    assert client.request[0] == "https://github.com/trending/python"
    assert client.request[1] == {"since": "daily"}
    assert client.request[2]["User-Agent"] == "github-hotspots/1.0"


def test_fetch_trending_degrades_to_empty_list_on_http_error() -> None:
    # Arrange
    class FailingClient:
        @staticmethod
        def get(*args: object, **kwargs: object) -> object:
            raise httpx.ConnectError("offline")

    # Act
    repositories = fetch_trending("weekly", client=FailingClient())

    # Assert
    assert repositories == []


def test_enrichment_and_deduplication_preserve_daily_and_weekly_signals() -> None:
    # Arrange
    daily = Repository(
        full_name="Acme/Tool",
        html_url="https://github.com/Acme/Tool",
        daily_stars=25,
        trending_rank_daily=2,
        sources=("trending_daily",),
    )
    weekly = Repository(
        repository_id=99,
        full_name="acme/tool",
        weekly_stars=120,
        trending_rank_weekly=4,
        sources=("trending_weekly",),
    )

    class ApiResponse:
        @staticmethod
        def raise_for_status() -> None:
            return None

        @staticmethod
        def json() -> dict[str, object]:
            return {
                "id": 99,
                "full_name": "acme/tool",
                "html_url": "https://github.com/acme/tool",
                "description": "API description",
                "language": "Python",
                "stargazers_count": 2_000,
                "forks_count": 300,
                "open_issues_count": 12,
                "subscribers_count": 17,
                "topics": ["automation"],
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2026-07-10T00:00:00Z",
                "pushed_at": "2026-07-11T00:00:00Z",
            }

    class ApiClient:
        @staticmethod
        def get(path: str, *, params: dict[str, object]) -> ApiResponse:
            assert path == "/repos/acme/tool"
            assert params == {}
            return ApiResponse()

    combined = deduplicate_repositories([daily, weekly])

    # Act
    enriched = GitHubClient(client=ApiClient()).enrich_repositories(combined)

    # Assert
    assert len(enriched) == 1
    repository = enriched[0]
    assert repository.repository_id == 99
    assert repository.stars == 2_000
    assert repository.daily_stars == 25
    assert repository.weekly_stars == 120
    assert repository.sources == (
        "trending_daily",
        "trending_weekly",
        "github_api",
    )

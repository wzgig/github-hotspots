"""Collect and parse GitHub Trending pages."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any, Literal
from urllib.parse import quote, urljoin

import httpx
from bs4 import BeautifulSoup, Tag

from .models import Repository

TrendingPeriod = Literal["daily", "weekly"]

TRENDING_URL = "https://github.com/trending"
_NUMBER_RE = re.compile(r"(?P<number>\d[\d,]*(?:\.\d+)?\s*[kKmM]?)")
_PERIOD_STARS_RE = re.compile(
    r"(?P<number>\d[\d,]*(?:\.\d+)?\s*[kKmM]?)\s+stars?\s+"
    r"(?:today|this\s+week)",
    re.IGNORECASE,
)


def parse_count(value: str | None) -> int:
    """Parse GitHub counters such as ``1,234`` or ``1.2k``.

    Missing or unrecognisable counters degrade to zero so one changed HTML
    fragment does not discard an otherwise useful Trending entry.
    """

    if not value:
        return 0
    match = _NUMBER_RE.search(value)
    if not match:
        return 0
    token = match.group("number").replace(",", "").replace(" ", "")
    multiplier = 1
    if token[-1:].lower() == "k":
        token = token[:-1]
        multiplier = 1_000
    elif token[-1:].lower() == "m":
        token = token[:-1]
        multiplier = 1_000_000
    try:
        return int(float(token) * multiplier)
    except ValueError:
        return 0


def parse_trending_html(html: str, period: TrendingPeriod = "daily") -> list[Repository]:
    """Parse a GitHub Trending HTML document into repositories.

    Parsing is deliberately entry-scoped: malformed articles are skipped while
    valid neighbours are still returned.  Optional fields become ``None`` or
    zero when GitHub changes a selector.
    """

    _validate_period(period)
    try:
        soup = BeautifulSoup(html or "", "html.parser")
    except Exception:
        return []

    repositories: list[Repository] = []
    for position, article in enumerate(soup.select("article.Box-row"), start=1):
        try:
            repository = _parse_article(article, period, position)
        except (AttributeError, KeyError, TypeError, ValueError):
            repository = None
        if repository is not None:
            repositories.append(repository)
    return repositories


def fetch_trending(
    period: TrendingPeriod = "daily",
    *,
    language: str | None = None,
    spoken_language: str | None = None,
    client: Any | None = None,
    timeout: float = 20.0,
    headers: Mapping[str, str] | None = None,
) -> list[Repository]:
    """Fetch and parse GitHub Trending, returning an empty list on HTTP errors.

    Passing a client with a ``get`` method keeps the function straightforward to
    test and lets an application reuse its own :class:`httpx.Client`.
    """

    _validate_period(period)
    url = TRENDING_URL
    if language:
        url = f"{url}/{quote(language.strip(), safe='')}"
    params: dict[str, str] = {"since": period}
    if spoken_language:
        params["spoken_language_code"] = spoken_language
    request_headers = {
        "Accept": "text/html,application/xhtml+xml",
        "User-Agent": "github-hotspots/1.0",
        **dict(headers or {}),
    }

    if client is not None:
        return _fetch_with_client(client, url, params, request_headers)

    try:
        with httpx.Client(
            timeout=timeout, headers=request_headers, follow_redirects=True
        ) as session:
            return _fetch_with_client(session, url, params, {})
    except httpx.HTTPError:
        return []


def _fetch_with_client(
    client: Any,
    url: str,
    params: Mapping[str, str],
    headers: Mapping[str, str],
) -> list[Repository]:
    try:
        response = client.get(url, params=dict(params), headers=dict(headers))
        response.raise_for_status()
    except (httpx.HTTPError, OSError):
        return []
    return parse_trending_html(getattr(response, "text", ""), params["since"])


def _parse_article(article: Tag, period: TrendingPeriod, position: int) -> Repository | None:
    link = article.select_one("h2 a[href]")
    if not isinstance(link, Tag):
        return None
    full_name = _full_name_from_link(link)
    if not full_name:
        return None

    description_node = article.select_one("p")
    language_node = article.select_one('[itemprop="programmingLanguage"]')
    star_node = article.select_one(f'a[href="/{full_name}/stargazers"]')
    fork_node = article.select_one(f'a[href="/{full_name}/forks"]')

    # The period signal has changed wrappers several times.  Matching its
    # human-readable phrase is more resilient than relying on one CSS class.
    period_match = _PERIOD_STARS_RE.search(article.get_text(" ", strip=True))
    period_stars = parse_count(period_match.group("number")) if period_match else None

    values: dict[str, Any] = {
        "full_name": full_name,
        "html_url": urljoin("https://github.com", str(link.get("href", ""))),
        "description": _optional_text(description_node),
        "language": _optional_text(language_node),
        "stars": parse_count(star_node.get_text(" ", strip=True))
        if isinstance(star_node, Tag)
        else 0,
        "forks": parse_count(fork_node.get_text(" ", strip=True))
        if isinstance(fork_node, Tag)
        else 0,
        "sources": (f"trending_{period}",),
    }
    if period == "daily":
        values["daily_stars"] = period_stars
        values["trending_rank_daily"] = position
    else:
        values["weekly_stars"] = period_stars
        values["trending_rank_weekly"] = position
    return Repository(**values)


def _full_name_from_link(link: Tag) -> str | None:
    href = str(link.get("href", "")).strip()
    path_parts = [part for part in href.split("?")[0].split("/") if part]
    if len(path_parts) >= 2:
        return "/".join(path_parts[:2])
    text = re.sub(r"\s+", "", link.get_text(" ", strip=True)).strip("/")
    return text if text.count("/") == 1 else None


def _optional_text(node: Tag | None) -> str | None:
    if not isinstance(node, Tag):
        return None
    value = node.get_text(" ", strip=True)
    return value or None


def _validate_period(period: str) -> None:
    if period not in {"daily", "weekly"}:
        raise ValueError("period must be 'daily' or 'weekly'")

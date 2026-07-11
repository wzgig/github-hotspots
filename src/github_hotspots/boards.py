"""Repository selection rules for independently ranked hotspot boards."""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence

from .config import BoardSettings
from .models import Repository

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def select_ai_repositories(
    repositories: Iterable[Repository], settings: BoardSettings
) -> list[Repository]:
    """Return repositories that match the configured AI taxonomy.

    GitHub topics first use case-insensitive exact matching.  Configured
    keywords then use whole-token or contiguous-token-phrase matching over the
    repository name, description, and topics.  This lets ``awesome-ai`` match
    the token ``ai`` without treating unrelated strings such as ``rails`` or
    ``maintainer`` as AI signals.
    """

    if not settings.enabled:
        return []
    return [repository for repository in repositories if is_ai_repository(repository, settings)]


def is_ai_repository(repository: Repository, settings: BoardSettings) -> bool:
    """Return whether one repository belongs to the configured AI board."""

    configured_topics = {topic.casefold() for topic in settings.topics}
    repository_topics = {topic.strip().casefold() for topic in repository.topics}
    if configured_topics.intersection(repository_topics):
        return True

    keyword_phrases = [_tokens(keyword) for keyword in settings.keywords]
    keyword_phrases = [phrase for phrase in keyword_phrases if phrase]
    searchable_fields = [repository.name, repository.description or "", *repository.topics]
    field_tokens = [_tokens(value) for value in searchable_fields]
    return any(
        _contains_phrase(tokens, phrase) for tokens in field_tokens for phrase in keyword_phrases
    )


def _tokens(value: str) -> tuple[str, ...]:
    return tuple(_TOKEN_PATTERN.findall(value.casefold()))


def _contains_phrase(tokens: Sequence[str], phrase: Sequence[str]) -> bool:
    phrase_length = len(phrase)
    if phrase_length == 0 or phrase_length > len(tokens):
        return False
    return any(
        tuple(tokens[index : index + phrase_length]) == tuple(phrase)
        for index in range(len(tokens) - phrase_length + 1)
    )

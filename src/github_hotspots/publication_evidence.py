"""Orchestrate publication evidence without exposing private runtime details.

The lower-level :mod:`github_hotspots.evidence` module validates individual
GitHub responses and avatar files.  This module coordinates those operations
for a set of repositories, deduplicates repositories shared by multiple
boards, and exposes a deliberately small public-metadata view.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import quote, urlsplit, urlunsplit

from .evidence import (
    UNTRUSTED_EXTERNAL_DATA,
    CachedAvatar,
    ReadmeEvidence,
    RepositoryEvidence,
    RepositoryMetadataEvidence,
    clean_readme_markdown,
)

_LICENSE_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9.+-]{0,127}\Z")
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\Z")

_WARNING_TEXT = {
    "invalid_full_name": "Repository name was invalid; remote evidence was not requested.",
    "metadata_unavailable": "Repository metadata could not be collected.",
    "metadata_identity_mismatch": "Repository metadata did not match the requested repository.",
    "readme_unavailable": "README evidence could not be collected.",
    "readme_identity_mismatch": "README evidence did not match the requested repository.",
    "avatar_url_unavailable": "The repository owner avatar URL was unavailable.",
    "avatar_cache_unavailable": "The repository owner avatar could not be cached.",
    "avatar_record_invalid": "The cached avatar record was invalid and was ignored.",
    "avatar_path_rejected": "The cached avatar path was outside the publication asset root.",
}


@dataclass(frozen=True, slots=True)
class PublicationEvidenceWarning:
    """A stable, non-sensitive warning suitable for public report metadata."""

    code: str
    message: str

    def to_dict(self) -> dict[str, str]:
        """Return a JSON-compatible warning record."""

        return {"code": self.code, "message": self.message}


@dataclass(frozen=True, slots=True)
class PublicationEvidenceBundle:
    """Editorial evidence plus publication-safe avatar and warning metadata."""

    repository_evidence: RepositoryEvidence
    avatar: CachedAvatar | None = None
    avatar_relative_path: str | None = None
    warnings: tuple[PublicationEvidenceWarning, ...] = ()

    def __post_init__(self) -> None:
        """Keep local avatar records and their public paths in lockstep."""

        if (self.avatar is None) != (self.avatar_relative_path is None):
            raise ValueError("avatar and avatar_relative_path must be provided together")
        if self.avatar_relative_path is None:
            return
        relative = PurePosixPath(self.avatar_relative_path)
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or "\\" in self.avatar_relative_path
            or relative.as_posix() != self.avatar_relative_path
        ):
            raise ValueError("avatar_relative_path must be a safe relative POSIX path")

    @property
    def evidence(self) -> RepositoryEvidence:
        """Short alias for consumers that expect a repository evidence object."""

        return self.repository_evidence

    @property
    def full_name(self) -> str:
        """Return the repository identity represented by this bundle."""

        return self.repository_evidence.metadata.full_name

    def to_public_dict(self) -> dict[str, Any]:
        """Return public JSON metadata without README text or absolute paths."""

        metadata = self.repository_evidence.metadata
        readme = self.repository_evidence.readme
        avatar = self.avatar
        return {
            "full_name": metadata.full_name,
            "license_spdx_id": metadata.license_spdx_id,
            "readme": (
                {"sha": readme.sha, "source_url": readme.source_url} if readme is not None else None
            ),
            "avatar": (
                {
                    "path": self.avatar_relative_path,
                    "sha256": avatar.sha256,
                    "width": avatar.width,
                    "height": avatar.height,
                }
                if avatar is not None
                else None
            ),
            "warnings": [warning.to_dict() for warning in self.warnings],
        }

    def to_public_metadata(self) -> dict[str, Any]:
        """Alias that makes the intended JSON use explicit to callers."""

        return self.to_public_dict()


@dataclass(frozen=True, slots=True)
class _RepositorySeed:
    full_name: str
    repository_id: int | None


def collect_publication_evidence(
    client: Any,
    repositories: Iterable[Any],
    cache_dir: str | Path,
    avatar_root: str | Path,
    include_readme: bool = True,
) -> dict[str, PublicationEvidenceBundle]:
    """Collect reusable evidence for repositories or ranked repositories.

    Network collection is deduplicated by case-insensitive ``full_name``.  The
    returned mapping retains every distinct input spelling as a key, and aliases
    for the same repository point to the same immutable bundle.  This lets the
    comprehensive and AI boards reuse one metadata, README, and avatar fetch.

    Relative ``cache_dir`` values are resolved underneath ``avatar_root``.
    Absolute cache directories must already be contained by ``avatar_root``;
    escaping that boundary is a caller error and raises :class:`ValueError`.
    Individual network, README, and avatar failures instead degrade to warnings.
    """

    root, resolved_cache_dir = _publication_paths(cache_dir, avatar_root)
    seeds: dict[str, _RepositorySeed] = {}
    aliases: dict[str, str] = {}
    for item in repositories:
        seed = _seed_from_input(item)
        normalized_name = seed.full_name.casefold()
        seeds.setdefault(normalized_name, seed)
        aliases[seed.full_name] = normalized_name

    collected = {
        normalized_name: _collect_one(
            client,
            seed,
            cache_dir=resolved_cache_dir,
            avatar_root=root,
            include_readme=bool(include_readme),
        )
        for normalized_name, seed in seeds.items()
    }
    return {
        original_name: collected[normalized_name]
        for original_name, normalized_name in aliases.items()
    }


def _collect_one(
    client: Any,
    seed: _RepositorySeed,
    *,
    cache_dir: Path,
    avatar_root: Path,
    include_readme: bool,
) -> PublicationEvidenceBundle:
    warnings: list[PublicationEvidenceWarning] = []
    if not _valid_full_name(seed.full_name):
        warnings.append(_warning("invalid_full_name"))
        metadata = _fallback_metadata(seed)
        return PublicationEvidenceBundle(
            repository_evidence=RepositoryEvidence(metadata=metadata, readme=None),
            warnings=tuple(warnings),
        )

    metadata = _fetch_metadata(client, seed, warnings)
    readme = _fetch_readme(client, seed.full_name, warnings) if include_readme else None
    avatar, relative_path = _cache_avatar(
        client,
        metadata,
        cache_dir=cache_dir,
        avatar_root=avatar_root,
        warnings=warnings,
    )
    return PublicationEvidenceBundle(
        repository_evidence=RepositoryEvidence(metadata=metadata, readme=readme),
        avatar=avatar,
        avatar_relative_path=relative_path,
        warnings=tuple(warnings),
    )


def _fetch_metadata(
    client: Any,
    seed: _RepositorySeed,
    warnings: list[PublicationEvidenceWarning],
) -> RepositoryMetadataEvidence:
    try:
        value = client.get_repository_metadata(seed.full_name)
    except Exception:  # A collection failure must not expose exception text.
        value = None
    if not isinstance(value, RepositoryMetadataEvidence):
        warnings.append(_warning("metadata_unavailable"))
        return _fallback_metadata(seed)
    if value.full_name.casefold() != seed.full_name.casefold():
        warnings.append(_warning("metadata_identity_mismatch"))
        return _fallback_metadata(seed)

    source_url = _safe_public_url(value.source_url) or _github_api_url(seed.full_name)
    html_url = _safe_public_url(value.html_url) or _github_repository_url(seed.full_name)
    license_spdx_id = _safe_license_id(value.license_spdx_id)
    return RepositoryMetadataEvidence(
        repository_id=value.repository_id,
        full_name=seed.full_name,
        html_url=html_url,
        owner_avatar_url=value.owner_avatar_url,
        license_spdx_id=license_spdx_id,
        default_branch=value.default_branch,
        source_url=source_url,
        source_trust=UNTRUSTED_EXTERNAL_DATA,
    )


def _fetch_readme(
    client: Any,
    full_name: str,
    warnings: list[PublicationEvidenceWarning],
) -> ReadmeEvidence | None:
    try:
        value = client.get_readme(full_name)
    except Exception:  # A collection failure must not expose exception text.
        value = None
    if not isinstance(value, ReadmeEvidence):
        warnings.append(_warning("readme_unavailable"))
        return None
    if value.full_name.casefold() != full_name.casefold():
        warnings.append(_warning("readme_identity_mismatch"))
        return None
    try:
        markdown = clean_readme_markdown(value.markdown)
    except (TypeError, ValueError):
        warnings.append(_warning("readme_unavailable"))
        return None
    return ReadmeEvidence(
        full_name=full_name,
        sha=value.sha,
        markdown=markdown,
        decoded_bytes=value.decoded_bytes,
        source_url=_safe_public_url(value.source_url) or _github_readme_api_url(full_name),
        source_trust=UNTRUSTED_EXTERNAL_DATA,
    )


def _cache_avatar(
    client: Any,
    metadata: RepositoryMetadataEvidence,
    *,
    cache_dir: Path,
    avatar_root: Path,
    warnings: list[PublicationEvidenceWarning],
) -> tuple[CachedAvatar | None, str | None]:
    if not metadata.owner_avatar_url:
        warnings.append(_warning("avatar_url_unavailable"))
        return None, None

    cache_key = f"repo-{sha256(metadata.full_name.casefold().encode('utf-8')).hexdigest()[:24]}"
    try:
        value = client.cache_owner_avatar(
            metadata.owner_avatar_url,
            cache_dir,
            cache_key=cache_key,
        )
    except Exception:  # A collection failure must not expose exception text.
        value = None
    if value is None:
        warnings.append(_warning("avatar_cache_unavailable"))
        return None, None
    if not _valid_avatar_record(value):
        warnings.append(_warning("avatar_record_invalid"))
        return None, None

    resolved_path = value.path.expanduser().resolve()
    if not resolved_path.is_relative_to(avatar_root):
        warnings.append(_warning("avatar_path_rejected"))
        return None, None
    relative_path = resolved_path.relative_to(avatar_root).as_posix()
    return value, relative_path


def _publication_paths(cache_dir: str | Path, avatar_root: str | Path) -> tuple[Path, Path]:
    root = Path(avatar_root).expanduser().resolve()
    candidate = Path(cache_dir).expanduser()
    if candidate.is_absolute():
        resolved_cache_dir = candidate.resolve()
    else:
        cwd_relative = candidate.resolve()
        resolved_cache_dir = (
            cwd_relative if cwd_relative.is_relative_to(root) else (root / candidate).resolve()
        )
    if not resolved_cache_dir.is_relative_to(root):
        raise ValueError("cache_dir must be contained by avatar_root")
    return root, resolved_cache_dir


def _seed_from_input(item: Any) -> _RepositorySeed:
    candidate = item
    if isinstance(item, Mapping) and "repository" in item:
        candidate = item["repository"]
    elif not isinstance(item, (str, Mapping)):
        candidate = getattr(item, "repository", item)

    if isinstance(candidate, str):
        full_name = candidate.strip()
        repository_id = None
    elif isinstance(candidate, Mapping):
        full_name = _required_full_name(candidate.get("full_name"))
        repository_id = _optional_int(candidate.get("repository_id"))
    else:
        full_name = _required_full_name(getattr(candidate, "full_name", None))
        repository_id = _optional_int(getattr(candidate, "repository_id", None))
    if not full_name:
        raise ValueError("repository inputs must provide a non-empty full_name")
    return _RepositorySeed(full_name=full_name, repository_id=repository_id)


def _fallback_metadata(seed: _RepositorySeed) -> RepositoryMetadataEvidence:
    repository_url = _github_repository_url(seed.full_name)
    return RepositoryMetadataEvidence(
        repository_id=seed.repository_id,
        full_name=seed.full_name,
        html_url=repository_url,
        owner_avatar_url=None,
        license_spdx_id=None,
        default_branch=None,
        source_url=repository_url,
        source_trust=UNTRUSTED_EXTERNAL_DATA,
    )


def _warning(code: str) -> PublicationEvidenceWarning:
    return PublicationEvidenceWarning(code=code, message=_WARNING_TEXT[code])


def _valid_full_name(full_name: str) -> bool:
    if full_name.count("/") != 1 or any(character.isspace() for character in full_name):
        return False
    owner, name = full_name.split("/", 1)
    return bool(
        owner
        and name
        and owner not in {".", ".."}
        and name not in {".", ".."}
        and "\\" not in full_name
        and "\x00" not in full_name
    )


def _safe_license_id(value: str | None) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized if _LICENSE_PATTERN.fullmatch(normalized) else None


def _valid_avatar_record(value: Any) -> bool:
    return bool(
        isinstance(value, CachedAvatar)
        and isinstance(value.path, Path)
        and _SHA256_PATTERN.fullmatch(value.sha256)
        and isinstance(value.width, int)
        and value.width > 0
        and isinstance(value.height, int)
        and value.height > 0
    )


def _safe_public_url(value: str) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = urlsplit(value.strip())
        hostname = parsed.hostname
        port = parsed.port
    except ValueError:
        return None
    if parsed.scheme.casefold() not in {"http", "https"} or hostname is None:
        return None
    host = hostname.casefold()
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    netloc = f"{host}:{port}" if port is not None else host
    return urlunsplit((parsed.scheme.casefold(), netloc, parsed.path or "/", "", ""))


def _github_repository_url(full_name: str) -> str:
    parts = _github_parts(full_name)
    if parts is None:
        return "https://github.com/"
    owner, name = parts
    return f"https://github.com/{quote(owner, safe='')}/{quote(name, safe='')}"


def _github_api_url(full_name: str) -> str:
    parts = _github_parts(full_name)
    if parts is None:
        return "https://api.github.com/"
    owner, name = parts
    return f"https://api.github.com/repos/{quote(owner, safe='')}/{quote(name, safe='')}"


def _github_readme_api_url(full_name: str) -> str:
    return f"{_github_api_url(full_name).rstrip('/')}/readme"


def _github_parts(full_name: str) -> tuple[str, str] | None:
    if not _valid_full_name(full_name):
        return None
    owner, name = full_name.split("/", 1)
    return owner, name


def _required_full_name(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _optional_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None

"""Tests for publication-oriented evidence orchestration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from github_hotspots.evidence import (
    UNTRUSTED_EXTERNAL_DATA,
    UNTRUSTED_README_BANNER,
    CachedAvatar,
    ReadmeEvidence,
    RepositoryMetadataEvidence,
)
from github_hotspots.models import RankedRepository, Repository
from github_hotspots.publication_evidence import collect_publication_evidence

AVATAR_URL = "https://avatars.githubusercontent.com/u/42?v=4"
README_SHA = "a" * 40
AVATAR_SHA = "b" * 64


class SuccessfulClient:
    def __init__(self, avatar_root: Path) -> None:
        self.avatar_root = avatar_root
        self.metadata_calls: list[str] = []
        self.readme_calls: list[str] = []
        self.avatar_calls: list[tuple[str, Path, str]] = []

    def get_repository_metadata(self, full_name: str) -> RepositoryMetadataEvidence:
        self.metadata_calls.append(full_name)
        return RepositoryMetadataEvidence(
            repository_id=42,
            full_name="acme/tool",
            html_url="https://github.com/acme/tool?access_token=not-public",
            owner_avatar_url=AVATAR_URL,
            license_spdx_id="Apache-2.0",
            default_branch="main",
            source_url="https://api.github.com/repos/acme/tool?access_token=not-public",
        )

    def get_readme(self, full_name: str) -> ReadmeEvidence:
        self.readme_calls.append(full_name)
        return ReadmeEvidence(
            full_name="acme/tool",
            sha=README_SHA,
            markdown=(
                "# Useful tool\n\n"
                "<script>copy a local token</script>\n"
                "[![CI](https://img.shields.io/badge/ci-ok-green)](https://example.test)\n"
                "Turns input into a concise report.\n"
            ),
            decoded_bytes=180,
            source_url=("https://api.github.com/repos/acme/tool/readme?access_token=not-public"),
        )

    def cache_owner_avatar(
        self,
        avatar_url: str,
        cache_dir: Path,
        *,
        cache_key: str,
    ) -> CachedAvatar:
        self.avatar_calls.append((avatar_url, cache_dir, cache_key))
        path = cache_dir / "owner.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"safe png placeholder")
        return CachedAvatar(
            path=path.resolve(),
            sha256=AVATAR_SHA,
            width=96,
            height=96,
            source_url=avatar_url,
        )


def _ranked(full_name: str) -> RankedRepository:
    return RankedRepository(
        repository=Repository(full_name=full_name, repository_id=42),
        rank=1,
        score=99.0,
        star_delta=200,
        delta_source="snapshot",
    )


def test_collection_deduplicates_cross_board_aliases_and_emits_public_metadata(
    tmp_path: Path,
) -> None:
    client = SuccessfulClient(tmp_path)
    repositories = [
        Repository(full_name="Acme/Tool", repository_id=42),
        _ranked("acme/tool"),
        {"full_name": "Acme/Tool", "repository_id": 42},
    ]

    result = collect_publication_evidence(
        client,
        repositories,
        Path("assets") / "avatars",
        tmp_path,
        include_readme=True,
    )

    assert set(result) == {"Acme/Tool", "acme/tool"}
    assert result["Acme/Tool"] is result["acme/tool"]
    assert client.metadata_calls == ["Acme/Tool"]
    assert client.readme_calls == ["Acme/Tool"]
    assert len(client.avatar_calls) == 1
    assert client.avatar_calls[0][1] == (tmp_path / "assets" / "avatars").resolve()
    assert client.avatar_calls[0][2].startswith("repo-")

    bundle = result["Acme/Tool"]
    assert bundle.evidence is bundle.repository_evidence
    assert bundle.full_name == "Acme/Tool"
    assert bundle.repository_evidence.readme is not None
    assert bundle.repository_evidence.readme.markdown.startswith(UNTRUSTED_README_BANNER)
    assert "Turns input into a concise report." in bundle.repository_evidence.readme.markdown
    assert "copy a local token" not in bundle.repository_evidence.readme.markdown
    assert "shields.io" not in bundle.repository_evidence.readme.markdown
    assert bundle.repository_evidence.metadata.source_trust == UNTRUSTED_EXTERNAL_DATA

    public = bundle.to_public_metadata()
    assert public == bundle.to_public_dict()
    assert public["license_spdx_id"] == "Apache-2.0"
    assert public["readme"] == {
        "sha": README_SHA,
        "source_url": "https://api.github.com/repos/acme/tool/readme",
    }
    assert public["avatar"] == {
        "path": "assets/avatars/owner.png",
        "sha256": AVATAR_SHA,
        "width": 96,
        "height": 96,
    }
    serialized = json.dumps(public)
    assert "markdown" not in serialized
    assert "Turns input" not in serialized
    assert "access_token" not in serialized
    assert str(tmp_path) not in serialized


def test_include_readme_false_skips_readme_collection(tmp_path: Path) -> None:
    client = SuccessfulClient(tmp_path)

    result = collect_publication_evidence(
        client,
        [Repository(full_name="acme/tool")],
        "avatars",
        tmp_path,
        include_readme=False,
    )

    assert client.readme_calls == []
    assert result["acme/tool"].repository_evidence.readme is None
    assert result["acme/tool"].to_public_dict()["readme"] is None
    assert result["acme/tool"].warnings == ()


def test_failures_degrade_per_repository_without_exposing_exception_details(
    tmp_path: Path,
) -> None:
    class FailingClient:
        @staticmethod
        def get_repository_metadata(full_name: str) -> object:
            raise RuntimeError(f"Bearer super-secret from private-provider for {full_name}")

        @staticmethod
        def get_readme(full_name: str) -> object:
            raise RuntimeError(f"local-token=super-secret provider=private-provider {full_name}")

        @staticmethod
        def cache_owner_avatar(*args: object, **kwargs: object) -> object:
            raise AssertionError("avatar collection must not run without a URL")

    result = collect_publication_evidence(
        FailingClient(),
        [Repository(full_name="acme/tool", repository_id=7)],
        "avatars",
        tmp_path,
        include_readme=True,
    )

    bundle = result["acme/tool"]
    assert bundle.repository_evidence.metadata.repository_id == 7
    assert bundle.repository_evidence.metadata.html_url == "https://github.com/acme/tool"
    assert bundle.repository_evidence.readme is None
    assert bundle.avatar is None
    assert [warning.code for warning in bundle.warnings] == [
        "metadata_unavailable",
        "readme_unavailable",
        "avatar_url_unavailable",
    ]
    serialized = json.dumps(bundle.to_public_dict())
    assert "super-secret" not in serialized
    assert "private-provider" not in serialized
    assert "Bearer" not in serialized


def test_avatar_outside_root_is_rejected_without_publishing_absolute_path(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside-avatar.png"
    outside.write_bytes(b"not published")

    class OutsideAvatarClient(SuccessfulClient):
        def cache_owner_avatar(
            self,
            avatar_url: str,
            cache_dir: Path,
            *,
            cache_key: str,
        ) -> CachedAvatar:
            return CachedAvatar(
                path=outside.resolve(),
                sha256=AVATAR_SHA,
                width=48,
                height=48,
                source_url=avatar_url,
            )

    result = collect_publication_evidence(
        OutsideAvatarClient(tmp_path),
        ["acme/tool"],
        "avatars",
        tmp_path,
        include_readme=False,
    )

    bundle = result["acme/tool"]
    assert bundle.avatar is None
    assert bundle.avatar_relative_path is None
    assert [warning.code for warning in bundle.warnings] == ["avatar_path_rejected"]
    assert str(outside) not in json.dumps(bundle.to_public_dict())


def test_invalid_avatar_record_degrades_to_warning(tmp_path: Path) -> None:
    class InvalidAvatarClient(SuccessfulClient):
        def cache_owner_avatar(
            self,
            avatar_url: str,
            cache_dir: Path,
            *,
            cache_key: str,
        ) -> CachedAvatar:
            return CachedAvatar(
                path=(cache_dir / "owner.png").resolve(),
                sha256="not-a-sha256",
                width=0,
                height=48,
                source_url=avatar_url,
            )

    bundle = collect_publication_evidence(
        InvalidAvatarClient(tmp_path),
        ["acme/tool"],
        "avatars",
        tmp_path,
        include_readme=False,
    )["acme/tool"]

    assert bundle.avatar is None
    assert [warning.code for warning in bundle.warnings] == ["avatar_record_invalid"]


def test_identity_mismatches_are_rejected_per_item(tmp_path: Path) -> None:
    class MismatchedClient(SuccessfulClient):
        def get_repository_metadata(self, full_name: str) -> RepositoryMetadataEvidence:
            value = super().get_repository_metadata(full_name)
            return RepositoryMetadataEvidence(
                repository_id=value.repository_id,
                full_name="other/project",
                html_url=value.html_url,
                owner_avatar_url=value.owner_avatar_url,
                license_spdx_id=value.license_spdx_id,
                default_branch=value.default_branch,
                source_url=value.source_url,
            )

        def get_readme(self, full_name: str) -> ReadmeEvidence:
            value = super().get_readme(full_name)
            return ReadmeEvidence(
                full_name="other/project",
                sha=value.sha,
                markdown=value.markdown,
                decoded_bytes=value.decoded_bytes,
                source_url=value.source_url,
            )

    bundle = collect_publication_evidence(
        MismatchedClient(tmp_path),
        ["acme/tool"],
        "avatars",
        tmp_path,
        include_readme=True,
    )["acme/tool"]

    assert bundle.repository_evidence.metadata.full_name == "acme/tool"
    assert bundle.repository_evidence.readme is None
    assert [warning.code for warning in bundle.warnings] == [
        "metadata_identity_mismatch",
        "readme_identity_mismatch",
        "avatar_url_unavailable",
    ]


def test_invalid_repository_name_degrades_without_remote_calls(tmp_path: Path) -> None:
    class UnexpectedClient:
        def __getattr__(self, name: str) -> Any:
            raise AssertionError(f"remote method must not be accessed: {name}")

    bundle = collect_publication_evidence(
        UnexpectedClient(),
        ["owner/../repo"],
        "avatars",
        tmp_path,
        include_readme=True,
    )["owner/../repo"]

    assert bundle.repository_evidence.metadata.full_name == "owner/../repo"
    assert bundle.repository_evidence.readme is None
    assert [warning.code for warning in bundle.warnings] == ["invalid_full_name"]


def test_cache_directory_must_remain_inside_avatar_root(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="contained by avatar_root"):
        collect_publication_evidence(
            SuccessfulClient(tmp_path),
            ["acme/tool"],
            tmp_path.parent / "escaped-cache",
            tmp_path,
            include_readme=False,
        )


def test_workspace_relative_cache_path_is_not_duplicated_under_relative_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    avatar_root = Path("public") / "assets"
    cache_dir = avatar_root / "avatars"
    client = SuccessfulClient(tmp_path)

    collect_publication_evidence(
        client,
        ["acme/tool"],
        cache_dir,
        avatar_root,
        include_readme=False,
    )

    assert client.avatar_calls[0][1] == (tmp_path / cache_dir).resolve()


def test_missing_full_name_is_rejected_as_invalid_input(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="non-empty full_name"):
        collect_publication_evidence(
            SuccessfulClient(tmp_path),
            [{"repository_id": 42}],
            "avatars",
            tmp_path,
        )

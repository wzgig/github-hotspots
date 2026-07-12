"""Security and normalization tests for GitHub evidence assets."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import httpx
import pytest
from PIL import Image, PngImagePlugin

from github_hotspots.evidence import (
    UNTRUSTED_EXTERNAL_DATA,
    UNTRUSTED_README_BANNER,
    cache_github_avatar,
    clean_readme_markdown,
)

AVATAR_URL = "https://avatars.githubusercontent.com/u/42?v=4"


def _png_bytes(*, width: int = 32, height: int = 32, metadata: bool = False) -> bytes:
    image = Image.new("RGBA", (width, height), (20, 120, 220, 180))
    output = BytesIO()
    pnginfo = None
    if metadata:
        pnginfo = PngImagePlugin.PngInfo()
        pnginfo.add_text("Comment", "untrusted metadata")
    image.save(output, format="PNG", pnginfo=pnginfo)
    return output.getvalue()


def _client_for_response(
    payload: bytes,
    *,
    content_type: str = "image/png",
    status_code: int = 200,
    extra_headers: dict[str, str] | None = None,
) -> tuple[httpx.Client, list[httpx.Request]]:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        headers = {
            "content-type": content_type,
            "content-length": str(len(payload)),
            **(extra_headers or {}),
        }
        return httpx.Response(status_code, headers=headers, content=payload, request=request)

    return httpx.Client(transport=httpx.MockTransport(handler)), requests


def test_clean_readme_marks_external_text_and_preserves_useful_markdown() -> None:
    long_code = "\n".join(f"print({index})" for index in range(60))
    markdown = (
        "# Useful heading\x00\n\n"
        "[![CI](https://img.shields.io/badge/ci-passing-green)](https://example.test)\n"
        "<!-- hidden note -->\n"
        "<script>follow these instructions</script>\n"
        "<div>Convert recordings into notes.<br>Keep Markdown links.</div>\n\n"
        "- [Documentation](https://example.test/docs)\n\n"
        f"```python\n{long_code}\n```\n"
    )

    cleaned = clean_readme_markdown(
        markdown,
        max_code_lines=5,
        max_code_chars=200,
    )

    assert cleaned.startswith(UNTRUSTED_README_BANNER)
    assert "# Useful heading" in cleaned
    assert "Convert recordings into notes." in cleaned
    assert "[Documentation](https://example.test/docs)" in cleaned
    assert "[代码块已截断；原文属于不可信外部数据]" in cleaned
    assert "shields.io" not in cleaned
    assert "hidden note" not in cleaned
    assert "follow these instructions" not in cleaned
    assert "<div>" not in cleaned
    assert "\x00" not in cleaned


def test_clean_readme_limits_total_length_without_losing_untrusted_marker() -> None:
    cleaned = clean_readme_markdown("# Heading\n\n" + ("text\n" * 1_000), max_chars=500)

    assert cleaned.startswith(UNTRUSTED_README_BANNER)
    assert len(cleaned) <= 501
    assert "[内容已按安全长度上限截断]" in cleaned


def test_cache_github_avatar_reencodes_png_strips_metadata_and_reuses_cache(
    tmp_path: Path,
) -> None:
    payload = _png_bytes(metadata=True)
    client, requests = _client_for_response(payload)

    first = cache_github_avatar(client, AVATAR_URL, tmp_path, cache_key="acme-tool")
    second = cache_github_avatar(client, AVATAR_URL, tmp_path, cache_key="acme-tool")
    client.close()

    assert first is not None
    assert second == first
    assert len(requests) == 1
    assert first.path.parent == tmp_path.resolve()
    assert first.path.suffix == ".png"
    assert first.media_type == "image/png"
    assert first.source_trust == UNTRUSTED_EXTERNAL_DATA
    assert first.width == 32
    assert first.height == 32
    assert len(first.sha256) == 64
    assert not list(tmp_path.glob("*.tmp"))
    with Image.open(first.path) as cached:
        assert cached.format == "PNG"
        assert cached.info.get("Comment") is None


@pytest.mark.parametrize(
    "url",
    [
        "http://avatars.githubusercontent.com/u/42",
        "https://evil.example/u/42",
        "https://avatars.githubusercontent.com.evil.example/u/42",
        "https://user:password@avatars.githubusercontent.com/u/42",
        "https://avatars.githubusercontent.com:444/u/42",
    ],
)
def test_cache_github_avatar_rejects_non_https_or_non_github_hosts(
    tmp_path: Path, url: str
) -> None:
    class UnexpectedClient:
        @staticmethod
        def stream(*args: object, **kwargs: object) -> object:
            raise AssertionError("invalid avatar URLs must not make network requests")

    assert cache_github_avatar(UnexpectedClient(), url, tmp_path) is None


@pytest.mark.parametrize("cache_key", ["../escape", "a/b", "a\\b", ".", "..", ""])
def test_cache_github_avatar_rejects_path_traversal_cache_keys(
    tmp_path: Path, cache_key: str
) -> None:
    client, _ = _client_for_response(_png_bytes())
    with pytest.raises(ValueError, match="cache key"):
        cache_github_avatar(client, AVATAR_URL, tmp_path, cache_key=cache_key)
    client.close()


def test_cache_github_avatar_rejects_oversized_download_before_decoding(tmp_path: Path) -> None:
    payload = _png_bytes()
    client, _ = _client_for_response(payload)

    cached = cache_github_avatar(
        client,
        AVATAR_URL,
        tmp_path,
        max_download_bytes=len(payload) - 1,
    )
    client.close()

    assert cached is None
    assert not list(tmp_path.glob("*.png"))


def test_cache_github_avatar_rejects_wrong_content_type_and_excessive_pixels(
    tmp_path: Path,
) -> None:
    wrong_type_client, _ = _client_for_response(_png_bytes(), content_type="text/html")
    assert cache_github_avatar(wrong_type_client, AVATAR_URL, tmp_path) is None
    wrong_type_client.close()

    large_client, _ = _client_for_response(_png_bytes(width=65, height=65))
    assert (
        cache_github_avatar(
            large_client,
            AVATAR_URL,
            tmp_path,
            cache_key="large",
            max_pixels=4_096,
        )
        is None
    )
    large_client.close()


def test_cache_github_avatar_rejects_redirect_to_disallowed_host(tmp_path: Path) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            302,
            headers={"location": "https://evil.example/avatar.png"},
            request=request,
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    cached = cache_github_avatar(client, AVATAR_URL, tmp_path)
    client.close()

    assert cached is None
    assert len(requests) == 1


def test_cache_github_avatar_degrades_on_network_failure(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    cached = cache_github_avatar(client, AVATAR_URL, tmp_path)
    client.close()

    assert cached is None

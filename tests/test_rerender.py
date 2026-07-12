import json
from pathlib import Path
from typing import Any

import pytest

import github_hotspots.rerender as rerender_module
from github_hotspots.config import Settings, load_settings
from github_hotspots.rerender import rerender_report


def _settings(tmp_path: Path) -> Settings:
    project = tmp_path / "project"
    config_dir = project / "config"
    config_dir.mkdir(parents=True)
    source_config = Path("config/hotspots.yaml").read_text(encoding="utf-8")
    config_path = config_dir / "hotspots.yaml"
    config_path.write_text(source_config, encoding="utf-8")
    return load_settings(config_path)


def _repository() -> dict[str, Any]:
    return {
        "repository_id": 42,
        "full_name": "example/frozen-tool",
        "owner": "example",
        "name": "frozen-tool",
        "html_url": "https://github.com/example/frozen-tool",
        "description": "A frozen public fact set.",
        "language": "Python",
        "stars": 1_200,
        "forks": 80,
        "open_issues": 12,
        "watchers": 1_200,
        "topics": ["automation"],
        "created_at": "2025-01-01T00:00:00Z",
        "updated_at": "2026-07-11T00:00:00Z",
        "pushed_at": "2026-07-11T00:00:00Z",
        "daily_stars": 125,
        "weekly_stars": 480,
        "trending_rank_daily": 1,
        "trending_rank_weekly": 2,
        "sources": ["search"],
        "rank": 1,
        "score": 90.0,
        "star_delta": 125,
        "fork_delta": 4,
        "delta_source": "snapshot",
        "component_percentiles": {
            "star_growth": 100.0,
            "relative_growth": 90.0,
        },
    }


def _payload(repository: dict[str, Any] | None = None, *, schema_version: int = 3) -> dict:
    item = repository or _repository()
    payload = {
        "schema_version": schema_version,
        "period": "daily",
        "run_date": "2026-07-11",
        "warnings": [],
        "repositories": [item],
    }
    if schema_version >= 2:
        payload["boards"] = {
            "comprehensive": {
                "label": "Comprehensive",
                "repositories": [item],
            },
            "ai": {"label": "AI", "repositories": []},
        }
    return payload


def _write_report(tmp_path: Path, payload: dict[str, Any]) -> Path:
    report = tmp_path / "input.json"
    report.write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )
    return report


def test_rerender_uses_frozen_report_facts_without_collection(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    repository = _repository()
    payload = _payload(repository)
    comprehensive_label = settings.board("comprehensive").label
    payload["boards"]["comprehensive"]["label"] = comprehensive_label
    payload["boards"]["ai"]["label"] = settings.board("ai").label
    payload["warnings"] = [
        "REST Search temporarily degraded",
        f"{comprehensive_label}\uff1aold quality warning",
    ]

    artifacts = rerender_report(settings, _write_report(tmp_path, payload))

    rendered = json.loads(artifacts.json.read_text(encoding="utf-8"))
    assert rendered["repositories"][0]["stars"] == 1_200
    assert rendered["repositories"][0]["star_delta"] == 125
    assert rendered["repositories"][0]["full_name"] == "example/frozen-tool"
    assert "REST Search temporarily degraded" in rendered["warnings"]
    assert f"{comprehensive_label}\uff1aold quality warning" not in rendered["warnings"]
    assert artifacts.poster_manifest is not None
    assert artifacts.poster_manifest.is_file()


def test_rerender_preserves_rich_summary_and_refreshes_evidence_on_request(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(tmp_path)
    repository = _repository()
    repository["summary"] = {
        "one_line": "一句话说明真实用途。",
        "highlights": ["能力一", "能力二", "能力三"],
        "audience": "具体任务人群",
        "capabilities": ["能力一", "能力二", "能力三", "能力四", "能力五"],
        "core_title": "核心亮点",
        "core_summary": "完整解释项目如何工作。",
        "prerequisites": "需要本地工具",
        "limitations": "仍需人工确认",
        "license_label": "MIT",
        "license_restrictions": "",
        "readme_sha": "abc123",
        "content_status": "readme_enriched",
        "evidence_ids": {},
    }
    payload = _payload(repository)
    payload["editorial"] = {
        "boards": {
            "comprehensive": {
                "prompt_version": "4.0",
                "schema_version": "4.0",
                "requested_backend": "codex-cli",
                "used_backend": "codex-cli",
                "fallback_used": False,
                "error_category": None,
            }
        }
    }
    captured: dict[str, Any] = {}
    sentinel = object()
    evidence = {"example/frozen-tool": object()}

    monkeypatch.setattr(
        rerender_module,
        "_refresh_publication_evidence",
        lambda *_, **__: evidence,
    )

    def fake_render_reports(**kwargs: Any) -> object:
        captured.update(kwargs)
        return sentinel

    monkeypatch.setattr(rerender_module, "render_reports", fake_render_reports)

    result = rerender_report(
        settings,
        _write_report(tmp_path, payload),
        refresh_evidence=True,
    )

    assert result is sentinel
    summary = captured["summary_overrides"]["comprehensive"][0]
    assert summary.capabilities[-1] == "能力五"
    assert summary.core_summary == "完整解释项目如何工作。"
    assert captured["publication_evidence"] is evidence
    assert captured["editorial_metadata_overrides"] is None


def test_offline_rerender_rehydrates_public_avatar_and_readme_metadata(tmp_path: Path) -> None:
    repository = _repository()
    repository["avatar_path"] = "avatars/2026-07-11/owner.png"
    repository["publication_evidence"] = {
        "full_name": repository["full_name"],
        "license_spdx_id": "MIT",
        "readme": {
            "sha": "abc123",
            "source_url": "https://api.github.com/repos/example/frozen-tool/readme",
        },
        "avatar": {
            "path": repository["avatar_path"],
            "sha256": "a" * 64,
            "width": 96,
            "height": 96,
        },
        "warnings": [],
    }
    payload = _payload(repository)
    report = _write_report(tmp_path, payload)
    avatar = report.parent / repository["avatar_path"]
    avatar.parent.mkdir(parents=True)
    avatar.write_bytes(b"cached-avatar")

    bundles = rerender_module._publication_overrides(payload, report)

    bundle = bundles[repository["full_name"]]
    assert bundle.avatar_relative_path == repository["avatar_path"]
    assert bundle.repository_evidence.readme.sha == "abc123"
    assert bundle.to_public_dict()["readme"]["source_url"].endswith("/readme")


def test_offline_rerender_preserves_existing_editorial_provenance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(tmp_path)
    payload = _payload()
    payload["editorial"] = {
        "boards": {
            "comprehensive": {
                "prompt_version": "4.0",
                "schema_version": "4.0",
                "requested_backend": "codex-cli",
                "used_backend": "codex-cli",
                "fallback_used": False,
                "error_category": None,
            }
        }
    }
    captured: dict[str, Any] = {}
    sentinel = object()

    def fake_render_reports(**kwargs: Any) -> object:
        captured.update(kwargs)
        return sentinel

    monkeypatch.setattr(rerender_module, "render_reports", fake_render_reports)

    result = rerender_report(settings, _write_report(tmp_path, payload))

    assert result is sentinel
    assert captured["editorial_metadata_overrides"]["comprehensive"]["used_backend"] == (
        "codex-cli"
    )


@pytest.mark.parametrize("schema_version", [1, 2, 3])
def test_rerender_accepts_repository_generated_schema_versions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    schema_version: int,
) -> None:
    settings = _settings(tmp_path)
    payload = _payload(schema_version=schema_version)
    captured: dict[str, Any] = {}
    sentinel = object()

    def fake_render_reports(**kwargs: Any) -> object:
        captured.update(kwargs)
        return sentinel

    monkeypatch.setattr(rerender_module, "render_reports", fake_render_reports)

    result = rerender_report(settings, _write_report(tmp_path, payload))

    assert result is sentinel
    assert captured["rankings"][0].repository.full_name == "example/frozen-tool"
    assert captured["ai_rankings"] == []


@pytest.mark.parametrize("schema_version", [0, 4, "3", True])
def test_rerender_rejects_unsupported_schema_versions(tmp_path: Path, schema_version: Any) -> None:
    settings = _settings(tmp_path)
    payload = _payload()
    payload["schema_version"] = schema_version

    with pytest.raises(ValueError, match="schema_version"):
        rerender_report(settings, _write_report(tmp_path, payload))


def test_rerender_rejects_missing_required_report_fields(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    payload = _payload()
    del payload["repositories"]

    with pytest.raises(ValueError, match=r"report\.repositories is required"):
        rerender_report(settings, _write_report(tmp_path, payload))


def test_rerender_rejects_non_object_repository_items(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    payload = _payload()
    payload["boards"]["ai"]["repositories"] = [None]

    with pytest.raises(ValueError, match=r"boards\.ai\.repositories\[0\] must be an object"):
        rerender_report(settings, _write_report(tmp_path, payload))


def test_rerender_rejects_missing_repository_fields(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    repository = _repository()
    del repository["stars"]

    with pytest.raises(ValueError, match=r"missing fields: stars"):
        rerender_report(settings, _write_report(tmp_path, _payload(repository)))


@pytest.mark.parametrize(
    ("field", "invalid_value", "message"),
    [
        ("full_name", "", "full_name must be a non-empty"),
        ("owner", "different", "owner must match full_name"),
        ("html_url", "https://example.com/example/frozen-tool", "GitHub repository URL"),
        ("delta_source", "api", "delta_source must be one of"),
        ("score", float("nan"), "score must be a finite number"),
        (
            "component_percentiles",
            {"star_growth": float("inf")},
            "component_percentiles.star_growth must be a finite number",
        ),
        ("stars", "1200", "stars must be an integer"),
    ],
)
def test_rerender_rejects_invalid_repository_facts(
    tmp_path: Path,
    field: str,
    invalid_value: Any,
    message: str,
) -> None:
    settings = _settings(tmp_path)
    repository = _repository()
    repository[field] = invalid_value

    with pytest.raises(ValueError, match=message):
        rerender_report(settings, _write_report(tmp_path, _payload(repository)))


def test_rerender_rejects_root_and_board_fact_mismatch(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    payload = _payload()
    board_repository = dict(_repository())
    board_repository["stars"] = 1_201
    payload["boards"]["comprehensive"]["repositories"] = [board_repository]

    with pytest.raises(ValueError, match="must match report.repositories"):
        rerender_report(settings, _write_report(tmp_path, payload))

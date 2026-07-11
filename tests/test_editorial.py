import json
import subprocess
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

from github_hotspots.config import EditorialSettings
from github_hotspots.editorial import (
    CodexEditorialError,
    _verified_mcp_disable_overrides,
    edit_summary_batch,
)
from github_hotspots.models import RankedRepository, Repository
from github_hotspots.summarizer import RepositorySummary, summary_candidates


@pytest.fixture(autouse=True)
def _isolate_editorial_unit_tests(monkeypatch) -> None:
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.setattr(
        "github_hotspots.editorial._verified_mcp_disable_overrides",
        lambda *_args, **_kwargs: (),
    )


def _settings(tmp_path: Path, *, backend: str = "codex-cli") -> EditorialSettings:
    prompt = tmp_path / "prompt.md"
    schema = tmp_path / "schema.json"
    prompt.write_text("只输出结构化事实摘要。", encoding="utf-8")
    schema.write_text("{}", encoding="utf-8")
    return EditorialSettings(
        backend=backend,
        fallback="deterministic",
        timeout_seconds=10,
        allow_in_ci=False,
        executable="codex",
        prompt_path=prompt,
        schema_path=schema,
        reasoning_effort_override="xhigh",
    )


def _ranking(*, rank: int = 1, repository_id: int = 42, name: str = "hot-repo") -> RankedRepository:
    return RankedRepository(
        repository=Repository(
            repository_id=repository_id,
            full_name=f"example/{name}",
            html_url=f"https://github.com/example/{name}",
            description="A developer automation toolkit.",
            language="Python",
            stars=1_200,
            forks=80,
            topics=("automation",),
        ),
        rank=rank,
        score=91.5,
        star_delta=125,
        fork_delta=4,
        delta_source="snapshot",
    )


def _draft() -> RepositorySummary:
    return RepositorySummary(
        one_line="规则摘要",
        highlights=("亮点一", "亮点二", "亮点三"),
        audience="开发者",
    )


def _response(
    *,
    rankings: tuple[RankedRepository, ...] | None = None,
    angles: tuple[str, ...] | None = None,
    one_line: str | None = None,
) -> dict:
    rankings = rankings or (_ranking(),)
    angles = angles or ("positioning",)
    items = []
    for ranked, angle in zip(rankings, angles, strict=True):
        candidates = dict(
            summary_candidates(
                ranked.repository,
                ranked.star_delta,
                ranked.delta_source,
            )
        )
        candidate = candidates[angle]
        source = ranked.repository
        items.append(
            {
                "status": "ok",
                "rank": ranked.rank,
                "repository": {
                    "repository_id": source.repository_id,
                    "full_name": source.full_name,
                    "html_url": source.html_url,
                },
                "card": {
                    "project_name": source.name,
                    "angle": angle,
                    "language": source.language,
                    "stars_total": source.stars,
                    "period_stars_added": ranked.star_delta,
                    "period_stars_added_display": f"本日净增 +{ranked.star_delta} Star",
                    "forks_total": source.forks,
                    "one_line": one_line if one_line is not None else candidate.one_line,
                    "highlights": list(candidate.highlights),
                    "audience": candidate.audience,
                    "repository_url": source.html_url,
                },
                "evidence": {
                    "one_line": ["candidate_summaries"],
                    "highlights": [
                        ["candidate_summaries"],
                        ["candidate_summaries"],
                        ["candidate_summaries"],
                    ],
                    "audience": ["candidate_summaries"],
                },
                "data_quality": {
                    "delta_source": ranked.delta_source,
                    "delta_is_exact": True,
                    "warnings": [],
                },
            }
        )
    return {
        "schema_version": "3.0",
        "period": {"type": "daily", "start": "2026-07-10", "end": "2026-07-11"},
        "items": items,
        "batch_quality": {
            "forbidden_phrase_hits": [],
            "adjacent_angle_repeats": [],
            "warnings": [],
        },
    }


def test_deterministic_backend_never_invokes_codex(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("github_hotspots.editorial.shutil.which", lambda _name: None)

    result = edit_summary_batch(
        [_ranking()],
        [_draft()],
        period="daily",
        period_start=date(2026, 7, 10),
        period_end=date(2026, 7, 11),
        settings=_settings(tmp_path, backend="deterministic"),
    )

    assert result.summaries == (_draft(),)
    assert result.used_backend == "deterministic"
    assert result.fallback_used is False


def test_mcp_overrides_disable_every_cli_server(monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_run(command, **kwargs):
        calls.append(command)
        disabled = any("mcp_servers." in value for value in command)
        payload = [
            {
                "name": "local_tools",
                "enabled": not disabled,
                "disabled_reason": None,
                "transport": {},
                "startup_timeout_sec": None,
                "tool_timeout_sec": None,
                "auth_status": "unsupported",
            }
        ]
        assert kwargs["shell"] is False
        return SimpleNamespace(returncode=0, stdout=json.dumps(payload), stderr="")

    monkeypatch.setattr("github_hotspots.editorial.subprocess.run", fake_run)

    overrides = _verified_mcp_disable_overrides(
        "codex",
        reasoning_effort="xhigh",
        timeout_seconds=10,
    )

    assert overrides == ("mcp_servers.local_tools.enabled=false",)
    assert len(calls) == 2
    assert all(command[-3:] == ["mcp", "list", "--json"] for command in calls)
    assert overrides[0] in calls[1]


def test_mcp_isolation_failure_falls_back_for_the_batch(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("github_hotspots.editorial.shutil.which", lambda _name: "codex")

    def fail_isolation(*_args, **_kwargs):
        raise CodexEditorialError("mcp_isolation_failed")

    monkeypatch.setattr(
        "github_hotspots.editorial._verified_mcp_disable_overrides",
        fail_isolation,
    )

    result = edit_summary_batch(
        [_ranking()],
        [_draft()],
        period="daily",
        period_start=date(2026, 7, 10),
        period_end=date(2026, 7, 11),
        settings=_settings(tmp_path),
    )

    assert result.fallback_used is True
    assert result.error_category == "mcp_isolation_failed"


def test_codex_cli_batch_accepts_fact_checked_output(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("github_hotspots.editorial.shutil.which", lambda _name: "codex")

    def fake_run(command, **kwargs):
        output = Path(command[command.index("--output-last-message") + 1])
        output.write_text(json.dumps(_response(), ensure_ascii=False), encoding="utf-8")
        assert command[:2] == ["codex", "exec"]
        assert "--ephemeral" in command
        assert ["--sandbox", "read-only"] == command[
            command.index("--sandbox") : command.index("--sandbox") + 2
        ]
        assert 'model_reasoning_effort="xhigh"' in command
        assert "mcp_servers={}" not in command
        assert "--ignore-rules" in command
        assert command[command.index("--disable") + 1] == "shell_tool"
        assert "browser_use" in command
        assert "plugins" in command
        assert kwargs["shell"] is False
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("github_hotspots.editorial.subprocess.run", fake_run)

    result = edit_summary_batch(
        [_ranking()],
        [_draft()],
        period="daily",
        period_start=date(2026, 7, 10),
        period_end=date(2026, 7, 11),
        settings=_settings(tmp_path),
    )

    assert result.used_backend == "codex-cli"
    assert result.fallback_used is False
    expected = dict(summary_candidates(_ranking().repository, 125, "snapshot"))["positioning"]
    assert result.summaries[0] == expected


def test_codex_cli_fact_drift_falls_back_for_the_whole_batch(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("github_hotspots.editorial.shutil.which", lambda _name: "codex")

    def fake_run(command, **_kwargs):
        payload = _response()
        payload["items"][0]["card"]["stars_total"] = 9_999
        output = Path(command[command.index("--output-last-message") + 1])
        output.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("github_hotspots.editorial.subprocess.run", fake_run)

    result = edit_summary_batch(
        [_ranking()],
        [_draft()],
        period="daily",
        period_start=date(2026, 7, 10),
        period_end=date(2026, 7, 11),
        settings=_settings(tmp_path),
    )

    assert result.summaries == (_draft(),)
    assert result.fallback_used is True
    assert result.error_category == "fact_mismatch"


def test_codex_cli_rejects_data_quality_warning_drift(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("github_hotspots.editorial.shutil.which", lambda _name: "codex")

    def fake_run(command, **_kwargs):
        payload = _response()
        payload["items"][0]["data_quality"]["warnings"] = ["invented_warning"]
        output = Path(command[command.index("--output-last-message") + 1])
        output.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("github_hotspots.editorial.subprocess.run", fake_run)

    result = edit_summary_batch(
        [_ranking()],
        [_draft()],
        period="daily",
        period_start=date(2026, 7, 10),
        period_end=date(2026, 7, 11),
        settings=_settings(tmp_path),
    )

    assert result.fallback_used is True
    assert result.error_category == "fact_mismatch"


def test_codex_cli_rejects_text_not_present_in_controlled_candidates(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr("github_hotspots.editorial.shutil.which", lambda _name: "codex")

    def fake_run(command, **_kwargs):
        payload = _response(one_line="仓库简介之外声称累计9999名用户")
        output = Path(command[command.index("--output-last-message") + 1])
        output.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("github_hotspots.editorial.subprocess.run", fake_run)

    result = edit_summary_batch(
        [_ranking()],
        [_draft()],
        period="daily",
        period_start=date(2026, 7, 10),
        period_end=date(2026, 7, 11),
        settings=_settings(tmp_path),
    )

    assert result.summaries == (_draft(),)
    assert result.fallback_used is True
    assert result.error_category == "candidate_mismatch"


def test_codex_cli_rejects_dynamic_marketing_cliches(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("github_hotspots.editorial.shutil.which", lambda _name: "codex")

    def fake_run(command, **_kwargs):
        payload = _response(one_line="这是一个值得关注的开源项目")
        output = Path(command[command.index("--output-last-message") + 1])
        output.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("github_hotspots.editorial.subprocess.run", fake_run)

    result = edit_summary_batch(
        [_ranking()],
        [_draft()],
        period="daily",
        period_start=date(2026, 7, 10),
        period_end=date(2026, 7, 11),
        settings=_settings(tmp_path),
    )

    assert result.fallback_used is True
    assert result.error_category == "forbidden_phrase"


def test_codex_cli_requires_full_angle_coverage_before_reuse(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("github_hotspots.editorial.shutil.which", lambda _name: "codex")
    rankings = (
        _ranking(rank=1, repository_id=41, name="repo-one"),
        _ranking(rank=2, repository_id=42, name="repo-two"),
        _ranking(rank=3, repository_id=43, name="repo-three"),
    )

    def fake_run(command, **_kwargs):
        payload = _response(
            rankings=rankings,
            angles=("positioning", "growth_signal", "positioning"),
        )
        output = Path(command[command.index("--output-last-message") + 1])
        output.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("github_hotspots.editorial.subprocess.run", fake_run)

    result = edit_summary_batch(
        rankings,
        [_draft(), _draft(), _draft()],
        period="daily",
        period_start=date(2026, 7, 10),
        period_end=date(2026, 7, 11),
        settings=_settings(tmp_path),
    )

    assert result.fallback_used is True
    assert result.error_category == "angle_coverage_failed"


def test_codex_cli_rejects_empty_evidence_mappings(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("github_hotspots.editorial.shutil.which", lambda _name: "codex")

    def fake_run(command, **_kwargs):
        payload = _response()
        payload["items"][0]["evidence"]["one_line"] = []
        output = Path(command[command.index("--output-last-message") + 1])
        output.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("github_hotspots.editorial.subprocess.run", fake_run)

    result = edit_summary_batch(
        [_ranking()],
        [_draft()],
        period="daily",
        period_start=date(2026, 7, 10),
        period_end=date(2026, 7, 11),
        settings=_settings(tmp_path),
    )

    assert result.fallback_used is True
    assert result.error_category == "evidence_missing"


def test_codex_cli_os_error_falls_back(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("github_hotspots.editorial.shutil.which", lambda _name: "codex")
    monkeypatch.setattr(
        "github_hotspots.editorial.subprocess.run",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("spawn failed")),
    )

    result = edit_summary_batch(
        [_ranking()],
        [_draft()],
        period="daily",
        period_start=date(2026, 7, 10),
        period_end=date(2026, 7, 11),
        settings=_settings(tmp_path),
    )

    assert result.fallback_used is True
    assert result.error_category == "io_error"


def test_codex_cli_timeout_falls_back_without_raw_error(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("github_hotspots.editorial.shutil.which", lambda _name: "codex")

    def fake_run(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(cmd=["codex", "exec"], timeout=10)

    monkeypatch.setattr("github_hotspots.editorial.subprocess.run", fake_run)

    result = edit_summary_batch(
        [_ranking()],
        [_draft()],
        period="daily",
        period_start=date(2026, 7, 10),
        period_end=date(2026, 7, 11),
        settings=_settings(tmp_path),
    )

    assert result.fallback_used is True
    assert result.error_category == "timeout"


@pytest.mark.parametrize("ci_variable", ["CI", "GITHUB_ACTIONS"])
def test_codex_cli_is_disabled_in_ci_by_default(
    tmp_path: Path, monkeypatch, ci_variable: str
) -> None:
    monkeypatch.setenv(ci_variable, "true")

    result = edit_summary_batch(
        [_ranking()],
        [_draft()],
        period="daily",
        period_start=date(2026, 7, 10),
        period_end=date(2026, 7, 11),
        settings=_settings(tmp_path),
    )

    assert result.fallback_used is True
    assert result.error_category == "disabled_in_ci"

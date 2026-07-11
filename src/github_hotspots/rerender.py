"""Rebuild presentation artifacts from an already frozen report JSON."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from datetime import date
from numbers import Integral, Real
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from .config import Settings
from .models import RankedRepository, Repository
from .report import ReportArtifacts, render_reports

SUPPORTED_SCHEMA_VERSIONS = frozenset({1, 2, 3})
ALLOWED_DELTA_SOURCES = frozenset({"snapshot", "trending", "estimate"})
REQUIRED_REPOSITORY_FIELDS = frozenset(
    {
        "repository_id",
        "full_name",
        "owner",
        "name",
        "html_url",
        "description",
        "language",
        "stars",
        "forks",
        "open_issues",
        "watchers",
        "topics",
        "created_at",
        "updated_at",
        "pushed_at",
        "daily_stars",
        "weekly_stars",
        "trending_rank_daily",
        "trending_rank_weekly",
        "sources",
        "rank",
        "score",
        "star_delta",
        "fork_delta",
        "delta_source",
        "component_percentiles",
    }
)


def rerender_report(
    settings: Settings,
    report_path: str | Path,
    *,
    editorial_backend: str | None = None,
) -> ReportArtifacts:
    """Rebuild copy and posters without collecting or ranking GitHub data again."""

    path = Path(report_path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read report JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError("Report JSON root must be an object")

    schema_version = _integer_field(payload, "schema_version", "report")
    if schema_version not in SUPPORTED_SCHEMA_VERSIONS:
        supported = ", ".join(str(version) for version in sorted(SUPPORTED_SCHEMA_VERSIONS))
        raise ValueError(f"Unsupported report schema_version; expected one of: {supported}")

    period = _text_field(payload, "period", "report", nonempty=True)
    if period not in {"daily", "weekly"}:
        raise ValueError("Report period must be daily or weekly")
    run_date_text = _text_field(payload, "run_date", "report", nonempty=True)
    try:
        run_date = date.fromisoformat(run_date_text)
        if run_date.isoformat() != run_date_text:
            raise ValueError
    except ValueError as exc:
        raise ValueError("Report run_date must use YYYY-MM-DD") from exc

    root_rankings = _rankings(_field(payload, "repositories", "report"), "repositories")
    if schema_version == 1:
        comprehensive_rankings = root_rankings
        ai_rankings: list[RankedRepository] = []
    else:
        boards = _mapping_field(payload, "boards", "report")
        comprehensive_rankings = _board_rankings(boards, "comprehensive")
        ai_rankings = _board_rankings(boards, "ai")
        if _ranking_facts(root_rankings) != _ranking_facts(comprehensive_rankings):
            raise ValueError("boards.comprehensive.repositories must match report.repositories")

    return render_reports(
        settings=settings,
        period=period,
        run_date=run_date,
        rankings=comprehensive_rankings,
        ai_rankings=ai_rankings,
        extra_warnings=_external_warnings(payload),
        editorial_backend=editorial_backend,
    )


def _board_rankings(boards: Mapping[str, Any], key: str) -> list[RankedRepository]:
    board = _mapping_field(boards, key, "boards")
    _text_field(board, "label", f"boards.{key}", nonempty=True)
    return _rankings(
        _field(board, "repositories", f"boards.{key}"),
        f"boards.{key}.repositories",
    )


def _rankings(value: Any, path: str) -> list[RankedRepository]:
    if not isinstance(value, list):
        raise ValueError(f"{path} must be an array")
    rankings: list[RankedRepository] = []
    for index, item in enumerate(value):
        item_path = f"{path}[{index}]"
        if not isinstance(item, Mapping):
            raise ValueError(f"{item_path} must be an object")
        missing = sorted(REQUIRED_REPOSITORY_FIELDS - set(item))
        if missing:
            raise ValueError(f"{item_path} is missing fields: {', '.join(missing)}")

        full_name = _text_field(item, "full_name", item_path, nonempty=True)
        _validate_repository_name(full_name, item_path)
        owner, name = full_name.split("/", maxsplit=1)
        if _text_field(item, "owner", item_path, nonempty=True) != owner:
            raise ValueError(f"{item_path}.owner must match full_name")
        if _text_field(item, "name", item_path, nonempty=True) != name:
            raise ValueError(f"{item_path}.name must match full_name")
        html_url = _text_field(item, "html_url", item_path, nonempty=True)
        _validate_github_url(html_url, full_name, item_path)
        repository_id = _optional_integer_field(
            item,
            "repository_id",
            item_path,
            minimum=1,
        )
        repository = Repository(
            repository_id=repository_id,
            full_name=full_name,
            html_url=html_url,
            description=_optional_text_field(item, "description", item_path),
            language=_optional_text_field(item, "language", item_path),
            stars=_integer_field(item, "stars", item_path, minimum=0),
            forks=_integer_field(item, "forks", item_path, minimum=0),
            open_issues=_integer_field(item, "open_issues", item_path, minimum=0),
            watchers=_integer_field(item, "watchers", item_path, minimum=0),
            topics=_string_tuple_field(item, "topics", item_path),
            created_at=_optional_text_field(item, "created_at", item_path),
            updated_at=_optional_text_field(item, "updated_at", item_path),
            pushed_at=_optional_text_field(item, "pushed_at", item_path),
            daily_stars=_optional_integer_field(item, "daily_stars", item_path, minimum=0),
            weekly_stars=_optional_integer_field(item, "weekly_stars", item_path, minimum=0),
            trending_rank_daily=_optional_integer_field(
                item, "trending_rank_daily", item_path, minimum=1
            ),
            trending_rank_weekly=_optional_integer_field(
                item, "trending_rank_weekly", item_path, minimum=1
            ),
            sources=_string_tuple_field(item, "sources", item_path),
        )
        delta_source = _text_field(item, "delta_source", item_path, nonempty=True)
        if delta_source not in ALLOWED_DELTA_SOURCES:
            allowed = ", ".join(sorted(ALLOWED_DELTA_SOURCES))
            raise ValueError(f"{item_path}.delta_source must be one of: {allowed}")
        rankings.append(
            RankedRepository(
                repository=repository,
                rank=_integer_field(item, "rank", item_path, minimum=1),
                score=_finite_number_field(item, "score", item_path),
                star_delta=_integer_field(item, "star_delta", item_path),
                fork_delta=_integer_field(item, "fork_delta", item_path),
                delta_source=delta_source,
                component_percentiles=_percentiles(item, item_path),
            )
        )
    ranks = [item.rank for item in rankings]
    if len(ranks) != len(set(ranks)):
        raise ValueError(f"{path} must not contain duplicate ranks")
    return sorted(rankings, key=lambda ranked: ranked.rank)


def _ranking_facts(rankings: list[RankedRepository]) -> list[dict[str, Any]]:
    return [ranking.to_dict() for ranking in rankings]


def _external_warnings(payload: dict[str, Any]) -> tuple[str, ...]:
    warnings = payload.get("warnings", [])
    if not isinstance(warnings, list):
        raise ValueError("report.warnings must be an array")
    for index, warning in enumerate(warnings):
        if not isinstance(warning, str):
            raise ValueError(f"report.warnings[{index}] must be a string")
    boards = payload.get("boards")
    boards = boards if isinstance(boards, dict) else {}
    labels = {"综合主榜", "AI 专题榜"}
    for board in boards.values():
        if isinstance(board, dict) and board.get("label"):
            labels.add(str(board["label"]))
    prefixes = tuple(f"{label}：" for label in labels)
    return tuple(
        text
        for warning in warnings
        if (text := str(warning).strip())
        and not text.startswith(prefixes)
        and "本地 Codex 文案增强不可用" not in text
    )


def _field(value: Mapping[str, Any], key: str, path: str) -> Any:
    if key not in value:
        raise ValueError(f"{path}.{key} is required")
    return value[key]


def _mapping_field(value: Mapping[str, Any], key: str, path: str) -> Mapping[str, Any]:
    field = _field(value, key, path)
    if not isinstance(field, Mapping):
        raise ValueError(f"{path}.{key} must be an object")
    return field


def _text_field(
    value: Mapping[str, Any],
    key: str,
    path: str,
    *,
    nonempty: bool = False,
) -> str:
    field = _field(value, key, path)
    if not isinstance(field, str):
        raise ValueError(f"{path}.{key} must be a string")
    if nonempty and (not field.strip() or field != field.strip()):
        raise ValueError(f"{path}.{key} must be a non-empty trimmed string")
    return field


def _optional_text_field(value: Mapping[str, Any], key: str, path: str) -> str | None:
    field = _field(value, key, path)
    if field is None:
        return None
    if not isinstance(field, str):
        raise ValueError(f"{path}.{key} must be a string or null")
    return field


def _integer_field(
    value: Mapping[str, Any],
    key: str,
    path: str,
    *,
    minimum: int | None = None,
) -> int:
    field = _field(value, key, path)
    return _integer_value(field, f"{path}.{key}", minimum=minimum)


def _optional_integer_field(
    value: Mapping[str, Any],
    key: str,
    path: str,
    *,
    minimum: int | None = None,
) -> int | None:
    field = _field(value, key, path)
    if field is None:
        return None
    return _integer_value(field, f"{path}.{key}", minimum=minimum)


def _integer_value(value: Any, path: str, *, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise ValueError(f"{path} must be an integer")
    number = int(value)
    if minimum is not None and number < minimum:
        raise ValueError(f"{path} must be at least {minimum}")
    return number


def _finite_number_field(value: Mapping[str, Any], key: str, path: str) -> float:
    return _finite_number(_field(value, key, path), f"{path}.{key}")


def _finite_number(value: Any, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{path} must be a number")
    try:
        number = float(value)
    except (OverflowError, ValueError) as exc:
        raise ValueError(f"{path} must be a finite number") from exc
    if not math.isfinite(number):
        raise ValueError(f"{path} must be a finite number")
    return number


def _percentiles(value: Mapping[str, Any], path: str) -> dict[str, float]:
    percentiles = _field(value, "component_percentiles", path)
    if not isinstance(percentiles, Mapping) or not percentiles:
        raise ValueError(f"{path}.component_percentiles must be a non-empty object")

    parsed: dict[str, float] = {}
    for key, component in percentiles.items():
        if not isinstance(key, str) or not key.strip() or key != key.strip():
            raise ValueError(f"{path}.component_percentiles keys must be non-empty strings")
        number = _finite_number(component, f"{path}.component_percentiles.{key}")
        if not 0 <= number <= 100:
            raise ValueError(f"{path}.component_percentiles.{key} must be between 0 and 100")
        parsed[key] = number
    return parsed


def _string_tuple_field(value: Mapping[str, Any], key: str, path: str) -> tuple[str, ...]:
    field = _field(value, key, path)
    if not isinstance(field, list):
        raise ValueError(f"{path}.{key} must be an array")

    parsed: list[str] = []
    for index, item in enumerate(field):
        if not isinstance(item, str) or not item.strip() or item != item.strip():
            raise ValueError(f"{path}.{key}[{index}] must be a non-empty trimmed string")
        parsed.append(item)
    return tuple(parsed)


def _validate_repository_name(full_name: str, path: str) -> None:
    parts = full_name.split("/")
    if len(parts) != 2 or not all(parts) or any(character.isspace() for character in full_name):
        raise ValueError(f"{path}.full_name must use the owner/repository format")


def _validate_github_url(html_url: str, full_name: str, path: str) -> None:
    try:
        parsed = urlsplit(html_url)
    except ValueError as exc:
        raise ValueError(f"{path}.html_url must be a canonical GitHub repository URL") from exc

    expected_path = f"/{full_name}".casefold()
    if (
        parsed.scheme != "https"
        or parsed.netloc.casefold() != "github.com"
        or parsed.path.rstrip("/").casefold() != expected_path
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(f"{path}.html_url must be a canonical GitHub repository URL")

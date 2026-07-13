"""Configuration loading and validation for GitHub Hotspots."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import yaml

MIN_POSTER_WIDTH = 600
MIN_POSTER_HEIGHT = 800
MAX_POSTER_WIDTH = 2400
MAX_POSTER_HEIGHT = 3200


class ConfigurationError(ValueError):
    """Raised when the project configuration is incomplete or inconsistent."""


@dataclass(frozen=True, slots=True)
class RunSettings:
    """Settings for one reporting cadence."""

    period: str
    top_n: int
    lookback_days: int


@dataclass(frozen=True, slots=True)
class BoardSettings:
    """Settings for one independently ranked hotspot board."""

    key: str
    label: str
    enabled: bool
    daily_top_n: int
    weekly_top_n: int
    topics: tuple[str, ...] = ()
    keywords: tuple[str, ...] = ()

    def top_n(self, period: str) -> int:
        """Return the result limit for a reporting cadence."""

        if period == "daily":
            return self.daily_top_n
        if period == "weekly":
            return self.weekly_top_n
        raise ConfigurationError(f"Unsupported period: {period}")


@dataclass(frozen=True, slots=True)
class EditorialSettings:
    """Configuration for the optional evidence-bound editorial pass."""

    backend: str
    fallback: str
    timeout_seconds: int
    allow_in_ci: bool
    executable: str
    prompt_path: Path
    schema_path: Path
    reasoning_effort_override: str | None = None


@dataclass(frozen=True, slots=True)
class PosterSettings:
    """Configuration for deterministic social-card rendering."""

    enabled: bool
    width: int
    height: int


@dataclass(frozen=True, slots=True)
class PublicationSettings:
    """Settings for local, human-reviewed social publication bundles."""

    root_dir: Path
    daily_first_issue_date: date
    weekly_first_issue_date: date
    title_max_chars: int
    caption_max_chars: int

    def first_issue_date(self, period: str) -> date:
        """Return the first public issue date for one cadence."""

        if period == "daily":
            return self.daily_first_issue_date
        if period == "weekly":
            return self.weekly_first_issue_date
        raise ConfigurationError(f"Unsupported period: {period}")


@dataclass(frozen=True, slots=True)
class Settings:
    """Small typed facade over the YAML document.

    The nested dictionaries remain available so the configuration can evolve
    without forcing a large class hierarchy for every optional key.
    """

    path: Path
    timezone: str
    github: Mapping[str, Any]
    outputs: Mapping[str, Any]
    runs: Mapping[str, Mapping[str, Any]]
    sources: Mapping[str, Mapping[str, Any]]
    filters: Mapping[str, Any]
    ranking: Mapping[str, Any]
    boards: Mapping[str, Mapping[str, Any]]
    editorial: Mapping[str, Any] = field(default_factory=dict)
    posters: Mapping[str, Any] = field(default_factory=dict)
    publication: Mapping[str, Any] = field(default_factory=dict)

    def run(self, period: str) -> RunSettings:
        try:
            raw = self.runs[period]
        except KeyError as exc:
            raise ConfigurationError(f"Unsupported period: {period}") from exc
        return RunSettings(
            period=str(raw.get("period", period)),
            top_n=int(raw["top_n"]),
            lookback_days=int(raw["lookback_days"]),
        )

    @property
    def ranking_weights(self) -> dict[str, float]:
        raw = self.ranking.get("weights", {})
        return {str(key): float(value) for key, value in raw.items()}

    def board(self, key: str) -> BoardSettings:
        """Return typed settings for a configured board."""

        try:
            raw = _mapping(self.boards[key], f"boards.{key}")
        except KeyError as exc:
            raise ConfigurationError(f"Unsupported board: {key}") from exc
        return BoardSettings(
            key=key,
            label=str(raw.get("label", key)).strip(),
            enabled=_boolean(raw.get("enabled", True), f"boards.{key}.enabled"),
            daily_top_n=int(raw["daily_top_n"]),
            weekly_top_n=int(raw["weekly_top_n"]),
            topics=_string_tuple(raw.get("topics", ())),
            keywords=_string_tuple(raw.get("keywords", ())),
        )

    def editorial_settings(self, backend_override: str | None = None) -> EditorialSettings:
        """Return safe settings for deterministic or local Codex editing."""

        raw = _mapping(self.editorial, "editorial")
        codex = _mapping(raw.get("codex_cli", {}), "editorial.codex_cli")
        backend = str(backend_override or raw.get("backend", "deterministic")).strip()
        fallback = str(raw.get("fallback", "deterministic")).strip()
        timeout_seconds = int(raw.get("timeout_seconds", 120))
        executable = str(codex.get("executable", "codex")).strip()
        reasoning = codex.get("reasoning_effort_override")
        reasoning_effort = str(reasoning).strip() if reasoning is not None else None

        if backend not in {"deterministic", "codex-cli"}:
            raise ConfigurationError(f"Unsupported editorial backend: {backend}")
        if fallback != "deterministic":
            raise ConfigurationError("editorial.fallback must be deterministic")
        if timeout_seconds < 1:
            raise ConfigurationError("editorial.timeout_seconds must be positive")
        if not executable:
            raise ConfigurationError("editorial.codex_cli.executable must not be empty")
        if reasoning_effort not in {None, "none", "minimal", "low", "medium", "high", "xhigh"}:
            raise ConfigurationError(
                "editorial.codex_cli.reasoning_effort_override is not supported"
            )

        return EditorialSettings(
            backend=backend,
            fallback=fallback,
            timeout_seconds=timeout_seconds,
            allow_in_ci=_boolean(raw.get("allow_in_ci", False), "editorial.allow_in_ci"),
            executable=executable,
            prompt_path=self.resolve_path(
                str(raw.get("prompt_path", "prompts/repository_summary_zh.md"))
            ),
            schema_path=self.resolve_path(
                str(raw.get("schema_path", "schemas/repository_summary.schema.json"))
            ),
            reasoning_effort_override=reasoning_effort,
        )

    def poster_settings(self) -> PosterSettings:
        """Return validated poster dimensions and enablement."""

        raw = _mapping(self.posters, "posters")
        try:
            width = int(raw.get("width", 1200))
            height = int(raw.get("height", 1600))
        except (TypeError, ValueError) as exc:
            raise ConfigurationError("posters dimensions must be integers") from exc
        width, height = validate_poster_dimensions(width, height)
        return PosterSettings(
            enabled=_boolean(raw.get("enabled", False), "posters.enabled"),
            width=width,
            height=height,
        )

    def publication_settings(self) -> PublicationSettings:
        """Return validated settings for local publication packaging."""

        raw = _mapping(self.publication, "publication")
        title_max_chars = int(raw.get("title_max_chars", 30))
        caption_max_chars = int(raw.get("caption_max_chars", 1000))
        if title_max_chars < 10 or title_max_chars > 80:
            raise ConfigurationError("publication.title_max_chars must be between 10 and 80")
        if caption_max_chars < 200 or caption_max_chars > 5000:
            raise ConfigurationError("publication.caption_max_chars must be between 200 and 5000")

        daily_first_issue_date = _date_value(
            raw.get("daily_first_issue_date", "2026-07-12"),
            "publication.daily_first_issue_date",
        )
        weekly_first_issue_date = _date_value(
            raw.get("weekly_first_issue_date", "2026-07-12"),
            "publication.weekly_first_issue_date",
        )
        if weekly_first_issue_date.weekday() != 6:
            raise ConfigurationError("publication.weekly_first_issue_date must be a Sunday")

        return PublicationSettings(
            root_dir=self.resolve_path(str(raw.get("root_dir", "publish"))),
            daily_first_issue_date=daily_first_issue_date,
            weekly_first_issue_date=weekly_first_issue_date,
            title_max_chars=title_max_chars,
            caption_max_chars=caption_max_chars,
        )

    def resolve_path(self, value: str | Path) -> Path:
        """Resolve a configured path relative to the repository root."""

        root = self.path.parent.parent
        candidate = Path(value)
        return candidate if candidate.is_absolute() else root / candidate

    def report_dir(self, period: str) -> Path:
        key = f"{period}_reports_dir"
        return self.resolve_path(str(self.outputs[key]))

    @property
    def snapshots_dir(self) -> Path:
        return self.resolve_path(str(self.outputs["snapshots_dir"]))


def load_settings(path: str | Path = "config/hotspots.yaml") -> Settings:
    """Load YAML settings and fail early on invalid required values."""

    config_path = Path(path).resolve()
    if not config_path.exists():
        raise ConfigurationError(f"Configuration file not found: {config_path}")

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, Mapping):
        raise ConfigurationError("Configuration root must be a mapping")
    required = (
        "timezone",
        "github",
        "outputs",
        "runs",
        "boards",
        "sources",
        "filters",
        "ranking",
    )
    missing = [key for key in required if key not in raw]
    if missing:
        raise ConfigurationError(f"Missing configuration keys: {', '.join(missing)}")

    editorial = _mapping(raw.get("editorial", {}), "editorial")
    posters = _mapping(raw.get("posters", {}), "posters")
    publication = _mapping(raw.get("publication", {}), "publication")
    settings = Settings(
        path=config_path,
        timezone=str(raw["timezone"]),
        github=raw["github"],
        outputs=raw["outputs"],
        runs=raw["runs"],
        sources=raw["sources"],
        filters=raw["filters"],
        ranking=raw["ranking"],
        boards=raw["boards"],
        editorial=editorial,
        posters=posters,
        publication=publication,
    )

    for period in ("daily", "weekly"):
        run = settings.run(period)
        if run.top_n < 1 or run.lookback_days < 1:
            raise ConfigurationError(f"runs.{period} values must be positive")

    for key in ("comprehensive", "ai"):
        board = settings.board(key)
        if not board.label:
            raise ConfigurationError(f"boards.{key}.label must not be empty")
        if board.daily_top_n < 1 or board.weekly_top_n < 1:
            raise ConfigurationError(f"boards.{key} result limits must be positive")
    ai_board = settings.board("ai")
    if ai_board.enabled and not (ai_board.topics or ai_board.keywords):
        raise ConfigurationError("boards.ai must define topics or keywords when enabled")

    settings.editorial_settings()
    settings.poster_settings()
    settings.publication_settings()
    _validate_runtime_booleans(settings)

    weights = settings.ranking_weights
    if weights and abs(sum(weights.values()) - 1.0) > 1e-6:
        raise ConfigurationError("ranking.weights must add up to 1.0")
    return settings


def validate_poster_dimensions(width: int, height: int) -> tuple[int, int]:
    """Return one legal 3:4 poster size shared by generators and consumers."""

    if (
        isinstance(width, bool)
        or isinstance(height, bool)
        or not isinstance(width, int)
        or not isinstance(height, int)
    ):
        raise ConfigurationError("posters dimensions must be integers")
    if width < MIN_POSTER_WIDTH or height < MIN_POSTER_HEIGHT or width * 4 != height * 3:
        raise ConfigurationError("posters dimensions must use a 3:4 ratio and be at least 600x800")
    if width > MAX_POSTER_WIDTH or height > MAX_POSTER_HEIGHT:
        raise ConfigurationError(
            f"posters dimensions must not exceed {MAX_POSTER_WIDTH}x{MAX_POSTER_HEIGHT}"
        )
    return width, height


def _string_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple, set)):
        return ()
    return tuple(text for item in value if (text := str(item).strip()))


def _mapping(value: object, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ConfigurationError(f"{path} must be a mapping")
    return value


def _boolean(value: object, path: str) -> bool:
    if not isinstance(value, bool):
        raise ConfigurationError(f"{path} must be a boolean")
    return value


def _date_value(value: object, path: str) -> date:
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        raise ConfigurationError(f"{path} must use YYYY-MM-DD")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ConfigurationError(f"{path} must use YYYY-MM-DD") from exc
    if parsed.isoformat() != value:
        raise ConfigurationError(f"{path} must use YYYY-MM-DD")
    return parsed


def _validate_runtime_booleans(settings: Settings) -> None:
    """Reject truthy strings for options consumed directly by the pipeline."""

    for source_key in ("trending", "search"):
        source = _mapping(settings.sources.get(source_key, {}), f"sources.{source_key}")
        _boolean(source.get("enabled", True), f"sources.{source_key}.enabled")

    for filter_key, default in (
        ("require_description", False),
        ("exclude_archived", True),
        ("exclude_forks", True),
        ("exclude_mirrors", True),
    ):
        _boolean(settings.filters.get(filter_key, default), f"filters.{filter_key}")

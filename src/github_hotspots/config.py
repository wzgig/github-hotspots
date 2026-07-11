"""Configuration loading and validation for GitHub Hotspots."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


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
            raw = self.boards[key]
        except KeyError as exc:
            raise ConfigurationError(f"Unsupported board: {key}") from exc
        return BoardSettings(
            key=key,
            label=str(raw.get("label", key)).strip(),
            enabled=bool(raw.get("enabled", True)),
            daily_top_n=int(raw["daily_top_n"]),
            weekly_top_n=int(raw["weekly_top_n"]),
            topics=_string_tuple(raw.get("topics", ())),
            keywords=_string_tuple(raw.get("keywords", ())),
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

    weights = settings.ranking_weights
    if weights and abs(sum(weights.values()) - 1.0) > 1e-6:
        raise ConfigurationError("ranking.weights must add up to 1.0")
    return settings


def _string_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple, set)):
        return ()
    return tuple(text for item in value if (text := str(item).strip()))

from pathlib import Path
from typing import Any

import pytest
import yaml

from github_hotspots.config import ConfigurationError, load_settings


def _write_config(tmp_path: Path, document: dict[str, Any]) -> Path:
    config_path = tmp_path / "config" / "hotspots.yaml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        yaml.safe_dump(document, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return config_path


def _config_document() -> dict[str, Any]:
    document = yaml.safe_load(Path("config/hotspots.yaml").read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    return document


def _set_nested(document: dict[str, Any], path: tuple[str, ...], value: Any) -> None:
    current = document
    for key in path[:-1]:
        nested = current[key]
        assert isinstance(nested, dict)
        current = nested
    current[path[-1]] = value


def test_project_configuration_loads_with_expected_cadence() -> None:
    settings = load_settings(Path("config/hotspots.yaml"))

    assert settings.timezone == "Asia/Shanghai"
    assert settings.run("daily").top_n == 3
    assert settings.run("weekly").top_n == 7
    assert settings.board("comprehensive").label == "综合主榜"
    assert settings.board("comprehensive").top_n("daily") == 3
    assert settings.board("ai").label == "AI 专题榜"
    assert settings.board("ai").top_n("weekly") == 7
    assert "machine-learning" in settings.board("ai").topics
    assert "machine learning" in settings.board("ai").keywords
    assert sum(settings.ranking_weights.values()) == pytest.approx(1.0)
    editorial = settings.editorial_settings()
    assert editorial.backend == "deterministic"
    assert editorial.fallback == "deterministic"
    assert editorial.reasoning_effort_override == "xhigh"
    assert editorial.prompt_path.name == "repository_summary_zh.md"
    posters = settings.poster_settings()
    assert posters.enabled is True
    assert (posters.width, posters.height) == (1200, 1600)
    publication = settings.publication_settings()
    assert publication.root_dir.name == "publish"
    assert publication.daily_first_issue_date.isoformat() == "2026-07-12"
    assert publication.weekly_first_issue_date.isoformat() == "2026-07-12"
    assert publication.title_max_chars == 30
    assert publication.caption_max_chars == 1000


def test_configuration_rejects_unknown_period() -> None:
    settings = load_settings(Path("config/hotspots.yaml"))

    with pytest.raises(ConfigurationError, match="Unsupported period"):
        settings.run("monthly")


def test_configuration_rejects_unknown_board() -> None:
    settings = load_settings(Path("config/hotspots.yaml"))

    with pytest.raises(ConfigurationError, match="Unsupported board"):
        settings.board("security")


@pytest.mark.parametrize("section", ["editorial", "posters", "publication"])
def test_configuration_requires_mapping_sections(tmp_path: Path, section: str) -> None:
    document = _config_document()
    document[section] = []

    with pytest.raises(ConfigurationError, match=rf"{section} must be a mapping"):
        load_settings(_write_config(tmp_path, document))


def test_configuration_requires_mapping_codex_cli_options(tmp_path: Path) -> None:
    document = _config_document()
    editorial = document["editorial"]
    assert isinstance(editorial, dict)
    editorial["codex_cli"] = "codex"

    with pytest.raises(ConfigurationError, match=r"editorial\.codex_cli must be a mapping"):
        load_settings(_write_config(tmp_path, document))


@pytest.mark.parametrize(
    "path",
    [
        ("boards", "ai", "enabled"),
        ("editorial", "allow_in_ci"),
        ("posters", "enabled"),
        ("sources", "search", "enabled"),
        ("filters", "require_description"),
    ],
)
def test_configuration_rejects_string_boolean_values(tmp_path: Path, path: tuple[str, ...]) -> None:
    document = _config_document()
    _set_nested(document, path, "false")

    with pytest.raises(ConfigurationError, match="must be a boolean"):
        load_settings(_write_config(tmp_path, document))


def test_configuration_caps_poster_dimensions(tmp_path: Path) -> None:
    document = _config_document()
    posters = document["posters"]
    assert isinstance(posters, dict)
    posters.update({"width": 3000, "height": 4000})

    with pytest.raises(ConfigurationError, match="must not exceed 2400x3200"):
        load_settings(_write_config(tmp_path, document))


def test_configuration_accepts_non_default_legal_poster_dimensions(tmp_path: Path) -> None:
    document = _config_document()
    posters = document["posters"]
    assert isinstance(posters, dict)
    posters.update({"width": 600, "height": 800})

    settings = load_settings(_write_config(tmp_path, document))

    assert (settings.poster_settings().width, settings.poster_settings().height) == (600, 800)


@pytest.mark.parametrize(
    ("key", "value", "message"),
    [
        ("daily_first_issue_date", "2026/07/12", "must use YYYY-MM-DD"),
        ("weekly_first_issue_date", 20260712, "must use YYYY-MM-DD"),
        ("weekly_first_issue_date", "2026-07-13", "must be a Sunday"),
        ("title_max_chars", 5, "must be between 10 and 80"),
        ("caption_max_chars", 100, "must be between 200 and 5000"),
    ],
)
def test_configuration_validates_publication_settings(
    tmp_path: Path,
    key: str,
    value: object,
    message: str,
) -> None:
    document = _config_document()
    publication = document["publication"]
    assert isinstance(publication, dict)
    publication[key] = value

    with pytest.raises(ConfigurationError, match=message):
        load_settings(_write_config(tmp_path, document))

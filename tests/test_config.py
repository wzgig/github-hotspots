from pathlib import Path

import pytest

from github_hotspots.config import ConfigurationError, load_settings


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


def test_configuration_rejects_unknown_period() -> None:
    settings = load_settings(Path("config/hotspots.yaml"))

    with pytest.raises(ConfigurationError, match="Unsupported period"):
        settings.run("monthly")


def test_configuration_rejects_unknown_board() -> None:
    settings = load_settings(Path("config/hotspots.yaml"))

    with pytest.raises(ConfigurationError, match="Unsupported board"):
        settings.board("security")

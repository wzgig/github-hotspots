from pathlib import Path

import pytest

from github_hotspots.config import ConfigurationError, load_settings


def test_project_configuration_loads_with_expected_cadence() -> None:
    settings = load_settings(Path("config/hotspots.yaml"))

    assert settings.timezone == "Asia/Shanghai"
    assert settings.run("daily").top_n == 3
    assert settings.run("weekly").top_n == 7
    assert sum(settings.ranking_weights.values()) == pytest.approx(1.0)


def test_configuration_rejects_unknown_period() -> None:
    settings = load_settings(Path("config/hotspots.yaml"))

    with pytest.raises(ConfigurationError, match="Unsupported period"):
        settings.run("monthly")

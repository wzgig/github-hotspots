from __future__ import annotations

import json
from datetime import date

from github_hotspots.models import Repository, RepositorySnapshot
from github_hotspots.snapshot import SnapshotStore


def test_save_merges_same_date_by_name_and_keeps_latest_counters(tmp_path) -> None:
    # Arrange
    store = SnapshotStore(tmp_path / "snapshots")
    captured_on = date(2026, 7, 11)
    first_batch = [
        Repository(full_name="Acme/One", stars=10, forks=1),
        Repository(repository_id=2, full_name="acme/two", stars=20, forks=2),
    ]
    second_batch = [
        Repository(
            repository_id=1,
            full_name="acme/one",
            stars=15,
            forks=3,
            open_issues=4,
        )
    ]

    # Act
    path = store.save(captured_on, first_batch)
    store.save(captured_on, second_batch)
    loaded = store.load(captured_on)
    payload = json.loads(path.read_text(encoding="utf-8"))

    # Assert
    assert path.name == "2026-07-11.json"
    assert len(loaded) == 2
    by_name = {item.full_name: item for item in loaded}
    assert by_name["acme/one"].repository_id == 1
    assert by_name["acme/one"].stars == 15
    assert by_name["acme/one"].forks == 3
    assert by_name["acme/one"].open_issues == 4
    assert payload["date"] == "2026-07-11"
    assert [item["full_name"] for item in payload["repositories"]] == [
        "acme/one",
        "acme/two",
    ]


def test_find_one_and_seven_day_baselines_by_id_or_full_name(tmp_path) -> None:
    # Arrange
    store = SnapshotStore(tmp_path)
    current_date = date(2026, 7, 11)
    store.save(
        date(2026, 7, 10),
        [Repository(full_name="Acme/Project", stars=90, forks=9)],
    )
    store.save(
        date(2026, 7, 4),
        [
            Repository(
                repository_id=77,
                full_name="old-owner/project",
                stars=50,
                forks=5,
            )
        ],
    )
    current = Repository(
        repository_id=77,
        full_name="acme/project",
        stars=100,
        forks=10,
    )

    # Act
    found = store.find_baselines(current_date, current)
    baseline_1d, baseline_7d = store.baselines(current_date)

    # Assert
    assert found[1] is not None
    assert found[1].stars == 90
    assert found[7] is not None
    assert found[7].stars == 50
    assert len(baseline_1d) == 1
    assert len(baseline_7d) == 1


def test_save_accepts_snapshot_and_normalises_its_date(tmp_path) -> None:
    # Arrange
    store = SnapshotStore(tmp_path)
    stale_snapshot = RepositorySnapshot(
        captured_on=date(2020, 1, 1),
        repository_id=5,
        full_name="acme/repo",
        stars=7,
    )

    # Act
    store.save("2026-07-11", [stale_snapshot])
    loaded = store.load("2026-07-11")

    # Assert
    assert loaded[0].captured_on == date(2026, 7, 11)
    assert loaded[0].to_dict()["captured_on"] == "2026-07-11"


def test_load_malformed_json_degrades_to_empty_list(tmp_path) -> None:
    # Arrange
    store = SnapshotStore(tmp_path)
    malformed_path = store.path_for("2026-07-11")
    malformed_path.write_text("{not-json", encoding="utf-8")

    # Act
    loaded = store.load("2026-07-11")

    # Assert
    assert loaded == []
    assert store.load_baseline("2026-07-11", 1) == []

from __future__ import annotations

import json
import threading
from datetime import date
from pathlib import Path

import pytest

from github_hotspots import snapshot as snapshot_module
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


def test_concurrent_saves_reload_and_merge_inside_the_store_lock(tmp_path, monkeypatch) -> None:
    # Arrange: pause the first writer while it still owns the store lock.
    store = SnapshotStore(tmp_path / "snapshots")
    original_write = snapshot_module._atomic_write_snapshot
    first_write_entered = threading.Event()
    release_first_write = threading.Event()
    second_save_finished = threading.Event()
    call_guard = threading.Lock()
    write_calls = 0
    errors: list[BaseException] = []

    def delayed_first_write(path: Path, payload: dict[str, object]) -> None:
        nonlocal write_calls
        with call_guard:
            write_calls += 1
            is_first = write_calls == 1
        if is_first:
            first_write_entered.set()
            assert release_first_write.wait(5)
        original_write(path, payload)

    def save(repository: Repository, finished: threading.Event | None = None) -> None:
        try:
            store.save("2026-07-11", [repository])
        except BaseException as exc:  # Surface worker failures in the main test thread.
            errors.append(exc)
        finally:
            if finished is not None:
                finished.set()

    monkeypatch.setattr(snapshot_module, "_atomic_write_snapshot", delayed_first_write)
    first = threading.Thread(target=save, args=(Repository(full_name="acme/first", stars=1),))
    second = threading.Thread(
        target=save,
        args=(Repository(full_name="acme/second", stars=2), second_save_finished),
    )

    # Act
    first.start()
    assert first_write_entered.wait(5)
    second.start()
    assert not second_save_finished.wait(0.2)
    release_first_write.set()
    first.join(5)
    second.join(5)

    # Assert
    assert not first.is_alive()
    assert not second.is_alive()
    assert errors == []
    assert {item.full_name for item in store.load("2026-07-11")} == {
        "acme/first",
        "acme/second",
    }


def test_failed_snapshot_replace_cleans_each_unique_temporary_file(tmp_path, monkeypatch) -> None:
    # Arrange
    store = SnapshotStore(tmp_path / "snapshots")
    target = store.path_for("2026-07-11")
    original_replace = Path.replace
    temporary_paths: list[Path] = []

    def fail_snapshot_replace(path: Path, destination: Path) -> Path:
        if Path(destination) == target and path.suffix == ".tmp":
            temporary_paths.append(path)
            raise OSError("simulated replace failure")
        return original_replace(path, destination)

    monkeypatch.setattr(Path, "replace", fail_snapshot_replace)

    # Act / Assert
    for stars in (1, 2):
        with pytest.raises(OSError, match="simulated replace failure"):
            store.save("2026-07-11", [Repository(full_name="acme/failure", stars=stars)])

    assert len(temporary_paths) == 2
    assert temporary_paths[0] != temporary_paths[1]
    assert all(not path.exists() for path in temporary_paths)
    assert list(target.parent.glob(f".{target.name}.*.tmp")) == []

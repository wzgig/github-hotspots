"""Date-partitioned JSON snapshot storage."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from collections.abc import Iterable
from contextlib import contextmanager
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path
from typing import BinaryIO

from .models import Repository, RepositorySnapshot


class SnapshotStore:
    """Persist repository counters in one mergeable JSON file per date."""

    def __init__(self, directory: str | Path) -> None:
        self.directory = Path(directory)

    def path_for(self, captured_on: date | str) -> Path:
        """Return ``<directory>/YYYY-MM-DD.json``."""

        snapshot_date = _coerce_date(captured_on)
        return self.directory / f"{snapshot_date.isoformat()}.json"

    def save(
        self,
        captured_on: date | str,
        repositories: Iterable[Repository | RepositorySnapshot],
    ) -> Path:
        """Merge repositories into the date file and return its path.

        A later save for the same repository replaces counters from an earlier
        save while keeping the best available ID/name identity.
        """

        snapshot_date = _coerce_date(captured_on)
        incoming = [_as_snapshot(repository, snapshot_date) for repository in repositories]
        path = self.path_for(snapshot_date)
        path.parent.mkdir(parents=True, exist_ok=True)
        with _exclusive_store_lock(self.directory):
            # Reload after acquiring the process-wide lock.  A writer that was
            # waiting must merge the snapshot committed by the previous writer.
            merged = _merge_snapshots(self.load(snapshot_date), incoming)
            payload = {
                "date": snapshot_date.isoformat(),
                "repositories": [
                    snapshot.to_dict()
                    for snapshot in sorted(merged, key=lambda item: item.full_name.casefold())
                ],
            }
            _atomic_write_snapshot(path, payload)
        return path

    def load(self, captured_on: date | str) -> list[RepositorySnapshot]:
        """Load one date, returning an empty list for missing/malformed JSON."""

        snapshot_date = _coerce_date(captured_on)
        path = self.path_for(snapshot_date)
        if not path.exists():
            return []
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return []
        if not isinstance(payload, dict):
            return []
        raw_repositories = payload.get("repositories", [])
        if not isinstance(raw_repositories, list):
            return []

        repositories: list[RepositorySnapshot] = []
        for raw_repository in raw_repositories:
            if not isinstance(raw_repository, dict):
                continue
            try:
                snapshot = RepositorySnapshot.from_dict(raw_repository)
            except (KeyError, TypeError, ValueError):
                continue
            # The file name is authoritative.  Normalising here prevents a bad
            # row date from leaking into later calculations.
            repositories.append(replace(snapshot, captured_on=snapshot_date))
        return _merge_snapshots([], repositories)

    def load_baseline(self, captured_on: date | str, days: int) -> list[RepositorySnapshot]:
        """Load the exact snapshot ``days`` before ``captured_on``."""

        if days < 1:
            raise ValueError("days must be positive")
        snapshot_date = _coerce_date(captured_on)
        return self.load(snapshot_date - timedelta(days=days))

    def baselines(
        self, captured_on: date | str
    ) -> tuple[list[RepositorySnapshot], list[RepositorySnapshot]]:
        """Return the exact 1-day and 7-day baseline collections."""

        return (
            self.load_baseline(captured_on, 1),
            self.load_baseline(captured_on, 7),
        )

    def find_baseline(
        self,
        captured_on: date | str,
        days: int,
        repository: Repository | RepositorySnapshot,
    ) -> RepositorySnapshot | None:
        """Find one repository in an exact prior-day baseline."""

        for candidate in self.load_baseline(captured_on, days):
            if _same_identity(candidate, repository):
                return candidate
        return None

    def find_baselines(
        self,
        captured_on: date | str,
        repository: Repository | RepositorySnapshot,
    ) -> dict[int, RepositorySnapshot | None]:
        """Find both standard baselines for one repository."""

        return {
            1: self.find_baseline(captured_on, 1, repository),
            7: self.find_baseline(captured_on, 7, repository),
        }


def _as_snapshot(
    repository: Repository | RepositorySnapshot, captured_on: date
) -> RepositorySnapshot:
    if isinstance(repository, Repository):
        return RepositorySnapshot.from_repository(repository, captured_on)
    if isinstance(repository, RepositorySnapshot):
        return replace(repository, captured_on=captured_on)
    raise TypeError("repositories must contain Repository or RepositorySnapshot")


def _merge_snapshots(
    existing: Iterable[RepositorySnapshot],
    incoming: Iterable[RepositorySnapshot],
) -> list[RepositorySnapshot]:
    result = list(existing)
    for snapshot in incoming:
        matching_indexes = [
            index for index, current in enumerate(result) if _same_identity(current, snapshot)
        ]
        if not matching_indexes:
            result.append(snapshot)
            continue
        target = matching_indexes[0]
        previous = result[target]
        updated = replace(
            snapshot,
            repository_id=snapshot.repository_id or previous.repository_id,
            full_name=snapshot.full_name or previous.full_name,
        )
        for duplicate_index in reversed(matching_indexes[1:]):
            duplicate = result[duplicate_index]
            updated = replace(
                updated,
                repository_id=updated.repository_id or duplicate.repository_id,
                full_name=updated.full_name or duplicate.full_name,
            )
            del result[duplicate_index]
        result[target] = updated
    return result


def _same_identity(
    left: Repository | RepositorySnapshot,
    right: Repository | RepositorySnapshot,
) -> bool:
    ids_match = (
        left.repository_id is not None
        and right.repository_id is not None
        and left.repository_id == right.repository_id
    )
    return ids_match or left.full_name.casefold() == right.full_name.casefold()


@contextmanager
def _exclusive_store_lock(directory: Path):
    """Serialise snapshot read-modify-write cycles across local processes."""

    lock_path = _store_lock_path(directory)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+b") as stream:
        # Windows byte-range locks work reliably when the range exists.  The
        # file lives under the OS temp directory, never in the Git worktree.
        stream.seek(0, os.SEEK_END)
        if stream.tell() == 0:
            stream.write(b"\0")
            stream.flush()
        _lock_stream(stream)
        try:
            yield
        finally:
            _unlock_stream(stream)


def _store_lock_path(directory: Path) -> Path:
    resolved = str(directory.resolve())
    identity = os.path.normcase(resolved) if os.name == "nt" else resolved
    digest = hashlib.sha256(os.fsencode(identity)).hexdigest()
    return Path(tempfile.gettempdir()) / "github-hotspots" / "snapshot-locks" / f"{digest}.lock"


def _lock_stream(stream: BinaryIO) -> None:
    stream.seek(0)
    if os.name == "nt":
        import msvcrt

        msvcrt.locking(stream.fileno(), msvcrt.LK_LOCK, 1)
        return

    import fcntl

    fcntl.flock(stream.fileno(), fcntl.LOCK_EX)


def _unlock_stream(stream: BinaryIO) -> None:
    stream.seek(0)
    if os.name == "nt":
        import msvcrt

        msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
        return

    import fcntl

    fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def _atomic_write_snapshot(path: Path, payload: dict[str, object]) -> None:
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _coerce_date(value: date | str) -> date:
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError) as error:
        raise ValueError("captured_on must be an ISO date") from error

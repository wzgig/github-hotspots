"""Validation helpers for unattended report generation.

This module deliberately uses only the Python standard library so GitHub
Actions can decide whether a local Codex-enriched report already exists before
installing the project dependencies.  It never reads Codex or GitHub
credentials and only reports stable, non-sensitive error categories.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import struct
import sys
import zlib
from dataclasses import dataclass
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Any

REPORT_SCHEMA_VERSION = 3
MANIFEST_SCHEMA_VERSION = 2
BOARD_KEYS = ("comprehensive", "ai")
MAX_JSON_BYTES = 8 * 1024 * 1024
MAX_TEXT_SCAN_BYTES = 8 * 1024 * 1024
MAX_PNG_BYTES = 32 * 1024 * 1024
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
EDITORIAL_PROMPT_VERSION = "4.1"
EDITORIAL_SCHEMA_VERSION = "4.0"
POSTER_RENDERER_NAME = "github-hotspots-pillow"
POSTER_RENDERER_VERSION = "4.0"
POSTER_STYLE_VERSION = "signal-broadsheet-v1"
PUBLICATION_FIRST_ISSUE_DATE = date(2026, 7, 12)

_PERIODS = frozenset({"daily", "weekly"})
_HIGH_CONFIDENCE_SECRET_PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bgh[opusr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{20,}\b", re.IGNORECASE),
    re.compile(r"\bxsec_token=[^&\s\"']{10,}", re.IGNORECASE),
)
_TEXT_SUFFIXES = frozenset(
    {".css", ".csv", ".html", ".js", ".json", ".md", ".txt", ".yaml", ".yml"}
)


class AutomationValidationError(ValueError):
    """A safe validation failure suitable for scheduler and Actions logs."""

    def __init__(self, category: str, message: str) -> None:
        super().__init__(message)
        self.category = category


@dataclass(frozen=True, slots=True)
class BundleValidation:
    """Validated report bundle metadata used by automation callers."""

    period: str
    run_date: date
    stem: str
    report_path: Path
    manifest_path: Path
    poster_paths: tuple[Path, ...]
    used_backends: tuple[str, ...]

    def to_dict(self, root: Path) -> dict[str, Any]:
        return {
            "status": "valid",
            "period": self.period,
            "run_date": self.run_date.isoformat(),
            "stem": self.stem,
            "report": _relative_posix(self.report_path, root),
            "manifest": _relative_posix(self.manifest_path, root),
            "poster_count": len(self.poster_paths),
            "used_backends": list(self.used_backends),
        }


def parse_run_date(value: str | date) -> date:
    """Return an ISO date and reject ambiguous scheduler input."""

    if isinstance(value, date):
        return value
    try:
        parsed = date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise AutomationValidationError("invalid_date", "date must use YYYY-MM-DD") from exc
    if parsed.isoformat() != value:
        raise AutomationValidationError("invalid_date", "date must use YYYY-MM-DD")
    return parsed


def report_stem(period: str, run_date: str | date) -> str:
    """Return the filename stem used by daily or weekly report bundles."""

    selected = parse_run_date(run_date)
    if period == "daily":
        return selected.isoformat()
    if period == "weekly":
        iso_year, iso_week, _ = selected.isocalendar()
        return f"{iso_year}-W{iso_week:02d}"
    raise AutomationValidationError("invalid_period", "period must be daily or weekly")


def validate_report_bundle(
    root: str | Path,
    period: str,
    run_date: str | date,
    *,
    require_codex: bool = False,
) -> BundleValidation:
    """Validate one complete report, copy, manifest, and PNG bundle."""

    repository_root = Path(root).resolve()
    selected = parse_run_date(run_date)
    stem = report_stem(period, selected)
    report_directory = repository_root / "reports" / period
    report_path = report_directory / f"{stem}.json"
    required_text_paths = (
        report_directory / f"{stem}.md",
        report_directory / f"{stem}.xiaohongshu.md",
        report_directory / f"{stem}.ai.xiaohongshu.md",
    )
    for path in (report_path, *required_text_paths):
        _require_nonempty_file(path, "artifact_missing")

    payload = _load_json_object(report_path, "report_invalid")
    if payload.get("schema_version") != REPORT_SCHEMA_VERSION:
        raise AutomationValidationError("report_schema", "unsupported report schema")
    if payload.get("period") != period or payload.get("run_date") != selected.isoformat():
        raise AutomationValidationError("report_identity", "report period or date does not match")

    used_backends = _validate_editorial(payload, require_codex=require_codex)
    _validate_publication_metadata(
        payload.get("publication"),
        period=period,
        run_date=selected,
        category="report_publication",
    )
    assets = _require_mapping(payload.get("assets"), "report_assets")
    if assets.get("enabled") is not True:
        raise AutomationValidationError("report_assets", "poster assets must be enabled")
    _validate_publication_metadata(
        assets.get("publication"),
        period=period,
        run_date=selected,
        category="asset_publication",
    )
    width = _positive_int(assets.get("width"), "report_assets")
    height = _positive_int(assets.get("height"), "report_assets")
    manifest_path = _resolve_repo_path(repository_root, assets.get("manifest"), "manifest_path")
    manifest = _load_json_object(manifest_path, "manifest_invalid")
    _validate_manifest_identity(
        manifest,
        period=period,
        run_date=selected,
        source_report=_relative_posix(report_path, repository_root),
        width=width,
        height=height,
    )

    report_boards = _require_mapping(payload.get("boards"), "report_boards")
    manifest_boards = _require_mapping(manifest.get("boards"), "manifest_boards")
    poster_paths: list[Path] = []
    seen_paths: set[Path] = set()
    for board_key in BOARD_KEYS:
        report_board = _require_mapping(report_boards.get(board_key), "report_board")
        manifest_board = _require_mapping(manifest_boards.get(board_key), "manifest_board")
        repositories = report_board.get("repositories")
        projects = manifest_board.get("projects")
        if not isinstance(repositories, list) or not isinstance(projects, list):
            raise AutomationValidationError("board_projects", "board projects must be lists")
        if not repositories or not projects:
            raise AutomationValidationError("board_projects", "both boards must contain projects")
        if len(repositories) != len(projects):
            raise AutomationValidationError("board_projects", "poster count does not match ranking")

        cover_path = _resolve_repo_path(repository_root, manifest_board.get("cover"), "cover_path")
        _validate_png(cover_path, width=width, height=height)
        _append_unique_path(cover_path, seen_paths, poster_paths)

        expected_projects = {
            (
                _positive_int(item.get("rank"), "repository_rank"),
                _nonempty_text(item.get("full_name")),
            ): item
            for item in repositories
            if isinstance(item, dict)
        }
        if len(expected_projects) != len(repositories):
            raise AutomationValidationError("board_projects", "repository identity is invalid")

        actual_projects: set[tuple[int, str]] = set()
        for project in projects:
            if not isinstance(project, dict):
                raise AutomationValidationError("board_projects", "project entry is invalid")
            identity = (
                _positive_int(project.get("rank"), "project_rank"),
                _nonempty_text(project.get("full_name")),
            )
            if identity not in expected_projects or identity in actual_projects:
                raise AutomationValidationError("board_projects", "project identity does not match")
            actual_projects.add(identity)
            project_path = _resolve_repo_path(
                repository_root, project.get("path"), "project_poster_path"
            )
            _validate_png(project_path, width=width, height=height)
            _append_unique_path(project_path, seen_paths, poster_paths)
        if actual_projects != set(expected_projects):
            raise AutomationValidationError("board_projects", "project posters are incomplete")

    return BundleValidation(
        period=period,
        run_date=selected,
        stem=stem,
        report_path=report_path,
        manifest_path=manifest_path,
        poster_paths=tuple(poster_paths),
        used_backends=used_backends,
    )


def validate_generated_paths(
    paths: list[str] | tuple[str, ...], period: str, run_date: str | date
) -> tuple[str, ...]:
    """Return normalised paths or fail when automation touched unrelated files."""

    selected = parse_run_date(run_date)
    stem = report_stem(period, selected)
    normalised: list[str] = []
    for raw_path in paths:
        path = _normalise_git_path(raw_path)
        if not _is_allowed_generated_path(path, period=period, selected=selected, stem=stem):
            raise AutomationValidationError(
                "unexpected_path", f"automation changed an unrelated path: {path}"
            )
        normalised.append(path)
    return tuple(dict.fromkeys(normalised))


def validate_remote_update_paths(paths: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    """Allow only immutable, date-scoped report artifacts from remote automation."""

    normalised: list[str] = []
    for raw_path in paths:
        path = _normalise_git_path(raw_path)
        if not _is_allowed_remote_update_path(path):
            raise AutomationValidationError(
                "remote_update_path",
                f"remote update contains a non-generated path: {path}",
            )
        normalised.append(path)
    return tuple(dict.fromkeys(normalised))


def scan_generated_files(root: str | Path, paths: list[str] | tuple[str, ...]) -> None:
    """Scan staged text artifacts for high-confidence credential signatures."""

    repository_root = Path(root).resolve()
    for raw_path in paths:
        path = _resolve_repo_path(repository_root, _normalise_git_path(raw_path), "scan_path")
        if not path.is_file() or path.suffix.casefold() not in _TEXT_SUFFIXES:
            continue
        if path.stat().st_size > MAX_TEXT_SCAN_BYTES:
            raise AutomationValidationError("scan_too_large", "text artifact exceeds scan limit")
        text = path.read_text(encoding="utf-8", errors="replace")
        if any(pattern.search(text) for pattern in _HIGH_CONFIDENCE_SECRET_PATTERNS):
            raise AutomationValidationError(
                "suspected_secret",
                f"suspected credential in {_relative_posix(path, repository_root)}",
            )


def _validate_editorial(payload: dict[str, Any], *, require_codex: bool) -> tuple[str, ...]:
    editorial = _require_mapping(payload.get("editorial"), "editorial_missing")
    boards = _require_mapping(editorial.get("boards"), "editorial_missing")
    backends: list[str] = []
    for board_key in BOARD_KEYS:
        board = _require_mapping(boards.get(board_key), "editorial_missing")
        used_backend = board.get("used_backend")
        fallback_used = board.get("fallback_used")
        if used_backend not in {"deterministic", "codex-cli"} or not isinstance(
            fallback_used, bool
        ):
            raise AutomationValidationError("editorial_invalid", "editorial metadata is invalid")
        if (
            board.get("prompt_version") != EDITORIAL_PROMPT_VERSION
            or board.get("schema_version") != EDITORIAL_SCHEMA_VERSION
        ):
            raise AutomationValidationError(
                "editorial_version", "both boards must use the current editorial contract"
            )
        if require_codex and (used_backend != "codex-cli" or fallback_used):
            raise AutomationValidationError(
                "editorial_fallback", "both boards must use Codex without fallback"
            )
        backends.append(used_backend)
    return tuple(backends)


def _validate_manifest_identity(
    manifest: dict[str, Any],
    *,
    period: str,
    run_date: date,
    source_report: str,
    width: int,
    height: int,
) -> None:
    if manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        raise AutomationValidationError("manifest_schema", "unsupported manifest schema")
    if manifest.get("period") != period or manifest.get("run_date") != run_date.isoformat():
        raise AutomationValidationError("manifest_identity", "manifest period or date mismatch")
    if manifest.get("source_report") != source_report:
        raise AutomationValidationError("manifest_identity", "manifest source report mismatch")
    if manifest.get("width") != width or manifest.get("height") != height:
        raise AutomationValidationError("manifest_dimensions", "manifest dimensions mismatch")
    renderer = _require_mapping(manifest.get("renderer"), "poster_version")
    if (
        renderer.get("name") != POSTER_RENDERER_NAME
        or renderer.get("version") != POSTER_RENDERER_VERSION
        or manifest.get("style_version") != POSTER_STYLE_VERSION
    ):
        raise AutomationValidationError("poster_version", "poster renderer or style is not current")
    _validate_publication_metadata(
        manifest.get("publication"),
        period=period,
        run_date=run_date,
        category="manifest_publication",
    )


def _is_allowed_generated_path(path: str, *, period: str, selected: date, stem: str) -> bool:
    exact = {
        f"data/snapshots/{selected.isoformat()}.json",
        f"reports/{period}/{stem}.json",
        f"reports/{period}/{stem}.md",
        f"reports/{period}/{stem}.xiaohongshu.md",
        f"reports/{period}/{stem}.ai.xiaohongshu.md",
    }
    prefixes = (
        f"reports/{period}/assets/{stem}/",
        f"reports/{period}/avatars/{stem}/",
        f"publish/{period}/{stem}/",
    )
    return path in exact or any(path.startswith(prefix) for prefix in prefixes)


def _is_allowed_remote_update_path(path: str) -> bool:
    parts = PurePosixPath(path).parts
    if len(parts) == 3 and parts[:2] == ("data", "snapshots"):
        filename = parts[2]
        if not filename.endswith(".json"):
            return False
        return _is_valid_period_stem("daily", filename.removesuffix(".json"))

    if len(parts) < 3 or parts[0] != "reports" or parts[1] not in _PERIODS:
        return False
    period = parts[1]
    if len(parts) == 3:
        stem = _report_filename_stem(parts[2])
        return stem is not None and _is_valid_period_stem(period, stem)
    if len(parts) != 5 or parts[2] not in {"assets", "avatars"}:
        return False

    kind, stem, filename = parts[2:]
    if not _is_valid_period_stem(period, stem):
        return False
    if kind == "assets":
        return filename == "manifest.json" or filename.endswith(".png")
    return filename.endswith(".png")


def _report_filename_stem(filename: str) -> str | None:
    for suffix in (".ai.xiaohongshu.md", ".xiaohongshu.md", ".json", ".md"):
        if filename.endswith(suffix):
            return filename[: -len(suffix)]
    return None


def _is_valid_period_stem(period: str, stem: str) -> bool:
    if period == "daily":
        try:
            return parse_run_date(stem).isoformat() == stem
        except AutomationValidationError:
            return False
    match = re.fullmatch(r"(\d{4})-W(\d{2})", stem)
    if match is None:
        return False
    try:
        date.fromisocalendar(int(match.group(1)), int(match.group(2)), 1)
    except ValueError:
        return False
    return True


def _validate_publication_metadata(
    value: Any,
    *,
    period: str,
    run_date: date,
    category: str,
) -> None:
    publication = _require_mapping(value, category)
    expected = _expected_publication_metadata(period, run_date)
    if any(publication.get(key) != expected_value for key, expected_value in expected.items()):
        raise AutomationValidationError(category, "publication issue metadata is not current")


def _expected_publication_metadata(period: str, run_date: date) -> dict[str, Any]:
    prefix = "D" if period == "daily" else "W"
    if run_date < PUBLICATION_FIRST_ISSUE_DATE:
        return {
            "issue_number": None,
            "issue_code": f"{prefix}-PREVIEW",
            "issue_label": "\u9884\u89c8",
            "status": "preview",
        }
    elapsed_days = (run_date - PUBLICATION_FIRST_ISSUE_DATE).days
    number = elapsed_days + 1 if period == "daily" else elapsed_days // 7 + 1
    return {
        "issue_number": number,
        "issue_code": f"{prefix}{number:03d}",
        "issue_label": f"\u7b2c{number}\u671f",
        "status": "official",
    }


def _normalise_git_path(value: str) -> str:
    if not isinstance(value, str):
        raise AutomationValidationError("invalid_path", "changed path must be text")
    candidate = value.strip().replace("\\", "/")
    pure = PurePosixPath(candidate)
    if (
        not candidate
        or pure.is_absolute()
        or candidate != pure.as_posix()
        or any(part in {"", ".", ".."} for part in pure.parts)
        or any(":" in part for part in pure.parts)
    ):
        raise AutomationValidationError("invalid_path", "changed path is not repository-relative")
    return candidate


def _resolve_repo_path(root: Path, value: Any, category: str) -> Path:
    try:
        relative = _normalise_git_path(_nonempty_text(value))
    except AutomationValidationError as exc:
        raise AutomationValidationError(category, "artifact path is invalid") from exc
    path = (root / Path(*PurePosixPath(relative).parts)).resolve()
    try:
        common = os.path.commonpath((str(root), str(path)))
    except ValueError as exc:
        raise AutomationValidationError(category, "artifact path escapes repository") from exc
    if Path(common) != root:
        raise AutomationValidationError(category, "artifact path escapes repository")
    return path


def _load_json_object(path: Path, category: str) -> dict[str, Any]:
    _require_nonempty_file(path, category)
    if path.stat().st_size > MAX_JSON_BYTES:
        raise AutomationValidationError(category, "JSON artifact exceeds size limit")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AutomationValidationError(category, "JSON artifact is invalid") from exc
    if not isinstance(payload, dict):
        raise AutomationValidationError(category, "JSON artifact root must be an object")
    return payload


def _require_nonempty_file(path: Path, category: str) -> None:
    if not path.is_file() or path.stat().st_size < 1:
        raise AutomationValidationError(category, "required artifact is missing")


def _validate_png(path: Path, *, width: int, height: int) -> None:
    _require_nonempty_file(path, "poster_missing")
    if path.stat().st_size > MAX_PNG_BYTES:
        raise AutomationValidationError("poster_invalid", "poster exceeds PNG size limit")
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise AutomationValidationError("poster_invalid", "poster cannot be read") from exc
    if len(payload) < 8 or payload[:8] != PNG_SIGNATURE:
        raise AutomationValidationError("poster_invalid", "poster is not a PNG")

    offset = len(PNG_SIGNATURE)
    chunk_index = 0
    saw_ihdr = False
    saw_idat = False
    saw_iend = False
    while offset < len(payload):
        if len(payload) - offset < 12:
            raise AutomationValidationError("poster_invalid", "PNG chunk is truncated")
        chunk_length = struct.unpack(">I", payload[offset : offset + 4])[0]
        chunk_type = payload[offset + 4 : offset + 8]
        chunk_end = offset + 12 + chunk_length
        if chunk_end > len(payload):
            raise AutomationValidationError("poster_invalid", "PNG chunk is truncated")
        if len(chunk_type) != 4 or any(
            not (65 <= byte <= 90 or 97 <= byte <= 122) for byte in chunk_type
        ):
            raise AutomationValidationError("poster_invalid", "PNG chunk type is invalid")
        chunk_data = payload[offset + 8 : offset + 8 + chunk_length]
        expected_crc = struct.unpack(">I", payload[offset + 8 + chunk_length : chunk_end])[0]
        actual_crc = zlib.crc32(chunk_type)
        actual_crc = zlib.crc32(chunk_data, actual_crc) & 0xFFFFFFFF
        if actual_crc != expected_crc:
            raise AutomationValidationError("poster_invalid", "PNG chunk checksum is invalid")

        if chunk_index == 0 and chunk_type != b"IHDR":
            raise AutomationValidationError("poster_invalid", "PNG must start with IHDR")
        if chunk_type == b"IHDR":
            if saw_ihdr or chunk_index != 0 or chunk_length != 13:
                raise AutomationValidationError("poster_invalid", "PNG IHDR is invalid")
            saw_ihdr = True
            actual_width, actual_height = struct.unpack(">II", chunk_data[:8])
            if (actual_width, actual_height) != (width, height):
                raise AutomationValidationError(
                    "poster_dimensions", "poster dimensions do not match"
                )
            bit_depth, colour_type, compression, filter_method, interlace = chunk_data[8:]
            valid_depths = {
                0: {1, 2, 4, 8, 16},
                2: {8, 16},
                3: {1, 2, 4, 8},
                4: {8, 16},
                6: {8, 16},
            }
            if (
                actual_width < 1
                or actual_height < 1
                or colour_type not in valid_depths
                or bit_depth not in valid_depths[colour_type]
                or compression != 0
                or filter_method != 0
                or interlace not in {0, 1}
            ):
                raise AutomationValidationError("poster_invalid", "PNG IHDR values are invalid")
        elif chunk_type == b"IDAT":
            if not saw_ihdr or saw_iend:
                raise AutomationValidationError("poster_invalid", "PNG IDAT order is invalid")
            saw_idat = True
        elif chunk_type == b"IEND":
            if chunk_length != 0 or not saw_idat or saw_iend:
                raise AutomationValidationError("poster_invalid", "PNG IEND is invalid")
            saw_iend = True
            offset = chunk_end
            if offset != len(payload):
                raise AutomationValidationError("poster_invalid", "PNG has trailing data")
            break

        offset = chunk_end
        chunk_index += 1

    if not saw_ihdr or not saw_idat or not saw_iend:
        raise AutomationValidationError("poster_invalid", "PNG is incomplete")


def _append_unique_path(path: Path, seen: set[Path], output: list[Path]) -> None:
    if path in seen:
        raise AutomationValidationError("poster_duplicate", "poster path is duplicated")
    seen.add(path)
    output.append(path)


def _require_mapping(value: Any, category: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AutomationValidationError(category, "required object is missing")
    return value


def _positive_int(value: Any, category: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise AutomationValidationError(category, "required integer is invalid")
    return value


def _nonempty_text(value: Any) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise AutomationValidationError("invalid_text", "required text is invalid")
    return value


def _relative_posix(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _read_paths(args: argparse.Namespace) -> list[str]:
    paths = list(args.paths or [])
    if args.paths_file:
        paths.extend(Path(args.paths_file).read_text(encoding="utf-8").splitlines())
    if not paths and not args.paths_file and not sys.stdin.isatty():
        paths.extend(sys.stdin.read().splitlines())
    return [path for path in paths if path.strip()]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate scheduled GitHub Hotspots artifacts")
    subparsers = parser.add_subparsers(dest="command", required=True)

    verify = subparsers.add_parser("verify", help="validate one complete report bundle")
    verify.add_argument("--root", default=".")
    verify.add_argument("--period", choices=sorted(_PERIODS), required=True)
    verify.add_argument("--date", required=True)
    verify.add_argument("--require-codex", action="store_true")
    verify.add_argument("--quiet", action="store_true")

    stem = subparsers.add_parser("stem", help="print the report filename stem")
    stem.add_argument("--period", choices=sorted(_PERIODS), required=True)
    stem.add_argument("--date", required=True)

    validate_paths = subparsers.add_parser(
        "validate-paths", help="reject changes outside the generated allowlist"
    )
    validate_paths.add_argument("--period", choices=sorted(_PERIODS), required=True)
    validate_paths.add_argument("--date", required=True)
    validate_paths.add_argument("--paths-file")
    validate_paths.add_argument("paths", nargs="*")

    validate_remote = subparsers.add_parser(
        "validate-remote-paths", help="reject remote changes outside dated report artifacts"
    )
    validate_remote.add_argument("--paths-file")
    validate_remote.add_argument("paths", nargs="*")

    scan = subparsers.add_parser("scan-paths", help="scan generated text for credentials")
    scan.add_argument("--root", default=".")
    scan.add_argument("--paths-file")
    scan.add_argument("paths", nargs="*")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the small standard-library automation command surface."""

    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "verify":
            validation = validate_report_bundle(
                args.root,
                args.period,
                args.date,
                require_codex=args.require_codex,
            )
            if not args.quiet:
                print(json.dumps(validation.to_dict(Path(args.root).resolve()), ensure_ascii=False))
            return 0
        if args.command == "stem":
            print(report_stem(args.period, args.date))
            return 0
        paths = _read_paths(args)
        if args.command == "validate-paths":
            validated = validate_generated_paths(paths, args.period, args.date)
            print(json.dumps({"status": "valid", "path_count": len(validated)}))
            return 0
        if args.command == "validate-remote-paths":
            validated = validate_remote_update_paths(paths)
            print(json.dumps({"status": "valid", "path_count": len(validated)}))
            return 0
        if args.command == "scan-paths":
            scan_generated_files(args.root, paths)
            print(json.dumps({"status": "valid", "path_count": len(paths)}))
            return 0
    except (AutomationValidationError, OSError) as exc:
        category = getattr(exc, "category", "io_error")
        quiet = getattr(args, "quiet", False)
        if not quiet:
            print(json.dumps({"status": "invalid", "category": category}), file=sys.stderr)
        return 1
    parser.error("unsupported command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

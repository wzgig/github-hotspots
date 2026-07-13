"""Build local, reviewable Xiaohongshu publication bundles from frozen reports."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from PIL import Image, UnidentifiedImageError

from .config import PublicationSettings, Settings, validate_poster_dimensions

_BOARD_ORDER = (
    ("comprehensive", "综合主榜", "C"),
    ("ai", "AI 专题榜", "A"),
)
_ALLOWED_BACKENDS = frozenset({"deterministic", "codex-cli"})
PUBLISH_BUNDLE_GENERATOR_NAME = "github-hotspots-publish-bundle"
PUBLISH_BUNDLE_GENERATOR_VERSION = "1.1"
PUBLISH_HISTORY_SCHEMA_VERSION = 1
_CAPTION_FORBIDDEN = (
    "# 标题",
    "# 正文",
    "# 配图清单",
    "reports/",
    "发布前人工审核",
)


@dataclass(frozen=True, slots=True)
class PublicationIssue:
    """Stable publication-series identity for one report date."""

    period: str
    run_date: date
    number: int | None
    code: str
    stem: str
    label: str
    status: str


@dataclass(frozen=True, slots=True)
class PublishBundleArtifacts:
    """Paths produced by one successful local publication packaging run."""

    period: str
    issue_code: str
    issue_stem: str
    current_dir: Path | None
    manifest: Path | None
    checklist: Path | None
    today: Path
    board_dirs: tuple[Path, ...]
    archived_dir: Path | None
    history_dir: Path
    history_manifest: Path
    history_index_json: Path
    history_index_markdown: Path
    activated_current: bool


def publication_issue(
    publication: PublicationSettings,
    period: str,
    run_date: date,
) -> PublicationIssue:
    """Calculate issue identity from the configured public-series anchor."""

    first_date = publication.first_issue_date(period)
    prefix = "D" if period == "daily" else "W"
    date_stem = (
        run_date.isoformat()
        if period == "daily"
        else f"{run_date.isocalendar().year}-W{run_date.isocalendar().week:02d}"
    )
    if run_date < first_date:
        return PublicationIssue(
            period=period,
            run_date=run_date,
            number=None,
            code=f"{prefix}-PREVIEW",
            stem=f"{prefix}-PREVIEW-{date_stem}",
            label="预览",
            status="preview",
        )

    elapsed_days = (run_date - first_date).days
    number = elapsed_days + 1 if period == "daily" else elapsed_days // 7 + 1
    code = f"{prefix}{number:03d}"
    return PublicationIssue(
        period=period,
        run_date=run_date,
        number=number,
        code=code,
        stem=f"{code}-{date_stem}",
        label=f"第{number}期",
        status="official",
    )


def build_publish_bundle(
    settings: Settings,
    report_path: str | Path,
    *,
    activate_current: bool = True,
    allow_older_current: bool = False,
) -> PublishBundleArtifacts:
    """Create immutable thin history and optionally activate a local publication bundle."""

    publication = settings.publication_settings()
    repository_root = settings.path.parent.parent.resolve()
    publish_root = publication.root_dir.resolve()
    _require_descendant(publish_root, repository_root, "publication.root_dir")

    source_report = _resolve_repository_path(report_path, repository_root, "report")
    report = _read_json_object(source_report, "report")
    period = _text(report.get("period"), "report.period")
    if period not in {"daily", "weekly"}:
        raise ValueError("report.period must be daily or weekly")
    run_date = _iso_date(report.get("run_date"), "report.run_date")
    issue = publication_issue(publication, period, run_date)
    editorial = _validate_editorial(report)

    report_assets = _mapping(report.get("assets"), "report.assets")
    poster_manifest_value = _text(report_assets.get("manifest"), "report.assets.manifest")
    poster_manifest_path = _resolve_repository_path(
        poster_manifest_value,
        repository_root,
        "report.assets.manifest",
    )
    poster_manifest = _read_json_object(poster_manifest_path, "poster manifest")
    poster_size = _validate_poster_manifest(
        poster_manifest,
        report_assets=report_assets,
        period=period,
        run_date=run_date,
        source_report=source_report,
        repository_root=repository_root,
    )

    current_root = publish_root / "current"
    current_root.mkdir(parents=True, exist_ok=True)
    target = current_root / period
    if activate_current and not allow_older_current:
        _reject_older_activation(target, run_date)

    staging = Path(tempfile.mkdtemp(prefix=f".{period}.", dir=current_root))
    now = datetime.now(ZoneInfo(settings.timezone)).isoformat(timespec="microseconds")
    board_manifests: list[dict[str, Any]] = []
    board_dirs: list[Path] = []
    archived_dir: Path | None = None
    activated_current = False
    history_dir: Path | None = None
    try:
        report_boards = _mapping(report.get("boards"), "report.boards")
        poster_boards = _mapping(poster_manifest.get("boards"), "poster manifest.boards")
        for position, (board_key, default_label, board_suffix) in enumerate(_BOARD_ORDER, start=1):
            report_board = _mapping(report_boards.get(board_key), f"report.boards.{board_key}")
            poster_board = _mapping(
                poster_boards.get(board_key), f"poster manifest.boards.{board_key}"
            )
            board_dir = staging / f"{position:02d}-{board_key}"
            board_manifest = _build_board_package(
                publication=publication,
                repository_root=repository_root,
                board_dir=board_dir,
                board_key=board_key,
                default_label=default_label,
                board_suffix=board_suffix,
                report_board=report_board,
                poster_board=poster_board,
                editorial=editorial["boards"][board_key],
                issue=issue,
                poster_size=poster_size,
            )
            board_manifests.append(board_manifest)
            board_dirs.append(Path(board_manifest["directory"]))

        source_report_relative = _relative_path(source_report, repository_root)
        poster_manifest_relative = _relative_path(poster_manifest_path, repository_root)
        bundle_status = "preview" if issue.status == "preview" else "draft"
        checklist_content = _render_checklist(issue, board_manifests)
        _write_text(staging / "CHECKLIST.md", checklist_content)
        generator = {
            "name": PUBLISH_BUNDLE_GENERATOR_NAME,
            "version": PUBLISH_BUNDLE_GENERATOR_VERSION,
        }
        fingerprint_payload = {
            "generator": generator,
            "status": bundle_status,
            "period": period,
            "run_date": run_date.isoformat(),
            "issue": {
                "number": issue.number,
                "code": issue.code,
                "stem": issue.stem,
                "label": issue.label,
                "status": issue.status,
            },
            "source": {
                "report_sha256": _sha256_text_file(source_report),
                "poster_manifest_sha256": _sha256_text_file(poster_manifest_path),
            },
            "editorial": editorial,
            "boards": _fingerprint_boards(board_manifests),
            "checklist_sha256": _sha256_text(checklist_content),
        }
        manifest = {
            "schema_version": 1,
            "generator": generator,
            "content_fingerprint": _sha256_text(
                json.dumps(
                    fingerprint_payload,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
            ),
            "checklist_sha256": _sha256_text(checklist_content),
            "status": bundle_status,
            "period": period,
            "run_date": run_date.isoformat(),
            "generated_at": now,
            "issue": {
                "number": issue.number,
                "code": issue.code,
                "stem": issue.stem,
                "label": issue.label,
                "status": issue.status,
            },
            "source": {
                "report": source_report_relative,
                "report_sha256": _sha256_text_file(source_report),
                "poster_manifest": poster_manifest_relative,
                "poster_manifest_sha256": _sha256_text_file(poster_manifest_path),
                "poster_style_version": _text(
                    poster_manifest.get("style_version"), "poster manifest.style_version"
                ),
            },
            "editorial": editorial,
            "boards": board_manifests,
        }
        _write_text(
            staging / "MANIFEST.json",
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        )

        history_dir = _write_history_revision(
            publish_root=publish_root,
            repository_root=repository_root,
            source_report=source_report,
            period=period,
            run_date=run_date,
            staging=staging,
            manifest=manifest,
        )
        history_index_json, history_index_markdown = refresh_history_index(publish_root)

        if activate_current:
            current_is_identical = _current_bundle_matches(target, manifest)
            if not current_is_identical:
                archived_dir = _rotate_current(target, publish_root / "archive")
                try:
                    staging.replace(target)
                except Exception:
                    if archived_dir is not None and archived_dir.exists() and not target.exists():
                        archived_dir.replace(target)
                    raise
            activated_current = True
            refresh_publish_index(publish_root, timezone=settings.timezone, generated_at=now)

        _append_local_log(
            publish_root / "logs" / "publication.jsonl",
            {
                "generated_at": now,
                "period": period,
                "run_date": run_date.isoformat(),
                "issue_code": issue.code,
                "issue_stem": issue.stem,
                "source_report": source_report_relative,
                "history": _relative_path(history_dir, repository_root),
                "current": (_relative_path(target, repository_root) if activate_current else None),
                "action": (
                    "history-only"
                    if not activate_current
                    else "reused-current"
                    if current_is_identical
                    else "activated-current"
                ),
                "archived": (
                    _relative_path(archived_dir, repository_root)
                    if archived_dir is not None
                    else None
                ),
            },
        )
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)

    if history_dir is None:
        raise RuntimeError("publication history was not created")
    current_dir = target if activate_current else None
    return PublishBundleArtifacts(
        period=period,
        issue_code=issue.code,
        issue_stem=issue.stem,
        current_dir=current_dir,
        manifest=current_dir / "MANIFEST.json" if current_dir is not None else None,
        checklist=current_dir / "CHECKLIST.md" if current_dir is not None else None,
        today=current_root / "TODAY.md",
        board_dirs=(
            tuple(current_dir / path for path in board_dirs) if current_dir is not None else ()
        ),
        archived_dir=archived_dir,
        history_dir=history_dir,
        history_manifest=history_dir / "MANIFEST.json",
        history_index_json=history_index_json,
        history_index_markdown=history_index_markdown,
        activated_current=activated_current,
    )


def refresh_publish_index(
    publish_root: str | Path,
    *,
    timezone: str = "Asia/Shanghai",
    generated_at: str | None = None,
) -> Path:
    """Rebuild TODAY.md from the daily and weekly manifests already on disk."""

    root = Path(publish_root).resolve()
    current_root = root / "current"
    current_root.mkdir(parents=True, exist_ok=True)
    timestamp = generated_at or datetime.now(ZoneInfo(timezone)).isoformat(timespec="seconds")
    today = current_root / "TODAY.md"
    _write_text(today, _render_today(current_root, timestamp))
    return today


def refresh_history_index(publish_root: str | Path) -> tuple[Path, Path]:
    """Rebuild deterministic JSON and Markdown indexes from thin history manifests."""

    root = Path(publish_root).resolve()
    history_root = root / "history"
    history_root.mkdir(parents=True, exist_ok=True)
    grouped: dict[tuple[str, int, str], list[dict[str, Any]]] = {}
    generated_values: list[str] = []

    for manifest_path in sorted(history_root.glob("*/*/*/*/MANIFEST.json")):
        relative = manifest_path.relative_to(history_root)
        if len(relative.parts) != 5:
            continue
        period_dir, year_dir, report_stem_dir, revision_dir, _ = relative.parts
        if period_dir not in {"daily", "weekly"} or not year_dir.isdigit():
            continue

        manifest = _read_json_object(manifest_path, "publication history manifest")
        period = _text(manifest.get("period"), "history manifest.period")
        run_date = _iso_date(manifest.get("run_date"), "history manifest.run_date")
        issue = _mapping(manifest.get("issue"), "history manifest.issue")
        history = _mapping(manifest.get("history"), "history manifest.history")
        fingerprint = _history_fingerprint(manifest)
        report_stem = _safe_component(
            _text(history.get("report_stem"), "history manifest.history.report_stem")
        )
        generated_at = _text(manifest.get("generated_at"), "history manifest.generated_at")
        try:
            datetime.fromisoformat(generated_at)
        except ValueError as exc:
            raise ValueError("history manifest.generated_at must be ISO 8601") from exc

        expected_year = run_date.year if period == "daily" else run_date.isocalendar().year
        if (
            period != period_dir
            or int(year_dir) != expected_year
            or report_stem != report_stem_dir
            or revision_dir != fingerprint[:12]
        ):
            raise ValueError(f"publication history path does not match manifest: {manifest_path}")

        revision = {
            "fingerprint": fingerprint,
            "revision": revision_dir,
            "generated_at": generated_at,
            "path": _relative_path(manifest_path.parent, root),
        }
        grouped.setdefault((period, expected_year, report_stem), []).append(
            {
                "run_date": run_date.isoformat(),
                "issue": dict(issue),
                "source_report": _text(
                    _mapping(manifest.get("source"), "history manifest.source").get("report"),
                    "history manifest.source.report",
                ),
                "revision": revision,
            }
        )
        generated_values.append(generated_at)

    issues: list[dict[str, Any]] = []
    for (period, year, report_stem), values in grouped.items():
        run_dates = {str(value["run_date"]) for value in values}
        issue_values = {
            json.dumps(value["issue"], ensure_ascii=False, sort_keys=True) for value in values
        }
        source_reports = {str(value["source_report"]) for value in values}
        if len(run_dates) != 1 or len(issue_values) != 1 or len(source_reports) != 1:
            raise ValueError(f"publication history revisions disagree for {period}/{report_stem}")
        revisions = sorted(
            (dict(value["revision"]) for value in values),
            key=lambda item: (str(item["generated_at"]), str(item["fingerprint"])),
        )
        issues.append(
            {
                "period": period,
                "year": year,
                "report_stem": report_stem,
                "run_date": next(iter(run_dates)),
                "issue": json.loads(next(iter(issue_values))),
                "source_report": next(iter(source_reports)),
                "latest": dict(revisions[-1]),
                "revisions": revisions,
            }
        )

    issues.sort(
        key=lambda item: (
            str(item["run_date"]),
            1 if item["period"] == "daily" else 0,
            str(item["report_stem"]),
        ),
        reverse=True,
    )
    index = {
        "schema_version": PUBLISH_HISTORY_SCHEMA_VERSION,
        "updated_at": max(generated_values) if generated_values else None,
        "issues": issues,
    }
    json_path = history_root / "INDEX.json"
    markdown_path = history_root / "INDEX.md"
    _write_text(
        json_path,
        json.dumps(index, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
    )
    _write_text(markdown_path, _render_history_index(index))
    return json_path, markdown_path


def _build_board_package(
    *,
    publication: PublicationSettings,
    repository_root: Path,
    board_dir: Path,
    board_key: str,
    default_label: str,
    board_suffix: str,
    report_board: Mapping[str, Any],
    poster_board: Mapping[str, Any],
    editorial: Mapping[str, Any],
    issue: PublicationIssue,
    poster_size: tuple[int, int],
) -> dict[str, Any]:
    label = _text(report_board.get("label", default_label), f"{board_key}.label")
    repositories = _sequence(report_board.get("repositories"), f"{board_key}.repositories")
    if not repositories:
        raise ValueError(f"report.boards.{board_key}.repositories must not be empty")
    if poster_board.get("enabled") is not True:
        raise ValueError(f"poster manifest.boards.{board_key}.enabled must be true")

    board_dir.mkdir(parents=True, exist_ok=False)
    images_dir = board_dir / "images"
    images_dir.mkdir()
    issue_post_id = f"{issue.code}-{board_suffix}"
    title = _build_title(issue, board_key, len(repositories))
    caption = _build_caption(issue, board_key, label, repositories)
    _validate_copy(title, caption, publication)

    title_path = board_dir / "TITLE.txt"
    caption_path = board_dir / "CAPTION.txt"
    review_path = board_dir / "REVIEW.md"
    _write_text(title_path, title + "\n")
    _write_text(caption_path, caption)

    images: list[dict[str, Any]] = []
    cover = _text(poster_board.get("cover"), f"poster manifest.boards.{board_key}.cover")
    cover_source = _resolve_repository_path(cover, repository_root, f"{board_key}.cover")
    cover_destination = images_dir / "01-cover.png"
    images.append(
        _materialize_image(
            source=cover_source,
            destination=cover_destination,
            repository_root=repository_root,
            package_root=board_dir,
            order=1,
            role="cover",
            expected_size=poster_size,
        )
    )

    projects = _sequence(poster_board.get("projects"), f"poster manifest.{board_key}.projects")
    project_by_rank: dict[int, Mapping[str, Any]] = {}
    for raw_project in projects:
        project = _mapping(raw_project, f"poster manifest.{board_key}.projects[]")
        rank = _positive_integer(project.get("rank"), f"poster manifest.{board_key}.rank")
        if rank in project_by_rank:
            raise ValueError(f"poster manifest.boards.{board_key} contains duplicate rank {rank}")
        project_by_rank[rank] = project

    normalized_repositories: list[Mapping[str, Any]] = []
    for expected_rank, raw_repository in enumerate(repositories, start=1):
        repository = _mapping(raw_repository, f"report.boards.{board_key}.repositories[]")
        rank = _positive_integer(repository.get("rank"), f"{board_key}.repository.rank")
        if rank != expected_rank:
            raise ValueError(f"report.boards.{board_key} ranks must be contiguous from 1")
        full_name = _text(repository.get("full_name"), f"{board_key}.repository.full_name")
        project = project_by_rank.get(rank)
        if project is None:
            raise ValueError(f"poster manifest.boards.{board_key} is missing rank {rank}")
        if _text(project.get("full_name"), f"{board_key}.project.full_name") != full_name:
            raise ValueError(f"poster manifest.boards.{board_key} rank {rank} repository mismatch")
        project_source = _resolve_repository_path(
            _text(project.get("path"), f"{board_key}.project.path"),
            repository_root,
            f"poster manifest.boards.{board_key}.projects[{rank}].path",
        )
        filename = f"{rank + 1:02d}-rank-{rank:02d}-{_slug(full_name)}.png"
        image_manifest = _materialize_image(
            source=project_source,
            destination=images_dir / filename,
            repository_root=repository_root,
            package_root=board_dir,
            order=rank + 1,
            role="project",
            expected_size=poster_size,
        )
        image_manifest.update({"rank": rank, "full_name": full_name})
        images.append(image_manifest)
        normalized_repositories.append(repository)

    if len(project_by_rank) != len(normalized_repositories):
        raise ValueError(f"poster manifest.boards.{board_key} project count does not match report")

    _write_text(
        review_path,
        _render_review(
            title=title,
            caption=caption,
            issue_post_id=issue_post_id,
            label=label,
            repositories=normalized_repositories,
            images=images,
            editorial=editorial,
        ),
    )
    directory = board_dir.name
    return {
        "key": board_key,
        "label": label,
        "post_id": issue_post_id,
        "status": "preview" if issue.status == "preview" else "draft",
        "directory": directory,
        "title": f"{directory}/TITLE.txt",
        "title_chars": len(title),
        "title_sha256": _sha256_text_file(title_path),
        "caption": f"{directory}/CAPTION.txt",
        "caption_chars": len(caption.rstrip("\n")),
        "caption_sha256": _sha256_text_file(caption_path),
        "review": f"{directory}/REVIEW.md",
        "review_sha256": _sha256_text_file(review_path),
        "editorial": dict(editorial),
        "images": images,
    }


def _build_title(issue: PublicationIssue, board_key: str, repository_count: int) -> str:
    issue_label = issue.label if issue.number is not None else "预览"
    if board_key == "ai":
        cadence = "GitHub AI日报" if issue.period == "daily" else "GitHub AI周报"
        ending = "讲明白" if issue.period == "daily" else "值得收藏"
        return f"{cadence}{issue_label}｜{repository_count}个AI项目{ending}"
    cadence = "GitHub日报" if issue.period == "daily" else "GitHub周报"
    ending = "讲明白" if issue.period == "daily" else "值得收藏"
    return f"{cadence}{issue_label}｜{repository_count}个开源项目{ending}"


def _build_caption(
    issue: PublicationIssue,
    board_key: str,
    label: str,
    repositories: Sequence[object],
) -> str:
    repository_count = len(repositories)
    if issue.period == "daily" and board_key == "comprehensive":
        intro = (
            f"GitHub Hotspots 日报{issue.label}。今天把 {repository_count} 个上榜项目翻译成人话："
            "它解决什么、能替你做什么、适不适合现在上手。"
        )
        question = "如果只能先试一个，你会选哪一个？"
    elif issue.period == "daily":
        intro = (
            f"GitHub Hotspots AI 日报{issue.label}。今天这 {repository_count} 个项目不按名气讲，"
            "只看实际任务、使用边界和适合谁。"
        )
        question = "哪一个值得下一期做成上手卡？"
    elif board_key == "comprehensive":
        intro = (
            f"GitHub Hotspots 周报{issue.label}。把这一周的 {repository_count} 个热点压缩成一组"
            "可收藏的项目卡：先看用途，再看为什么值得关注。"
        )
        question = "这一周你最想把哪一个加入收藏夹？"
    else:
        intro = (
            f"GitHub Hotspots AI 周报{issue.label}。去掉术语包装，用 {repository_count} 张项目卡"
            "讲清实际能力、适用人群和上手前提。"
        )
        question = "下周想看我深挖哪一个的真实使用门槛？"
    lines = [f"{issue.run_date.isoformat()} · {label} · {issue.label}", "", intro, "", "先看结论："]
    for raw_repository in repositories:
        repository = _mapping(raw_repository, f"{board_key}.repository")
        rank = _positive_integer(repository.get("rank"), f"{board_key}.repository.rank")
        full_name = _text(repository.get("full_name"), f"{board_key}.repository.full_name")
        summary = _mapping(repository.get("summary"), f"{board_key}.repository.summary")
        one_line = _text(summary.get("one_line"), f"{board_key}.summary.one_line")
        lines.append(f"{rank:02d}｜{full_name}：{one_line}")
    hashtags = (
        "#GitHub #开源项目 #程序员 #开发者工具"
        if board_key == "comprehensive"
        else "#GitHub #开源项目 #AI #AI工具"
    )
    lines.extend(("", question, "", "AI 辅助整理｜人工发布", "", hashtags))
    return "\n".join(lines).rstrip() + "\n"


def _validate_copy(
    title: str,
    caption: str,
    publication: PublicationSettings,
) -> None:
    if len(title) > publication.title_max_chars:
        raise ValueError(
            f"publication title exceeds {publication.title_max_chars} characters: {len(title)}"
        )
    caption_length = len(caption.rstrip("\n"))
    if caption_length > publication.caption_max_chars:
        raise ValueError(
            f"publication caption exceeds {publication.caption_max_chars} characters: "
            f"{caption_length}"
        )
    forbidden = next((text for text in _CAPTION_FORBIDDEN if text in caption), None)
    if forbidden is not None:
        raise ValueError(f"publication caption contains internal text: {forbidden}")


def _materialize_image(
    *,
    source: Path,
    destination: Path,
    repository_root: Path,
    package_root: Path,
    order: int,
    role: str,
    expected_size: tuple[int, int],
) -> dict[str, Any]:
    width, height = _validate_png(source, expected_size=expected_size)
    destination.parent.mkdir(parents=True, exist_ok=True)
    # The publication folder is an editable workbench.  Hard links would let
    # an in-place crop or annotation mutate the versioned report asset and
    # invalidate both Pages and publication-history hashes.
    shutil.copy2(source, destination)
    destination_width, destination_height = _validate_png(destination, expected_size=expected_size)
    source_hash = _sha256(source)
    destination_hash = _sha256(destination)
    if (destination_width, destination_height) != (
        width,
        height,
    ) or destination_hash != source_hash:
        raise RuntimeError(f"publication image verification failed: {destination}")
    return {
        "order": order,
        "role": role,
        "path": _relative_path(destination, package_root),
        "source": _relative_path(source, repository_root),
        "sha256": destination_hash,
        "width": destination_width,
        "height": destination_height,
        "materialization": "copy",
    }


def _validate_png(
    path: Path,
    *,
    expected_size: tuple[int, int] | None = None,
) -> tuple[int, int]:
    if not path.is_file():
        raise ValueError(f"publication image does not exist: {path}")
    try:
        with Image.open(path) as image:
            image.load()
            if image.format != "PNG":
                raise ValueError(f"publication image must be PNG: {path}")
            try:
                actual_size = validate_poster_dimensions(image.width, image.height)
            except ValueError as exc:
                raise ValueError(
                    f"publication image must use a legal 3:4 poster size: {path} is "
                    f"{image.width}x{image.height}"
                ) from exc
            if expected_size is not None and actual_size != expected_size:
                raise ValueError(
                    f"publication image size does not match its manifest: {path} is "
                    f"{image.width}x{image.height}, expected "
                    f"{expected_size[0]}x{expected_size[1]}"
                )
            return actual_size
    except (OSError, UnidentifiedImageError) as exc:
        raise ValueError(f"publication image cannot be decoded: {path}") from exc


def _validate_editorial(report: Mapping[str, Any]) -> dict[str, Any]:
    raw_editorial = _mapping(report.get("editorial"), "report.editorial")
    policy = _text(raw_editorial.get("policy"), "report.editorial.policy")
    raw_boards = _mapping(raw_editorial.get("boards"), "report.editorial.boards")
    boards: dict[str, dict[str, Any]] = {}
    for board_key, _, _ in _BOARD_ORDER:
        raw = _mapping(raw_boards.get(board_key), f"report.editorial.boards.{board_key}")
        requested = _text(raw.get("requested_backend"), f"{board_key}.requested_backend")
        used = _text(raw.get("used_backend"), f"{board_key}.used_backend")
        if requested not in _ALLOWED_BACKENDS or used not in _ALLOWED_BACKENDS:
            raise ValueError(f"report editorial backend is unsupported for {board_key}")
        fallback = raw.get("fallback_used")
        if not isinstance(fallback, bool):
            raise ValueError(f"report editorial fallback_used must be boolean for {board_key}")
        if fallback and used != "deterministic":
            raise ValueError(f"report editorial fallback must use deterministic for {board_key}")
        if not fallback and requested != used:
            raise ValueError(f"report editorial backend mismatch without fallback for {board_key}")
        error_category = raw.get("error_category")
        if error_category is not None and not isinstance(error_category, str):
            raise ValueError(
                f"report editorial error_category must be text or null for {board_key}"
            )
        boards[board_key] = {
            "prompt_version": _text(raw.get("prompt_version"), f"{board_key}.prompt_version"),
            "schema_version": _text(raw.get("schema_version"), f"{board_key}.schema_version"),
            "requested_backend": requested,
            "used_backend": used,
            "fallback_used": fallback,
            "error_category": error_category,
        }
    return {"policy": policy, "boards": boards}


def _validate_poster_manifest(
    manifest: Mapping[str, Any],
    *,
    report_assets: Mapping[str, Any],
    period: str,
    run_date: date,
    source_report: Path,
    repository_root: Path,
) -> tuple[int, int]:
    if _positive_integer(manifest.get("schema_version"), "poster manifest.schema_version") != 2:
        raise ValueError("poster manifest.schema_version must be 2")
    if _text(manifest.get("period"), "poster manifest.period") != period:
        raise ValueError("poster manifest period does not match report")
    if _iso_date(manifest.get("run_date"), "poster manifest.run_date") != run_date:
        raise ValueError("poster manifest run_date does not match report")
    if manifest.get("enabled") is not True:
        raise ValueError("poster manifest.enabled must be true")
    if _text(manifest.get("format"), "poster manifest.format").casefold() != "png":
        raise ValueError("poster manifest.format must be png")
    poster_size = validate_poster_dimensions(
        _positive_integer(manifest.get("width"), "poster manifest.width"),
        _positive_integer(manifest.get("height"), "poster manifest.height"),
    )
    if report_assets.get("enabled") is not True:
        raise ValueError("report.assets.enabled must be true")
    report_size = validate_poster_dimensions(
        _positive_integer(report_assets.get("width"), "report.assets.width"),
        _positive_integer(report_assets.get("height"), "report.assets.height"),
    )
    if report_size != poster_size:
        raise ValueError("poster manifest dimensions do not match report assets")
    manifest_source = _resolve_repository_path(
        _text(manifest.get("source_report"), "poster manifest.source_report"),
        repository_root,
        "poster manifest.source_report",
    )
    if manifest_source != source_report:
        raise ValueError("poster manifest.source_report does not match report")
    return poster_size


def _render_review(
    *,
    title: str,
    caption: str,
    issue_post_id: str,
    label: str,
    repositories: Sequence[Mapping[str, Any]],
    images: Sequence[Mapping[str, Any]],
    editorial: Mapping[str, Any],
) -> str:
    lines = [
        f"# {issue_post_id} · {label} 发布审核",
        "",
        "- 状态：`draft`",
        f"- 编辑后端：`{editorial['used_backend']}`",
        f"- 回退：`{str(editorial['fallback_used']).lower()}`",
        "",
        "## 标题",
        "",
        title,
        "",
        "## 可粘贴正文",
        "",
        caption.rstrip(),
        "",
        "## 项目事实",
        "",
    ]
    for repository in repositories:
        rank = _positive_integer(repository.get("rank"), "review.repository.rank")
        full_name = _text(repository.get("full_name"), "review.repository.full_name")
        summary = _mapping(repository.get("summary"), "review.repository.summary")
        lines.extend(
            (
                f"### {rank:02d}｜{full_name}",
                "",
                f"- 仓库：{_text(repository.get('html_url'), 'review.repository.html_url')}",
                f"- 定位：{_text(summary.get('one_line'), 'review.summary.one_line')}",
                f"- Star：{_nonnegative_integer(repository.get('stars'), 'review.repository.stars'):,}",
                f"- Fork：{_nonnegative_integer(repository.get('forks'), 'review.repository.forks'):,}",
                f"- 本期信号：{_integer(repository.get('star_delta'), 'review.repository.star_delta'):+,} Star（{_text(repository.get('delta_source'), 'review.repository.delta_source')}）",
            )
        )
        license_label = summary.get("license_label")
        if isinstance(license_label, str) and license_label.strip():
            lines.append(f"- 许可证：{license_label.strip()}")
        capabilities = summary.get("capabilities")
        if isinstance(capabilities, list) and capabilities:
            lines.append(
                "- 能力："
                + "；".join(str(item).strip() for item in capabilities if str(item).strip())
            )
        lines.append("")
    lines.extend(("## 配图顺序", ""))
    for image in images:
        label_text = "封面" if image["role"] == "cover" else image.get("full_name", "项目图")
        lines.append(f"{image['order']:02d}. `{image['path']}` — {label_text}")
    lines.extend(
        (
            "",
            "## 人工确认",
            "",
            "- [ ] 标题和正文已复核",
            "- [ ] 项目事实已复核",
            "- [ ] 图片顺序已复核",
            "- [ ] 发布后填写平台链接",
            "",
        )
    )
    return "\n".join(lines)


def _render_checklist(issue: PublicationIssue, boards: Sequence[Mapping[str, Any]]) -> str:
    lines = [
        f"# {issue.code} 发布检查清单",
        "",
        f"- 日期：{issue.run_date.isoformat()}",
        f"- 期号：{issue.label}",
        f"- 状态：`{'draft' if issue.status == 'official' else 'preview'}`",
        "",
    ]
    for board in boards:
        lines.extend(
            (
                f"## {board['post_id']} · {board['label']}",
                "",
                f"- 标题：`{board['title']}`（{board['title_chars']} 字）",
                f"- 正文：`{board['caption']}`（{board['caption_chars']} 字）",
                f"- 图片：{len(board['images'])} 张，按文件名前缀顺序上传",
                "- [ ] 阅读 `REVIEW.md` 并核对项目事实",
                "- [ ] 检查 Owner 头像、文字换行和图片顺序",
                "- [ ] 确认正文保留 AI 辅助标识，并按平台当前入口完成相应标记",
                "- [ ] 完成全部人工确认后再发布（当前没有自动 approve 命令）",
                "- [ ] 发布后记录帖子链接和发布时间",
                "",
            )
        )
    return "\n".join(lines)


def _render_today(current_root: Path, generated_at: str) -> str:
    current_manifests: dict[str, dict[str, Any]] = {}
    for period in ("daily", "weekly"):
        manifest_path = current_root / period / "MANIFEST.json"
        if manifest_path.is_file():
            current_manifests[period] = _read_json_object(
                manifest_path, f"current {period} manifest"
            )

    daily_manifest = current_manifests.get("daily")
    weekly_manifest = current_manifests.get("weekly")
    reference_manifest = daily_manifest or weekly_manifest
    reference_date = (
        _iso_date(reference_manifest.get("run_date"), "current run_date")
        if reference_manifest is not None
        else None
    )
    weekly_date = (
        _iso_date(weekly_manifest.get("run_date"), "current weekly.run_date")
        if weekly_manifest is not None
        else None
    )
    is_current_sunday_pair = (
        reference_date is not None
        and reference_date.weekday() == 6
        and weekly_date == reference_date
    )

    lines = [
        "# 当前待发布内容",
        "",
        f"更新时间：{generated_at}",
        "",
        "## 建议发布节奏",
        "",
    ]
    if is_current_sunday_pair:
        lines.extend(
            (
                "- 周日优先发布日报综合榜，晚些时候再发布周报综合榜。",
                "- AI 日榜与 AI 周榜保留为后续时段的独立帖子，不建议同一天连续发布四篇。",
            )
        )
    else:
        lines.extend(
            (
                "- 今天优先发布最新日报综合榜；AI 日榜作为独立帖子安排在后续时段。",
                "- `current/weekly` 仅保留最近一期周报供周日发布或回看，工作日不重复推送旧周报。",
            )
        )
    lines.extend(
        (
            "- 每个帖子进入对应目录，复制 `TITLE.txt` 和 `CAPTION.txt`，图片按文件名前缀上传。",
            "",
        )
    )
    for period, label in (("daily", "日报"), ("weekly", "周报")):
        manifest = current_manifests.get(period)
        if manifest is None:
            lines.extend((f"## {label}", "", "尚未生成。", ""))
            continue
        issue = _mapping(manifest.get("issue"), f"current {period}.issue")
        lines.extend(
            (
                f"## {label} · {_text(issue.get('code'), f'current {period}.issue.code')}",
                "",
                f"- 日期：{_text(manifest.get('run_date'), f'current {period}.run_date')}",
                f"- 状态：`{_text(manifest.get('status'), f'current {period}.status')}`",
                f"- 检查清单：`{period}/CHECKLIST.md`",
            )
        )
        for board in _sequence(manifest.get("boards"), f"current {period}.boards"):
            board_data = _mapping(board, f"current {period}.board")
            lines.append(
                f"- {_text(board_data.get('post_id'), 'current post_id')}："
                f"`{period}/{_text(board_data.get('directory'), 'current directory')}/`"
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _render_history_index(index: Mapping[str, Any]) -> str:
    lines = [
        "# 发布历史",
        "",
        "这里保存每期文案、审核稿和可验证清单；配图复用 `reports/` 中已版本化的源文件。",
        "",
        "| 日期 | 周期 | 期号 | 最新修订 | 修订数 | 内容 |",
        "| --- | --- | --- | --- | ---: | --- |",
    ]
    issues = _sequence(index.get("issues"), "history index.issues")
    for raw_issue in issues:
        issue = _mapping(raw_issue, "history index.issue")
        publication_issue_data = _mapping(issue.get("issue"), "history index.issue.issue")
        latest = _mapping(issue.get("latest"), "history index.issue.latest")
        revisions = _sequence(issue.get("revisions"), "history index.issue.revisions")
        period = _text(issue.get("period"), "history index.issue.period")
        period_label = "日报" if period == "daily" else "周报"
        latest_path = _text(latest.get("path"), "history index.issue.latest.path")
        if not latest_path.startswith("history/"):
            raise ValueError("history index revision path must stay below publish/history")
        relative_path = latest_path.removeprefix("history/")
        links = (
            f"[清单]({relative_path}/MANIFEST.json) · "
            f"[综合文案]({relative_path}/01-comprehensive/CAPTION.txt) · "
            f"[AI 文案]({relative_path}/02-ai/CAPTION.txt)"
        )
        lines.append(
            "| "
            f"{_text(issue.get('run_date'), 'history index.issue.run_date')} | "
            f"{period_label} | "
            f"{_text(publication_issue_data.get('code'), 'history index.issue.code')} | "
            f"`{_text(latest.get('revision'), 'history index.issue.latest.revision')}` | "
            f"{len(revisions)} | "
            f"{links} |"
        )
    if not issues:
        lines.append("| - | - | - | - | 0 | - |")
    lines.append("")
    return "\n".join(lines)


def _reject_older_activation(target: Path, incoming_date: date) -> None:
    if not target.exists():
        return
    if not target.is_dir():
        raise ValueError(f"current publication target is not a directory: {target}")
    manifest = _read_json_object(target / "MANIFEST.json", "current publication manifest")
    period = _text(manifest.get("period"), "current manifest.period")
    if period != target.name or period not in {"daily", "weekly"}:
        raise ValueError("current publication manifest period is invalid")
    current_date = _iso_date(manifest.get("run_date"), "current manifest.run_date")
    if current_date > incoming_date:
        raise ValueError(
            f"refusing to activate older {period} report {incoming_date.isoformat()} over "
            f"current {current_date.isoformat()}; use history-only mode or explicitly allow "
            "older current activation"
        )


def _write_history_revision(
    *,
    publish_root: Path,
    repository_root: Path,
    source_report: Path,
    period: str,
    run_date: date,
    staging: Path,
    manifest: Mapping[str, Any],
) -> Path:
    fingerprint = _history_fingerprint(manifest)
    report_stem = _safe_component(source_report.stem)
    year = run_date.year if period == "daily" else run_date.isocalendar().year
    issue_root = publish_root / "history" / period / str(year) / report_stem
    revision = issue_root / fingerprint[:12]
    thin_manifest = _thin_history_manifest(
        manifest,
        report_stem=report_stem,
        revision=fingerprint[:12],
    )
    _validate_history_image_sources(
        thin_manifest,
        repository_root=repository_root,
        period=period,
        report_stem=report_stem,
    )

    repair_existing = False
    if revision.exists():
        try:
            _validate_history_revision(
                revision,
                repository_root=repository_root,
                expected_fingerprint=fingerprint,
            )
            return revision
        except (OSError, ValueError):
            repair_existing = True

    issue_root.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{fingerprint[:12]}.", dir=issue_root))
    try:
        _copy_history_text_files(staging, temporary, thin_manifest)
        _write_text(
            temporary / "MANIFEST.json",
            json.dumps(thin_manifest, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        )
        _validate_history_revision(
            temporary,
            repository_root=repository_root,
            expected_fingerprint=fingerprint,
        )
        if repair_existing:
            quarantine_root = (
                publish_root / "archive" / "history-recovery" / period / str(year) / report_stem
            )
            quarantine_root.mkdir(parents=True, exist_ok=True)
            quarantine = quarantine_root / f"{revision.name}-{uuid.uuid4().hex[:12]}"
            revision.replace(quarantine)
            try:
                temporary.replace(revision)
            except Exception:
                if not revision.exists() and quarantine.exists():
                    quarantine.replace(revision)
                raise
            try:
                if quarantine.is_dir():
                    shutil.rmtree(quarantine)
                else:
                    quarantine.unlink(missing_ok=True)
            except OSError:
                # The valid revision is already active. Windows can temporarily lock files,
                # so retain the quarantined copy under ignored local archive storage instead
                # of turning a successful repair into a recurring automation failure.
                pass
        else:
            try:
                temporary.replace(revision)
            except OSError:
                if not revision.exists():
                    raise
                _validate_history_revision(
                    revision,
                    repository_root=repository_root,
                    expected_fingerprint=fingerprint,
                )
    finally:
        if temporary.exists():
            shutil.rmtree(temporary, ignore_errors=True)
    return revision


def _thin_history_manifest(
    manifest: Mapping[str, Any],
    *,
    report_stem: str,
    revision: str,
) -> dict[str, Any]:
    thin = json.loads(json.dumps(dict(manifest), ensure_ascii=False))
    thin["history"] = {
        "schema_version": PUBLISH_HISTORY_SCHEMA_VERSION,
        "kind": "thin-publication-history",
        "report_stem": report_stem,
        "revision": revision,
        "image_policy": "repository-source-reference",
    }
    for raw_board in _sequence(thin.get("boards"), "history manifest.boards"):
        board = _mapping(raw_board, "history manifest.board")
        history_images: list[dict[str, Any]] = []
        for raw_image in _sequence(board.get("images"), "history manifest.board.images"):
            image = dict(_mapping(raw_image, "history manifest.board.image"))
            image["publication_path"] = image.pop("path")
            image.pop("materialization", None)
            history_images.append(image)
        raw_board["images"] = history_images
    return thin


def _copy_history_text_files(
    source_root: Path,
    destination_root: Path,
    manifest: Mapping[str, Any],
) -> None:
    relative_paths = ["CHECKLIST.md"]
    for raw_board in _sequence(manifest.get("boards"), "history manifest.boards"):
        board = _mapping(raw_board, "history manifest.board")
        relative_paths.extend(
            _text(board.get(field), f"history manifest.board.{field}")
            for field in ("title", "caption", "review")
        )
    for relative in relative_paths:
        source = _bundle_child(source_root, relative, "history source text")
        if not source.is_file():
            raise ValueError(f"publication history source file is missing: {source}")
        _write_text(
            _bundle_child(destination_root, relative, "history destination text"),
            source.read_text(encoding="utf-8"),
        )


def _validate_history_revision(
    revision: Path,
    *,
    repository_root: Path,
    expected_fingerprint: str,
) -> None:
    if not revision.is_dir():
        raise ValueError(f"publication history revision is not a directory: {revision}")
    manifest = _read_json_object(revision / "MANIFEST.json", "publication history manifest")
    fingerprint = _history_fingerprint(manifest)
    if fingerprint != expected_fingerprint:
        raise ValueError(f"publication history fingerprint collision: {revision}")
    history = _mapping(manifest.get("history"), "history manifest.history")
    if (
        _positive_integer(history.get("schema_version"), "history manifest.schema_version")
        != PUBLISH_HISTORY_SCHEMA_VERSION
        or _text(history.get("kind"), "history manifest.kind") != "thin-publication-history"
        or _text(history.get("image_policy"), "history manifest.image_policy")
        != "repository-source-reference"
    ):
        raise ValueError(f"publication history metadata is invalid: {revision}")
    period = _text(manifest.get("period"), "history manifest.period")
    report_stem = _safe_component(_text(history.get("report_stem"), "history manifest.report_stem"))
    _validate_history_image_sources(
        manifest,
        repository_root=repository_root,
        period=period,
        report_stem=report_stem,
    )
    _validate_bundle_text_files(revision, manifest)

    expected_files = {"MANIFEST.json", "CHECKLIST.md"}
    for raw_board in _sequence(manifest.get("boards"), "history manifest.boards"):
        board = _mapping(raw_board, "history manifest.board")
        expected_files.update(
            _text(board.get(field), f"history manifest.board.{field}")
            for field in ("title", "caption", "review")
        )
        for raw_image in _sequence(board.get("images"), "history manifest.board.images"):
            image = _mapping(raw_image, "history manifest.board.image")
            if "path" in image or "materialization" in image:
                raise ValueError("thin publication history must not reference packaged images")
    actual_files = {
        path.relative_to(revision).as_posix() for path in revision.rglob("*") if path.is_file()
    }
    if actual_files != expected_files or any(
        path.suffix.casefold() == ".png" for path in revision.rglob("*")
    ):
        raise ValueError(f"publication history revision contains unexpected files: {revision}")


def _validate_history_image_sources(
    manifest: Mapping[str, Any],
    *,
    repository_root: Path,
    period: str,
    report_stem: str,
) -> None:
    expected_root = (repository_root / "reports" / period / "assets" / report_stem).resolve()
    for raw_board in _sequence(manifest.get("boards"), "history manifest.boards"):
        board = _mapping(raw_board, "history manifest.board")
        for raw_image in _sequence(board.get("images"), "history manifest.board.images"):
            image = _mapping(raw_image, "history manifest.board.image")
            source = _resolve_repository_path(
                _text(image.get("source"), "history manifest.image.source"),
                repository_root,
                "history manifest.image.source",
            )
            if source == expected_root or not source.is_relative_to(expected_root):
                raise ValueError("publication history images must reference report poster assets")
            if _sha256(source) != _text(image.get("sha256"), "history manifest.image.sha256"):
                raise ValueError(f"publication history image source hash mismatch: {source}")
            expected_size = (
                _positive_integer(image.get("width"), "history manifest.image.width"),
                _positive_integer(image.get("height"), "history manifest.image.height"),
            )
            if _validate_png(source) != expected_size:
                raise ValueError(f"publication history image source dimensions mismatch: {source}")


def _current_bundle_matches(target: Path, incoming_manifest: Mapping[str, Any]) -> bool:
    if not target.exists():
        return False
    if not target.is_dir():
        return False
    try:
        manifest = _read_json_object(target / "MANIFEST.json", "current publication manifest")
        if _history_fingerprint(manifest) != _history_fingerprint(incoming_manifest):
            return False
        if _manifest_content_projection(manifest) != _manifest_content_projection(
            incoming_manifest
        ):
            return False
        _validate_materialized_bundle(target, manifest)
    except (OSError, ValueError):
        return False
    return True


def _validate_materialized_bundle(root: Path, manifest: Mapping[str, Any]) -> None:
    _validate_bundle_text_files(root, manifest)
    for raw_board in _sequence(manifest.get("boards"), "publication manifest.boards"):
        board = _mapping(raw_board, "publication manifest.board")
        board_root = _bundle_child(
            root,
            _text(board.get("directory"), "publication manifest.board.directory"),
            "publication board directory",
        )
        for raw_image in _sequence(board.get("images"), "publication manifest.board.images"):
            image = _mapping(raw_image, "publication manifest.board.image")
            if image.get("materialization") != "copy":
                raise ValueError("publication working images must be independent copies")
            packaged = _bundle_child(
                board_root,
                _text(image.get("path"), "publication manifest.image.path"),
                "publication image",
            )
            if not packaged.is_file():
                raise ValueError(f"publication image is missing: {packaged}")
            if _sha256(packaged) != _text(image.get("sha256"), "publication manifest.image.sha256"):
                raise ValueError(f"publication image hash mismatch: {packaged}")
            expected_size = (
                _positive_integer(image.get("width"), "publication manifest.image.width"),
                _positive_integer(image.get("height"), "publication manifest.image.height"),
            )
            if _validate_png(packaged) != expected_size:
                raise ValueError(f"publication image dimensions mismatch: {packaged}")


def _validate_bundle_text_files(root: Path, manifest: Mapping[str, Any]) -> None:
    checklist = _bundle_child(root, "CHECKLIST.md", "publication checklist")
    if not checklist.is_file() or _sha256_text_file(checklist) != _text(
        manifest.get("checklist_sha256"), "publication manifest.checklist_sha256"
    ):
        raise ValueError(f"publication checklist hash mismatch: {checklist}")
    for raw_board in _sequence(manifest.get("boards"), "publication manifest.boards"):
        board = _mapping(raw_board, "publication manifest.board")
        for field in ("title", "caption", "review"):
            path = _bundle_child(
                root,
                _text(board.get(field), f"publication manifest.board.{field}"),
                f"publication {field}",
            )
            expected_hash = _text(
                board.get(f"{field}_sha256"),
                f"publication manifest.board.{field}_sha256",
            )
            if not path.is_file() or _sha256_text_file(path) != expected_hash:
                raise ValueError(f"publication {field} hash mismatch: {path}")


def _bundle_child(root: Path, relative: str, label: str) -> Path:
    candidate = (root / relative).resolve()
    resolved_root = root.resolve()
    if candidate == resolved_root or not candidate.is_relative_to(resolved_root):
        raise ValueError(f"{label} must stay inside its publication bundle")
    return candidate


def _history_fingerprint(manifest: Mapping[str, Any]) -> str:
    fingerprint = _text(manifest.get("content_fingerprint"), "manifest.content_fingerprint")
    if re.fullmatch(r"[0-9a-f]{64}", fingerprint) is None:
        raise ValueError("manifest.content_fingerprint must be a lowercase SHA-256 digest")
    calculated = _sha256_text(
        json.dumps(
            _fingerprint_payload_from_manifest(manifest),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    if fingerprint != calculated:
        raise ValueError("manifest.content_fingerprint does not match publication content")
    return fingerprint


def _fingerprint_payload_from_manifest(manifest: Mapping[str, Any]) -> dict[str, Any]:
    source = _mapping(manifest.get("source"), "manifest.source")
    return {
        "generator": dict(_mapping(manifest.get("generator"), "manifest.generator")),
        "status": _text(manifest.get("status"), "manifest.status"),
        "period": _text(manifest.get("period"), "manifest.period"),
        "run_date": _text(manifest.get("run_date"), "manifest.run_date"),
        "issue": dict(_mapping(manifest.get("issue"), "manifest.issue")),
        "source": {
            "report_sha256": _text(source.get("report_sha256"), "manifest.report_sha256"),
            "poster_manifest_sha256": _text(
                source.get("poster_manifest_sha256"),
                "manifest.poster_manifest_sha256",
            ),
        },
        "editorial": dict(_mapping(manifest.get("editorial"), "manifest.editorial")),
        "boards": _fingerprint_boards(_sequence(manifest.get("boards"), "manifest.boards")),
        "checklist_sha256": _text(manifest.get("checklist_sha256"), "manifest.checklist_sha256"),
    }


def _manifest_content_projection(manifest: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": manifest.get("schema_version"),
        "content_fingerprint": _history_fingerprint(manifest),
        **_fingerprint_payload_from_manifest(manifest),
        "source": dict(_mapping(manifest.get("source"), "manifest.source")),
    }


def _rotate_current(target: Path, archive_root: Path) -> Path | None:
    if not target.exists():
        return None
    if not target.is_dir():
        raise ValueError(f"current publication target is not a directory: {target}")
    manifest = _read_json_object(target / "MANIFEST.json", "current publication manifest")
    period = _text(manifest.get("period"), "current manifest.period")
    if period != target.name or period not in {"daily", "weekly"}:
        raise ValueError("current publication manifest period is invalid")
    run_date = _iso_date(manifest.get("run_date"), "current manifest.run_date")
    issue = _mapping(manifest.get("issue"), "current manifest.issue")
    stem = _safe_component(_text(issue.get("stem"), "current manifest.issue.stem"))
    year = run_date.year if period == "daily" else run_date.isocalendar().year
    base = archive_root / period / str(year) / stem
    destination = _available_archive_path(base)
    destination.parent.mkdir(parents=True, exist_ok=True)
    target.replace(destination)
    return destination


def _available_archive_path(base: Path) -> Path:
    if not base.exists():
        return base
    revision = 2
    while True:
        candidate = base.with_name(f"{base.name}-r{revision:02d}")
        if not candidate.exists():
            return candidate
        revision += 1


def _append_local_log(path: Path, item: Mapping[str, Any]) -> None:
    existing = path.read_text(encoding="utf-8") if path.is_file() else ""
    line = json.dumps(dict(item), ensure_ascii=False, sort_keys=False) + "\n"
    _write_text(path, existing + line)


def _read_json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read {label}: {path}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} root must be an object")
    return value


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent, text=True
    )
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
        Path(temporary_name).replace(path)
    except Exception:
        Path(temporary_name).unlink(missing_ok=True)
        raise


def _resolve_repository_path(value: str | Path, repository_root: Path, label: str) -> Path:
    candidate = Path(value)
    resolved = (
        candidate.resolve() if candidate.is_absolute() else (repository_root / candidate).resolve()
    )
    if not resolved.is_relative_to(repository_root):
        raise ValueError(f"{label} must stay inside the repository")
    return resolved


def _require_descendant(path: Path, root: Path, label: str) -> None:
    if path == root or not path.is_relative_to(root):
        raise ValueError(f"{label} must be a subdirectory of the repository")


def _relative_path(path: Path, root: Path) -> str:
    resolved = path.resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ValueError(f"path must stay inside root: {path}")
    return resolved.relative_to(root.resolve()).as_posix()


def _safe_component(value: str) -> str:
    if value in {"", ".", ".."} or "/" in value or "\\" in value:
        raise ValueError("publication archive stem is unsafe")
    return value


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return (slug or "repository")[:72].rstrip("-")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_text_file(path: Path) -> str:
    """Hash UTF-8 text after universal-newline normalization.

    Git may check tracked text out as CRLF on Windows and LF on Linux.  A
    publication fingerprint must describe content rather than a workstation's
    line-ending policy, so all text hashes use canonical LF before hashing.
    """

    try:
        value = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ValueError(f"publication text cannot be read as UTF-8: {path}") from exc
    return _sha256_text(value)


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _fingerprint_boards(boards: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Exclude filesystem materialization while fingerprinting publishable content."""

    normalized: list[dict[str, Any]] = []
    for board in boards:
        item = dict(board)
        normalized_images: list[dict[str, Any]] = []
        for image in _sequence(board.get("images"), "board.images"):
            normalized_image = {
                key: value
                for key, value in _mapping(image, "board.image").items()
                if key not in {"materialization", "publication_path"}
            }
            publication_path = _mapping(image, "board.image").get("publication_path")
            if "path" not in normalized_image and publication_path is not None:
                normalized_image["path"] = publication_path
            normalized_images.append(normalized_image)
        item["images"] = normalized_images
        normalized.append(item)
    return normalized


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    return value


def _sequence(value: object, label: str) -> Sequence[object]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be an array")
    return value


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be non-empty text")
    return value.strip()


def _integer(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} must be an integer")
    return value


def _positive_integer(value: object, label: str) -> int:
    parsed = _integer(value, label)
    if parsed < 1:
        raise ValueError(f"{label} must be positive")
    return parsed


def _nonnegative_integer(value: object, label: str) -> int:
    parsed = _integer(value, label)
    if parsed < 0:
        raise ValueError(f"{label} must be non-negative")
    return parsed


def _iso_date(value: object, label: str) -> date:
    text = _text(value, label)
    try:
        parsed = date.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{label} must use YYYY-MM-DD") from exc
    if parsed.isoformat() != text:
        raise ValueError(f"{label} must use YYYY-MM-DD")
    return parsed

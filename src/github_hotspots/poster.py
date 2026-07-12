"""Create original, data-bound Xiaohongshu poster cards with Pillow.

The renderer deliberately has no network code and no dependency on external
visual assets.  It accepts either ranked repository objects or the mappings
already stored in report JSON, then creates one board cover and one portrait
card per repository.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from PIL import Image, ImageDraw, ImageFont, ImageOps

from .models import RankedRepository
from .summarizer import summarize_repository

DEFAULT_POSTER_SIZE = (1200, 1600)
POSTER_RENDERER_NAME = "github-hotspots-pillow"
POSTER_RENDERER_VERSION = "4.0"
POSTER_STYLE_VERSION = "signal-broadsheet-v1"
_BASE_WIDTH = 1080
_BASE_HEIGHT = 1440
_VALID_PERIODS = {"daily", "weekly"}
_VALID_DELTA_SOURCES = {"snapshot", "trending", "estimate"}
_CJK_PROBE_TEXT = "中文开源情报"
_MISSING_GLYPH_SENTINEL = "\U0010ffff"

_PAPER = "#F2ECD9"
_PAPER_LIGHT = "#FFFAF0"
_INK = "#11110F"
_MUTED_INK = "#59554B"
_ORANGE = "#FF5B1F"
_ACID = "#CAFF3D"
_RULE = "#CFC6B3"
_DARK_SURFACE = "#1B1C18"
_DARK_RULE = "#55534B"

# Compatibility aliases for the small reusable drawing helpers retained below.
_WARM_BACKGROUND = _PAPER
_PAPER_ALT = "#E8E3D6"
_BORDER = _RULE
_GROWTH = _ORANGE
_MAX_AVATAR_BYTES = 5 * 1024 * 1024
_ALLOWED_AVATAR_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


@dataclass(frozen=True, slots=True)
class _SignalTheme:
    page: str
    surface: str
    ink: str
    muted: str
    accent: str
    accent_alt: str
    rule: str
    inverse: str
    inverse_text: str
    grid: str


_BOARD_THEMES = {
    "comprehensive": _SignalTheme(
        page=_PAPER,
        surface=_PAPER_LIGHT,
        ink=_INK,
        muted=_MUTED_INK,
        accent=_ORANGE,
        accent_alt=_ACID,
        rule=_RULE,
        inverse=_INK,
        inverse_text=_PAPER_LIGHT,
        grid="#DDD5C2",
    ),
    "ai": _SignalTheme(
        page=_INK,
        surface=_DARK_SURFACE,
        ink=_PAPER_LIGHT,
        muted="#B8B3A7",
        accent=_ACID,
        accent_alt=_ORANGE,
        rule=_DARK_RULE,
        inverse=_PAPER_LIGHT,
        inverse_text=_INK,
        grid="#292A25",
    ),
}

_IDENTITY_COLOURS = (
    ("#D8F1E7", "#126A50"),
    ("#E8E3FA", "#5647A8"),
    ("#F8E5C3", "#8A5B06"),
    ("#DDECF8", "#24658D"),
    ("#F5DDE8", "#9B416B"),
    ("#E5ECD5", "#527129"),
)


@dataclass(frozen=True, slots=True)
class PosterPalette:
    """A small original palette used by the procedural poster themes."""

    background: str
    background_alt: str
    surface: str
    surface_strong: str
    primary: str
    accent: str
    text: str
    muted: str


_PALETTES = (
    PosterPalette(
        background="#081421",
        background_alt="#102C3C",
        surface="#142D3A",
        surface_strong="#1A3A49",
        primary="#52E6C8",
        accent="#FFCA62",
        text="#F4FBFA",
        muted="#A9C2C2",
    ),
    PosterPalette(
        background="#18122B",
        background_alt="#39255D",
        surface="#2C2144",
        surface_strong="#43315F",
        primary="#C8A7FF",
        accent="#FF8F70",
        text="#FFF9F4",
        muted="#C9BBD5",
    ),
    PosterPalette(
        background="#102018",
        background_alt="#244331",
        surface="#1E3829",
        surface_strong="#2A4B38",
        primary="#B7F36B",
        accent="#6ED9FF",
        text="#F6FBEF",
        muted="#B8C9B8",
    ),
    PosterPalette(
        background="#171A20",
        background_alt="#29313D",
        surface="#242A33",
        surface_strong="#343D49",
        primary="#FF6FAE",
        accent="#80E8FF",
        text="#FFF8FC",
        muted="#BCC3CC",
    ),
    PosterPalette(
        background="#1E170D",
        background_alt="#4B3520",
        surface="#342719",
        surface_strong="#4A3823",
        primary="#FFB55E",
        accent="#8FE3C2",
        text="#FFF9EF",
        muted="#D6C4AA",
    ),
)


@dataclass(frozen=True, slots=True)
class PosterRepository:
    """The fact set rendered on one project poster."""

    rank: int
    full_name: str
    html_url: str
    short_description: str
    stars: int
    star_delta: int
    delta_source: str
    forks: int
    language: str
    highlights: tuple[str, str, str]
    audience: str
    capabilities: tuple[str, ...] = ()
    core_value: str = ""
    why_hot: str = ""
    avatar_path: Path | None = None
    license_spdx: str = ""
    core_title: str = ""
    core_summary: str = ""

    @classmethod
    def from_ranked(cls, item: RankedRepository) -> PosterRepository:
        """Build poster data from a core ranking result."""

        summary = summarize_repository(
            item.repository,
            item.star_delta,
            item.delta_source,
        )
        highlights = _three_highlights(
            summary.highlights,
            description=item.repository.description,
            language=item.repository.language,
            stars=item.repository.stars,
            forks=item.repository.forks,
            period="daily",
            star_delta=item.star_delta,
            delta_source=item.delta_source,
        )
        return cls(
            rank=item.rank,
            full_name=item.repository.full_name,
            html_url=item.repository.html_url,
            short_description=summary.one_line,
            stars=item.repository.stars,
            star_delta=item.star_delta,
            delta_source=item.delta_source,
            forks=item.repository.forks,
            language=item.repository.language or "未标注",
            highlights=highlights,
            audience=summary.audience,
            capabilities=highlights,
            core_value=highlights[0],
        )

    @classmethod
    def from_mapping(
        cls,
        value: Mapping[str, Any],
        *,
        fallback_rank: int = 1,
        period: str = "daily",
        avatar_root: str | Path | None = None,
    ) -> PosterRepository:
        """Build poster data from one repository object in report JSON."""

        raw_summary = value.get("summary")
        summary = raw_summary if isinstance(raw_summary, Mapping) else {}
        raw_highlights = summary.get("highlights", ())
        highlights: Sequence[Any]
        if isinstance(raw_highlights, Sequence) and not isinstance(raw_highlights, str):
            highlights = raw_highlights
        else:
            highlights = ()

        raw_capabilities = (
            value.get("poster_capabilities")
            or value.get("capabilities")
            or summary.get("capabilities")
            or highlights
        )
        capability_values: Sequence[Any]
        if isinstance(raw_capabilities, Sequence) and not isinstance(raw_capabilities, str):
            capability_values = raw_capabilities
        else:
            capability_values = ()

        description = _clean_text(value.get("description")) or "暂无仓库简介"
        short_description = (
            _clean_text(value.get("plain_summary"))
            or _clean_text(value.get("poster_summary"))
            or _clean_text(value.get("poster_description"))
            or _clean_text(summary.get("one_line"))
            or description
        )
        language = _clean_text(value.get("language")) or "未标注"
        stars = _as_int(value.get("stars"))
        forks = _as_int(value.get("forks"))
        star_delta = _as_int(value.get("star_delta"))
        delta_source = _normalise_delta_source(value.get("delta_source"))

        poster_capabilities = _capability_list(capability_values or highlights)
        poster_highlights = _three_highlights(
            poster_capabilities,
            description=description,
            language=language,
            stars=stars,
            forks=forks,
            period=period,
            star_delta=star_delta,
            delta_source=delta_source,
        )
        core_title = (
            _clean_text(value.get("core_title"))
            or _clean_text(summary.get("core_title"))
            or _clean_text(value.get("core_value"))
            or _clean_text(summary.get("core_value"))
            or poster_capabilities[0]
        )
        core_summary = (
            _clean_text(value.get("core_summary"))
            or _clean_text(summary.get("core_summary"))
            or short_description
        )
        return cls(
            rank=max(_as_int(value.get("rank"), fallback_rank), 1),
            full_name=_clean_text(value.get("full_name")) or "unknown/repository",
            html_url=_clean_text(value.get("html_url")),
            short_description=short_description,
            stars=stars,
            star_delta=star_delta,
            delta_source=delta_source,
            forks=forks,
            language=language,
            highlights=poster_highlights,
            audience=(
                _clean_text(value.get("audience"))
                or _clean_text(summary.get("audience"))
                or "开发者与开源项目关注者"
            ),
            capabilities=poster_capabilities,
            core_value=core_title,
            why_hot=(_clean_text(value.get("why_hot")) or _clean_text(summary.get("why_hot"))),
            avatar_path=_safe_avatar_path(value.get("avatar_path"), root=avatar_root),
            license_spdx=_license_spdx(value),
            core_title=core_title,
            core_summary=core_summary,
        )


@dataclass(frozen=True, slots=True)
class PosterArtifacts:
    """Paths produced for one board."""

    cover: Path
    projects: tuple[Path, ...]
    project_keys: tuple[tuple[int, str], ...]

    @property
    def all_paths(self) -> tuple[Path, ...]:
        """Return the cover followed by project cards."""

        return (self.cover, *self.projects)


@dataclass(frozen=True, slots=True)
class _ProjectLayout:
    """Fixed base-grid regions for one Signal Broadsheet project poster."""

    masthead: tuple[int, int, int, int]
    identity: tuple[int, int, int, int]
    signal_bar: tuple[int, int, int, int]
    capabilities: tuple[int, int, int, int]
    core: tuple[int, int, int, int]
    audience: tuple[int, int, int, int]
    footer_y: int


class _FontBook:
    """Resolve CJK-capable fonts across Windows, Ubuntu, and macOS."""

    def __init__(self, scale: float) -> None:
        self.scale = scale
        self.regular_path = _resolve_font_path(bold=False)
        if self.regular_path is None:
            raise RuntimeError(
                "No CJK-capable regular font was found. Install Noto Sans CJK or configure "
                "GITHUB_HOTSPOTS_FONT_REGULAR."
            )
        self.bold_path = _resolve_font_path(bold=True) or self.regular_path
        self._cache: dict[tuple[int, bool], ImageFont.FreeTypeFont] = {}
        self._load_and_validate(24, bold=False)
        self._load_and_validate(24, bold=True)

    def get(
        self,
        size: int,
        *,
        bold: bool = False,
    ) -> ImageFont.FreeTypeFont:
        scaled_size = max(10, round(size * self.scale))
        key = (scaled_size, bold)
        if key not in self._cache:
            self._load_and_validate(size, bold=bold)
        return self._cache[key]

    def ensure_cjk_text(self, *values: str) -> None:
        """Fail before rendering when either selected face lacks required Chinese glyphs."""

        characters = sorted(
            {character for value in values for character in value if _is_cjk_character(character)}
        )
        if not characters:
            return
        for bold in (False, True):
            font = self.get(24, bold=bold)
            missing = [
                character for character in characters if not _font_has_glyph(font, character)
            ]
            if missing:
                path = self.bold_path if bold else self.regular_path
                preview = "".join(missing[:12])
                raise RuntimeError(
                    f"CJK font {path} is missing Chinese glyphs required by this poster: {preview}"
                )

    def _load_and_validate(self, size: int, *, bold: bool) -> None:
        scaled_size = max(10, round(size * self.scale))
        key = (scaled_size, bold)
        if key in self._cache:
            return
        path = self.bold_path if bold else self.regular_path
        try:
            font = ImageFont.truetype(str(path), scaled_size)
        except OSError as error:
            raise RuntimeError(f"Unable to load configured CJK font: {path}") from error
        if not _font_supports_cjk(font):
            raise RuntimeError(f"Configured font does not provide required Chinese glyphs: {path}")
        self._cache[key] = font


def format_delta_label(star_delta: int, delta_source: str, period: str) -> str:
    """Return a publication-safe period-growth label."""

    if period not in _VALID_PERIODS:
        raise ValueError("period must be 'daily' or 'weekly'")
    source = _normalise_delta_source(delta_source)
    signed = f"+{star_delta:,}" if star_delta >= 0 else f"{star_delta:,}"
    if source == "snapshot":
        if star_delta < 0:
            return f"快照差值 {signed} Star（待核验）"
        return f"已核验净增 Star {signed}"
    if source == "trending":
        label = "Trending 日周期 Star" if period == "daily" else "Trending 周期 Star"
        return f"{label} {signed}"
    label = "估算日周期 Star" if period == "daily" else "估算周榜 Star"
    return f"{label} {signed}"


def format_cover_selection_label(top_n: int, repository_count: int) -> str:
    """Return the explicit board size shown on a cover."""

    if top_n < 0 or repository_count < 0:
        raise ValueError("top_n and repository_count must not be negative")
    return f"Top {top_n} · 本期收录 {repository_count} 个项目"


def format_cover_window_label(window_start: date, window_end: date) -> str:
    """Return an explicit start/end statistics window for a cover."""

    if window_start > window_end:
        raise ValueError("window_start must not be after window_end")
    return f"统计窗口 {window_start:%Y.%m.%d} — {window_end:%Y.%m.%d}"


def format_cover_growth_status(repositories: Sequence[PosterRepository]) -> str:
    """Describe verified snapshot coverage without presenting estimates as exact growth."""

    verified = sum(
        item.delta_source == "snapshot" and item.star_delta >= 0 for item in repositories
    )
    pending = sum(item.delta_source == "snapshot" and item.star_delta < 0 for item in repositories)
    if verified:
        suffix = f"；另 {pending} 项待核验" if pending else ""
        return f"已核验净增 Star · {verified} 项使用历史快照{suffix}"
    if pending:
        return f"快照差值待核验 · {pending} 项暂不标记精确新增"
    return "净增基线积累中 · 当前不标记精确新增"


def render_board_posters(
    *,
    board_key: str,
    board_label: str,
    period: str,
    run_date: date | str,
    repositories: Sequence[PosterRepository | RankedRepository | Mapping[str, Any]],
    output_dir: str | Path,
    size: tuple[int, int] = DEFAULT_POSTER_SIZE,
    top_n: int | None = None,
    window_start: date | str | None = None,
    avatar_root: str | Path | None = None,
    issue_code: str | None = None,
) -> PosterArtifacts:
    """Render one cover plus one portrait PNG for every ranked repository."""

    if period not in _VALID_PERIODS:
        raise ValueError("period must be 'daily' or 'weekly'")
    _validate_size(size)
    parsed_date = _coerce_date(run_date)
    rendered_issue_code = _resolved_issue_code(period, parsed_date, issue_code)
    normalised = tuple(
        _coerce_repository(
            item,
            fallback_rank=index,
            period=period,
            avatar_root=avatar_root,
        )
        for index, item in enumerate(repositories, start=1)
    )
    normalised = tuple(sorted(normalised, key=lambda item: (item.rank, item.full_name.casefold())))
    selected_top_n = len(normalised) if top_n is None else top_n
    if (
        isinstance(selected_top_n, bool)
        or not isinstance(selected_top_n, int)
        or selected_top_n < 0
    ):
        raise ValueError("top_n must be a non-negative integer")
    parsed_window_start = (
        _coerce_date(window_start)
        if window_start is not None
        else parsed_date - timedelta(days=1 if period == "daily" else 7)
    )
    if parsed_window_start > parsed_date:
        raise ValueError("window_start must not be after run_date")

    fonts = _FontBook(size[0] / _BASE_WIDTH)
    fonts.ensure_cjk_text(
        board_label,
        format_cover_selection_label(selected_top_n, len(normalised)),
        format_cover_window_label(parsed_window_start, parsed_date),
        format_cover_growth_status(normalised),
        "开源热点编辑部 GitHub 热门项目 综合主榜 AI 专题榜 本期增长 "
        "每张图讲清一个仓库 先看它替谁解决什么 再看为什么上榜 "
        "这个项目替你完成 核心亮点 适合 总 Star 主要语言 许可证未标注 "
        "本期暂无入选项目 继续向左滑",
        *(repository.short_description for repository in normalised),
        *(repository.language for repository in normalised),
        *(repository.audience for repository in normalised),
        *(highlight for repository in normalised for highlight in repository.highlights),
        *(capability for repository in normalised for capability in repository.capabilities),
        *(repository.core_value for repository in normalised),
        *(repository.core_title for repository in normalised),
        *(repository.core_summary for repository in normalised),
        *(repository.license_spdx for repository in normalised),
        *(repository.why_hot for repository in normalised),
        *(
            format_delta_label(repository.star_delta, repository.delta_source, period)
            for repository in normalised
        ),
    )

    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    board_slug = _slug_component(board_key) or "board"
    stem = _report_stem(period, parsed_date)

    cover_path = target_dir / f"{stem}.{board_slug}.cover.png"
    cover = _render_cover(
        board_key=board_key,
        board_label=board_label,
        period=period,
        run_date=parsed_date,
        repositories=normalised,
        size=size,
        fonts=fonts,
        top_n=selected_top_n,
        window_start=parsed_window_start,
        issue_code=rendered_issue_code,
    )
    _save_png(cover, cover_path)

    project_paths: list[Path] = []
    for repository in normalised:
        repository_slug = _repository_slug(repository.full_name)
        project_path = (
            target_dir / f"{stem}.{board_slug}.{repository.rank:02d}.{repository_slug}.png"
        )
        poster = _render_project_card(
            board_key=board_key,
            board_label=board_label,
            period=period,
            run_date=parsed_date,
            repository=repository,
            size=size,
            fonts=fonts,
            issue_code=rendered_issue_code,
        )
        _save_png(poster, project_path)
        project_paths.append(project_path)

    return PosterArtifacts(
        cover=cover_path,
        projects=tuple(project_paths),
        project_keys=tuple((repository.rank, repository.full_name) for repository in normalised),
    )


def render_report_posters(
    report_path: str | Path,
    *,
    output_dir: str | Path | None = None,
    board_keys: Sequence[str] | None = None,
    size: tuple[int, int] = DEFAULT_POSTER_SIZE,
) -> dict[str, PosterArtifacts]:
    """Render poster sets from an existing daily or weekly report JSON file."""

    path = Path(report_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("report JSON root must be an object")
    period = str(payload.get("period", ""))
    if period not in _VALID_PERIODS:
        raise ValueError("report JSON period must be 'daily' or 'weekly'")
    run_date = _coerce_date(str(payload.get("run_date", "")))
    raw_window_start = payload.get("window_start")
    window_start = _coerce_date(str(raw_window_start)) if raw_window_start else None
    raw_publication = payload.get("publication")
    publication = raw_publication if isinstance(raw_publication, Mapping) else {}
    issue_code = _clean_text(publication.get("issue_code")) or None

    raw_boards = payload.get("boards")
    boards = raw_boards if isinstance(raw_boards, Mapping) else {}
    if not boards:
        boards = {
            "comprehensive": {
                "label": "综合主榜",
                "repositories": payload.get("repositories", ()),
            }
        }
    selected_keys = tuple(board_keys) if board_keys else tuple(str(key) for key in boards)
    target_dir = (
        Path(output_dir)
        if output_dir is not None
        else path.parent / "posters" / _report_stem(period, run_date)
    )

    result: dict[str, PosterArtifacts] = {}
    for key in selected_keys:
        raw_board = boards.get(key)
        if not isinstance(raw_board, Mapping):
            raise ValueError(f"report JSON does not contain board: {key}")
        raw_repositories = raw_board.get("repositories", ())
        if not isinstance(raw_repositories, Sequence) or isinstance(raw_repositories, str):
            raise ValueError(f"board {key} repositories must be an array")
        mappings = [item for item in raw_repositories if isinstance(item, Mapping)]
        raw_top_n = raw_board.get("top_n")
        top_n = len(mappings) if raw_top_n is None else _as_int(raw_top_n, -1)
        result[key] = render_board_posters(
            board_key=key,
            board_label=_clean_text(raw_board.get("label")) or key,
            period=period,
            run_date=run_date,
            repositories=mappings,
            output_dir=target_dir,
            size=size,
            top_n=top_n,
            window_start=window_start,
            avatar_root=path.parent,
            issue_code=issue_code,
        )
    return result


def _render_project_card(
    *,
    board_key: str,
    board_label: str,
    period: str,
    run_date: date,
    repository: PosterRepository,
    size: tuple[int, int],
    fonts: _FontBook,
    issue_code: str,
) -> Image.Image:
    scale = size[0] / _BASE_WIDTH
    theme = _signal_theme(board_key)
    layout = _project_layout(scale, size=size)
    image = Image.new("RGB", size, theme.page)
    draw = ImageDraw.Draw(image)

    def s(value: int) -> int:
        return round(value * scale)

    _draw_editorial_grid(draw, size=size, scale=scale, theme=theme)
    _draw_board_motif(
        draw,
        size=size,
        scale=scale,
        theme=theme,
        board_key=board_key,
        seed=_stable_seed(repository.full_name),
    )

    mark_rect = (s(48), s(36), s(104), s(92))
    draw.rectangle(mark_rect, fill=theme.inverse)
    draw.text(
        ((mark_rect[0] + mark_rect[2]) // 2, (mark_rect[1] + mark_rect[3]) // 2),
        "GH",
        font=fonts.get(19, bold=True),
        fill=theme.inverse_text,
        anchor="mm",
    )
    draw.text(
        (s(122), s(39)),
        "HOTSPOTS / 开源热点编辑部",
        font=fonts.get(19, bold=True),
        fill=theme.ink,
    )
    cadence_mark = _cadence_mark(period)
    draw.text(
        (s(122), s(76)),
        (
            f"{_board_code(board_key)} · {board_label} · {cadence_mark} · "
            f"{run_date:%Y.%m.%d} · ISSUE {issue_code}"
        ),
        font=fonts.get(15, bold=True),
        fill=theme.muted,
    )
    _draw_rank_tape(
        draw,
        (s(862), s(32), s(1032), s(112)),
        text=f"#{repository.rank:02d}",
        fill=theme.accent,
        text_fill=_INK,
        fonts=fonts,
        scale=scale,
    )
    draw.line(
        (layout.masthead[0], layout.masthead[3], layout.masthead[2], layout.masthead[3]),
        fill=theme.ink,
        width=max(2, s(3)),
    )

    owner, separator, name = repository.full_name.partition("/")
    project_name = name if separator else owner
    owner_name = owner if separator else "OPEN SOURCE"
    identity_rect = (s(48), s(188), s(180), s(320))
    draw.rectangle(
        (s(56), s(196), s(188), s(328)),
        fill=theme.accent,
    )
    _draw_avatar_or_identity(
        image,
        draw,
        identity_rect,
        repository.full_name,
        avatar_path=repository.avatar_path,
        fonts=fonts,
        scale=scale,
    )
    draw.text(
        (s(210), s(183)),
        f"OWNER / {owner_name}",
        font=fonts.get(17, bold=True),
        fill=theme.accent,
    )
    name_bottom = _draw_fitted_text(
        draw,
        (s(210), s(214)),
        project_name,
        fonts=fonts,
        fill=theme.ink,
        max_width=s(680),
        max_lines=2,
        max_size=50,
        min_size=34,
        line_gap=s(3),
    )
    license_text = repository.license_spdx if repository.license_spdx else "许可证未标注"
    draw.text(
        (s(210), min(name_bottom + s(10), s(312))),
        f"{repository.language}  /  {license_text}",
        font=fonts.get(17, bold=True),
        fill=theme.muted,
    )
    draw.rectangle(
        (s(48), s(346), s(58), s(422)),
        fill=theme.accent,
    )
    _draw_fitted_text(
        draw,
        (s(76), s(338)),
        repository.short_description,
        fonts=fonts,
        fill=theme.ink,
        max_width=s(928),
        max_lines=3,
        max_size=36,
        min_size=28,
        line_gap=s(6),
    )

    _draw_signal_bar(
        draw,
        layout.signal_bar,
        repository=repository,
        period=period,
        fonts=fonts,
        theme=theme,
        scale=scale,
    )

    draw.text(
        (layout.capabilities[0], layout.capabilities[1]),
        "这个项目替你完成",
        font=fonts.get(26, bold=True),
        fill=theme.ink,
    )
    _draw_right_text(
        draw,
        (layout.capabilities[2], layout.capabilities[1] + s(4)),
        "SIGNAL RAIL / 01—05",
        font=fonts.get(15, bold=True),
        fill=theme.accent,
    )
    draw.line(
        (
            layout.capabilities[0],
            layout.capabilities[1] + s(42),
            layout.capabilities[2],
            layout.capabilities[1] + s(42),
        ),
        fill=theme.rule,
        width=max(1, s(2)),
    )
    capabilities = _capability_list(repository.capabilities or repository.highlights)
    _draw_signal_rail(
        draw,
        (
            layout.capabilities[0],
            layout.capabilities[1] + s(62),
            layout.capabilities[2],
            layout.capabilities[3],
        ),
        capabilities=capabilities,
        fonts=fonts,
        theme=theme,
        scale=scale,
    )

    draw.rectangle(
        (
            layout.core[0] + s(8),
            layout.core[1] + s(8),
            layout.core[2] + s(8),
            layout.core[3] + s(8),
        ),
        fill=theme.accent_alt,
    )
    draw.rectangle(layout.core, fill=theme.inverse)
    draw.text(
        (layout.core[0] + s(28), layout.core[1] + s(22)),
        "CORE SIGNAL / 核心亮点",
        font=fonts.get(17, bold=True),
        fill=theme.accent_alt,
    )
    core_title = repository.core_title or repository.core_value or capabilities[0]
    core_title_bottom = _draw_fitted_text(
        draw,
        (layout.core[0] + s(28), layout.core[1] + s(52)),
        core_title,
        fonts=fonts,
        fill=theme.inverse_text,
        max_width=layout.core[2] - layout.core[0] - s(56),
        max_lines=2,
        max_size=31,
        min_size=25,
        line_gap=s(5),
    )
    core_summary = repository.core_summary or repository.short_description
    _draw_fitted_text(
        draw,
        (layout.core[0] + s(28), core_title_bottom + s(10)),
        core_summary,
        fonts=fonts,
        fill=theme.inverse_text,
        max_width=layout.core[2] - layout.core[0] - s(56),
        max_lines=3,
        max_size=20,
        min_size=17,
        line_gap=s(5),
        bold=False,
    )

    draw.text(
        (layout.audience[0], layout.audience[1]),
        "适合 /",
        font=fonts.get(20, bold=True),
        fill=theme.accent,
    )
    _draw_fitted_text(
        draw,
        (layout.audience[0] + s(108), layout.audience[1] - s(2)),
        repository.audience,
        fonts=fonts,
        fill=theme.ink,
        max_width=layout.audience[2] - layout.audience[0] - s(108),
        max_lines=2,
        max_size=22,
        min_size=19,
        line_gap=s(4),
    )

    short_link = _short_repository_link(repository)
    draw.line(
        (s(48), layout.footer_y - s(15), s(1032), layout.footer_y - s(15)),
        fill=theme.ink,
        width=max(1, s(2)),
    )
    draw.text(
        (s(48), layout.footer_y),
        "GITHUB HOTSPOTS",
        font=fonts.get(15, bold=True),
        fill=theme.muted,
    )
    link_font = fonts.get(16, bold=True)
    draw.text(
        (s(292), layout.footer_y),
        _ellipsize(draw, f"SEARCH / {short_link}", link_font, s(490)),
        font=link_font,
        fill=theme.accent,
    )
    _draw_right_text(
        draw,
        (s(1032), layout.footer_y),
        run_date.strftime("%Y.%m.%d"),
        font=fonts.get(15, bold=True),
        fill=theme.muted,
        max_width=s(220),
    )
    return image


def _render_cover(
    *,
    board_key: str,
    board_label: str,
    period: str,
    run_date: date,
    repositories: Sequence[PosterRepository],
    size: tuple[int, int],
    fonts: _FontBook,
    top_n: int,
    window_start: date,
    issue_code: str,
) -> Image.Image:
    scale = size[0] / _BASE_WIDTH
    theme = _signal_theme(board_key)
    image = Image.new("RGB", size, theme.page)
    draw = ImageDraw.Draw(image)

    def s(value: int) -> int:
        return round(value * scale)

    _draw_editorial_grid(draw, size=size, scale=scale, theme=theme)
    _draw_board_motif(
        draw,
        size=size,
        scale=scale,
        theme=theme,
        board_key=board_key,
        seed=_stable_seed(f"{board_key}:{period}:{run_date.isoformat()}"),
    )

    mark_rect = (s(48), s(36), s(104), s(92))
    draw.rectangle(mark_rect, fill=theme.inverse)
    draw.text(
        ((mark_rect[0] + mark_rect[2]) // 2, (mark_rect[1] + mark_rect[3]) // 2),
        "GH",
        font=fonts.get(19, bold=True),
        fill=theme.inverse_text,
        anchor="mm",
    )
    draw.text(
        (s(122), s(39)),
        "HOTSPOTS / 开源热点编辑部",
        font=fonts.get(19, bold=True),
        fill=theme.ink,
    )
    _draw_right_text(
        draw,
        (s(1032), s(48)),
        f"{run_date:%Y.%m.%d} / ISSUE {issue_code}",
        font=fonts.get(16, bold=True),
        fill=theme.muted,
    )
    draw.line((s(48), s(126), s(1032), s(126)), fill=theme.ink, width=max(2, s(3)))

    cadence_mark = _cadence_mark(period)
    draw.text(
        (s(48), s(156)),
        cadence_mark,
        font=fonts.get(112, bold=True),
        fill=_cadence_colour(period),
    )
    draw.text(
        (s(356), s(174)),
        f"{_board_code(board_key)} / {board_label}",
        font=fonts.get(24, bold=True),
        fill=theme.accent,
    )
    draw.text(
        (s(356), s(220)),
        "DAILY SIGNAL" if period == "daily" else "WEEKLY SIGNAL",
        font=fonts.get(17, bold=True),
        fill=theme.muted,
    )
    _draw_rank_tape(
        draw,
        (s(838), s(164), s(1032), s(236)),
        text=f"TOP {top_n}",
        fill=theme.inverse,
        text_fill=theme.inverse_text,
        fonts=fonts,
        scale=scale,
    )

    timing = "今天" if period == "daily" else "本周"
    _draw_fitted_text(
        draw,
        (s(48), s(310)),
        f"{timing} {len(repositories)} 个",
        fonts=fonts,
        fill=theme.ink,
        max_width=s(984),
        max_lines=1,
        max_size=82,
        min_size=68,
        line_gap=0,
    )
    _draw_fitted_text(
        draw,
        (s(48), s(402)),
        "GitHub 热门项目",
        fonts=fonts,
        fill=theme.ink,
        max_width=s(984),
        max_lines=1,
        max_size=68,
        min_size=58,
        line_gap=0,
    )
    draw.rectangle((s(48), s(486), s(420), s(496)), fill=theme.accent)
    draw.text(
        (s(48), s(520)),
        "先看它替谁解决什么，再看为什么上榜。",
        font=fonts.get(25, bold=True),
        fill=theme.muted,
    )
    _draw_right_text(
        draw,
        (s(1032), s(525)),
        format_cover_window_label(window_start, run_date),
        font=fonts.get(16, bold=True),
        fill=theme.muted,
        max_width=s(440),
    )

    top_items = repositories[:3]
    if top_items:
        for index, repository in enumerate(top_items):
            top = 594 + index * 154
            draw.line(
                (s(48), s(top), s(1032), s(top)),
                fill=theme.rule,
                width=max(1, s(2)),
            )
            node_x = s(72)
            node_y = s(top + 70)
            if index:
                draw.line(
                    (node_x, s(top - 84), node_x, node_y),
                    fill=theme.accent,
                    width=max(2, s(4)),
                )
            node_size = s(36)
            draw.rectangle(
                (
                    node_x - node_size // 2,
                    node_y - node_size // 2,
                    node_x + node_size // 2,
                    node_y + node_size // 2,
                ),
                fill=theme.accent,
            )
            draw.text(
                (node_x, node_y),
                f"{repository.rank:02d}",
                font=fonts.get(14, bold=True),
                fill=_INK,
                anchor="mm",
            )
            identity_rect = (s(112), s(top + 24), s(202), s(top + 114))
            draw.rectangle(
                (s(118), s(top + 30), s(208), s(top + 120)),
                fill=theme.accent_alt,
            )
            _draw_avatar_or_identity(
                image,
                draw,
                identity_rect,
                repository.full_name,
                avatar_path=repository.avatar_path,
                fonts=fonts,
                scale=scale,
            )
            _, _, project_name = repository.full_name.partition("/")
            display_name = project_name or repository.full_name
            _draw_fitted_text(
                draw,
                (s(236), s(top + 17)),
                display_name,
                fonts=fonts,
                fill=theme.ink,
                max_width=s(770),
                max_lines=1,
                max_size=38,
                min_size=29,
                line_gap=0,
                allow_truncation=True,
            )
            _draw_wrapped_text(
                draw,
                (s(236), s(top + 68)),
                repository.short_description,
                font=fonts.get(22, bold=True),
                fill=theme.muted,
                max_width=s(770),
                max_lines=2,
                line_gap=s(5),
            )
        draw.line(
            (s(48), s(594 + len(top_items) * 154), s(1032), s(594 + len(top_items) * 154)),
            fill=theme.rule,
            width=max(1, s(2)),
        )
    else:
        draw.text(
            (s(48), s(690)),
            "本期暂无入选项目",
            font=fonts.get(36, bold=True),
            fill=theme.muted,
        )

    remaining = max(0, len(repositories) - len(top_items))
    if remaining:
        draw.rectangle((s(760), s(1068), s(1032), s(1120)), fill=theme.inverse)
        draw.text(
            (s(896), s(1094)),
            f"+{remaining} 项继续向左滑",
            font=fonts.get(18, bold=True),
            fill=theme.inverse_text,
            anchor="mm",
        )

    growth_rect = (s(48), s(1160), s(1032), s(1304))
    draw.rectangle(
        (
            growth_rect[0] + s(8),
            growth_rect[1] + s(8),
            growth_rect[2] + s(8),
            growth_rect[3] + s(8),
        ),
        fill=theme.accent_alt,
    )
    draw.rectangle(growth_rect, fill=theme.accent)
    draw.text(
        (s(76), s(1182)),
        "SIGNAL CHECK / 本期增长",
        font=fonts.get(17, bold=True),
        fill=_INK,
    )
    _draw_fitted_text(
        draw,
        (s(76), s(1224)),
        _cover_growth_summary(repositories, period),
        fonts=fonts,
        fill=_INK,
        max_width=s(900),
        max_lines=2,
        max_size=25,
        min_size=21,
        line_gap=s(4),
    )
    draw.line((s(48), s(1368), s(1032), s(1368)), fill=theme.ink, width=max(1, s(2)))
    draw.text(
        (s(48), s(1390)),
        "GITHUB HOTSPOTS / 每张图讲清一个仓库",
        font=fonts.get(16, bold=True),
        fill=theme.muted,
    )
    _draw_right_text(
        draw,
        (s(1032), s(1390)),
        f"{cadence_mark} / {_board_code(board_key)} / SWIPE →",
        font=fonts.get(16, bold=True),
        fill=theme.accent,
    )
    return image


def _signal_theme(board_key: str) -> _SignalTheme:
    """Return the board-specific Signal Broadsheet palette."""

    return _BOARD_THEMES.get(board_key.casefold(), _BOARD_THEMES["comprehensive"])


def _issue_number(period: str, run_date: date) -> int:
    """Return the public issue number anchored to the 2026-07-12 launch."""

    first_issue = date(2026, 7, 12)
    if period == "daily":
        return max(0, (run_date - first_issue).days + 1)
    first_week = first_issue - timedelta(days=first_issue.weekday())
    run_week = run_date - timedelta(days=run_date.weekday())
    return max(0, (run_week - first_week).days // 7 + 1)


def _issue_code(period: str, run_date: date) -> str:
    """Return D001/W001 identity or PREVIEW for pre-launch material."""

    number = _issue_number(period, run_date)
    if number < 1:
        return "PREVIEW"
    prefix = "D" if period == "daily" else "W"
    return f"{prefix}{number:03d}"


def _resolved_issue_code(period: str, run_date: date, issue_code: str | None) -> str:
    """Prefer the report/config issue identity and validate direct-render overrides."""

    if issue_code is None:
        return _issue_code(period, run_date)
    candidate = _clean_text(issue_code)
    prefix = "D" if period == "daily" else "W"
    if not re.fullmatch(rf"(?:{prefix}\d{{3,}}|{prefix}-PREVIEW|PREVIEW)", candidate):
        raise ValueError(f"issue_code must match the {period} publication series")
    return candidate


def _cadence_mark(period: str) -> str:
    """Return the compact cadence label used as a visual navigation cue."""

    return "24H" if period == "daily" else "7D"


def _cadence_colour(period: str) -> str:
    """Use a second non-board cue so daily and weekly covers differ at thumbnail size."""

    return _ORANGE if period == "daily" else _ACID


def _board_code(board_key: str) -> str:
    """Return a short board code that remains readable without colour."""

    return "AI" if board_key.casefold() == "ai" else "ALL"


def _draw_editorial_grid(
    draw: ImageDraw.ImageDraw,
    *,
    size: tuple[int, int],
    scale: float,
    theme: _SignalTheme,
) -> None:
    """Draw a restrained print grid and crop marks behind the content."""

    step = max(28, round(48 * scale))
    for x in range(0, size[0] + 1, step):
        draw.line((x, 0, x, size[1]), fill=theme.grid, width=max(1, round(scale)))
    for y in range(0, size[1] + 1, step):
        draw.line((0, y, size[0], y), fill=theme.grid, width=max(1, round(scale)))

    inset = round(24 * scale)
    length = round(22 * scale)
    width = max(1, round(2 * scale))
    for x, x_direction in ((inset, 1), (size[0] - inset, -1)):
        for y, y_direction in ((inset, 1), (size[1] - inset, -1)):
            draw.line((x, y, x + length * x_direction, y), fill=theme.muted, width=width)
            draw.line((x, y, x, y + length * y_direction), fill=theme.muted, width=width)


def _draw_board_motif(
    draw: ImageDraw.ImageDraw,
    *,
    size: tuple[int, int],
    scale: float,
    theme: _SignalTheme,
    board_key: str,
    seed: int,
) -> None:
    """Add a deterministic heat-grid or radar fragment as the board signature."""

    def s(value: int) -> int:
        return round(value * scale)

    if board_key.casefold() == "ai":
        center_x = size[0] - s(88)
        center_y = s(182)
        for radius in (48, 92, 136, 180):
            draw.arc(
                (
                    center_x - s(radius),
                    center_y - s(radius),
                    center_x + s(radius),
                    center_y + s(radius),
                ),
                start=28,
                end=318,
                fill=theme.grid,
                width=max(1, s(2)),
            )
        angle_offset = seed % 70
        draw.line(
            (
                center_x,
                center_y,
                center_x - s(138 - angle_offset // 3),
                center_y + s(112 + angle_offset // 4),
            ),
            fill=theme.accent,
            width=max(2, s(4)),
        )
        draw.rectangle(
            (center_x - s(80), center_y + s(30), center_x - s(66), center_y + s(44)),
            fill=theme.accent_alt,
        )
        return

    cell = s(18)
    gap = s(7)
    origin_x = size[0] - s(272)
    origin_y = s(148)
    for row in range(5):
        for column in range(8):
            active = (seed >> ((row * 8 + column) % 32)) & 1
            fill = theme.accent if active else theme.grid
            x1 = origin_x + column * (cell + gap)
            y1 = origin_y + row * (cell + gap)
            draw.rectangle((x1, y1, x1 + cell, y1 + cell), fill=fill)


def _draw_rank_tape(
    draw: ImageDraw.ImageDraw,
    rect: tuple[int, int, int, int],
    *,
    text: str,
    fill: str,
    text_fill: str,
    fonts: _FontBook,
    scale: float,
) -> None:
    """Draw a hard-edged label with a ticket notch instead of a circular badge."""

    x1, y1, x2, y2 = rect
    notch = max(8, round(12 * scale))
    middle = (y1 + y2) // 2
    draw.polygon(
        ((x1, y1), (x2, y1), (x2, y2), (x1, y2), (x1 + notch, middle)),
        fill=fill,
    )
    draw.text(
        ((x1 + x2 + notch) // 2, middle),
        text,
        font=fonts.get(26, bold=True),
        fill=text_fill,
        anchor="mm",
    )


def _draw_signal_bar(
    draw: ImageDraw.ImageDraw,
    rect: tuple[int, int, int, int],
    *,
    repository: PosterRepository,
    period: str,
    fonts: _FontBook,
    theme: _SignalTheme,
    scale: float,
) -> None:
    """Render growth and repository facts as one compact editorial band."""

    def s(value: int) -> int:
        return round(value * scale)

    x1, y1, x2, y2 = rect
    draw.rectangle(rect, fill=theme.inverse)
    growth_width = min(s(310), round((x2 - x1) * 0.34))
    growth_right = x1 + growth_width
    draw.rectangle((x1, y1, growth_right, y2), fill=theme.accent)
    growth_label, growth_value = _growth_metric(repository, period)
    draw.text(
        (x1 + s(18), y1 + s(16)),
        growth_label.upper(),
        font=fonts.get(15, bold=True),
        fill=_INK,
    )
    draw.text(
        (x1 + s(18), y1 + s(48)),
        growth_value,
        font=fonts.get(32, bold=True),
        fill=_INK,
    )

    metrics = (
        ("TOTAL STAR", f"{repository.stars:,}"),
        ("FORK", f"{repository.forks:,}"),
        ("LANG", repository.language),
    )
    metric_width = (x2 - growth_right) / len(metrics)
    for index, (label, value) in enumerate(metrics):
        left = round(growth_right + index * metric_width)
        right = (
            x2 if index == len(metrics) - 1 else round(growth_right + (index + 1) * metric_width)
        )
        draw.line((left, y1, left, y2), fill=theme.page, width=max(1, s(2)))
        draw.text(
            (left + s(16), y1 + s(17)),
            label,
            font=fonts.get(14, bold=True),
            fill=theme.page,
        )
        value_font = fonts.get(24, bold=True)
        draw.text(
            (left + s(16), y1 + s(54)),
            _ellipsize(draw, value, value_font, right - left - s(30)),
            font=value_font,
            fill=theme.inverse_text,
        )


def _draw_signal_rail(
    draw: ImageDraw.ImageDraw,
    rect: tuple[int, int, int, int],
    *,
    capabilities: Sequence[str],
    fonts: _FontBook,
    theme: _SignalTheme,
    scale: float,
) -> None:
    """Use a Git-like signal rail to order up to five plain-language capabilities."""

    def s(value: int) -> int:
        return round(value * scale)

    visible = tuple(capabilities[:5])
    if not visible:
        return
    x1, y1, x2, y2 = rect
    rail_x = x1 + s(34)
    text_x = x1 + s(92)
    slot_height = max(s(70), (y2 - y1) // len(visible))
    centers = [y1 + index * slot_height + s(25) for index in range(len(visible))]
    if len(centers) > 1:
        draw.line(
            (rail_x, centers[0], rail_x, centers[-1]),
            fill=theme.accent,
            width=max(2, s(4)),
        )
    for index, (capability, center_y) in enumerate(zip(visible, centers, strict=True), start=1):
        node = s(30)
        half = node // 2
        draw.polygon(
            (
                (rail_x, center_y - half),
                (rail_x + half, center_y),
                (rail_x, center_y + half),
                (rail_x - half, center_y),
            ),
            fill=theme.accent,
        )
        draw.text(
            (rail_x, center_y),
            f"{index:02d}",
            font=fonts.get(12, bold=True),
            fill=_INK,
            anchor="mm",
        )
        text_top = y1 + (index - 1) * slot_height
        _draw_fitted_text(
            draw,
            (text_x, text_top),
            capability,
            fonts=fonts,
            fill=theme.ink,
            max_width=x2 - text_x,
            max_lines=2,
            max_size=27,
            min_size=22,
            line_gap=s(4),
        )
        if index < len(visible):
            rule_y = y1 + index * slot_height - s(9)
            draw.line((text_x, rule_y, x2, rule_y), fill=theme.rule, width=max(1, s(1)))


def _project_layout(scale: float, *, size: tuple[int, int] = DEFAULT_POSTER_SIZE) -> _ProjectLayout:
    """Scale the fixed Signal Broadsheet grid to a supported portrait size."""

    def rect(values: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
        return tuple(round(value * scale) for value in values)  # type: ignore[return-value]

    return _ProjectLayout(
        masthead=rect((48, 36, 1032, 126)),
        identity=rect((48, 164, 1032, 432)),
        signal_bar=rect((48, 452, 1032, 568)),
        capabilities=rect((48, 604, 1032, 1060)),
        core=rect((48, 1084, 1032, 1288)),
        audience=rect((48, 1310, 1032, 1368)),
        footer_y=round(1394 * scale),
    )


def _shadow_panel(
    draw: ImageDraw.ImageDraw,
    rect: tuple[int, int, int, int],
    *,
    radius: int,
    offset: int = 5,
) -> None:
    """Draw a restrained warm-grey shadow behind a paper card."""

    x1, y1, x2, y2 = rect
    draw.rounded_rectangle(
        (x1, y1 + offset, x2, y2 + offset),
        radius=radius,
        fill="#D7D5CE",
    )


def _identity_token(full_name: str) -> str:
    """Create a short deterministic repository monogram without external assets."""

    _, separator, repository_name = _clean_text(full_name).partition("/")
    source = repository_name if separator else _clean_text(full_name)
    parts = re.findall(r"[A-Za-z]+|[0-9]+|[\u3400-\u9fff]+", source)
    if not parts:
        return "<>"
    if len(parts) >= 2:
        left = parts[0][0]
        right = parts[1][0]
        return f"{left}{right}".upper()
    token = parts[0]
    if any(character.isdigit() for character in token):
        letters = "".join(character for character in token if character.isalpha())
        digits = "".join(character for character in token if character.isdigit())
        if letters and digits:
            return f"{letters[0]}{digits[0]}".upper()
    return token[:2].upper()


def _identity_colours(full_name: str) -> tuple[str, str]:
    """Return a stable colour pair that is independent of board membership."""

    return _IDENTITY_COLOURS[_stable_seed(full_name.casefold()) % len(_IDENTITY_COLOURS)]


def _draw_identity_block(
    draw: ImageDraw.ImageDraw,
    rect: tuple[int, int, int, int],
    full_name: str,
    *,
    fonts: _FontBook,
    scale: float,
    compact: bool = False,
) -> None:
    """Draw an original hard-edged signal tile; never imply an official logo."""

    background, foreground = _identity_colours(full_name)
    x1, y1, x2, y2 = rect
    width = x2 - x1
    draw.rectangle(rect, fill=background, outline=_INK, width=max(1, round(2 * scale)))
    seed = _stable_seed(full_name)
    inset = max(8, width // 9)
    rail_x = x1 + inset + seed % max(1, width // 4)
    draw.line(
        (rail_x, y1 + inset, rail_x, y2 - inset),
        fill=foreground,
        width=max(2, round((3 if compact else 4) * scale)),
    )
    node = max(5, round((7 if compact else 9) * scale))
    for offset in (0, width // 4, width // 2):
        center_y = min(y2 - inset, y1 + inset + offset)
        draw.rectangle(
            (rail_x - node, center_y - node, rail_x + node, center_y + node),
            fill=foreground,
        )
    draw.line(
        (
            rail_x,
            y1 + width // 2,
            x2 - inset,
            y1 + width // 3,
        ),
        fill=foreground,
        width=max(2, round((2 if compact else 3) * scale)),
    )
    token = _identity_token(full_name)
    font = fonts.get(30 if compact else 39, bold=True)
    draw.rectangle(
        (
            x1 + width // 3,
            y1 + width // 2,
            x2 - width // 10,
            y2 - width // 10,
        ),
        fill=background,
    )
    draw.text(
        (x1 + width * 2 // 3, y1 + width * 2 // 3),
        token,
        font=font,
        fill=foreground,
        anchor="mm",
    )


def _load_avatar_thumbnail(
    path: Path,
    size: tuple[int, int],
    *,
    radius: int,
) -> Image.Image:
    """Load, centre-crop and round one already validated local avatar."""

    if path.stat().st_size > _MAX_AVATAR_BYTES:
        raise ValueError("avatar file exceeds the 5 MB safety limit")
    try:
        with Image.open(path) as source:
            source.load()
            if source.width < 1 or source.height < 1:
                raise ValueError("avatar image has invalid dimensions")
            fitted = ImageOps.fit(
                source.convert("RGBA"),
                size,
                method=Image.Resampling.LANCZOS,
                centering=(0.5, 0.5),
            )
    except (OSError, Image.DecompressionBombError) as error:
        raise ValueError(f"unable to load cached avatar: {path.name}") from error

    mask = Image.new("L", size, 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), radius=radius, fill=255)
    fitted.putalpha(mask)
    return fitted


def _draw_avatar_or_identity(
    image: Image.Image,
    draw: ImageDraw.ImageDraw,
    rect: tuple[int, int, int, int],
    full_name: str,
    *,
    avatar_path: Path | None,
    fonts: _FontBook,
    scale: float,
) -> None:
    """Use a safe cached owner avatar or the deterministic identity fallback."""

    if avatar_path is None:
        _draw_identity_block(draw, rect, full_name, fonts=fonts, scale=scale)
        return

    x1, y1, x2, y2 = rect
    avatar = _load_avatar_thumbnail(
        avatar_path,
        (x2 - x1, y2 - y1),
        radius=max(2, round(5 * scale)),
    )
    image.paste(avatar, (x1, y1), avatar)
    draw.rounded_rectangle(
        rect,
        radius=max(2, round(5 * scale)),
        outline=_INK,
        width=max(2, round(3 * scale)),
    )
    avatar.close()


def _growth_metric(repository: PosterRepository, period: str) -> tuple[str, str]:
    """Return a compact, source-honest label/value pair for the stat grid."""

    source = _normalise_delta_source(repository.delta_source)
    if source == "snapshot" and repository.star_delta < 0:
        return "增长数据", "待核验"
    signed = (
        f"+{repository.star_delta:,}"
        if repository.star_delta >= 0
        else f"{repository.star_delta:,}"
    )
    if source == "snapshot":
        return ("近24h净增" if period == "daily" else "近7天净增", signed)
    if source == "trending":
        return "Trending", signed
    approximate = f"≈{signed}"
    return ("日期估算" if period == "daily" else "周期估算", approximate)


def _why_hot_text(repository: PosterRepository, period: str) -> str:
    """Explain board inclusion with a readable but auditable growth statement."""

    source = _normalise_delta_source(repository.delta_source)
    window = "过去 24 小时" if period == "daily" else "过去 7 天"
    if source == "snapshot" and repository.star_delta < 0:
        return f"{window}快照差值异常｜不展示精确新增｜累计 {repository.stars:,} Star"
    signed = (
        f"+{repository.star_delta:,}"
        if repository.star_delta >= 0
        else f"{repository.star_delta:,}"
    )
    if source == "snapshot":
        return f"{window}净增 {signed} Star（相邻快照核验）｜累计 {repository.stars:,} Star"
    if source == "trending":
        return f"本期 GitHub Trending 显示 {signed} Star｜不是快照净增"
    return f"本期估算 {signed} Star｜快照基线仍待积累"


def _cover_growth_summary(repositories: Sequence[PosterRepository], period: str) -> str:
    """Summarise reliable snapshot coverage without exposing pipeline jargon."""

    verified = [
        item for item in repositories if item.delta_source == "snapshot" and item.star_delta >= 0
    ]
    if repositories and len(verified) == len(repositories):
        total = sum(item.star_delta for item in verified)
        window = "过去 24 小时" if period == "daily" else "过去 7 天"
        return f"{len(verified)} 个项目均有快照基线，{window}合计净增 +{total:,} Star。"
    if verified:
        return f"{len(verified)}/{len(repositories)} 个项目具备可核验快照基线，未将 Trending 或估算值计入合计。"
    return "新增基线仍在积累，本期不把 Trending 或估算信号写成精确净增。"


def _stat_card(
    draw: ImageDraw.ImageDraw,
    fonts: _FontBook,
    palette: PosterPalette,
    rect: tuple[int, int, int, int],
    label: str,
    value: str,
    *,
    large: bool = False,
    compact: bool = False,
) -> None:
    _panel(draw, rect, palette.surface_strong, radius=max(18, (rect[3] - rect[1]) // 7))
    x1, y1, x2, y2 = rect
    height = y2 - y1
    padding = max(18, height // 6)
    if compact:
        draw.text(
            (x1 + padding, y1 + height // 2),
            label,
            font=fonts.get(19, bold=True),
            fill=palette.muted,
            anchor="lm",
        )
        _draw_right_text(
            draw,
            (x2 - padding, y1 + height // 2),
            value,
            font=fonts.get(27, bold=True),
            fill=palette.text,
            anchor="rm",
            max_width=x2 - x1 - padding * 2 - 100,
        )
        return
    draw.text(
        (x1 + padding, y1 + padding),
        label,
        font=fonts.get(19, bold=True),
        fill=palette.muted,
    )
    _draw_wrapped_text(
        draw,
        (x1 + padding, y1 + padding + max(35, height // 4)),
        value,
        font=fonts.get(42 if large else 31, bold=True),
        fill=palette.text,
        max_width=x2 - x1 - padding * 2,
        max_lines=2,
        line_gap=4,
    )


def _new_background(
    size: tuple[int, int],
    palette: PosterPalette,
    *,
    seed: int,
    variant: int,
) -> Image.Image:
    width, height = size
    start = _hex_to_rgb(palette.background)
    end = _hex_to_rgb(palette.background_alt)
    gradient = Image.new("RGB", (1, height))
    pixels = gradient.load()
    for y in range(height):
        progress = y / max(height - 1, 1)
        eased = progress * progress * (3 - 2 * progress)
        pixels[0, y] = tuple(
            round(start[channel] + (end[channel] - start[channel]) * eased * 0.72)
            for channel in range(3)
        )
    image = gradient.resize(size)
    overlay = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    rng = random.Random(seed)
    scale = width / _BASE_WIDTH

    def s(value: int) -> int:
        return round(value * scale)

    if variant == 0:
        for offset in range(-height, width, s(132)):
            draw.line(
                (offset, 0, offset + height, height),
                fill=(*_hex_to_rgb(palette.primary), 16),
                width=max(1, s(2)),
            )
        for _ in range(8):
            radius = rng.randint(s(18), s(90))
            x = rng.randint(width * 2 // 3, width + radius)
            y = rng.randint(-radius, height // 2)
            draw.ellipse(
                (x - radius, y - radius, x + radius, y + radius),
                outline=(*_hex_to_rgb(palette.accent), rng.randint(18, 42)),
                width=max(1, s(3)),
            )
    elif variant == 1:
        step = s(84)
        for x in range(0, width, step):
            draw.line((x, 0, x, height), fill=(255, 255, 255, 10), width=max(1, s(1)))
        for y in range(0, height, step):
            draw.line((0, y, width, y), fill=(255, 255, 255, 10), width=max(1, s(1)))
        draw.ellipse(
            (width - s(410), -s(190), width + s(190), s(410)),
            outline=(*_hex_to_rgb(palette.primary), 38),
            width=max(2, s(8)),
        )
    else:
        for ring in range(6):
            inset = s(28 + ring * 52)
            draw.arc(
                (width - s(500) + inset, -s(230) + inset, width + s(190) - inset, s(460) - inset),
                start=20,
                end=310,
                fill=(*_hex_to_rgb(palette.accent), max(10, 42 - ring * 5)),
                width=max(1, s(3)),
            )
        points = []
        for _ in range(18):
            x = rng.randint(0, width)
            y = rng.randint(0, height)
            points.append((x, y))
            radius = rng.randint(s(2), s(6))
            draw.ellipse(
                (x - radius, y - radius, x + radius, y + radius),
                fill=(*_hex_to_rgb(palette.primary), rng.randint(35, 78)),
            )
        for left, right in zip(points[::2], points[1::2], strict=True):
            draw.line((*left, *right), fill=(255, 255, 255, 12), width=max(1, s(1)))
    return Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")


def _panel(
    draw: ImageDraw.ImageDraw,
    rect: tuple[int, int, int, int],
    fill: str,
    *,
    outline: str | None = None,
    radius: int = 28,
) -> None:
    draw.rounded_rectangle(
        rect,
        radius=radius,
        fill=fill,
        outline=outline,
        width=max(1, radius // 12) if outline else 1,
    )


def _pill(
    draw: ImageDraw.ImageDraw,
    rect: tuple[int, int, int, int],
    fill: str,
    *,
    radius: int,
) -> None:
    draw.rounded_rectangle(rect, radius=radius, fill=fill)


def _number_badge(
    draw: ImageDraw.ImageDraw,
    *,
    center: tuple[int, int],
    number: int,
    fill: str,
    text_fill: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    radius: int,
) -> None:
    x, y = center
    draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=fill)
    draw.text((x, y), str(number), font=font, fill=text_fill, anchor="mm")


def _draw_wrapped_text(
    draw: ImageDraw.ImageDraw,
    position: tuple[int, int],
    text: str,
    *,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    fill: str,
    max_width: int,
    max_lines: int,
    line_gap: int,
) -> int:
    lines = _wrap_text(draw, _clean_text(text), font, max_width, max_lines)
    x, y = position
    line_height = _font_line_height(font)
    for index, line in enumerate(lines):
        draw.text((x, y + index * (line_height + line_gap)), line, font=font, fill=fill)
    return y + len(lines) * line_height + max(len(lines) - 1, 0) * line_gap


def _draw_fitted_text(
    draw: ImageDraw.ImageDraw,
    position: tuple[int, int],
    text: str,
    *,
    fonts: _FontBook,
    fill: str,
    max_width: int,
    max_lines: int,
    max_size: int,
    min_size: int,
    line_gap: int,
    allow_truncation: bool = False,
    bold: bool = True,
) -> int:
    """Shrink text within a bounded type scale and gate unexpected truncation."""

    selected_font = fonts.get(min_size, bold=bold)
    selected_lines, selected_truncated = _wrap_text_with_status(
        draw,
        _clean_text(text),
        selected_font,
        max_width,
        max_lines,
    )
    for size in range(max_size, min_size - 1, -2):
        candidate_font = fonts.get(size, bold=bold)
        candidate_lines, truncated = _wrap_text_with_status(
            draw,
            _clean_text(text),
            candidate_font,
            max_width,
            max_lines,
        )
        selected_font = candidate_font
        selected_lines = candidate_lines
        selected_truncated = truncated
        if not truncated and not _has_orphaned_punctuation_lead(candidate_lines):
            break

    if selected_truncated and not allow_truncation:
        raise ValueError(
            "poster text does not fit its Signal Broadsheet region: "
            f"{_clip_plain(_clean_text(text), 48)}"
        )

    x, y = position
    line_height = _font_line_height(selected_font)
    for index, line in enumerate(selected_lines):
        draw.text(
            (x, y + index * (line_height + line_gap)),
            line,
            font=selected_font,
            fill=fill,
        )
    return y + len(selected_lines) * line_height + max(len(selected_lines) - 1, 0) * line_gap


def _draw_right_text(
    draw: ImageDraw.ImageDraw,
    position: tuple[int, int],
    text: str,
    *,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    fill: str,
    anchor: str = "ra",
    max_width: int | None = None,
) -> None:
    rendered = _clean_text(text)
    if max_width is not None:
        rendered = _ellipsize(draw, rendered, font, max_width)
    draw.text(position, rendered, font=font, fill=fill, anchor=anchor)


def _wrap_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    max_width: int,
    max_lines: int,
) -> list[str]:
    lines, _ = _wrap_text_with_status(draw, text, font, max_width, max_lines)
    return lines


def _wrap_text_with_status(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    max_width: int,
    max_lines: int,
) -> tuple[list[str], bool]:
    """Wrap text and expose whether the final line had to be truncated."""

    if not text or max_lines < 1:
        return [], False
    tokens = re.findall(r"[A-Za-z0-9][A-Za-z0-9_./:+#@&-]*\s*|.\s*", text)
    lines: list[str] = []
    current = ""
    truncated = False
    for token_index, token in enumerate(tokens):
        candidate = current + token
        if draw.textlength(candidate.rstrip(), font=font) <= max_width:
            current = candidate
            continue
        if current.strip():
            kinsoku_break = _rebalance_line_end_punctuation(
                draw,
                current,
                token,
                font,
                max_width,
            )
            if kinsoku_break is None:
                kinsoku_break = _rebalance_line_start_punctuation(
                    draw,
                    current,
                    token,
                    font,
                    max_width,
                )
            if kinsoku_break is None:
                lines.append(current.rstrip())
                current = token.lstrip()
            else:
                completed_line, current = kinsoku_break
                lines.append(completed_line)
        else:
            split_token, remainder = _split_token(draw, token, font, max_width)
            lines.append(split_token)
            current = remainder.lstrip()
        if len(lines) >= max_lines:
            truncated = token_index < len(tokens) - 1 or bool(current.strip())
            break
        while current and draw.textlength(current.rstrip(), font=font) > max_width:
            split_token, current = _split_token(draw, current, font, max_width)
            lines.append(split_token)
            if len(lines) >= max_lines:
                truncated = True
                break
        if len(lines) >= max_lines:
            break
    else:
        if current.strip():
            lines.append(current.rstrip())

    lines = lines[:max_lines]
    if truncated and lines:
        lines[-1] = _ellipsize(draw, lines[-1] + "…", font, max_width)
    return lines, truncated


_FORBIDDEN_LINE_START = frozenset("，。！？；：、）》】」』〉〕］｝”’…—,.!?;:%)]}")
_FORBIDDEN_LINE_END = frozenset("（《【「『〈〔［｛“‘([{")
_TRAILING_WRAP_UNIT = re.compile(r"(?:[A-Za-z0-9][A-Za-z0-9_./:+#@&-]*|\S)\s*$")
_CJK_CHARACTER = re.compile(r"[\u3400-\u9fff]")


def _has_orphaned_punctuation_lead(lines: Sequence[str]) -> bool:
    """Detect a lone Han character carried before closing punctuation."""

    return any(
        len(line) >= 2
        and _CJK_CHARACTER.fullmatch(line[0]) is not None
        and line[1] in _FORBIDDEN_LINE_START
        for line in lines
    )


def _rebalance_line_end_punctuation(
    draw: ImageDraw.ImageDraw,
    current: str,
    token: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    max_width: int,
) -> tuple[str, str] | None:
    """Carry opening punctuation forward instead of leaving it at line end."""

    current_text = current.rstrip()
    if not current_text or current_text[-1] not in _FORBIDDEN_LINE_END:
        return None

    completed_line = current_text[:-1].rstrip()
    carried_text = current_text[-1] + token.lstrip()
    if (
        not completed_line
        or draw.textlength(completed_line, font=font) > max_width
        or draw.textlength(carried_text.rstrip(), font=font) > max_width
    ):
        return None
    return completed_line, carried_text


def _rebalance_line_start_punctuation(
    draw: ImageDraw.ImageDraw,
    current: str,
    token: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    max_width: int,
) -> tuple[str, str] | None:
    """Keep closing punctuation away from the start of a wrapped line."""

    next_text = token.lstrip()
    current_text = current.rstrip()
    if not next_text or next_text[0] not in _FORBIDDEN_LINE_START:
        return None

    trailing_unit = _TRAILING_WRAP_UNIT.search(current_text)
    if trailing_unit is None or trailing_unit.start() == 0:
        return None

    completed_line = current_text[: trailing_unit.start()].rstrip()
    carried_text = current_text[trailing_unit.start() :] + next_text
    if (
        not completed_line
        or draw.textlength(completed_line, font=font) > max_width
        or draw.textlength(carried_text.rstrip(), font=font) > max_width
    ):
        return None
    return completed_line, carried_text


def _split_token(
    draw: ImageDraw.ImageDraw,
    token: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    max_width: int,
) -> tuple[str, str]:
    head = ""
    for index, character in enumerate(token):
        candidate = head + character
        if head and draw.textlength(candidate, font=font) > max_width:
            return head.rstrip(), token[index:]
        head = candidate
    return head.rstrip(), ""


def _ellipsize(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    max_width: int,
) -> str:
    compact = text.rstrip()
    if draw.textlength(compact, font=font) <= max_width:
        return compact
    suffix = "…"
    while compact and draw.textlength(compact.rstrip() + suffix, font=font) > max_width:
        compact = compact[:-1]
    return compact.rstrip() + suffix


def _font_line_height(font: ImageFont.FreeTypeFont | ImageFont.ImageFont) -> int:
    left, top, right, bottom = font.getbbox("国Ag")
    return bottom - top


def _three_highlights(
    values: Sequence[Any],
    *,
    description: str | None,
    language: str | None,
    stars: int,
    forks: int,
    period: str,
    star_delta: int,
    delta_source: str,
) -> tuple[str, str, str]:
    del language, stars, forks, period, star_delta, delta_source
    candidates = list(_capability_list(values))
    fallback = (
        _clean_text(description),
        "需要查看仓库 README 确认更多具体能力",
        "需要人工核对功能与适用场景后再发布",
    )
    unique: list[str] = []
    for candidate in (*candidates, *fallback):
        if candidate and candidate not in unique:
            unique.append(candidate)
        if len(unique) == 3:
            break
    while len(unique) < 3:
        unique.append("需要人工确认更多具体能力")
    return unique[0], unique[1], unique[2]


def _capability_list(values: Sequence[Any]) -> tuple[str, ...]:
    """Return one to five unique capability statements with a safe review fallback."""

    unique: list[str] = []
    for value in values:
        candidate = _clean_text(value)
        if candidate and candidate not in unique:
            unique.append(candidate)
        if len(unique) == 5:
            break
    if not unique:
        unique.extend(
            (
                "需要查看仓库 README 确认主要用途",
                "需要核对实际输入、输出和使用方式",
                "需要人工确认适用场景后再发布",
            )
        )
    return tuple(unique)


def _license_spdx(value: Mapping[str, Any]) -> str:
    raw_license = value.get("license_spdx")
    if raw_license is None:
        license_value = value.get("license")
        if isinstance(license_value, Mapping):
            raw_license = license_value.get("spdx_id") or license_value.get("name")
        else:
            raw_license = license_value
    return _clip_plain(_clean_text(raw_license), 40) if raw_license else ""


def _safe_avatar_path(value: Any, *, root: str | Path | None) -> Path | None:
    """Resolve a cached avatar below an explicit local root without following escapes."""

    text = _clean_text(value)
    if not text:
        return None
    if re.match(r"^[a-z][a-z0-9+.-]*://", text, re.IGNORECASE) or text.startswith("\\\\"):
        raise ValueError("avatar_path must be a local relative path")
    relative = Path(text)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("avatar_path must stay inside the configured local root")
    base = Path(root) if root is not None else Path.cwd()
    base = base.resolve()
    candidate = (base / relative).resolve()
    try:
        candidate.relative_to(base)
    except ValueError as error:
        raise ValueError("avatar_path escapes the configured local root") from error
    if candidate.suffix.casefold() not in _ALLOWED_AVATAR_SUFFIXES:
        raise ValueError("avatar_path must use PNG, JPG, JPEG, or WebP")
    if not candidate.is_file():
        raise ValueError("avatar_path does not point to a cached local file")
    return candidate


def _coerce_repository(
    item: PosterRepository | RankedRepository | Mapping[str, Any],
    *,
    fallback_rank: int,
    period: str,
    avatar_root: str | Path | None,
) -> PosterRepository:
    if isinstance(item, PosterRepository):
        if item.avatar_path is None:
            return item
        return replace(
            item,
            avatar_path=_safe_avatar_path(item.avatar_path, root=avatar_root),
        )
    if isinstance(item, RankedRepository):
        repository = PosterRepository.from_ranked(item)
        if period == "daily":
            return repository
        summary = summarize_repository(item.repository, item.star_delta, item.delta_source)
        highlights = _three_highlights(
            summary.highlights,
            description=item.repository.description,
            language=item.repository.language,
            stars=item.repository.stars,
            forks=item.repository.forks,
            period=period,
            star_delta=item.star_delta,
            delta_source=item.delta_source,
        )
        return replace(
            repository,
            highlights=highlights,
            capabilities=highlights,
            core_value=highlights[0],
        )
    if isinstance(item, Mapping):
        return PosterRepository.from_mapping(
            item,
            fallback_rank=fallback_rank,
            period=period,
            avatar_root=avatar_root,
        )
    raise TypeError("repositories must contain PosterRepository, RankedRepository, or mapping")


def _normalise_delta_source(value: Any) -> str:
    source = str(value or "estimate").strip().casefold()
    return source if source in _VALID_DELTA_SOURCES else "estimate"


def _short_repository_link(repository: PosterRepository) -> str:
    parsed = urlsplit(repository.html_url)
    if parsed.netloc.casefold() in {"github.com", "www.github.com"}:
        path = parsed.path.strip("/")
        if path:
            return path
    return repository.full_name.strip("/")


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())


def _clip_plain(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _stable_seed(value: str) -> int:
    digest = hashlib.sha256(value.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    cleaned = value.removeprefix("#")
    return (
        int(cleaned[0:2], 16),
        int(cleaned[2:4], 16),
        int(cleaned[4:6], 16),
    )


def _repository_slug(full_name: str) -> str:
    parts = [_slug_component(part) for part in full_name.split("/") if part]
    return "--".join(part for part in parts if part)[:96] or "repository"


def _slug_component(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


def _report_stem(period: str, run_date: date) -> str:
    if period == "daily":
        return run_date.isoformat()
    iso_year, iso_week, _ = run_date.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"


def _coerce_date(value: date | str) -> date:
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError) as error:
        raise ValueError("run_date must be an ISO date") from error


def _validate_size(size: tuple[int, int]) -> None:
    if len(size) != 2 or any(not isinstance(value, int) for value in size):
        raise ValueError("size must contain integer width and height")
    width, height = size
    if width < 600 or height < 800 or width * 4 != height * 3:
        raise ValueError("poster size must use a 3:4 ratio and be at least 600x800")


def _is_cjk_character(character: str) -> bool:
    codepoint = ord(character)
    return (
        0x3400 <= codepoint <= 0x4DBF
        or 0x4E00 <= codepoint <= 0x9FFF
        or 0xF900 <= codepoint <= 0xFAFF
    )


def _glyph_signature(font: ImageFont.FreeTypeFont, character: str) -> tuple[Any, ...]:
    mask = font.getmask(character)
    return mask.size, font.getbbox(character), bytes(mask)


def _font_has_glyph(font: ImageFont.FreeTypeFont, character: str) -> bool:
    return _glyph_signature(font, character) != _glyph_signature(font, _MISSING_GLYPH_SENTINEL)


def _font_supports_cjk(font: ImageFont.FreeTypeFont) -> bool:
    return all(_font_has_glyph(font, character) for character in _CJK_PROBE_TEXT)


def _resolve_font_path(*, bold: bool) -> Path | None:
    environment_name = "GITHUB_HOTSPOTS_FONT_BOLD" if bold else "GITHUB_HOTSPOTS_FONT_REGULAR"
    configured = os.environ.get(environment_name)
    candidates = [Path(configured)] if configured else []
    if bold:
        candidates.extend(
            [
                Path("C:/Windows/Fonts/msyhbd.ttc"),
                Path("C:/Windows/Fonts/simhei.ttf"),
                Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"),
                Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc"),
                Path("/usr/share/fonts/opentype/noto/NotoSansCJKsc-Bold.otf"),
                Path("/System/Library/Fonts/PingFang.ttc"),
            ]
        )
    else:
        candidates.extend(
            [
                Path("C:/Windows/Fonts/msyh.ttc"),
                Path("C:/Windows/Fonts/simhei.ttf"),
                Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
                Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"),
                Path("/usr/share/fonts/opentype/noto/NotoSansCJKsc-Regular.otf"),
                Path("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"),
                Path("/System/Library/Fonts/PingFang.ttc"),
            ]
        )
    return next((candidate for candidate in candidates if candidate.is_file()), None)


def _save_png(image: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        image.save(temporary, format="PNG", optimize=True)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
        image.close()


def _parse_size(value: str) -> tuple[int, int]:
    match = re.fullmatch(r"(\d+)[xX](\d+)", value.strip())
    if not match:
        raise argparse.ArgumentTypeError("size must look like 1200x1600")
    size = int(match.group(1)), int(match.group(2))
    try:
        _validate_size(size)
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from error
    return size


def main(argv: Sequence[str] | None = None) -> int:
    """Command-line entry point for rendering an existing report JSON."""

    parser = argparse.ArgumentParser(description="Render Xiaohongshu poster cards from a report")
    parser.add_argument("report", type=Path, help="Daily or weekly report JSON path")
    parser.add_argument("--output-dir", type=Path, help="Destination directory")
    parser.add_argument(
        "--board",
        action="append",
        dest="boards",
        help="Board key to render; repeat for multiple boards",
    )
    parser.add_argument("--size", type=_parse_size, default=DEFAULT_POSTER_SIZE)
    arguments = parser.parse_args(argv)
    artifacts = render_report_posters(
        arguments.report,
        output_dir=arguments.output_dir,
        board_keys=arguments.boards,
        size=arguments.size,
    )
    for board_key, board_artifacts in artifacts.items():
        print(f"{board_key}: {len(board_artifacts.all_paths)} PNG files")
        for path in board_artifacts.all_paths:
            print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

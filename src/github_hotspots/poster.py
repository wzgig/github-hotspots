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

from PIL import Image, ImageDraw, ImageFont

from .models import RankedRepository
from .summarizer import summarize_repository

DEFAULT_POSTER_SIZE = (1200, 1600)
POSTER_RENDERER_NAME = "github-hotspots-pillow"
POSTER_RENDERER_VERSION = "1.0"
POSTER_STYLE_VERSION = "open-source-intel-v1"
_BASE_WIDTH = 1080
_BASE_HEIGHT = 1440
_VALID_PERIODS = {"daily", "weekly"}
_VALID_DELTA_SOURCES = {"snapshot", "trending", "estimate"}
_CJK_PROBE_TEXT = "中文开源情报"
_MISSING_GLYPH_SENTINEL = "\U0010ffff"


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

    @classmethod
    def from_ranked(cls, item: RankedRepository) -> PosterRepository:
        """Build poster data from a core ranking result."""

        summary = summarize_repository(
            item.repository,
            item.star_delta,
            item.delta_source,
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
            highlights=_three_highlights(
                summary.highlights,
                description=item.repository.description,
                language=item.repository.language,
                stars=item.repository.stars,
                forks=item.repository.forks,
                period="daily",
                star_delta=item.star_delta,
                delta_source=item.delta_source,
            ),
            audience=summary.audience,
        )

    @classmethod
    def from_mapping(
        cls,
        value: Mapping[str, Any],
        *,
        fallback_rank: int = 1,
        period: str = "daily",
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

        description = _clean_text(value.get("description")) or "暂无仓库简介"
        short_description = (
            _clean_text(value.get("poster_description"))
            or _clean_text(summary.get("one_line"))
            or description
        )
        language = _clean_text(value.get("language")) or "未标注"
        stars = _as_int(value.get("stars"))
        forks = _as_int(value.get("forks"))
        star_delta = _as_int(value.get("star_delta"))
        delta_source = _normalise_delta_source(value.get("delta_source"))

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
            highlights=_three_highlights(
                highlights,
                description=description,
                language=language,
                stars=stars,
                forks=forks,
                period=period,
                star_delta=star_delta,
                delta_source=delta_source,
            ),
            audience=_clean_text(summary.get("audience")) or "开发者与开源项目关注者",
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
) -> PosterArtifacts:
    """Render one cover plus one portrait PNG for every ranked repository."""

    if period not in _VALID_PERIODS:
        raise ValueError("period must be 'daily' or 'weekly'")
    _validate_size(size)
    parsed_date = _coerce_date(run_date)
    normalised = tuple(
        _coerce_repository(item, fallback_rank=index, period=period)
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
        "开源情报卡 每天更新 · 逐项目拆解 每周复盘 · 逐项目拆解 本期入选 "
        "本期暂无入选项目 数据来自 GitHub 与本地快照 · 不混淆精确值、Trending 与估算 "
        "快照数据 一句话看懂 周期信号 三条情报 适合谁 人工审核稿",
        *(repository.short_description for repository in normalised),
        *(repository.language for repository in normalised),
        *(repository.audience for repository in normalised),
        *(highlight for repository in normalised for highlight in repository.highlights),
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
) -> Image.Image:
    scale = size[0] / _BASE_WIDTH
    seed = _stable_seed(f"{board_key}:{repository.full_name}")
    palette = _PALETTES[seed % len(_PALETTES)]
    variant = seed % 3
    image = _new_background(size, palette, seed=seed, variant=variant)
    draw = ImageDraw.Draw(image)

    def s(value: int) -> int:
        return round(value * scale)

    _pill(
        draw,
        (s(72), s(64), s(72 + min(330, 116 + len(board_label) * 34)), s(124)),
        palette.primary,
        radius=s(30),
    )
    draw.text(
        (s(96), s(79)),
        board_label,
        font=fonts.get(27, bold=True),
        fill=palette.background,
    )
    period_label = "DAILY" if period == "daily" else "WEEKLY"
    date_text = f"{period_label} · {run_date:%Y.%m.%d}"
    _draw_right_text(
        draw,
        (s(1008), s(82)),
        date_text,
        font=fonts.get(24, bold=True),
        fill=palette.muted,
    )

    rank_text = f"#{repository.rank:02d}"
    draw.text(
        (s(72), s(162)),
        rank_text,
        font=fonts.get(82, bold=True),
        fill=palette.accent,
    )
    owner, separator, name = repository.full_name.partition("/")
    project_name = name if separator else owner
    owner_name = owner if separator else "OPEN SOURCE"
    _draw_wrapped_text(
        draw,
        (s(260), s(164)),
        project_name,
        font=fonts.get(68, bold=True),
        fill=palette.text,
        max_width=s(748),
        max_lines=1,
        line_gap=s(8),
    )
    draw.text(
        (s(264), s(249)),
        f"by {owner_name}",
        font=fonts.get(27),
        fill=palette.muted,
    )
    _draw_right_text(
        draw,
        (s(1008), s(249)),
        f"LANG · {repository.language}",
        font=fonts.get(21, bold=True),
        fill=palette.primary,
        max_width=s(310),
    )

    description_rect = (s(72), s(322), s(1008), s(510))
    _panel(draw, description_rect, palette.surface, outline=palette.primary, radius=s(34))
    accent_x = s(92) if variant != 1 else s(974)
    draw.rounded_rectangle(
        (accent_x, s(354), accent_x + s(7), s(476)),
        radius=s(4),
        fill=palette.primary,
    )
    description_x = s(122) if variant != 1 else s(102)
    draw.text(
        (description_x, s(350)),
        "一句话看懂",
        font=fonts.get(23, bold=True),
        fill=palette.primary,
    )
    _draw_wrapped_text(
        draw,
        (description_x, s(395)),
        repository.short_description,
        font=fonts.get(32, bold=True),
        fill=palette.text,
        max_width=s(825),
        max_lines=2,
        line_gap=s(12),
    )

    stats_bottom = _draw_stats(
        draw,
        fonts,
        palette,
        repository,
        period=period,
        variant=variant,
        scale=scale,
    )
    highlights_top = stats_bottom + s(30)
    highlights_bottom = s(1158)
    _panel(
        draw,
        (s(72), highlights_top, s(1008), highlights_bottom),
        palette.surface,
        radius=s(34),
    )
    draw.text(
        (s(108), highlights_top + s(32)),
        "三条情报",
        font=fonts.get(25, bold=True),
        fill=palette.primary,
    )
    bullet_y = highlights_top + s(86)
    available_height = highlights_bottom - bullet_y - s(22)
    bullet_step = max(s(78), available_height // 3)
    for index, highlight in enumerate(repository.highlights, start=1):
        y = bullet_y + (index - 1) * bullet_step
        _number_badge(
            draw,
            center=(s(124), y + s(22)),
            number=index,
            fill=palette.accent if index == 1 else palette.surface_strong,
            text_fill=palette.background if index == 1 else palette.text,
            font=fonts.get(22, bold=True),
            radius=s(22),
        )
        _draw_wrapped_text(
            draw,
            (s(170), y),
            highlight,
            font=fonts.get(27, bold=index == 1),
            fill=palette.text if index == 1 else palette.muted,
            max_width=s(786),
            max_lines=2,
            line_gap=s(7),
        )

    _panel(
        draw,
        (s(72), s(1190), s(1008), s(1302)),
        palette.surface_strong,
        radius=s(28),
    )
    draw.text(
        (s(106), s(1216)),
        "适合谁",
        font=fonts.get(23, bold=True),
        fill=palette.accent,
    )
    _draw_wrapped_text(
        draw,
        (s(230), s(1212)),
        repository.audience,
        font=fonts.get(27, bold=True),
        fill=palette.text,
        max_width=s(728),
        max_lines=2,
        line_gap=s(6),
    )

    short_link = _short_repository_link(repository)
    link_font = fonts.get(24, bold=True)
    draw.text(
        (s(72), s(1352)),
        _ellipsize(draw, short_link, link_font, s(760)),
        font=link_font,
        fill=palette.primary,
    )
    _draw_right_text(
        draw,
        (s(1008), s(1352)),
        "人工审核稿",
        font=fonts.get(18, bold=True),
        fill=palette.muted,
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
) -> Image.Image:
    scale = size[0] / _BASE_WIDTH
    seed = _stable_seed(f"cover:{board_key}:{run_date.isoformat()}")
    palette = _PALETTES[seed % len(_PALETTES)]
    variant = (seed + 1) % 3
    image = _new_background(size, palette, seed=seed, variant=variant)
    draw = ImageDraw.Draw(image)

    def s(value: int) -> int:
        return round(value * scale)

    draw.text(
        (s(72), s(76)),
        "GITHUB HOTSPOTS / OPEN SOURCE INTEL",
        font=fonts.get(22, bold=True),
        fill=palette.primary,
    )
    _draw_right_text(
        draw,
        (s(1008), s(76)),
        run_date.strftime("%Y.%m.%d"),
        font=fonts.get(22, bold=True),
        fill=palette.muted,
    )

    draw.text(
        (s(72), s(190)),
        board_label,
        font=fonts.get(86, bold=True),
        fill=palette.text,
    )
    draw.text(
        (s(72), s(300)),
        "开源情报卡",
        font=fonts.get(86, bold=True),
        fill=palette.text,
    )
    draw.rounded_rectangle(
        (s(72), s(426), s(490), s(438)),
        radius=s(6),
        fill=palette.accent,
    )
    cadence = "每天更新 · 逐项目拆解" if period == "daily" else "每周复盘 · 逐项目拆解"
    draw.text(
        (s(72), s(478)),
        cadence,
        font=fonts.get(31, bold=True),
        fill=palette.muted,
    )
    draw.text(
        (s(72), s(528)),
        format_cover_window_label(window_start, run_date),
        font=fonts.get(21, bold=True),
        fill=palette.primary,
    )

    _panel(
        draw,
        (s(72), s(590), s(1008), s(862)),
        palette.surface,
        outline=palette.primary,
        radius=s(42),
    )
    draw.text(
        (s(112), s(616)),
        format_cover_selection_label(top_n, len(repositories)),
        font=fonts.get(44, bold=True),
        fill=palette.text,
    )
    source_counts = {
        source: sum(item.delta_source == source for item in repositories)
        for source in _VALID_DELTA_SOURCES
    }
    source_labels = (
        ("快照数据", source_counts["snapshot"], palette.primary),
        ("Trending", source_counts["trending"], palette.accent),
        ("估算", source_counts["estimate"], palette.muted),
    )
    for index, (label, count, color) in enumerate(source_labels):
        x = s(112 + index * 294)
        draw.text(
            (x, s(716)),
            f"{count:02d}",
            font=fonts.get(38, bold=True),
            fill=color,
        )
        draw.text(
            (x + s(62), s(727)),
            label,
            font=fonts.get(21, bold=True),
            fill=palette.muted,
        )

    draw.text(
        (s(112), s(797)),
        format_cover_growth_status(repositories),
        font=fonts.get(19, bold=True),
        fill=palette.text,
    )

    draw.text(
        (s(72), s(900)),
        "本期入选",
        font=fonts.get(25, bold=True),
        fill=palette.primary,
    )
    top_items = repositories[:3]
    if top_items:
        for index, repository in enumerate(top_items, start=1):
            y = s(956 + (index - 1) * 92)
            _number_badge(
                draw,
                center=(s(100), y + s(26)),
                number=repository.rank,
                fill=palette.accent if index == 1 else palette.surface_strong,
                text_fill=palette.background if index == 1 else palette.text,
                font=fonts.get(21, bold=True),
                radius=s(23),
            )
            _draw_wrapped_text(
                draw,
                (s(146), y),
                repository.full_name,
                font=fonts.get(34, bold=True),
                fill=palette.text,
                max_width=s(820),
                max_lines=1,
                line_gap=0,
            )
    else:
        draw.text(
            (s(72), s(964)),
            "本期暂无入选项目",
            font=fonts.get(36, bold=True),
            fill=palette.muted,
        )

    _panel(
        draw,
        (s(72), s(1254), s(1008), s(1358)),
        palette.surface_strong,
        radius=s(30),
    )
    draw.text(
        (s(104), s(1285)),
        "数据来自 GitHub 与本地快照 · 不混淆精确值、Trending 与估算",
        font=fonts.get(21, bold=True),
        fill=palette.text,
    )
    return image


def _draw_stats(
    draw: ImageDraw.ImageDraw,
    fonts: _FontBook,
    palette: PosterPalette,
    repository: PosterRepository,
    *,
    period: str,
    variant: int,
    scale: float,
) -> int:
    def s(value: int) -> int:
        return round(value * scale)

    delta = format_delta_label(repository.star_delta, repository.delta_source, period)
    if variant == 0:
        top, bottom = s(544), s(732)
        cards = (
            ((s(72), top, s(366), bottom), "STAR", f"{repository.stars:,}"),
            ((s(386), top, s(680), bottom), "FORK", f"{repository.forks:,}"),
            ((s(700), top, s(1008), bottom), "周期信号", delta),
        )
        for rect, label, value in cards:
            _stat_card(draw, fonts, palette, rect, label, value)
        return bottom
    if variant == 1:
        top, bottom = s(544), s(744)
        _stat_card(
            draw,
            fonts,
            palette,
            (s(72), top, s(498), bottom),
            "STAR",
            f"{repository.stars:,}",
            large=True,
        )
        _stat_card(
            draw,
            fonts,
            palette,
            (s(518), top, s(1008), s(635)),
            "FORK",
            f"{repository.forks:,}",
            compact=True,
        )
        _stat_card(
            draw,
            fonts,
            palette,
            (s(518), s(653), s(1008), bottom),
            "周期信号",
            delta,
            compact=True,
        )
        return bottom
    top, bottom = s(544), s(750)
    _stat_card(
        draw,
        fonts,
        palette,
        (s(72), top, s(1008), s(641)),
        "周期信号",
        delta,
        compact=True,
    )
    _stat_card(
        draw,
        fonts,
        palette,
        (s(72), s(660), s(530), bottom),
        "STAR",
        f"{repository.stars:,}",
        compact=True,
    )
    _stat_card(
        draw,
        fonts,
        palette,
        (s(550), s(660), s(1008), bottom),
        "FORK",
        f"{repository.forks:,}",
        compact=True,
    )
    return bottom


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
    if not text or max_lines < 1:
        return []
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
            lines.append(current.rstrip())
            current = token.lstrip()
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
    return lines


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
    candidates = [_clean_text(value) for value in values]
    fallback = (
        f"项目定位：{_clean_text(description) or '暂无仓库简介'}",
        f"主要语言：{_clean_text(language) or '未标注'}；累计 {stars:,} Star / {forks:,} Fork",
        format_delta_label(star_delta, delta_source, period),
    )
    unique: list[str] = []
    for candidate in (*candidates, *fallback):
        if candidate and candidate not in unique:
            unique.append(candidate)
        if len(unique) == 3:
            break
    while len(unique) < 3:
        unique.append("更多信息请以 GitHub 仓库页面为准")
    return unique[0], unique[1], unique[2]


def _coerce_repository(
    item: PosterRepository | RankedRepository | Mapping[str, Any],
    *,
    fallback_rank: int,
    period: str,
) -> PosterRepository:
    if isinstance(item, PosterRepository):
        return item
    if isinstance(item, RankedRepository):
        repository = PosterRepository.from_ranked(item)
        if period == "daily":
            return repository
        summary = summarize_repository(item.repository, item.star_delta, item.delta_source)
        return replace(
            repository,
            highlights=_three_highlights(
                summary.highlights,
                description=item.repository.description,
                language=item.repository.language,
                stars=item.repository.stars,
                forks=item.repository.forks,
                period=period,
                star_delta=item.star_delta,
                delta_source=item.delta_source,
            ),
        )
    if isinstance(item, Mapping):
        return PosterRepository.from_mapping(
            item,
            fallback_rank=fallback_rank,
            period=period,
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
            return f"github.com/{path}"
    return f"github.com/{repository.full_name.strip('/')}"


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())


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

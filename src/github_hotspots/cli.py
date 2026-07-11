"""Command-line entry point for GitHub Hotspots."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Annotated
from zoneinfo import ZoneInfo

import typer

from .config import ConfigurationError, load_settings
from .pipeline import run_pipeline
from .rerender import rerender_report

app = typer.Typer(
    no_args_is_help=True,
    add_completion=False,
    help="Generate explainable daily and weekly GitHub hotspot reports.",
)


def _parse_date(value: str | None, timezone: str) -> date:
    if value is None:
        return datetime.now(ZoneInfo(timezone)).date()
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise typer.BadParameter("date must use YYYY-MM-DD") from exc


@app.command("run")
def run_command(
    period: Annotated[
        str,
        typer.Option("--period", "-p", help="daily or weekly"),
    ] = "daily",
    run_date: Annotated[
        str | None,
        typer.Option("--date", help="Override the run date (YYYY-MM-DD)"),
    ] = None,
    config: Annotated[
        Path,
        typer.Option("--config", help="Path to the YAML configuration"),
    ] = Path("config/hotspots.yaml"),
    editorial_backend: Annotated[
        str | None,
        typer.Option(
            "--editorial-backend",
            help="deterministic or codex-cli; overrides config for this run",
        ),
    ] = None,
) -> None:
    """Collect candidates and write one report bundle."""

    try:
        settings = load_settings(config)
        selected_date = _parse_date(run_date, settings.timezone)
        result = run_pipeline(
            settings,
            period,
            selected_date,
            editorial_backend=editorial_backend,
        )
    except (ConfigurationError, RuntimeError, ValueError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    comprehensive = settings.board("comprehensive")
    ai = settings.board("ai")
    typer.echo(f"Generated {result.period} dual boards from {result.candidate_count} candidates.")
    typer.echo(f"{comprehensive.label}: Top {result.ranked_count}")
    typer.echo(f"{ai.label}: Top {result.ai_ranked_count}")
    typer.echo(f"Snapshot: {result.snapshot}")
    typer.echo(f"Markdown: {result.artifacts.markdown}")
    typer.echo(f"JSON: {result.artifacts.json}")
    typer.echo(f"Xiaohongshu copy ({comprehensive.label}): {result.artifacts.xiaohongshu}")
    typer.echo(f"Xiaohongshu copy ({ai.label}): {result.artifacts.ai_xiaohongshu}")
    if result.artifacts.poster_manifest:
        typer.echo(f"Poster manifest: {result.artifacts.poster_manifest}")
        typer.echo(f"Poster PNG files: {len(result.artifacts.poster_files)}")
    for warning in result.warnings:
        typer.echo(f"Warning: {warning}", err=True)


@app.command("run-all")
def run_all_command(
    run_date: Annotated[
        str | None,
        typer.Option("--date", help="Override the run date (YYYY-MM-DD)"),
    ] = None,
    config: Annotated[
        Path,
        typer.Option("--config", help="Path to the YAML configuration"),
    ] = Path("config/hotspots.yaml"),
    editorial_backend: Annotated[
        str | None,
        typer.Option(
            "--editorial-backend",
            help="deterministic or codex-cli; overrides config for this run",
        ),
    ] = None,
) -> None:
    """Generate both daily and weekly bundles using one date."""

    try:
        settings = load_settings(config)
        selected_date = _parse_date(run_date, settings.timezone)
        comprehensive = settings.board("comprehensive")
        ai = settings.board("ai")
        for period in ("daily", "weekly"):
            result = run_pipeline(
                settings,
                period,
                selected_date,
                editorial_backend=editorial_backend,
            )
            typer.echo(
                f"Generated {period}: {comprehensive.label} Top {result.ranked_count}, "
                f"{ai.label} Top {result.ai_ranked_count}: {result.artifacts.markdown}"
            )
            for warning in result.warnings:
                typer.echo(f"Warning: {warning}", err=True)
    except (ConfigurationError, RuntimeError, ValueError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc


@app.command("rerender")
def rerender_command(
    report: Annotated[
        Path,
        typer.Argument(help="Existing daily or weekly report JSON"),
    ],
    config: Annotated[
        Path,
        typer.Option("--config", help="Path to the YAML configuration"),
    ] = Path("config/hotspots.yaml"),
    editorial_backend: Annotated[
        str | None,
        typer.Option(
            "--editorial-backend",
            help="deterministic or codex-cli; facts and rankings are not recollected",
        ),
    ] = None,
) -> None:
    """Rebuild copy and posters from frozen report facts without GitHub requests."""

    try:
        settings = load_settings(config)
        artifacts = rerender_report(
            settings,
            report,
            editorial_backend=editorial_backend,
        )
    except (ConfigurationError, RuntimeError, ValueError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"Re-rendered: {artifacts.json}")
    typer.echo(f"Markdown: {artifacts.markdown}")
    typer.echo(f"Xiaohongshu: {artifacts.xiaohongshu}")
    typer.echo(f"AI Xiaohongshu: {artifacts.ai_xiaohongshu}")
    if artifacts.poster_manifest:
        typer.echo(f"Poster manifest: {artifacts.poster_manifest}")
        typer.echo(f"Poster PNG files: {len(artifacts.poster_files)}")
    for warning in artifacts.warnings:
        typer.echo(f"Warning: {warning}", err=True)


if __name__ == "__main__":
    app()

"""Command-line entry point for GitHub Hotspots."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Annotated
from zoneinfo import ZoneInfo

import typer

from .config import ConfigurationError, load_settings
from .pipeline import run_pipeline

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
) -> None:
    """Collect candidates and write one report bundle."""

    try:
        settings = load_settings(config)
        selected_date = _parse_date(run_date, settings.timezone)
        result = run_pipeline(settings, period, selected_date)
    except (ConfigurationError, RuntimeError, ValueError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(
        f"Generated {result.period} Top {result.ranked_count} from "
        f"{result.candidate_count} candidates."
    )
    typer.echo(f"Snapshot: {result.snapshot}")
    typer.echo(f"Markdown: {result.artifacts.markdown}")
    typer.echo(f"JSON: {result.artifacts.json}")
    typer.echo(f"Xiaohongshu copy: {result.artifacts.xiaohongshu}")
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
) -> None:
    """Generate both daily and weekly bundles using one date."""

    try:
        settings = load_settings(config)
        selected_date = _parse_date(run_date, settings.timezone)
        for period in ("daily", "weekly"):
            result = run_pipeline(settings, period, selected_date)
            typer.echo(f"Generated {period} Top {result.ranked_count}: {result.artifacts.markdown}")
    except (ConfigurationError, RuntimeError, ValueError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc


if __name__ == "__main__":
    app()

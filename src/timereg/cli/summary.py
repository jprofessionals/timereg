"""CLI summary command — generate summary reports with budget tracking."""

from __future__ import annotations

import json
from datetime import date
from typing import Annotated

import typer

from timereg.cli.app import app, state
from timereg.core.projects import get_project
from timereg.core.reports import generate_summary


@app.command()
def summary(
    week: Annotated[bool, typer.Option("--week", help="Show weekly summary")] = False,
    month: Annotated[bool, typer.Option("--month", help="Show monthly summary")] = False,
    day: Annotated[bool, typer.Option("--day", help="Show daily summary")] = False,
    date_from: Annotated[str | None, typer.Option("--from", help="Start date (YYYY-MM-DD)")] = None,
    date_to: Annotated[str | None, typer.Option("--to", help="End date (YYYY-MM-DD)")] = None,
    date_str: Annotated[
        str | None, typer.Option("--date", help="Reference date (YYYY-MM-DD)")
    ] = None,
    project_slug: Annotated[
        str | None, typer.Option("--project", help="Filter by project slug")
    ] = None,
    tags: Annotated[str | None, typer.Option("--tags", help="Comma-separated tag filter")] = None,
    detail: Annotated[str, typer.Option("--detail", help="Detail level: brief or full")] = "brief",
) -> None:
    """Generate a summary report for a period."""
    # Determine period from mutually exclusive flags
    period: str | None = None
    period_flags = sum([week, month, day])
    if period_flags > 1:
        typer.echo("Error: --week, --month, and --day are mutually exclusive.", err=True)
        raise typer.Exit(1)
    if week:
        period = "week"
    elif month:
        period = "month"
    elif day:
        period = "day"

    # Parse dates
    reference_date = date.fromisoformat(date_str) if date_str else None
    from_date = date.fromisoformat(date_from) if date_from else None
    to_date = date.fromisoformat(date_to) if date_to else None

    # Resolve project
    project_id: int | None = None
    if project_slug:
        project = get_project(state.db, project_slug)
        if project is None:
            typer.echo(f"Error: Project '{project_slug}' not found.", err=True)
            raise typer.Exit(1)
        project_id = project.id

    # Parse tags
    tag_filter: list[str] | None = None
    if tags:
        tag_filter = [t.strip() for t in tags.split(",") if t.strip()]

    # Generate report
    report = generate_summary(
        db=state.db,
        period=period,
        date_from=from_date,
        date_to=to_date,
        project_id=project_id,
        tag_filter=tag_filter,
        detail=detail,
        reference_date=reference_date,
    )

    # Output
    if state.output_format == "json":
        typer.echo(json.dumps(report.model_dump(mode="json"), indent=2, default=str))
        return

    _print_text_output(report, detail)


def _format_budget_bar(percent: float, width: int = 20) -> str:
    """Render a simple ASCII budget bar. Delegates to shared helper."""
    from timereg.cli import format_budget_bar

    return format_budget_bar(percent, width)


def _print_text_output(report: object, detail: str) -> None:
    """Print summary report as formatted text."""
    from timereg.core.models import SummaryReport

    assert isinstance(report, SummaryReport)

    typer.echo(f"Summary: {report.period_label}")
    typer.echo(f"Period: {report.period_start} to {report.period_end}")
    typer.echo("")

    if not report.projects:
        typer.echo("No entries found for this period.")
        return

    for ps in report.projects:
        typer.echo(f"  {ps.project.name} ({ps.project.slug})")
        typer.echo(f"    Hours: {ps.total_hours:.2f}h")

        if ps.budget_percent is not None:
            bar = _format_budget_bar(ps.budget_percent)
            budget_label = ""
            if ps.budget_weekly is not None:
                budget_label = f" / {ps.budget_weekly:.0f}h weekly"
            elif ps.budget_monthly is not None:
                budget_label = f" / {ps.budget_monthly:.0f}h monthly"
            typer.echo(f"    Budget: {bar}{budget_label}")

        if detail == "full":
            for day_detail in ps.days:
                typer.echo(f"    {day_detail.date}  {day_detail.total_hours:.2f}h")
                for entry in day_detail.entries:
                    tags_str = f"  [{', '.join(entry.tags)}]" if entry.tags else ""
                    typer.echo(f"      - {entry.short_summary} ({entry.hours:.2f}h){tags_str}")

        typer.echo("")

    typer.echo(f"Total: {report.total_hours:.2f}h")

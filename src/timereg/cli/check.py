"""CLI check command — gap and conflict detection across a date range."""

from __future__ import annotations

import calendar
import json
from datetime import date, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import typer

from timereg.cli.app import app, state
from timereg.core.checks import run_checks
from timereg.core.config import ensure_global_config, load_global_config
from timereg.core.projects import list_projects

if TYPE_CHECKING:
    from timereg.core.models import CheckReport


def _resolve_date_range(
    period: str | None,
    date_from: date | None,
    date_to: date | None,
    reference_date: date | None,
) -> tuple[date, date]:
    """Resolve the date range from period + reference_date or explicit bounds."""
    if date_from is not None and date_to is not None:
        return date_from, date_to

    ref = reference_date or date.today()

    if period == "day":
        return ref, ref
    if period == "week":
        monday = ref - timedelta(days=ref.weekday())
        friday = monday + timedelta(days=4)
        return monday, friday
    if period == "month":
        _, last_day = calendar.monthrange(ref.year, ref.month)
        return date(ref.year, ref.month, 1), date(ref.year, ref.month, last_day)

    # Default: week
    monday = ref - timedelta(days=ref.weekday())
    friday = monday + timedelta(days=4)
    return monday, friday


@app.command()
def check(
    week: Annotated[bool, typer.Option("--week", help="Check weekly period")] = False,
    month: Annotated[bool, typer.Option("--month", help="Check monthly period")] = False,
    day: Annotated[bool, typer.Option("--day", help="Check single day")] = False,
    date_from: Annotated[str | None, typer.Option("--from", help="Start date (YYYY-MM-DD)")] = None,
    date_to: Annotated[str | None, typer.Option("--to", help="End date (YYYY-MM-DD)")] = None,
    date_str: Annotated[
        str | None, typer.Option("--date", help="Reference date (YYYY-MM-DD)")
    ] = None,
) -> None:
    """Run gap and conflict detection checks."""
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
    else:
        period = "week"  # default

    # Parse dates
    reference_date = date.fromisoformat(date_str) if date_str else None
    from_date = date.fromisoformat(date_from) if date_from else None
    to_date = date.fromisoformat(date_to) if date_to else None

    # Resolve period to date range
    resolved_from, resolved_to = _resolve_date_range(
        period=period if from_date is None or to_date is None else None,
        date_from=from_date,
        date_to=to_date,
        reference_date=reference_date,
    )

    # Get projects and repo paths
    projects = list_projects(state.db)

    repo_paths_by_project: dict[int, list[Path]] = {}
    for p in projects:
        if p.id is not None:
            rows = state.db.execute(
                "SELECT absolute_path FROM project_repos WHERE project_id=?",
                (p.id,),
            ).fetchall()
            if rows:
                repo_paths_by_project[p.id] = [Path(r[0]) for r in rows]

    # Resolve user email and max_daily_hours from global config
    user_email = "unknown"
    max_daily_hours = 12.0
    try:
        global_config = load_global_config(ensure_global_config())
        if global_config.user_email:
            user_email = global_config.user_email
        if global_config.max_daily_hours is not None:
            max_daily_hours = global_config.max_daily_hours
    except Exception:
        pass

    report = run_checks(
        db=state.db,
        projects=projects,
        repo_paths_by_project=repo_paths_by_project,
        user_email=user_email,
        date_from=resolved_from,
        date_to=resolved_to,
        max_daily_hours=max_daily_hours,
    )

    if state.output_format == "json":
        typer.echo(json.dumps(report.model_dump(mode="json"), indent=2, default=str))
        return

    _print_text_output(report)


def _print_text_output(report: CheckReport) -> None:
    """Print check report as formatted text."""

    # Header with date range
    start_str = report.date_from.strftime("%b %d")
    end_str = report.date_to.strftime("%b %d, %Y")
    typer.echo(f"Check: {start_str} - {end_str}")
    typer.echo("")

    # Per-day results
    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    for dc in report.days:
        day_name = day_names[dc.date.weekday()]
        date_str = dc.date.strftime("%b %d")
        hours_str = f"{dc.total_hours:.1f}h"

        if dc.ok:
            status = "ok"
        else:
            # Pick the first warning as inline status
            warning_text = dc.warnings[0] if dc.warnings else "warning"
            # Simplify the warning for inline display
            if "no hours" in warning_text.lower():
                status = "! No hours registered"
            elif "seems high" in warning_text.lower():
                status = f"! {dc.total_hours:.1f}h registered (seems high)"
            elif "unregistered commits" in warning_text.lower():
                status = f"! {warning_text}"
            else:
                status = f"! {warning_text}"

        typer.echo(f"  {day_name} {date_str}  {hours_str:>6}  {status}")

    typer.echo("")
    typer.echo(f"Summary: {report.summary_total:.1f}h total")

    # Budget warnings
    if report.budget_warnings:
        typer.echo("")
        typer.echo("Budget:")
        for bw in report.budget_warnings:
            if "over budget" in bw.lower():
                typer.echo(f"  {bw}")
            else:
                typer.echo(f"  {bw}")

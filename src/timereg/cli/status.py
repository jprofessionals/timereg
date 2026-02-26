"""CLI status command — show status dashboard across all projects."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import typer

from timereg.cli.app import app, state
from timereg.core.checks import get_status
from timereg.core.config import load_global_config
from timereg.core.projects import list_projects

if TYPE_CHECKING:
    from timereg.core.models import StatusReport


def _format_budget_bar(percent: float, width: int = 20) -> str:
    """Render a simple ASCII budget bar like [=========>          ] 50%."""
    filled = round(percent / 100 * width)
    filled = min(filled, width)
    bar = "=" * filled
    if filled < width:
        bar += ">"
        bar = bar[:width]
    empty = width - len(bar)
    return f"[{bar}{' ' * empty}] {percent:.0f}%"


@app.command()
def status(
    date_str: Annotated[
        str | None, typer.Option("--date", help="Reference date (YYYY-MM-DD)")
    ] = None,
) -> None:
    """Show status dashboard across all projects."""
    target_date = date.fromisoformat(date_str) if date_str else date.today()

    projects = list_projects(state.db)
    if not projects:
        if state.output_format == "json":
            typer.echo(
                json.dumps(
                    {"date": target_date.isoformat(), "projects": [], "warnings": []},
                    indent=2,
                )
            )
        else:
            typer.echo("No projects registered.")
        return

    # Get repo paths per project from project_repos table
    repo_paths_by_project: dict[int, list[Path]] = {}
    for p in projects:
        if p.id is not None:
            rows = state.db.execute(
                "SELECT absolute_path FROM project_repos WHERE project_id=?",
                (p.id,),
            ).fetchall()
            if rows:
                repo_paths_by_project[p.id] = [Path(r[0]) for r in rows]

    # Resolve user email: try global config, fall back to "unknown"
    user_email = "unknown"
    try:
        from timereg.core.config import ensure_global_config

        global_config = load_global_config(ensure_global_config())
        if global_config.user_email:
            user_email = global_config.user_email
    except Exception:
        pass

    report = get_status(
        db=state.db,
        projects=projects,
        repo_paths_by_project=repo_paths_by_project,
        user_email=user_email,
        target_date=target_date,
    )

    if state.output_format == "json":
        typer.echo(json.dumps(report.model_dump(mode="json"), indent=2, default=str))
        return

    _print_text_output(report)


def _print_text_output(report: StatusReport) -> None:
    """Print status report as formatted text."""
    typer.echo(f"Status for {report.date}")
    typer.echo("")

    if not report.projects:
        typer.echo("No entries found.")
        return

    for ps in report.projects:
        typer.echo(f"  {ps.project.name} ({ps.project.slug})")
        typer.echo(f"    Today: {ps.today_hours:.2f}h ({ps.today_entry_count} entries)")
        typer.echo(f"    Week:  {ps.week_hours:.2f}h")

        if ps.unregistered_commits > 0:
            typer.echo(f"    Unregistered commits: {ps.unregistered_commits}")

        if ps.budget_percent is not None and ps.budget_weekly is not None:
            bar = _format_budget_bar(ps.budget_percent)
            typer.echo(f"    Budget: {bar} ({ps.week_hours:.1f}h / {ps.budget_weekly:.0f}h weekly)")

        typer.echo("")

    if report.warnings:
        typer.echo("Warnings:")
        for w in report.warnings:
            typer.echo(f"  - {w}")
        typer.echo("")

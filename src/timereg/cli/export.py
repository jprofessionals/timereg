"""CLI export command — CSV and JSON export of time entries."""

from __future__ import annotations

from datetime import date
from typing import Annotated

import typer

from timereg.cli.app import app, state
from timereg.core.export import export_entries
from timereg.core.projects import get_project


@app.command()
def export(
    project_slug: Annotated[
        str | None, typer.Option("--project", help="Filter by project slug")
    ] = None,
    date_from: Annotated[str | None, typer.Option("--from", help="Start date (YYYY-MM-DD)")] = None,
    date_to: Annotated[str | None, typer.Option("--to", help="End date (YYYY-MM-DD)")] = None,
    export_format: Annotated[
        str, typer.Option("--export-format", help="Export format: csv or json")
    ] = "csv",
) -> None:
    """Export time entries as CSV or JSON."""
    # Resolve project
    project_id: int | None = None
    if project_slug:
        project = get_project(state.db, project_slug)
        if project is None:
            typer.echo(f"Error: Project '{project_slug}' not found.", err=True)
            raise typer.Exit(1)
        project_id = project.id

    # Parse dates
    from_date = date.fromisoformat(date_from) if date_from else None
    to_date = date.fromisoformat(date_to) if date_to else None

    # Export and print
    output = export_entries(
        db=state.db,
        format=export_format,
        project_id=project_id,
        date_from=from_date,
        date_to=to_date,
    )
    typer.echo(output, nl=False)

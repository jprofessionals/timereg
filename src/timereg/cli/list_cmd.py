"""CLI list command — display time entries."""

from __future__ import annotations

import json
from datetime import date
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from timereg.cli import entry_to_dict
from timereg.cli.app import app, state
from timereg.core.config import find_project_config, load_project_config
from timereg.core.entries import list_entries
from timereg.core.projects import auto_register_project, get_project

console = Console()


@app.command("list")
def list_cmd(
    date_str: Annotated[
        str | None, typer.Option("--date", help="Filter by exact date (YYYY-MM-DD)")
    ] = None,
    date_from: Annotated[str | None, typer.Option("--from", help="Start date (YYYY-MM-DD)")] = None,
    date_to: Annotated[str | None, typer.Option("--to", help="End date (YYYY-MM-DD)")] = None,
    project_slug: Annotated[
        str | None, typer.Option("--project", help="Filter by project slug")
    ] = None,
    all_projects: Annotated[
        bool, typer.Option("--all", help="Show entries across all projects")
    ] = False,
    detail: Annotated[str, typer.Option("--detail", help="Detail level: brief or full")] = "brief",
) -> None:
    """List time entries with optional filters."""
    # Resolve project
    project_id: int | None = None

    if project_slug:
        project = get_project(state.db, project_slug)
        if project is None:
            typer.echo(f"Error: Project '{project_slug}' not found.", err=True)
            raise typer.Exit(1)
        project_id = project.id
    elif not all_projects:
        config_path = find_project_config()
        if config_path is not None:
            project_config = load_project_config(config_path)
            config_dir = config_path.parent
            repo_paths = project_config.resolve_repo_paths(config_dir)
            project = auto_register_project(state.db, project_config, config_path, repo_paths)
            project_id = project.id

    # Parse date filters
    date_filter = date.fromisoformat(date_str) if date_str else None
    from_filter = date.fromisoformat(date_from) if date_from else None
    to_filter = date.fromisoformat(date_to) if date_to else None

    entries = list_entries(
        db=state.db,
        project_id=project_id,
        date_filter=date_filter,
        date_from=from_filter,
        date_to=to_filter,
        all_projects=all_projects,
    )

    if state.output_format == "json":
        typer.echo(json.dumps([entry_to_dict(e) for e in entries], indent=2))
        return

    if not entries:
        typer.echo("No entries found.")
        return

    table = Table(title="Time Entries")
    table.add_column("ID", style="cyan", justify="right")
    table.add_column("Date", style="green")
    table.add_column("Hours", style="yellow", justify="right")
    table.add_column("Summary")
    table.add_column("Tags", style="magenta")
    table.add_column("Type", style="blue")

    if detail == "full":
        table.add_column("Long Summary")

    for entry in entries:
        tags_str = ", ".join(entry.tags) if entry.tags else ""
        row = [
            str(entry.id or ""),
            str(entry.date),
            f"{entry.hours:.2f}",
            entry.short_summary,
            tags_str,
            entry.entry_type,
        ]
        if detail == "full":
            row.append(entry.long_summary or "")
        table.add_row(*row)

    total_hours = sum(e.hours for e in entries)
    console.print(table)
    typer.echo(f"\nTotal: {total_hours:.2f}h across {len(entries)} entries")

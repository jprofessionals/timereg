"""Interactive mode — prompt-driven time registration when no subcommand is given."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

import typer
from rich.console import Console
from rich.table import Table

from timereg.core.entries import create_entry
from timereg.core.projects import add_project, list_projects, slugify
from timereg.core.time_parser import parse_time

if TYPE_CHECKING:
    from timereg.core.database import Database

console = Console()


def run_interactive(db: Database) -> None:
    """Run the interactive time registration flow."""
    console.print("\n[bold]TimeReg — Interactive Registration[/bold]\n")

    # Step 1: Select or create a project
    projects = list_projects(db)

    if not projects:
        console.print("No projects registered yet. Let's create one.\n")
        project_name = typer.prompt("Project name")
        suggested_slug = slugify(project_name)
        project_slug = typer.prompt("Project slug (lowercase, hyphens)", default=suggested_slug)
        try:
            project = add_project(db, name=project_name, slug=project_slug)
        except ValueError as e:
            typer.echo(f"Error: {e}", err=True)
            raise typer.Exit(1) from None
        console.print(f"Created project: [bold]{project.name}[/bold] ({project.slug})\n")
    elif len(projects) == 1:
        project = projects[0]
        console.print(f"Using project: [bold]{project.name}[/bold] ({project.slug})\n")
    else:
        table = Table(title="Projects")
        table.add_column("#", justify="right", style="dim")
        table.add_column("Name")
        table.add_column("Slug")
        for i, p in enumerate(projects, 1):
            table.add_row(str(i), p.name, p.slug)
        console.print(table)
        console.print()

        choice = typer.prompt("Select project number", type=int)
        if choice < 1 or choice > len(projects):
            typer.echo("Error: Invalid project number.", err=True)
            raise typer.Exit(1)
        project = projects[choice - 1]
        console.print(f"Selected: [bold]{project.name}[/bold]\n")

    # Step 2: Date
    today = date.today().isoformat()
    date_str = typer.prompt("Date", default=today)
    try:
        entry_date = date.fromisoformat(date_str)
    except ValueError:
        typer.echo(f"Error: Invalid date format: {date_str!r}", err=True)
        raise typer.Exit(1) from None

    # Step 3: Hours
    hours_str = typer.prompt("Hours (e.g. 2h30m, 1.5, 90m)")
    try:
        hours = parse_time(hours_str)
    except ValueError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1) from None

    # Step 4: Description
    short_summary = typer.prompt("Description")
    if not short_summary.strip():
        typer.echo("Error: Description cannot be empty.", err=True)
        raise typer.Exit(1)

    # Step 5: Tags (optional)
    tags_str = typer.prompt("Tags (comma-separated, optional)", default="")
    tag_list: list[str] | None = None
    if tags_str.strip():
        tag_list = [t.strip() for t in tags_str.split(",") if t.strip()]

    # Create the entry
    project_id = project.id or 0
    entry = create_entry(
        db=db,
        project_id=project_id,
        hours=hours,
        short_summary=short_summary.strip(),
        entry_date=entry_date,
        git_user_name="Interactive",
        git_user_email="interactive@local",
        entry_type="manual",
        tags=tag_list,
    )

    # Confirmation
    if isinstance(entry, list):
        entry = entry[0]
    console.print()
    msg = f"[green bold]Registered {hours}h for {project.name} on {entry_date}[/green bold]"
    console.print(msg)
    console.print(f"  Entry ID: {entry.id}")
    console.print(f"  Summary: {short_summary.strip()}")
    if tag_list:
        console.print(f"  Tags: {', '.join(tag_list)}")

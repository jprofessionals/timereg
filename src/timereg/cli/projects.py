"""CLI projects subcommands — manage project registry."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Annotated

import typer
from rich.console import Console
from rich.table import Table

from timereg.cli.app import app, state
from timereg.core.projects import add_project, get_project, list_projects, remove_project

if TYPE_CHECKING:
    from timereg.core.models import Project

projects_app = typer.Typer(help="Manage projects")
app.add_typer(projects_app, name="projects")

console = Console()


def _project_to_dict(project: Project) -> dict[str, object]:
    """Convert a Project to a JSON-serialisable dict."""
    d = project.model_dump()
    if d.get("created_at"):
        d["created_at"] = str(d["created_at"])
    if d.get("updated_at"):
        d["updated_at"] = str(d["updated_at"])
    return d


@projects_app.command("list")
def list_projects_cmd() -> None:
    """List all registered projects."""
    projects = list_projects(state.db)

    if state.output_format == "json":
        typer.echo(json.dumps([_project_to_dict(p) for p in projects], indent=2))
        return

    if not projects:
        typer.echo("No projects registered.")
        return

    table = Table(title="Projects")
    table.add_column("ID", style="cyan", justify="right")
    table.add_column("Name", style="green")
    table.add_column("Slug", style="yellow")
    table.add_column("Config Path")

    for p in projects:
        table.add_row(
            str(p.id or ""),
            p.name,
            p.slug,
            p.config_path or "",
        )

    console.print(table)


@projects_app.command("add")
def add_project_cmd(
    name: Annotated[str, typer.Option("--name", help="Project display name")],
    slug: Annotated[str, typer.Option("--slug", help="Project slug (lowercase, hyphens)")],
) -> None:
    """Manually add a project to the registry."""
    try:
        project = add_project(state.db, name=name, slug=slug)
    except ValueError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1) from None

    if state.output_format == "json":
        typer.echo(json.dumps(_project_to_dict(project), indent=2))
    else:
        typer.echo(f"Added project '{project.name}' ({project.slug})")
        typer.echo(f"  ID: {project.id}")


@projects_app.command("remove")
def remove_project_cmd(
    slug: Annotated[str, typer.Argument(help="Project slug to remove")],
    keep_entries: Annotated[
        bool,
        typer.Option(
            "--keep-entries/--delete-entries",
            help="Keep or delete associated entries",
        ),
    ] = True,
) -> None:
    """Remove a project from the registry."""
    try:
        remove_project(state.db, slug=slug, keep_entries=keep_entries)
    except ValueError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1) from None

    if state.output_format == "json":
        typer.echo(json.dumps({"removed": slug, "kept_entries": keep_entries}))
    else:
        typer.echo(f"Removed project '{slug}'")
        if keep_entries:
            typer.echo("  (entries preserved)")
        else:
            typer.echo("  (entries deleted)")


@projects_app.command("show")
def show_project_cmd(
    slug: Annotated[str, typer.Argument(help="Project slug to show")],
) -> None:
    """Show details for a single project."""
    project = get_project(state.db, slug)
    if project is None:
        typer.echo(f"Error: Project '{slug}' not found.", err=True)
        raise typer.Exit(1)

    # Get repo paths
    repos = state.db.execute(
        "SELECT absolute_path, relative_path FROM project_repos WHERE project_id=?",
        (project.id,),
    ).fetchall()

    if state.output_format == "json":
        d = _project_to_dict(project)
        d["repos"] = [{"absolute_path": r[0], "relative_path": r[1]} for r in repos]
        typer.echo(json.dumps(d, indent=2))
    else:
        typer.echo(f"Project: {project.name}")
        typer.echo(f"  Slug: {project.slug}")
        typer.echo(f"  ID: {project.id}")
        if project.config_path:
            typer.echo(f"  Config: {project.config_path}")
        if repos:
            typer.echo("  Repos:")
            for r in repos:
                typer.echo(f"    {r[1]} ({r[0]})")
        else:
            typer.echo("  Repos: (none)")

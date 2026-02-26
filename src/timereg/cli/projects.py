"""CLI projects subcommands — manage project registry."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import typer
from rich.console import Console
from rich.table import Table

from timereg.cli.app import app, state
from timereg.core.config import CONFIG_FILENAME, find_project_config, load_project_config
from timereg.core.projects import (
    add_project,
    auto_register_project,
    list_projects,
    remove_project,
    resolve_project,
)

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
    path: Annotated[
        str | None, typer.Argument(help="Path to project directory with .timereg.toml (e.g. '.')")
    ] = None,
    name: Annotated[str | None, typer.Option("--name", help="Project display name")] = None,
    slug: Annotated[
        str | None, typer.Option("--slug", help="Project slug (lowercase, hyphens)")
    ] = None,
) -> None:
    """Add a project to the registry.

    With a path argument (e.g. 'timereg projects add .'), reads the .timereg.toml
    config and registers the project with its repos.

    With --name and --slug, creates a manual project entry without config or repos.
    """
    if path is not None:
        _add_from_config(path)
    elif name is not None and slug is not None:
        _add_manual(name, slug)
    else:
        typer.echo(
            "Error: Provide a path to a project directory, or both --name and --slug.",
            err=True,
        )
        raise typer.Exit(1)


def _add_from_config(path_str: str) -> None:
    """Register a project from its .timereg.toml config file."""
    project_dir = Path(path_str).resolve()
    config_path = find_project_config(project_dir)
    if config_path is None:
        typer.echo(
            f"Error: No {CONFIG_FILENAME} found in {project_dir} or parent directories.",
            err=True,
        )
        raise typer.Exit(1)

    project_config = load_project_config(config_path)
    config_dir = config_path.parent
    repo_paths = project_config.resolve_repo_paths(config_dir)

    project = auto_register_project(state.db, project_config, config_path, repo_paths)

    if state.output_format == "json":
        typer.echo(json.dumps(_project_to_dict(project), indent=2))
    else:
        typer.echo(f"Registered project '{project.name}' ({project.slug})")
        typer.echo(f"  ID: {project.id}")
        typer.echo(f"  Config: {config_path}")
        if repo_paths:
            typer.echo(f"  Repos: {len(repo_paths)}")
            for rp in repo_paths:
                typer.echo(f"    {rp}")


def _add_manual(name: str, slug: str) -> None:
    """Add a manual project entry without config or repos."""
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
    identifier: Annotated[str, typer.Argument(help="Project ID, slug, or name")],
    keep_entries: Annotated[
        bool,
        typer.Option(
            "--keep-entries/--delete-entries",
            help="Keep or delete associated entries",
        ),
    ] = True,
) -> None:
    """Remove a project from the registry."""
    project = resolve_project(state.db, identifier)
    if project is None:
        typer.echo(f"Error: Project '{identifier}' not found.", err=True)
        raise typer.Exit(1)
    try:
        remove_project(state.db, slug=project.slug, keep_entries=keep_entries)
    except ValueError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1) from None

    if state.output_format == "json":
        typer.echo(json.dumps({"removed": project.slug, "kept_entries": keep_entries}))
    else:
        typer.echo(f"Removed project '{project.name}' ({project.slug})")
        if keep_entries:
            typer.echo("  (entries preserved)")
        else:
            typer.echo("  (entries deleted)")


@projects_app.command("show")
def show_project_cmd(
    identifier: Annotated[str, typer.Argument(help="Project ID, slug, or name")],
) -> None:
    """Show details for a single project."""
    project = resolve_project(state.db, identifier)
    if project is None:
        typer.echo(f"Error: Project '{identifier}' not found.", err=True)
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

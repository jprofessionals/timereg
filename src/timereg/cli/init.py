"""CLI init command — create .timereg.toml in the current directory."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from timereg.cli.app import app
from timereg.core.config import CONFIG_FILENAME
from timereg.core.projects import slugify


@app.command()
def init(
    name: Annotated[str | None, typer.Option("--name", help="Project name")] = None,
    slug: Annotated[str | None, typer.Option("--slug", help="Project slug")] = None,
    yes: Annotated[
        bool, typer.Option("--yes", "-y", help="Accept defaults without prompting")
    ] = False,
) -> None:
    """Initialize a .timereg.toml in the current directory."""
    config_path = Path.cwd() / CONFIG_FILENAME

    if config_path.exists():
        typer.echo(f"Error: {CONFIG_FILENAME} already exists in this directory.", err=True)
        raise typer.Exit(1)

    # Derive defaults from directory name
    dir_name = Path.cwd().name

    if yes:
        # Non-interactive: use flags or defaults
        project_name = name or dir_name
        project_slug = slug or slugify(project_name)
    else:
        # Interactive: prompt with defaults, allowing flags to override defaults
        project_name = typer.prompt("Project name", default=name or dir_name)
        project_slug = typer.prompt("Project slug", default=slug or slugify(project_name))

    config_text = (
        "[project]\n"
        f'name = "{project_name}"\n'
        f'slug = "{project_slug}"\n'
        "\n"
        "[repos]\n"
        'paths = ["."]\n'
        "\n"
        "# [budget]\n"
        "# weekly_hours = 37.5\n"
        "# monthly_hours = 150.0\n"
        "\n"
        "# [tags]\n"
        '# allowed = ["development", "review", "meeting", "planning", "bugfix"]\n'
    )

    config_path.write_text(config_text)
    typer.echo(f"\nCreated {CONFIG_FILENAME} in {Path.cwd()}")
    typer.echo(f"  Project: {project_name} ({project_slug})")
    typer.echo("\nEdit the file to customize repos, budget, and tag constraints.")

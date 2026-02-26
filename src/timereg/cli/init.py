"""CLI init command — create .timetracker.toml in the current directory."""

from __future__ import annotations

from pathlib import Path

import typer

from timereg.cli.app import app
from timereg.core.config import CONFIG_FILENAME
from timereg.core.projects import slugify


@app.command()
def init() -> None:
    """Initialize a .timetracker.toml in the current directory."""
    config_path = Path.cwd() / CONFIG_FILENAME

    if config_path.exists():
        typer.echo(f"Error: {CONFIG_FILENAME} already exists in this directory.", err=True)
        raise typer.Exit(1)

    # Derive defaults from directory name
    dir_name = Path.cwd().name

    name = typer.prompt("Project name", default=dir_name)
    slug = typer.prompt("Project slug", default=slugify(name))

    config_text = (
        "[project]\n"
        f'name = "{name}"\n'
        f'slug = "{slug}"\n'
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
    typer.echo(f"  Project: {name} ({slug})")
    typer.echo("\nEdit the file to customize repos, budget, and tag constraints.")

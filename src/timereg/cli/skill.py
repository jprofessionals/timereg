"""CLI skill command — output bundled agent skill file."""

from __future__ import annotations

import importlib.resources
from typing import Annotated

import typer

from timereg.cli.app import app


@app.command()
def skill(
    path: Annotated[
        bool, typer.Option("--path", help="Print the path to the bundled skill file")
    ] = False,
) -> None:
    """Output the bundled agent skill file.

    Prints the skill definition to stdout so it can be piped to any
    agent's config directory. For example:

        timereg skill > ~/.claude/skills/timereg/SKILL.md
    """
    ref = importlib.resources.files("timereg.data").joinpath("SKILL.md")
    if path:
        with importlib.resources.as_file(ref) as p:
            typer.echo(str(p))
    else:
        typer.echo(ref.read_text(encoding="utf-8"), nl=False)

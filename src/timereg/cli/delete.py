"""CLI delete command — remove a time entry."""

from __future__ import annotations

import json
from typing import Annotated

import typer

from timereg.cli.app import app, state
from timereg.core.entries import delete_entry


@app.command()
def delete(
    entry_id: Annotated[int, typer.Argument(help="Entry ID to delete")],
    release_commits: Annotated[
        bool,
        typer.Option("--release-commits/--keep-commits", help="Release or keep commits as claimed"),
    ] = True,
    delete_peers: Annotated[
        bool, typer.Option("--delete-peers", help="Also delete peer entries")
    ] = False,
) -> None:
    """Delete a time entry."""
    try:
        delete_entry(
            db=state.db,
            entry_id=entry_id,
            release_commits=release_commits,
            delete_peers=delete_peers,
        )
    except ValueError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1) from None

    if state.output_format == "json":
        typer.echo(json.dumps({"deleted": entry_id, "delete_peers": delete_peers}))
    else:
        typer.echo(f"Deleted entry {entry_id}")
        if delete_peers:
            typer.echo("  (peer entries also deleted)")

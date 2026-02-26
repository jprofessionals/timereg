"""CLI edit command — modify an existing time entry."""

from __future__ import annotations

import json
from datetime import date
from typing import Annotated

import typer

from timereg.cli import entry_to_dict
from timereg.cli.app import app, state
from timereg.core.entries import edit_entry
from timereg.core.time_parser import parse_time


@app.command()
def edit(
    entry_id: Annotated[int, typer.Argument(help="Entry ID to edit")],
    hours: Annotated[str | None, typer.Option("--hours", help="New time (e.g. 2h30m, 1.5)")] = None,
    short_summary: Annotated[
        str | None, typer.Option("--short-summary", help="New short summary")
    ] = None,
    long_summary: Annotated[
        str | None, typer.Option("--long-summary", help="New long summary")
    ] = None,
    tags: Annotated[str | None, typer.Option("--tags", help="New comma-separated tags")] = None,
    date_str: Annotated[str | None, typer.Option("--date", help="New date (YYYY-MM-DD)")] = None,
    apply_to_peers: Annotated[
        bool, typer.Option("--apply-to-peers", help="Apply changes to peer entries")
    ] = False,
) -> None:
    """Edit an existing time entry."""
    # Parse hours if provided
    parsed_hours: float | None = None
    if hours is not None:
        try:
            parsed_hours = parse_time(hours)
        except ValueError as e:
            typer.echo(f"Error: {e}", err=True)
            raise typer.Exit(1) from None

    # Parse tags
    tag_list: list[str] | None = None
    if tags is not None:
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]

    # Parse date
    entry_date = date.fromisoformat(date_str) if date_str else None

    try:
        updated = edit_entry(
            db=state.db,
            entry_id=entry_id,
            hours=parsed_hours,
            short_summary=short_summary,
            long_summary=long_summary,
            tags=tag_list,
            entry_date=entry_date,
            apply_to_peers=apply_to_peers,
        )
    except ValueError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1) from None

    if state.output_format == "json":
        typer.echo(json.dumps(entry_to_dict(updated), indent=2))
    else:
        typer.echo(f"Updated entry {updated.id}")
        typer.echo(f"  Date: {updated.date}")
        typer.echo(f"  Hours: {updated.hours:.2f}")
        typer.echo(f"  Summary: {updated.short_summary}")
        if updated.tags:
            typer.echo(f"  Tags: {', '.join(updated.tags)}")

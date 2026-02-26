"""CLI delete command — remove a time entry."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Annotated

import typer
from rich.console import Console
from rich.table import Table

from timereg.cli.app import app, state
from timereg.core.entries import delete_entry, get_entry
from timereg.core.projects import get_project_by_id

if TYPE_CHECKING:
    from timereg.core.models import Entry

console = Console()


@app.command()
def delete(
    entry_ids: Annotated[list[int], typer.Argument(help="Entry ID(s) to delete")],
    release_commits: Annotated[
        bool,
        typer.Option("--release-commits/--keep-commits", help="Release or keep commits as claimed"),
    ] = True,
    delete_peers: Annotated[
        bool, typer.Option("--delete-peers", help="Also delete peer entries")
    ] = False,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation prompt")] = False,
) -> None:
    """Delete one or more time entries."""
    # Look up all entries first
    entries: list[Entry] = []
    for entry_id in entry_ids:
        entry = get_entry(state.db, entry_id)
        if entry is None:
            typer.echo(f"Error: Entry {entry_id} not found", err=True)
            raise typer.Exit(1)
        entries.append(entry)

    # Show what will be deleted and ask for confirmation
    # Skip confirmation in JSON mode (machine/agent usage) or with --yes
    if not yes and state.output_format != "json":
        n = len(entries)
        typer.echo(f"\nThis will delete {n} {'entry' if n == 1 else 'entries'}:\n")

        table = Table()
        table.add_column("ID", style="cyan", justify="right")
        table.add_column("Project", style="dim")
        table.add_column("Date", style="green")
        table.add_column("Hours", style="yellow", justify="right")
        table.add_column("Summary")
        table.add_column("Tags", style="magenta")

        for entry in entries:
            project = get_project_by_id(state.db, entry.project_id)
            project_name = project.name if project else "?"
            tags_str = ", ".join(entry.tags) if entry.tags else ""
            table.add_row(
                str(entry.id or ""),
                project_name,
                str(entry.date),
                f"{entry.hours:.2f}",
                entry.short_summary,
                tags_str,
            )

        console.print(table)
        typer.echo("")

        if not typer.confirm("Are you sure?"):
            typer.echo("Aborted.")
            raise typer.Exit(0)

    # Perform the deletions
    deleted: list[int] = []
    for entry_id in entry_ids:
        try:
            delete_entry(
                db=state.db,
                entry_id=entry_id,
                release_commits=release_commits,
                delete_peers=delete_peers,
            )
            deleted.append(entry_id)
        except ValueError as e:
            typer.echo(f"Error: {e}", err=True)
            raise typer.Exit(1) from None

    if state.output_format == "json":
        typer.echo(json.dumps({"deleted": deleted, "delete_peers": delete_peers}))
    else:
        ids_str = ", ".join(str(i) for i in deleted)
        typer.echo(
            f"Deleted {len(deleted)} {'entry' if len(deleted) == 1 else 'entries'}: {ids_str}"
        )
        if delete_peers:
            typer.echo("  (peer entries also deleted)")

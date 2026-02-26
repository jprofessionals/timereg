"""CLI undo command — undo the last time entry."""

from __future__ import annotations

import json
import subprocess

import typer

from timereg.cli.app import app, state
from timereg.core.config import find_project_config, load_project_config
from timereg.core.entries import undo_last
from timereg.core.git import resolve_git_user
from timereg.core.models import Entry, GitUser


def _entry_to_dict(entry: Entry) -> dict[str, object]:
    """Convert an Entry to a JSON-serialisable dict."""
    d = entry.model_dump()
    d["date"] = str(d["date"])
    if d.get("created_at"):
        d["created_at"] = str(d["created_at"])
    if d.get("updated_at"):
        d["updated_at"] = str(d["updated_at"])
    return d


@app.command()
def undo() -> None:
    """Undo the last time entry by the current git user."""
    # Resolve git user to find their last entry
    user: GitUser
    config_path = find_project_config()
    if config_path is not None:
        project_config = load_project_config(config_path)
        config_dir = config_path.parent
        repo_paths = project_config.resolve_repo_paths(config_dir)
        try:
            user = resolve_git_user(str(repo_paths[0]))
        except (subprocess.CalledProcessError, IndexError):
            user = GitUser(name="Unknown", email="unknown@unknown")
    else:
        user = GitUser(name="Unknown", email="unknown@unknown")

    undone = undo_last(state.db, user.email)

    if undone is None:
        if state.output_format == "json":
            typer.echo(json.dumps({"undone": None}))
        else:
            typer.echo("Nothing to undo.")
        return

    if state.output_format == "json":
        typer.echo(json.dumps({"undone": _entry_to_dict(undone)}, indent=2))
    else:
        typer.echo(f"Undone entry {undone.id}")
        typer.echo(f"  Date: {undone.date}")
        typer.echo(f"  Hours: {undone.hours:.2f}")
        typer.echo(f"  Summary: {undone.short_summary}")

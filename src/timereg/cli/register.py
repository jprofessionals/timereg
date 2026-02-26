"""CLI register command — create a time registration entry."""

from __future__ import annotations

import json
import subprocess
from datetime import date
from typing import TYPE_CHECKING, Annotated

import typer

from timereg.cli.app import app, state
from timereg.core.config import find_project_config, load_project_config
from timereg.core.entries import create_entry
from timereg.core.git import resolve_git_user
from timereg.core.models import CommitInfo, GitUser
from timereg.core.projects import auto_register_project, get_project
from timereg.core.time_parser import parse_time

if TYPE_CHECKING:
    from timereg.core.models import Entry


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
def register(
    hours: Annotated[str, typer.Option("--hours", help="Time to register (e.g. 2h30m, 1.5)")],
    short_summary: Annotated[
        str, typer.Option("--short-summary", help="Short summary (2-10 words)")
    ],
    long_summary: Annotated[
        str | None, typer.Option("--long-summary", help="Detailed summary (20-100 words)")
    ] = None,
    commits: Annotated[
        str | None, typer.Option("--commits", help="Comma-separated commit hashes")
    ] = None,
    tags: Annotated[str | None, typer.Option("--tags", help="Comma-separated tags")] = None,
    peer: Annotated[
        list[str] | None, typer.Option("--peer", help="Peer email (repeatable)")
    ] = None,
    date_str: Annotated[
        str | None, typer.Option("--date", help="Date (YYYY-MM-DD), default today")
    ] = None,
    project_slug: Annotated[str | None, typer.Option("--project", help="Project slug")] = None,
    entry_type: Annotated[
        str | None,
        typer.Option("--entry-type", help="Entry type: git or manual"),
    ] = None,
) -> None:
    """Register a time entry for a project."""
    # Parse hours
    try:
        parsed_hours = parse_time(hours)
    except ValueError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1) from None

    # Resolve date
    entry_date = date.fromisoformat(date_str) if date_str else date.today()

    # Parse commits
    commit_hashes: list[str] = []
    if commits:
        commit_hashes = [h.strip() for h in commits.split(",") if h.strip()]

    # Resolve entry type
    resolved_type = entry_type or ("git" if commit_hashes else "manual")
    if resolved_type not in ("git", "manual"):
        typer.echo(f"Error: entry-type must be 'git' or 'manual', got '{resolved_type}'", err=True)
        raise typer.Exit(1)

    # Parse tags
    tag_list: list[str] | None = None
    if tags:
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]

    # Resolve project
    project = None
    config_path = find_project_config()

    if project_slug:
        project = get_project(state.db, project_slug)
        if project is None:
            typer.echo(f"Error: Project '{project_slug}' not found.", err=True)
            raise typer.Exit(1)
    elif config_path is not None:
        project_config = load_project_config(config_path)
        config_dir = config_path.parent
        repo_paths = project_config.resolve_repo_paths(config_dir)
        project = auto_register_project(state.db, project_config, config_path, repo_paths)
    else:
        typer.echo("Error: No .timetracker.toml found. Use --project to specify one.", err=True)
        raise typer.Exit(1)

    assert project is not None
    project_id = project.id or 0

    # Resolve git user
    user: GitUser
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

    # Build CommitInfo objects if commit hashes were provided
    commit_infos: list[CommitInfo] | None = None
    if commit_hashes:
        commit_infos = [
            CommitInfo(
                hash=h,
                message="",
                author_name=user.name,
                author_email=user.email,
                timestamp=entry_date.isoformat(),
                repo_path="",
            )
            for h in commit_hashes
        ]

    # Create the entry
    result = create_entry(
        db=state.db,
        project_id=project_id,
        hours=parsed_hours,
        short_summary=short_summary,
        entry_date=entry_date,
        git_user_name=user.name,
        git_user_email=user.email,
        entry_type=resolved_type,
        long_summary=long_summary,
        commits=commit_infos,
        tags=tag_list,
        peer_emails=peer,
    )

    # Output
    if state.output_format == "json":
        if isinstance(result, list):
            typer.echo(json.dumps([_entry_to_dict(e) for e in result], indent=2))
        else:
            typer.echo(json.dumps(_entry_to_dict(result), indent=2))
    else:
        if isinstance(result, list):
            primary = result[0]
            typer.echo(f"Registered {parsed_hours}h for {project.name} on {entry_date}")
            typer.echo(f"  Entry ID: {primary.id}")
            typer.echo(f"  Summary: {short_summary}")
            typer.echo(f"  Peers: {len(result) - 1} peer entries created")
        else:
            typer.echo(f"Registered {parsed_hours}h for {project.name} on {entry_date}")
            typer.echo(f"  Entry ID: {result.id}")
            typer.echo(f"  Summary: {short_summary}")
            if commit_hashes:
                typer.echo(f"  Commits: {len(commit_hashes)}")
            if tag_list:
                typer.echo(f"  Tags: {', '.join(tag_list)}")

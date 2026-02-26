"""CLI fetch command — retrieve unregistered commits."""

from __future__ import annotations

import json
import subprocess
from datetime import date
from typing import Annotated

import typer

from timereg.cli.app import app, state
from timereg.core.config import find_project_config, load_project_config, no_config_message
from timereg.core.entries import get_registered_commit_hashes
from timereg.core.git import fetch_project_commits, resolve_git_user
from timereg.core.models import FetchResult, GitUser, WorkingTreeStatus
from timereg.core.projects import auto_register_project


def _format_wt_status(wt: WorkingTreeStatus) -> str:
    """Format working tree status as a short string."""
    if wt.staged_files == 0 and wt.unstaged_files == 0:
        return "clean"
    parts: list[str] = []
    if wt.staged_files > 0:
        parts.append(f"{wt.staged_files} staged")
    if wt.unstaged_files > 0:
        parts.append(f"{wt.unstaged_files} unstaged")
    return ", ".join(parts)


def _format_stat(insertions: int, deletions: int, files_changed: int) -> str:
    """Format commit stat line like (+87 -12, 4 files)."""
    parts: list[str] = []
    if insertions > 0:
        parts.append(f"+{insertions}")
    if deletions > 0:
        parts.append(f"-{deletions}")
    if not parts:
        parts.append("+0")
    return f"({' '.join(parts)}, {files_changed} file{'s' if files_changed != 1 else ''})"


def _print_text_output(result: FetchResult) -> None:
    """Print fetch result as formatted text."""
    total_commits = sum(len(r.commits) for r in result.repos)
    typer.echo(f"Unregistered commits for {result.project_name} ({result.date}):\n")

    if not result.repos:
        typer.echo("  (no repos)")
        return

    for repo in result.repos:
        wt_label = _format_wt_status(repo.uncommitted)
        typer.echo(f"  {repo.relative_path} ({repo.branch}) - {wt_label}")
        if repo.commits:
            for c in repo.commits:
                stat = _format_stat(c.insertions, c.deletions, c.files_changed)
                typer.echo(f"    {c.hash[:8]}  {c.message}    {stat}")
        else:
            typer.echo("    (no commits)")
        typer.echo("")

    if total_commits == 0:
        typer.echo("  No unregistered commits found.")


@app.command()
def fetch(
    date_str: Annotated[
        str | None, typer.Option("--date", help="Date (YYYY-MM-DD), default today")
    ] = None,
    project_slug: Annotated[str | None, typer.Option("--project", help="Project slug")] = None,
    fetch_all: Annotated[
        bool, typer.Option("--all", help="Fetch across all registered projects")
    ] = False,
) -> None:
    """Fetch unregistered commits for a project."""
    target_date = date_str or date.today().isoformat()

    config_path = find_project_config()
    if config_path is None and project_slug is None and not fetch_all:
        typer.echo(f"Error: {no_config_message()}", err=True)
        raise typer.Exit(1)

    if config_path is not None:
        project_config = load_project_config(config_path)
        config_dir = config_path.parent
        repo_paths = project_config.resolve_repo_paths(config_dir)
        project = auto_register_project(state.db, project_config, config_path, repo_paths)

        try:
            user = resolve_git_user(str(repo_paths[0]))
        except (subprocess.CalledProcessError, IndexError):
            user = GitUser(name="Unknown", email="unknown@unknown")

        registered = get_registered_commit_hashes(state.db, project.id or 0)

        result = fetch_project_commits(
            repo_paths=repo_paths,
            target_date=target_date,
            user_email=user.email,
            registered_hashes=registered,
            user=user,
            project_name=project.name,
            project_slug=project.slug,
            config_dir=config_dir,
        )

        if state.output_format == "json":
            typer.echo(json.dumps(result.model_dump(mode="json"), indent=2))
        else:
            _print_text_output(result)

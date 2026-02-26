"""CLI fetch command — retrieve unregistered commits."""

from __future__ import annotations

import json
import subprocess
from datetime import date
from typing import Annotated, Any

import typer

from timereg.cli.app import app, state
from timereg.core.config import find_project_config, load_project_config
from timereg.core.entries import get_registered_commit_hashes
from timereg.core.git import (
    fetch_commits,
    get_branch_info,
    get_working_tree_status,
    resolve_git_user,
)
from timereg.core.models import GitUser
from timereg.core.projects import auto_register_project


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
        typer.echo(
            "Error: No .timetracker.toml found. Use --project or --all.",
            err=True,
        )
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

        repos: list[dict[str, Any]] = []
        for repo_path in repo_paths:
            if not repo_path.is_dir():
                continue
            commits = fetch_commits(
                repo_path=str(repo_path),
                target_date=target_date,
                user_email=user.email,
                registered_hashes=registered,
            )
            branch = get_branch_info(str(repo_path), target_date)
            wt_status = get_working_tree_status(str(repo_path))
            repos.append(
                {
                    "relative_path": str(repo_path.relative_to(config_dir)),
                    "absolute_path": str(repo_path),
                    "branch": branch.current,
                    "branch_activity": branch.activity,
                    "uncommitted": wt_status.model_dump(),
                    "commits": [c.model_dump() for c in commits],
                }
            )

        if state.output_format == "json":
            output = {
                "project_name": project.name,
                "project_slug": project.slug,
                "date": target_date,
                "user": user.model_dump(),
                "repos": repos,
            }
            typer.echo(json.dumps(output, indent=2))
        else:
            typer.echo(f"Project: {project.name} ({project.slug})")
            typer.echo(f"Date: {target_date}")
            typer.echo(f"User: {user.name} <{user.email}>")
            total_commits = sum(len(r["commits"]) for r in repos)
            typer.echo(f"Unregistered commits: {total_commits}")
            for repo in repos:
                if repo["commits"]:
                    typer.echo(f"\n  {repo['relative_path']} ({repo['branch']}):")
                    for c in repo["commits"]:
                        typer.echo(f"    {c['hash'][:8]} {c['message']}")

"""CLI fetch command — retrieve unregistered commits."""

from __future__ import annotations

import json
import subprocess
from datetime import date
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from timereg.cli.app import app, state
from timereg.core.config import find_project_config, load_project_config, no_config_message
from timereg.core.entries import get_registered_commit_hashes
from timereg.core.git import fetch_project_commits, resolve_git_user
from timereg.core.models import (
    AllProjectsFetchResult,
    FetchResult,
    GitUser,
    WorkingTreeStatus,
)
from timereg.core.projects import auto_register_project, get_repo_paths_by_project, list_projects
from timereg.core.split import ProjectMetrics, calculate_split
from timereg.core.time_parser import parse_time

console = Console()


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


def _print_all_text_output(result: AllProjectsFetchResult) -> None:
    """Print cross-project fetch result as formatted text."""
    typer.echo(f"Unregistered commits across all projects ({result.date}):\n")

    for project_result in result.projects:
        commit_count = sum(len(r.commits) for r in project_result.repos)
        if commit_count == 0:
            continue
        typer.echo(f"  {project_result.project_name} ({commit_count} commits)")
        for repo in project_result.repos:
            if repo.commits:
                typer.echo(f"    {repo.relative_path} ({repo.branch})")
                for c in repo.commits:
                    stat = _format_stat(c.insertions, c.deletions, c.files_changed)
                    typer.echo(f"      {c.hash[:8]}  {c.message}    {stat}")
        typer.echo("")

    if not result.suggested_split:
        typer.echo("No unregistered commits found across any project.")
        return

    typer.echo(f"Suggested split for {result.total_hours:.2f}h:\n")
    table = Table()
    table.add_column("Project", style="cyan")
    table.add_column("Hours", style="yellow", justify="right")
    table.add_column("Weight", style="dim", justify="right")
    table.add_column("Commits", justify="right")
    table.add_column("Lines", style="green", justify="right")

    for entry in result.suggested_split:
        lines = entry.total_insertions + entry.total_deletions
        table.add_row(
            entry.project_name,
            f"{entry.suggested_hours:.2f}",
            f"{entry.weight:.0%}",
            str(entry.commit_count),
            f"+{entry.total_insertions} -{entry.total_deletions}" if lines > 0 else "0",
        )

    console.print(table)
    typer.echo(f"\nTotal: {result.total_hours:.2f}h")


def _fetch_all_projects(target_date: str, total_hours: float) -> None:
    """Fetch commits across all registered projects and suggest a time split."""
    projects = list_projects(state.db)
    if not projects:
        typer.echo(
            "Error: No projects registered. Use 'timereg init' or 'timereg projects add'.", err=True
        )
        raise typer.Exit(1)

    repo_paths_by_project = get_repo_paths_by_project(state.db, projects)

    # Resolve git user from the first available repo
    user = GitUser(name="Unknown", email="unknown@unknown")
    for paths in repo_paths_by_project.values():
        for path in paths:
            if path.is_dir():
                try:
                    user = resolve_git_user(str(path))
                    break
                except (subprocess.CalledProcessError, IndexError):
                    continue
        if user.email != "unknown@unknown":
            break

    # Fetch commits for each project
    project_results: list[FetchResult] = []
    metrics_list: list[ProjectMetrics] = []

    for project in projects:
        pid = project.id or 0
        paths = repo_paths_by_project.get(pid, [])
        if not paths:
            continue

        registered = get_registered_commit_hashes(state.db, pid)
        result = fetch_project_commits(
            repo_paths=paths,
            target_date=target_date,
            user_email=user.email,
            registered_hashes=registered,
            user=user,
            project_name=project.name,
            project_slug=project.slug,
            config_dir=paths[0].parent if paths else None,
        )
        project_results.append(result)

        # Aggregate metrics for the split calculation
        commit_count = 0
        total_ins = 0
        total_del = 0
        for repo in result.repos:
            for commit in repo.commits:
                commit_count += 1
                total_ins += commit.insertions
                total_del += commit.deletions

        if commit_count > 0:
            metrics_list.append(
                ProjectMetrics(
                    project_slug=project.slug,
                    project_name=project.name,
                    commit_count=commit_count,
                    total_insertions=total_ins,
                    total_deletions=total_del,
                )
            )

    split = calculate_split(metrics_list, total_hours, rounding_minutes=state.rounding_minutes)

    all_result = AllProjectsFetchResult(
        date=target_date,
        user=user,
        total_hours=total_hours,
        projects=project_results,
        suggested_split=split,
    )

    if state.output_format == "json":
        typer.echo(json.dumps(all_result.model_dump(mode="json"), indent=2))
    else:
        _print_all_text_output(all_result)


@app.command()
def fetch(
    date_str: Annotated[
        str | None, typer.Option("--date", help="Date (YYYY-MM-DD), default today")
    ] = None,
    project_slug: Annotated[str | None, typer.Option("--project", help="Project slug")] = None,
    fetch_all: Annotated[
        bool, typer.Option("--all", help="Fetch across all registered projects")
    ] = False,
    hours_str: Annotated[
        str | None, typer.Option("--hours", help="Total hours to split (required with --all)")
    ] = None,
) -> None:
    """Fetch unregistered commits for a project."""
    target_date = date_str or date.today().isoformat()

    # Validate --hours / --all combination
    if fetch_all and hours_str is None:
        typer.echo("Error: --hours is required when using --all", err=True)
        raise typer.Exit(1)
    if hours_str is not None and not fetch_all:
        typer.echo("Error: --hours can only be used with --all", err=True)
        raise typer.Exit(1)

    if fetch_all:
        try:
            total_hours = parse_time(hours_str)  # type: ignore[arg-type]
        except ValueError as e:
            typer.echo(f"Error: {e}", err=True)
            raise typer.Exit(1) from None
        _fetch_all_projects(target_date, total_hours)
        return

    # Single-project fetch
    config_path = find_project_config()
    if config_path is None and project_slug is None:
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

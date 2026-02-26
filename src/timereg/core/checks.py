"""Status dashboard and gap/conflict detection checks."""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import TYPE_CHECKING

from timereg.core.entries import get_registered_commit_hashes, list_entries
from timereg.core.git import fetch_commits
from timereg.core.models import CheckReport, DayCheck, ProjectStatus, StatusReport

if TYPE_CHECKING:
    from pathlib import Path

    from timereg.core.database import Database
    from timereg.core.models import Project

logger = logging.getLogger(__name__)


def _monday_of_week(d: date) -> date:
    """Return the Monday of the week containing *d*."""
    return d - timedelta(days=d.weekday())


def _count_unregistered_commits(
    db: Database,
    project: Project,
    repo_paths: list[Path],
    user_email: str,
    target_date: str,
) -> int:
    """Count unregistered commits across all repos for a project on a given date."""
    if not repo_paths or project.id is None:
        return 0

    registered = get_registered_commit_hashes(db, project.id)
    total = 0
    for repo_path in repo_paths:
        if not repo_path.is_dir():
            continue
        try:
            commits = fetch_commits(
                repo_path=str(repo_path),
                target_date=target_date,
                user_email=user_email,
                registered_hashes=registered,
            )
            total += len(commits)
        except Exception:
            logger.warning("Failed to fetch commits from %s", repo_path)
    return total


def get_status(
    db: Database,
    projects: list[Project],
    repo_paths_by_project: dict[int, list[Path]],
    user_email: str,
    target_date: date,
) -> StatusReport:
    """Build a status dashboard for the given date across all projects.

    Args:
        db: Database connection.
        projects: List of projects to include.
        repo_paths_by_project: Mapping of project ID to list of repo paths.
        user_email: The user's email for commit lookup.
        target_date: The date to report on.

    Returns:
        A StatusReport with per-project status and warnings.
    """
    monday = _monday_of_week(target_date)
    target_date_str = target_date.isoformat()

    project_statuses: list[ProjectStatus] = []
    warnings: list[str] = []

    for project in projects:
        pid = project.id

        # Today's entries for this project
        today_entries = list_entries(db, project_id=pid, date_filter=target_date)
        today_hours = sum(e.hours for e in today_entries)
        today_entry_count = len(today_entries)

        # Week entries for this project (Monday through target_date)
        week_entries = list_entries(
            db,
            project_id=pid,
            date_from=monday,
            date_to=target_date,
        )
        week_hours = sum(e.hours for e in week_entries)

        # Unregistered commits
        repo_paths = repo_paths_by_project.get(pid, []) if pid is not None else []
        unregistered = _count_unregistered_commits(
            db,
            project,
            repo_paths,
            user_email,
            target_date_str,
        )

        # Budget
        budget_weekly = project.weekly_hours
        budget_percent: float | None = None
        if budget_weekly is not None and budget_weekly > 0:
            budget_percent = (week_hours / budget_weekly) * 100

        project_statuses.append(
            ProjectStatus(
                project=project,
                today_hours=today_hours,
                today_entry_count=today_entry_count,
                unregistered_commits=unregistered,
                week_hours=week_hours,
                budget_weekly=budget_weekly,
                budget_percent=budget_percent,
            )
        )

        # Warnings
        if today_hours == 0:
            warnings.append(f"No hours registered for {project.name} today")

    return StatusReport(
        date=target_date,
        projects=project_statuses,
        warnings=warnings,
    )


def run_checks(
    db: Database,
    projects: list[Project],
    repo_paths_by_project: dict[int, list[Path]],
    user_email: str,
    date_from: date,
    date_to: date,
    max_daily_hours: float = 12.0,
) -> CheckReport:
    """Run gap and conflict detection checks over a date range.

    Iterates each weekday in the range, flags missing hours, high hours,
    and unregistered commits. Also generates budget warnings.

    Args:
        db: Database connection.
        projects: List of projects to check.
        repo_paths_by_project: Mapping of project ID to list of repo paths.
        user_email: The user's email for commit lookup.
        date_from: Start date (inclusive).
        date_to: End date (inclusive).
        max_daily_hours: Threshold above which hours are flagged as high.

    Returns:
        A CheckReport with per-day results and budget warnings.
    """
    days: list[DayCheck] = []
    summary_total = 0.0

    current = date_from
    while current <= date_to:
        # Skip weekends (Monday=0 ... Sunday=6)
        if current.weekday() >= 5:
            current += timedelta(days=1)
            continue

        # Get all entries for this day across all projects
        day_entries = list_entries(
            db,
            date_filter=current,
            all_projects=True,
        )
        day_hours = sum(e.hours for e in day_entries)
        summary_total += day_hours

        day_warnings: list[str] = []

        # Check: no hours registered
        if day_hours == 0:
            day_warnings.append(f"No hours registered on {current.isoformat()}")

        # Check: high hours
        if day_hours > max_daily_hours:
            day_warnings.append(
                f"{day_hours}h registered on {current.isoformat()} (seems high, "
                f"max {max_daily_hours}h)"
            )

        # Check: unregistered commits
        current_str = current.isoformat()
        for project in projects:
            pid = project.id
            repo_paths = repo_paths_by_project.get(pid, []) if pid is not None else []
            unreg = _count_unregistered_commits(
                db,
                project,
                repo_paths,
                user_email,
                current_str,
            )
            if unreg > 0:
                day_warnings.append(
                    f"{unreg} unregistered commits for {project.name} on {current.isoformat()}"
                )

        ok = len(day_warnings) == 0

        days.append(
            DayCheck(
                date=current,
                total_hours=day_hours,
                unregistered_commits=0,  # filled per-project above via warnings
                warnings=day_warnings,
                ok=ok,
            )
        )

        current += timedelta(days=1)

    # Budget warnings: compare total hours per project for the range
    budget_warnings: list[str] = []
    for project in projects:
        if project.weekly_hours is not None and project.weekly_hours > 0:
            proj_entries = list_entries(
                db,
                project_id=project.id,
                date_from=date_from,
                date_to=date_to,
            )
            proj_total = sum(e.hours for e in proj_entries)
            pct = (proj_total / project.weekly_hours) * 100
            if pct < 100:
                budget_warnings.append(
                    f"{project.slug}: {proj_total}h of {project.weekly_hours}h "
                    f"weekly budget ({pct:.0f}%)"
                )
            elif pct > 100:
                budget_warnings.append(
                    f"{project.slug}: {proj_total}h of {project.weekly_hours}h "
                    f"weekly budget ({pct:.0f}%) - over budget"
                )

    return CheckReport(
        date_from=date_from,
        date_to=date_to,
        days=days,
        budget_warnings=budget_warnings,
        summary_total=summary_total,
    )

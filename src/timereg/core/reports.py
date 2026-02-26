"""Summary report generation with budget comparison and tag filtering."""

from __future__ import annotations

import calendar
from collections import defaultdict
from datetime import date, timedelta
from typing import TYPE_CHECKING

from timereg.core.entries import list_entries
from timereg.core.models import DayDetail, ProjectSummary, SummaryReport
from timereg.core.projects import list_projects

if TYPE_CHECKING:
    from timereg.core.database import Database
    from timereg.core.models import Entry, Project


def _resolve_date_range(
    period: str | None,
    date_from: date | None,
    date_to: date | None,
    reference_date: date | None,
) -> tuple[date, date]:
    """Resolve the date range from period + reference_date or explicit bounds."""
    if date_from is not None and date_to is not None:
        return date_from, date_to

    ref = reference_date or date.today()

    if period == "day":
        return ref, ref
    if period == "week":
        monday = ref - timedelta(days=ref.weekday())
        sunday = monday + timedelta(days=6)
        return monday, sunday
    if period == "month":
        _, last_day = calendar.monthrange(ref.year, ref.month)
        return date(ref.year, ref.month, 1), date(ref.year, ref.month, last_day)

    # Fallback: single day
    return ref, ref


def _make_period_label(
    period: str | None,
    period_start: date,
    period_end: date,
    date_from: date | None,
    date_to: date | None,
) -> str:
    """Generate a human-readable period label."""
    if date_from is not None and date_to is not None and period is None:
        # Custom explicit range
        if period_start.year == period_end.year:
            return (
                f"{period_start.strftime('%b %d')} - "
                f"{period_end.strftime('%b %d')}, {period_end.year}"
            )
        return f"{period_start.strftime('%b %d, %Y')} - {period_end.strftime('%b %d, %Y')}"

    if period == "day":
        return period_start.strftime("%b %d, %Y")

    if period == "week":
        iso_year, iso_week, _ = period_start.isocalendar()
        return (
            f"Week {iso_week}, {iso_year} - "
            f"{period_start.strftime('%b %d')} - {period_end.strftime('%b %d')}"
        )

    if period == "month":
        return period_start.strftime("%B %Y")

    return period_start.strftime("%b %d, %Y")


def _filter_by_tags(entries: list[Entry], tag_filter: list[str]) -> list[Entry]:
    """Keep only entries that have at least one matching tag."""
    tag_set = set(tag_filter)
    return [e for e in entries if e.tags and tag_set.intersection(e.tags)]


def _build_project_lookup(db: Database) -> dict[int, Project]:
    """Build a mapping of project_id -> Project."""
    projects = list_projects(db)
    return {p.id: p for p in projects if p.id is not None}


def _get_budget(project: Project, period: str | None) -> float | None:
    """Get the relevant budget for the period."""
    if period == "week":
        return project.weekly_hours
    if period == "month":
        return project.monthly_hours
    return None


def generate_summary(
    db: Database,
    period: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    project_id: int | None = None,
    tag_filter: list[str] | None = None,
    detail: str = "brief",
    reference_date: date | None = None,
) -> SummaryReport:
    """Generate a summary report for a given period.

    Args:
        db: Database connection.
        period: One of "day", "week", "month". Ignored if date_from/date_to set.
        date_from: Explicit start date (inclusive).
        date_to: Explicit end date (inclusive).
        project_id: Filter to a single project.
        tag_filter: Include only entries with at least one matching tag.
        detail: Detail level ("brief" or "full").
        reference_date: Anchor date for period calculation. Defaults to today.

    Returns:
        A SummaryReport with per-project breakdowns.
    """
    period_start, period_end = _resolve_date_range(
        period,
        date_from,
        date_to,
        reference_date,
    )

    # Query entries
    entries = list_entries(
        db,
        project_id=project_id,
        date_from=period_start,
        date_to=period_end,
        all_projects=(project_id is None),
    )

    # Apply tag filter in Python
    if tag_filter:
        entries = _filter_by_tags(entries, tag_filter)

    # Build project lookup
    project_lookup = _build_project_lookup(db)

    # Group entries by project_id, then by date
    by_project: dict[int, list[Entry]] = defaultdict(list)
    for entry in entries:
        by_project[entry.project_id].append(entry)

    # Build ProjectSummary for each project
    project_summaries: list[ProjectSummary] = []
    for pid, proj_entries in sorted(by_project.items()):
        project = project_lookup.get(pid)
        if project is None:
            continue

        # Group by date
        by_date: dict[date, list[Entry]] = defaultdict(list)
        for entry in proj_entries:
            by_date[entry.date].append(entry)

        days: list[DayDetail] = []
        for d in sorted(by_date.keys()):
            day_entries = by_date[d]
            day_hours = sum(e.hours for e in day_entries)
            days.append(DayDetail(date=d, entries=day_entries, total_hours=day_hours))

        total_hours = sum(day.total_hours for day in days)

        budget = _get_budget(project, period)
        budget_percent: float | None = None
        if budget is not None and budget > 0:
            budget_percent = (total_hours / budget) * 100

        project_summaries.append(
            ProjectSummary(
                project=project,
                days=days,
                total_hours=total_hours,
                budget_weekly=project.weekly_hours,
                budget_monthly=project.monthly_hours,
                budget_percent=budget_percent,
            )
        )

    total_hours = sum(ps.total_hours for ps in project_summaries)

    period_label = _make_period_label(
        period,
        period_start,
        period_end,
        date_from,
        date_to,
    )

    return SummaryReport(
        period_start=period_start,
        period_end=period_end,
        period_label=period_label,
        projects=project_summaries,
        total_hours=total_hours,
    )

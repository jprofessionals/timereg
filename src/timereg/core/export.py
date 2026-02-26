"""CSV and JSON export for time entries."""

from __future__ import annotations

import csv
import io
import json
from typing import TYPE_CHECKING, Any

from timereg.core.entries import list_entries

if TYPE_CHECKING:
    from datetime import date

    from timereg.core.database import Database
    from timereg.core.models import Entry

_CSV_HEADER = [
    "date",
    "project",
    "hours",
    "short_summary",
    "long_summary",
    "tags",
    "entry_type",
    "git_user_email",
    "commits",
]


def _build_project_lookup(db: Database) -> dict[int, str]:
    """Build a mapping from project id to project name."""
    rows = db.execute("SELECT id, name FROM projects").fetchall()
    return {row[0]: row[1] for row in rows}


def _get_commit_hashes(db: Database, entry_id: int) -> list[str]:
    """Get commit hashes associated with an entry."""
    rows = db.execute(
        "SELECT commit_hash FROM entry_commits WHERE entry_id=?", (entry_id,)
    ).fetchall()
    return [row[0] for row in rows]


def export_entries(
    db: Database,
    format: str,
    project_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> str:
    """Export entries as CSV or JSON string.

    Args:
        db: Database connection.
        format: Output format, either "csv" or "json".
        project_id: Filter to a specific project. If None, includes all projects.
        date_from: Start of date range filter (inclusive).
        date_to: End of date range filter (inclusive).

    Returns:
        Formatted string of exported entries.
    """
    all_projects = project_id is None
    entries = list_entries(
        db,
        project_id=project_id,
        date_from=date_from,
        date_to=date_to,
        all_projects=all_projects,
    )

    project_lookup = _build_project_lookup(db)

    if format == "csv":
        return _export_csv(db, entries, project_lookup)
    if format == "json":
        return _export_json(db, entries, project_lookup)

    msg = f"Unsupported export format: {format}"
    raise ValueError(msg)


def _entry_to_dict(
    db: Database,
    entry: Entry,
    project_lookup: dict[int, str],
) -> dict[str, Any]:
    """Convert an Entry to a dict for export."""
    commits = _get_commit_hashes(db, entry.id) if entry.id else []
    tags = entry.tags or []

    return {
        "date": entry.date.isoformat(),
        "project": project_lookup.get(entry.project_id, ""),
        "hours": entry.hours,
        "short_summary": entry.short_summary,
        "long_summary": entry.long_summary or "",
        "tags": tags,
        "entry_type": entry.entry_type,
        "git_user_email": entry.git_user_email,
        "commits": commits,
    }


def _export_csv(
    db: Database,
    entries: list[Entry],
    project_lookup: dict[int, str],
) -> str:
    """Export entries as CSV."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(_CSV_HEADER)

    for entry in entries:
        data = _entry_to_dict(db, entry, project_lookup)
        tags: list[str] = data["tags"]
        commits: list[str] = data["commits"]
        writer.writerow(
            [
                data["date"],
                data["project"],
                data["hours"],
                data["short_summary"],
                data["long_summary"],
                ";".join(tags),
                data["entry_type"],
                data["git_user_email"],
                ";".join(commits),
            ]
        )

    return output.getvalue()


def _export_json(
    db: Database,
    entries: list[Entry],
    project_lookup: dict[int, str],
) -> str:
    """Export entries as JSON."""
    data = [_entry_to_dict(db, entry, project_lookup) for entry in entries]
    return json.dumps(data, indent=2, default=str)

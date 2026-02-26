"""Entry CRUD — create, read, edit, delete, undo with peer and split support."""

from __future__ import annotations

import json
import uuid
from typing import TYPE_CHECKING

from timereg.core.models import Entry

if TYPE_CHECKING:
    from datetime import date

    from timereg.core.database import Database
    from timereg.core.models import CommitInfo


def _row_to_entry(row: tuple[object, ...]) -> Entry:
    """Convert a database row to an Entry model."""
    return Entry(
        id=row[0],
        project_id=row[1],
        git_user_name=row[2],
        git_user_email=row[3],
        date=row[4],
        hours=row[5],
        short_summary=row[6],
        long_summary=row[7],
        entry_type=row[8],
        tags=json.loads(str(row[9])) if row[9] else None,
        peer_group_id=row[10],
        split_group_id=row[11],
        created_at=row[12],
        updated_at=row[13],
    )


_ENTRY_COLUMNS = (
    "id, project_id, git_user_name, git_user_email, date, hours, "
    "short_summary, long_summary, entry_type, tags, peer_group_id, "
    "split_group_id, created_at, updated_at"
)


def _insert_entry(
    db: Database,
    project_id: int,
    hours: float,
    short_summary: str,
    entry_date: date,
    git_user_name: str,
    git_user_email: str,
    entry_type: str,
    long_summary: str | None = None,
    tags: list[str] | None = None,
    peer_group_id: str | None = None,
    split_group_id: str | None = None,
) -> Entry:
    """Insert a single entry row and return it."""
    tags_json = json.dumps(tags) if tags else None
    cursor = db.execute(
        "INSERT INTO entries "
        "(project_id, git_user_name, git_user_email, date, hours, "
        "short_summary, long_summary, entry_type, tags, peer_group_id, split_group_id) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            project_id,
            git_user_name,
            git_user_email,
            entry_date.isoformat(),
            hours,
            short_summary,
            long_summary,
            entry_type,
            tags_json,
            peer_group_id,
            split_group_id,
        ),
    )
    row = db.execute(
        f"SELECT {_ENTRY_COLUMNS} FROM entries WHERE id=?", (cursor.lastrowid,)
    ).fetchone()
    assert row is not None
    return _row_to_entry(row)


def _insert_commits(db: Database, entry_id: int, commits: list[CommitInfo]) -> None:
    """Insert commit associations for an entry."""
    for c in commits:
        db.execute(
            "INSERT INTO entry_commits "
            "(entry_id, commit_hash, repo_path, message, author_name, "
            "author_email, timestamp, files_changed, insertions, deletions) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                entry_id,
                c.hash,
                c.repo_path,
                c.message,
                c.author_name,
                c.author_email,
                c.timestamp,
                c.files_changed,
                c.insertions,
                c.deletions,
            ),
        )


def create_entry(
    db: Database,
    project_id: int,
    hours: float,
    short_summary: str,
    entry_date: date,
    git_user_name: str,
    git_user_email: str,
    entry_type: str,
    long_summary: str | None = None,
    commits: list[CommitInfo] | None = None,
    tags: list[str] | None = None,
    peer_emails: list[str] | None = None,
    split_group_id: str | None = None,
) -> Entry | list[Entry]:
    """Create a time entry, optionally with peers."""
    peer_group_id = str(uuid.uuid4()) if peer_emails else None

    entry = _insert_entry(
        db=db,
        project_id=project_id,
        hours=hours,
        short_summary=short_summary,
        entry_date=entry_date,
        git_user_name=git_user_name,
        git_user_email=git_user_email,
        entry_type=entry_type,
        long_summary=long_summary,
        tags=tags,
        peer_group_id=peer_group_id,
        split_group_id=split_group_id,
    )
    if commits and entry.id is not None:
        _insert_commits(db, entry.id, commits)

    if not peer_emails:
        db.commit()
        return entry

    entries = [entry]
    for peer_email in peer_emails:
        peer_entry = _insert_entry(
            db=db,
            project_id=project_id,
            hours=hours,
            short_summary=short_summary,
            entry_date=entry_date,
            git_user_name=git_user_name,
            git_user_email=peer_email,
            entry_type=entry_type,
            long_summary=long_summary,
            tags=tags,
            peer_group_id=peer_group_id,
            split_group_id=split_group_id,
        )
        if commits and peer_entry.id is not None:
            _insert_commits(db, peer_entry.id, commits)
        entries.append(peer_entry)

    db.commit()
    return entries


def edit_entry(
    db: Database,
    entry_id: int,
    hours: float | None = None,
    short_summary: str | None = None,
    long_summary: str | None = None,
    tags: list[str] | None = None,
    entry_date: date | None = None,
    apply_to_peers: bool = False,
) -> Entry:
    """Edit an existing entry."""
    updates: list[str] = []
    params: list[object] = []

    if hours is not None:
        updates.append("hours=?")
        params.append(hours)
    if short_summary is not None:
        updates.append("short_summary=?")
        params.append(short_summary)
    if long_summary is not None:
        updates.append("long_summary=?")
        params.append(long_summary)
    if tags is not None:
        updates.append("tags=?")
        params.append(json.dumps(tags))
    if entry_date is not None:
        updates.append("date=?")
        params.append(entry_date.isoformat())

    if not updates:
        msg = "No fields to update"
        raise ValueError(msg)

    updates.append("updated_at=datetime('now')")
    set_clause = ", ".join(updates)

    if apply_to_peers:
        row = db.execute("SELECT peer_group_id FROM entries WHERE id=?", (entry_id,)).fetchone()
        if row and row[0]:
            db.execute(f"UPDATE entries SET {set_clause} WHERE peer_group_id=?", (*params, row[0]))
        else:
            db.execute(f"UPDATE entries SET {set_clause} WHERE id=?", (*params, entry_id))
    else:
        db.execute(f"UPDATE entries SET {set_clause} WHERE id=?", (*params, entry_id))

    db.commit()
    result = db.execute(f"SELECT {_ENTRY_COLUMNS} FROM entries WHERE id=?", (entry_id,)).fetchone()
    assert result is not None
    return _row_to_entry(result)


def delete_entry(
    db: Database,
    entry_id: int,
    release_commits: bool = True,
    delete_peers: bool = False,
) -> None:
    """Delete an entry."""
    row = db.execute(
        "SELECT project_id, peer_group_id FROM entries WHERE id=?", (entry_id,)
    ).fetchone()
    if row is None:
        msg = f"Entry {entry_id} not found"
        raise ValueError(msg)

    project_id, peer_group_id = row
    ids_to_delete = [entry_id]
    if delete_peers and peer_group_id:
        peer_rows = db.execute(
            "SELECT id FROM entries WHERE peer_group_id=?", (peer_group_id,)
        ).fetchall()
        ids_to_delete = [r[0] for r in peer_rows]

    for eid in ids_to_delete:
        if not release_commits:
            commit_rows = db.execute(
                "SELECT commit_hash FROM entry_commits WHERE entry_id=?", (eid,)
            ).fetchall()
            for crow in commit_rows:
                db.execute(
                    "INSERT INTO claimed_commits (commit_hash, project_id) VALUES (?, ?)",
                    (crow[0], project_id),
                )
        db.execute("DELETE FROM entries WHERE id=?", (eid,))

    db.commit()


def undo_last(db: Database, user_email: str) -> Entry | None:
    """Undo the last entry by this user. Always releases commits."""
    row = db.execute(
        f"SELECT {_ENTRY_COLUMNS} FROM entries WHERE git_user_email=? ORDER BY id DESC LIMIT 1",
        (user_email,),
    ).fetchone()
    if row is None:
        return None

    entry = _row_to_entry(row)
    assert entry.id is not None
    db.execute("DELETE FROM entries WHERE id=?", (entry.id,))
    db.commit()
    return entry


def list_entries(
    db: Database,
    project_id: int | None = None,
    date_filter: date | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    all_projects: bool = False,
) -> list[Entry]:
    """List entries with optional filters."""
    conditions: list[str] = []
    params: list[object] = []

    if project_id is not None and not all_projects:
        conditions.append("project_id=?")
        params.append(project_id)
    if date_filter is not None:
        conditions.append("date=?")
        params.append(date_filter.isoformat())
    if date_from is not None:
        conditions.append("date>=?")
        params.append(date_from.isoformat())
    if date_to is not None:
        conditions.append("date<=?")
        params.append(date_to.isoformat())

    where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
    rows = db.execute(
        f"SELECT {_ENTRY_COLUMNS} FROM entries{where} ORDER BY date, created_at",
        tuple(params),
    ).fetchall()
    return [_row_to_entry(r) for r in rows]


def get_registered_commit_hashes(db: Database, project_id: int) -> set[str]:
    """Get all commit hashes registered or claimed for a project."""
    entry_hashes = db.execute(
        "SELECT ec.commit_hash FROM entry_commits ec "
        "JOIN entries e ON ec.entry_id = e.id "
        "WHERE e.project_id=?",
        (project_id,),
    ).fetchall()

    claimed_hashes = db.execute(
        "SELECT commit_hash FROM claimed_commits WHERE project_id=?",
        (project_id,),
    ).fetchall()

    return {r[0] for r in entry_hashes} | {r[0] for r in claimed_hashes}

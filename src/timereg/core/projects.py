"""Project registry — auto-register, manual add, list, remove."""

from __future__ import annotations

from typing import TYPE_CHECKING

from timereg.core.models import Project

if TYPE_CHECKING:
    from pathlib import Path

    from timereg.core.database import Database
    from timereg.core.models import ProjectConfig

_INSERT_REPO_SQL = (
    "INSERT INTO project_repos (project_id, absolute_path, relative_path) VALUES (?, ?, ?)"
)


def auto_register_project(
    db: Database,
    config: ProjectConfig,
    config_path: Path,
    repo_paths: list[Path],
) -> Project:
    """Register or update a project from its config file."""
    existing = get_project(db, config.slug)
    if existing is not None:
        db.execute(
            "UPDATE projects SET name=?, config_path=?, updated_at=datetime('now') WHERE slug=?",
            (config.name, str(config_path), config.slug),
        )
        db.execute("DELETE FROM project_repos WHERE project_id=?", (existing.id,))
        for repo_path in repo_paths:
            db.execute(
                _INSERT_REPO_SQL,
                (existing.id, str(repo_path), str(repo_path.name)),
            )
        db.commit()
        return Project(
            id=existing.id,
            name=config.name,
            slug=config.slug,
            config_path=str(config_path),
        )

    cursor = db.execute(
        "INSERT INTO projects (name, slug, config_path) VALUES (?, ?, ?)",
        (config.name, config.slug, str(config_path)),
    )
    project_id = cursor.lastrowid
    for repo_path in repo_paths:
        db.execute(
            _INSERT_REPO_SQL,
            (project_id, str(repo_path), str(repo_path.name)),
        )
    db.commit()
    return Project(id=project_id, name=config.name, slug=config.slug, config_path=str(config_path))


def add_project(db: Database, name: str, slug: str) -> Project:
    """Manually add a project (no config file, no repos)."""
    existing = get_project(db, slug)
    if existing is not None:
        msg = f"Project with slug '{slug}' already exists"
        raise ValueError(msg)
    cursor = db.execute(
        "INSERT INTO projects (name, slug) VALUES (?, ?)",
        (name, slug),
    )
    db.commit()
    return Project(id=cursor.lastrowid, name=name, slug=slug)


def _row_to_project(row: tuple) -> Project:  # type: ignore[type-arg]
    """Convert a database row to a Project model."""
    return Project(
        id=row[0],
        name=row[1],
        slug=row[2],
        config_path=row[3],
        created_at=row[4],
        updated_at=row[5],
    )


_SELECT_PROJECT = "SELECT id, name, slug, config_path, created_at, updated_at FROM projects"


def get_project(db: Database, slug: str) -> Project | None:
    """Look up a project by slug."""
    row = db.execute(
        f"{_SELECT_PROJECT} WHERE slug=?",
        (slug,),
    ).fetchone()
    if row is None:
        return None
    return _row_to_project(row)


def list_projects(db: Database) -> list[Project]:
    """List all registered projects."""
    rows = db.execute(f"{_SELECT_PROJECT} ORDER BY name").fetchall()
    return [_row_to_project(r) for r in rows]


def remove_project(db: Database, slug: str, keep_entries: bool = True) -> None:
    """Remove a project from the registry."""
    project = get_project(db, slug)
    if project is None:
        msg = f"Project '{slug}' not found"
        raise ValueError(msg)
    if not keep_entries:
        db.execute("DELETE FROM entries WHERE project_id=?", (project.id,))
    db.execute("DELETE FROM project_repos WHERE project_id=?", (project.id,))
    db.execute("DELETE FROM projects WHERE id=?", (project.id,))
    db.commit()

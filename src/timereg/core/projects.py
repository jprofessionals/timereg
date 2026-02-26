"""Project registry — auto-register, manual add, list, remove."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING

from timereg.core.models import Project

if TYPE_CHECKING:
    from timereg.core.database import Database
    from timereg.core.models import ProjectConfig


def slugify(name: str) -> str:
    """Derive a slug from a project name: lowercase, non-alphanum replaced by hyphens."""
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug or "project"


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
    allowed_tags_json = json.dumps(config.allowed_tags) if config.allowed_tags else None
    if existing is not None:
        db.execute(
            "UPDATE projects SET name=?, config_path=?, weekly_hours=?, monthly_hours=?, "
            "allowed_tags=?, updated_at=datetime('now') WHERE slug=?",
            (
                config.name,
                str(config_path),
                config.weekly_budget_hours,
                config.monthly_budget_hours,
                allowed_tags_json,
                config.slug,
            ),
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
            weekly_hours=config.weekly_budget_hours,
            monthly_hours=config.monthly_budget_hours,
            allowed_tags=config.allowed_tags,
        )

    cursor = db.execute(
        "INSERT INTO projects (name, slug, config_path, weekly_hours, monthly_hours, allowed_tags) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            config.name,
            config.slug,
            str(config_path),
            config.weekly_budget_hours,
            config.monthly_budget_hours,
            allowed_tags_json,
        ),
    )
    project_id = cursor.lastrowid
    for repo_path in repo_paths:
        db.execute(
            _INSERT_REPO_SQL,
            (project_id, str(repo_path), str(repo_path.name)),
        )
    db.commit()
    return Project(
        id=project_id,
        name=config.name,
        slug=config.slug,
        config_path=str(config_path),
        weekly_hours=config.weekly_budget_hours,
        monthly_hours=config.monthly_budget_hours,
        allowed_tags=config.allowed_tags,
    )


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
        weekly_hours=row[4],
        monthly_hours=row[5],
        allowed_tags=json.loads(str(row[6])) if row[6] else None,
        created_at=row[7],
        updated_at=row[8],
    )


_SELECT_PROJECT = (
    "SELECT id, name, slug, config_path, weekly_hours, monthly_hours, "
    "allowed_tags, created_at, updated_at FROM projects"
)


def get_project(db: Database, slug: str) -> Project | None:
    """Look up a project by slug."""
    row = db.execute(
        f"{_SELECT_PROJECT} WHERE slug=?",
        (slug,),
    ).fetchone()
    if row is None:
        return None
    return _row_to_project(row)


def get_project_by_id(db: Database, project_id: int) -> Project | None:
    """Look up a project by ID."""
    row = db.execute(
        f"{_SELECT_PROJECT} WHERE id=?",
        (project_id,),
    ).fetchone()
    if row is None:
        return None
    return _row_to_project(row)


def list_projects(db: Database) -> list[Project]:
    """List all registered projects."""
    rows = db.execute(f"{_SELECT_PROJECT} ORDER BY name").fetchall()
    return [_row_to_project(r) for r in rows]


def get_repo_paths_by_project(db: Database, projects: list[Project]) -> dict[int, list[Path]]:
    """Get repo paths for each project from the project_repos table."""
    result: dict[int, list[Path]] = {}
    for p in projects:
        if p.id is not None:
            rows = db.execute(
                "SELECT absolute_path FROM project_repos WHERE project_id=?",
                (p.id,),
            ).fetchall()
            if rows:
                result[p.id] = [Path(r[0]) for r in rows]
    return result


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

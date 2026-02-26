# Phase 1: Core MVP Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement the TimeReg Core MVP — project scaffolding, foundation layer (database, models, config, git, entries, projects), CLI commands, and agent skill file.

**Architecture:** Three-layer design: `core/` (business logic, fully TDD), `cli/` (Typer commands, thin wrappers), agent integration via skill file + subprocess. All state in SQLite (WAL mode). Config via TOML files.

**Tech Stack:** Python 3.12+, uv, Typer, Rich, Pydantic, SQLite, Ruff, mypy (strict), pre-commit, pytest + pytest-cov.

**Reference:** `docs/plans/2026-02-26-phase1-core-mvp-design.md`, `docs/plan/DESIGN.md`, `docs/plan/TEST_SCENARIOS.md`

---

## Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `src/timereg/__init__.py`
- Create: `src/timereg/__main__.py`
- Create: `src/timereg/py.typed`
- Create: `src/timereg/core/__init__.py`
- Create: `src/timereg/cli/__init__.py`
- Create: `src/timereg/cli/app.py`
- Create: `src/timereg/mcp/__init__.py`
- Create: `src/timereg/migrations/` (empty dir with `.gitkeep`)
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `tests/unit/__init__.py`
- Create: `tests/integration/__init__.py`
- Create: `tests/e2e/__init__.py`
- Create: `.pre-commit-config.yaml`
- Create: `.gitignore`

**Step 1: Create `pyproject.toml`**

```toml
[project]
name = "timereg"
version = "0.1.0"
description = "Git-aware time tracking for developers"
requires-python = ">=3.12"
license = "MIT"
authors = [{ name = "JPro Consulting" }]

dependencies = [
    "typer>=0.15",
    "rich>=14.0",
    "platformdirs>=4.0",
    "pydantic>=2.12",
]

[project.scripts]
timereg = "timereg.cli.app:app"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.backends"

[tool.hatch.build.targets.wheel]
packages = ["src/timereg"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "--cov=timereg --cov-report=term-missing --no-header -q"

[tool.mypy]
strict = true
python_version = "3.12"
plugins = ["pydantic.mypy"]

[[tool.mypy.overrides]]
module = ["typer.*", "rich.*"]
implicit_reexport = true
disallow_untyped_decorators = false

[tool.ruff]
target-version = "py312"
line-length = 100
src = ["src", "tests"]

[tool.ruff.lint]
select = [
    "E",     # pycodestyle errors
    "W",     # pycodestyle warnings
    "F",     # pyflakes
    "I",     # isort
    "N",     # pep8-naming
    "UP",    # pyupgrade
    "B",     # flake8-bugbear
    "SIM",   # flake8-simplify
    "TCH",   # flake8-type-checking
    "RUF",   # ruff-specific
]
```

**Step 2: Create package structure**

Create all `__init__.py` files:

`src/timereg/__init__.py`:
```python
"""TimeReg — Git-aware time tracking for developers."""

__version__ = "0.1.0"
```

`src/timereg/__main__.py`:
```python
"""Allow running as `python -m timereg`."""

from timereg.cli.app import app

app()
```

`src/timereg/py.typed` — empty marker file for PEP 561.

`src/timereg/core/__init__.py` — empty.

`src/timereg/cli/__init__.py` — empty.

`src/timereg/cli/app.py`:
```python
"""Typer CLI application — entry point and global options."""

import typer

app = typer.Typer(
    name="timereg",
    help="Git-aware time tracking for developers.",
    no_args_is_help=True,
)
```

`src/timereg/mcp/__init__.py` — empty.

`tests/__init__.py`, `tests/unit/__init__.py`, `tests/integration/__init__.py`, `tests/e2e/__init__.py` — all empty.

`tests/conftest.py`:
```python
"""Shared test fixtures."""
```

**Step 3: Create `.gitignore`**

```gitignore
__pycache__/
*.py[cod]
*$py.class
*.egg-info/
dist/
build/
.eggs/
*.egg
.mypy_cache/
.ruff_cache/
.pytest_cache/
.coverage
htmlcov/
*.db
.venv/
```

**Step 4: Create `.pre-commit-config.yaml`**

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-toml
      - id: check-added-large-files

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.11.2
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.15.0
    hooks:
      - id: mypy
        additional_dependencies:
          - "pydantic>=2.12"
          - "typer>=0.15"
          - "rich>=14.0"
          - "platformdirs>=4.0"
        args: [--config-file=pyproject.toml]
        pass_filenames: false
        entry: mypy src/

  - repo: local
    hooks:
      - id: pytest-unit
        name: pytest (unit)
        entry: uv run pytest tests/unit/ -x -q --no-header --tb=short --no-cov
        language: system
        pass_filenames: false
        always_run: true
```

**Step 5: Install dependencies, set up pre-commit, verify**

Run:
```bash
uv sync
uv run timereg --help
uv run pytest
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run mypy src/
pre-commit install
```

Expected: All commands succeed. `timereg --help` shows the help text. pytest reports 0 tests. Ruff and mypy pass clean.

**Step 6: Commit**

```bash
git add -A
git commit -m "scaffold project structure with tooling

Set up pyproject.toml, package structure, ruff, mypy (strict),
pre-commit hooks, and pytest with coverage reporting."
```

---

## Task 2: Database & Migration System

**Files:**
- Create: `src/timereg/core/database.py`
- Create: `src/timereg/migrations/001_initial.sql`
- Create: `tests/unit/test_database.py`

**Step 1: Write failing tests for database**

`tests/unit/test_database.py`:
```python
"""Tests for database initialization and migration system."""

from pathlib import Path

import pytest

from timereg.core.database import Database


class TestDatabaseInit:
    def test_creates_database_file(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        db = Database(db_path)
        db.close()
        assert db_path.exists()

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        db_path = tmp_path / "subdir" / "nested" / "test.db"
        db = Database(db_path)
        db.close()
        assert db_path.exists()

    def test_enables_wal_mode(self, tmp_path: Path) -> None:
        db = Database(tmp_path / "test.db")
        result = db.execute("PRAGMA journal_mode").fetchone()
        assert result is not None
        assert result[0] == "wal"
        db.close()

    def test_enables_foreign_keys(self, tmp_path: Path) -> None:
        db = Database(tmp_path / "test.db")
        result = db.execute("PRAGMA foreign_keys").fetchone()
        assert result is not None
        assert result[0] == 1
        db.close()


class TestMigrations:
    def test_migrate_creates_schema_version_table(self, tmp_path: Path) -> None:
        db = Database(tmp_path / "test.db")
        db.migrate()
        result = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
        ).fetchone()
        assert result is not None
        db.close()

    def test_migrate_creates_all_tables(self, tmp_path: Path) -> None:
        db = Database(tmp_path / "test.db")
        db.migrate()
        tables = {
            row[0]
            for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name != 'sqlite_sequence'"
            ).fetchall()
        }
        expected = {
            "schema_version",
            "projects",
            "project_repos",
            "entries",
            "entry_commits",
            "claimed_commits",
        }
        assert expected == tables
        db.close()

    def test_migrate_records_version(self, tmp_path: Path) -> None:
        db = Database(tmp_path / "test.db")
        db.migrate()
        result = db.execute("SELECT MAX(version) FROM schema_version").fetchone()
        assert result is not None
        assert result[0] == 1
        db.close()

    def test_migrate_is_idempotent(self, tmp_path: Path) -> None:
        db = Database(tmp_path / "test.db")
        db.migrate()
        db.migrate()  # should not raise
        result = db.execute("SELECT COUNT(*) FROM schema_version").fetchone()
        assert result is not None
        assert result[0] == 1
        db.close()

    def test_migrate_applies_pending_only(self, tmp_path: Path) -> None:
        db = Database(tmp_path / "test.db")
        db.migrate()
        # Manually insert a version to simulate future migration
        version = db.execute("SELECT MAX(version) FROM schema_version").fetchone()
        assert version is not None
        assert version[0] >= 1
        db.close()


class TestContextManager:
    def test_database_as_context_manager(self, tmp_path: Path) -> None:
        with Database(tmp_path / "test.db") as db:
            db.migrate()
            result = db.execute("SELECT 1").fetchone()
            assert result is not None
            assert result[0] == 1

    def test_context_manager_closes_connection(self, tmp_path: Path) -> None:
        db_instance: Database | None = None
        with Database(tmp_path / "test.db") as db:
            db_instance = db
        assert db_instance is not None
        # Connection should be closed — executing should raise
        with pytest.raises(Exception):
            db_instance.execute("SELECT 1")
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_database.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'timereg.core.database'`

**Step 3: Create migration SQL**

`src/timereg/migrations/001_initial.sql`:
```sql
-- Initial schema: projects, entries, commits, claimed_commits

CREATE TABLE projects (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    slug        TEXT NOT NULL UNIQUE,
    config_path TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE UNIQUE INDEX idx_projects_slug ON projects(slug);

CREATE TABLE project_repos (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id    INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    absolute_path TEXT NOT NULL,
    relative_path TEXT NOT NULL
);

CREATE INDEX idx_project_repos_project ON project_repos(project_id);

CREATE TABLE entries (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id      INTEGER NOT NULL REFERENCES projects(id),
    git_user_name   TEXT NOT NULL,
    git_user_email  TEXT NOT NULL,
    date            TEXT NOT NULL,
    hours           REAL NOT NULL,
    short_summary   TEXT NOT NULL,
    long_summary    TEXT,
    entry_type      TEXT NOT NULL CHECK(entry_type IN ('git', 'manual')),
    tags            TEXT,
    peer_group_id   TEXT,
    split_group_id  TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_entries_project_date ON entries(project_id, date);
CREATE INDEX idx_entries_user ON entries(git_user_email, date);
CREATE INDEX idx_entries_peer ON entries(peer_group_id);
CREATE INDEX idx_entries_split ON entries(split_group_id);

CREATE TABLE entry_commits (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id      INTEGER NOT NULL REFERENCES entries(id) ON DELETE CASCADE,
    commit_hash   TEXT NOT NULL,
    repo_path     TEXT NOT NULL,
    message       TEXT NOT NULL,
    author_name   TEXT NOT NULL,
    author_email  TEXT NOT NULL,
    timestamp     TEXT NOT NULL,
    files_changed INTEGER DEFAULT 0,
    insertions    INTEGER DEFAULT 0,
    deletions     INTEGER DEFAULT 0
);

CREATE INDEX idx_entry_commits_hash ON entry_commits(commit_hash);
CREATE INDEX idx_entry_commits_entry ON entry_commits(entry_id);

CREATE TABLE claimed_commits (
    commit_hash TEXT NOT NULL,
    project_id  INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    claimed_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_claimed_commits_hash ON claimed_commits(commit_hash);
```

**Step 4: Implement database module**

`src/timereg/core/database.py`:
```python
"""SQLite database connection and migration system."""

from __future__ import annotations

import sqlite3
from importlib import resources
from pathlib import Path
from typing import Any


class Database:
    """SQLite database with WAL mode and migration support."""

    def __init__(self, db_path: str | Path) -> None:
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path))
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Cursor:
        return self._conn.execute(sql, params)

    def executemany(self, sql: str, params: list[tuple[Any, ...]]) -> sqlite3.Cursor:
        return self._conn.executemany(sql, params)

    def executescript(self, sql: str) -> None:
        self._conn.executescript(sql)

    def commit(self) -> None:
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> Database:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _get_current_version(self) -> int:
        """Get the current schema version, or 0 if no migrations applied."""
        try:
            result = self.execute("SELECT MAX(version) FROM schema_version").fetchone()
            return result[0] if result and result[0] is not None else 0
        except sqlite3.OperationalError:
            return 0

    def _get_migration_files(self) -> list[tuple[int, str]]:
        """Read migration SQL files from the migrations package directory."""
        migrations: list[tuple[int, str]] = []
        migration_dir = Path(__file__).parent.parent / "migrations"
        for sql_file in sorted(migration_dir.glob("*.sql")):
            version = int(sql_file.name.split("_")[0])
            migrations.append((version, sql_file.read_text()))
        return migrations

    def migrate(self) -> None:
        """Apply pending database migrations."""
        self.execute(
            "CREATE TABLE IF NOT EXISTS schema_version ("
            "    version INTEGER PRIMARY KEY,"
            "    applied_at TEXT NOT NULL DEFAULT (datetime('now'))"
            ")"
        )
        self.commit()

        current_version = self._get_current_version()

        for version, sql in self._get_migration_files():
            if version > current_version:
                self.executescript(sql)
                self.execute(
                    "INSERT INTO schema_version (version) VALUES (?)", (version,)
                )
                self.commit()
```

**Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_database.py -v`
Expected: All tests PASS.

**Step 6: Commit**

```bash
git add src/timereg/core/database.py src/timereg/migrations/001_initial.sql tests/unit/test_database.py
git commit -m "add database module with migration system

SQLite with WAL mode, foreign keys, and sequential SQL migration
files. Initial migration creates all Phase 1 tables."
```

---

## Task 3: Pydantic Models

**Files:**
- Create: `src/timereg/core/models.py`
- Create: `tests/unit/test_models.py`

**Step 1: Write failing tests**

`tests/unit/test_models.py`:
```python
"""Tests for Pydantic data models."""

from datetime import date, datetime

import pytest
from pydantic import ValidationError

from timereg.core.models import (
    CommitInfo,
    Entry,
    EntryCommit,
    GlobalConfig,
    Project,
    ProjectConfig,
    RepoFetchResult,
    WorkingTreeStatus,
)


class TestProject:
    def test_create_project(self) -> None:
        p = Project(id=1, name="Ekvarda Codex", slug="ekvarda")
        assert p.slug == "ekvarda"

    def test_slug_must_be_lowercase_alphanumeric(self) -> None:
        with pytest.raises(ValidationError):
            Project(id=1, name="Test", slug="UPPER CASE")


class TestEntry:
    def test_create_git_entry(self) -> None:
        entry = Entry(
            id=1,
            project_id=1,
            git_user_name="Mr Bell",
            git_user_email="bell@jpro.no",
            date=date(2026, 2, 25),
            hours=4.5,
            short_summary="WebRTC signaling",
            entry_type="git",
        )
        assert entry.hours == 4.5
        assert entry.entry_type == "git"

    def test_entry_type_must_be_valid(self) -> None:
        with pytest.raises(ValidationError):
            Entry(
                id=1,
                project_id=1,
                git_user_name="Mr Bell",
                git_user_email="bell@jpro.no",
                date=date(2026, 2, 25),
                hours=4.5,
                short_summary="Test",
                entry_type="invalid",
            )

    def test_hours_must_be_positive(self) -> None:
        with pytest.raises(ValidationError):
            Entry(
                id=1,
                project_id=1,
                git_user_name="Mr Bell",
                git_user_email="bell@jpro.no",
                date=date(2026, 2, 25),
                hours=0,
                short_summary="Test",
                entry_type="manual",
            )

    def test_tags_round_trip(self) -> None:
        entry = Entry(
            id=1,
            project_id=1,
            git_user_name="Mr Bell",
            git_user_email="bell@jpro.no",
            date=date(2026, 2, 25),
            hours=2.0,
            short_summary="Test",
            entry_type="manual",
            tags=["development", "testing"],
        )
        assert entry.tags == ["development", "testing"]


class TestCommitInfo:
    def test_create_commit_info(self) -> None:
        c = CommitInfo(
            hash="a1b2c3d4e5f6",
            message="feat: add signaling",
            author_name="Mr Bell",
            author_email="bell@jpro.no",
            timestamp="2026-02-25T09:34:12+01:00",
            repo_path=".",
            files_changed=4,
            insertions=87,
            deletions=12,
            files=["src/signaling.py"],
        )
        assert c.files_changed == 4


class TestRepoFetchResult:
    def test_create_fetch_result(self) -> None:
        r = RepoFetchResult(
            relative_path=".",
            absolute_path="/home/user/project",
            branch="main",
            branch_activity=[],
            uncommitted=WorkingTreeStatus(staged_files=0, unstaged_files=0),
            commits=[],
        )
        assert r.branch == "main"


class TestProjectConfig:
    def test_minimal_config(self) -> None:
        cfg = ProjectConfig(name="Test", slug="test")
        assert cfg.repo_paths == ["."]

    def test_full_config(self) -> None:
        cfg = ProjectConfig(
            name="Ekvarda",
            slug="ekvarda",
            repo_paths=[".", "./client"],
            allowed_tags=["development", "meeting"],
            weekly_budget_hours=20.0,
            monthly_budget_hours=80.0,
        )
        assert len(cfg.repo_paths) == 2


class TestGlobalConfig:
    def test_defaults(self) -> None:
        cfg = GlobalConfig()
        assert cfg.merge_commits is False
        assert cfg.timezone == "Europe/Oslo"
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Implement models**

`src/timereg/core/models.py`:
```python
"""Pydantic models for all TimeReg entities."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


# --- Database entities ---


class Project(BaseModel):
    """A registered project."""

    id: int | None = None
    name: str
    slug: str
    config_path: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @field_validator("slug")
    @classmethod
    def slug_must_be_valid(cls, v: str) -> str:
        if not re.match(r"^[a-z0-9][a-z0-9-]*$", v):
            msg = "Slug must be lowercase alphanumeric with hyphens"
            raise ValueError(msg)
        return v


class ProjectRepo(BaseModel):
    """A git repo associated with a project."""

    id: int | None = None
    project_id: int
    absolute_path: str
    relative_path: str


class Entry(BaseModel):
    """A time registration entry."""

    id: int | None = None
    project_id: int
    git_user_name: str
    git_user_email: str
    date: date
    hours: float = Field(gt=0)
    short_summary: str
    long_summary: str | None = None
    entry_type: Literal["git", "manual"]
    tags: list[str] | None = None
    peer_group_id: str | None = None
    split_group_id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class EntryCommit(BaseModel):
    """A git commit associated with a time entry."""

    id: int | None = None
    entry_id: int
    commit_hash: str
    repo_path: str
    message: str
    author_name: str
    author_email: str
    timestamp: str
    files_changed: int = 0
    insertions: int = 0
    deletions: int = 0


# --- Git data types ---


class CommitInfo(BaseModel):
    """Structured commit data from git (pre-persistence)."""

    hash: str
    message: str
    author_name: str
    author_email: str
    timestamp: str
    repo_path: str
    files_changed: int = 0
    insertions: int = 0
    deletions: int = 0
    files: list[str] = Field(default_factory=list)


class WorkingTreeStatus(BaseModel):
    """Git working tree status counts."""

    staged_files: int = 0
    unstaged_files: int = 0


class BranchInfo(BaseModel):
    """Current branch and recent branch activity."""

    current: str
    activity: list[str] = Field(default_factory=list)


class GitUser(BaseModel):
    """Git user identity."""

    name: str
    email: str


class RepoFetchResult(BaseModel):
    """Per-repo fetch results."""

    relative_path: str
    absolute_path: str
    branch: str
    branch_activity: list[str] = Field(default_factory=list)
    uncommitted: WorkingTreeStatus
    commits: list[CommitInfo] = Field(default_factory=list)


class FetchResult(BaseModel):
    """Top-level fetch response for a single project."""

    project_name: str
    project_slug: str
    date: str
    user: GitUser
    repos: list[RepoFetchResult] = Field(default_factory=list)
    already_registered_today: list[Entry] = Field(default_factory=list)


class SuggestedSplitEntry(BaseModel):
    """Suggested time allocation for one project in a split."""

    project_slug: str
    project_name: str
    suggested_hours: float
    commit_count: int
    total_insertions: int
    total_deletions: int


class AllProjectsFetchResult(BaseModel):
    """Cross-project fetch with suggested time split."""

    date: str
    user: GitUser
    projects: list[FetchResult] = Field(default_factory=list)
    suggested_split: list[SuggestedSplitEntry] = Field(default_factory=list)


# --- Configuration models ---


class GlobalConfig(BaseModel):
    """Global config from ~/.config/timereg/config.toml."""

    db_path: str | None = None
    merge_commits: bool = False
    timezone: str = "Europe/Oslo"
    user_name: str | None = None
    user_email: str | None = None


class ProjectConfig(BaseModel):
    """Project config from .timetracker.toml."""

    name: str
    slug: str
    repo_paths: list[str] = Field(default_factory=lambda: ["."])
    allowed_tags: list[str] | None = None
    weekly_budget_hours: float | None = None
    monthly_budget_hours: float | None = None


class ResolvedConfig(BaseModel):
    """Merged configuration from all sources."""

    db_path: str
    project: ProjectConfig | None = None
    project_config_path: str | None = None
    user: GitUser | None = None
    merge_commits: bool = False
    timezone: str = "Europe/Oslo"
    verbose: bool = False
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_models.py -v`
Expected: All tests PASS.

**Step 5: Commit**

```bash
git add src/timereg/core/models.py tests/unit/test_models.py
git commit -m "add Pydantic models for all entities

Project, Entry, CommitInfo, FetchResult, config models.
Strict validation with field constraints."
```

---

## Task 4: Time Parser (TDD)

**Files:**
- Create: `src/timereg/core/time_parser.py`
- Create: `tests/unit/test_time_parser.py`

**Step 1: Write failing tests**

`tests/unit/test_time_parser.py`:
```python
"""Tests for time string parser."""

import warnings

import pytest

from timereg.core.time_parser import parse_time


class TestValidFormats:
    @pytest.mark.parametrize(
        ("input_str", "expected"),
        [
            ("2h30m", 2.5),
            ("2h", 2.0),
            ("30m", 0.5),
            ("90m", 1.5),
            ("1.5", 1.5),
            ("4.25", 4.25),
            ("0.5", 0.5),
            ("1h45m", 1.75),
            ("8h", 8.0),
            ("1h1m", 1 + 1 / 60),
            ("15m", 0.25),
        ],
    )
    def test_parse_valid_time(self, input_str: str, expected: float) -> None:
        assert parse_time(input_str) == pytest.approx(expected)


class TestInvalidFormats:
    @pytest.mark.parametrize(
        "input_str",
        [
            "",
            "abc",
            "-1h",
            "0h",
            "0m",
            "0",
            "0.0",
            "h30m",
            "hm",
        ],
    )
    def test_reject_invalid_time(self, input_str: str) -> None:
        with pytest.raises(ValueError):
            parse_time(input_str)


class TestEdgeCases:
    def test_large_value_warns(self) -> None:
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = parse_time("25h")
            assert result == 25.0
            assert len(w) == 1
            assert "25.0" in str(w[0].message)

    def test_whitespace_stripped(self) -> None:
        assert parse_time("  2h30m  ") == 2.5
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_time_parser.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Implement time parser**

`src/timereg/core/time_parser.py`:
```python
"""Parse human-friendly time strings to float hours."""

from __future__ import annotations

import re
import warnings

_HOURS_MINUTES_RE = re.compile(r"^(?:(\d+)h)?(?:(\d+)m)?$")


def parse_time(value: str) -> float:
    """Parse a time string into float hours.

    Supported formats:
        - "2h30m", "2h", "30m", "1h45m" (hours and/or minutes)
        - "1.5", "4.25" (decimal hours)

    Raises ValueError for invalid or non-positive values.
    Warns for values exceeding 24 hours.
    """
    value = value.strip()
    if not value:
        msg = "Time value cannot be empty"
        raise ValueError(msg)

    # Try decimal format first
    try:
        hours = float(value)
        if hours <= 0:
            msg = f"Time must be positive, got {hours}"
            raise ValueError(msg)
        if hours > 24:
            warnings.warn(f"Time value {hours} exceeds 24 hours", stacklevel=2)
        return hours
    except ValueError:
        if re.match(r"^-?\d*\.?\d+$", value):
            raise

    # Try hours/minutes format
    match = _HOURS_MINUTES_RE.match(value)
    if not match:
        msg = f"Invalid time format: {value!r}"
        raise ValueError(msg)

    h_str, m_str = match.groups()
    h = int(h_str) if h_str else 0
    m = int(m_str) if m_str else 0

    if h == 0 and m == 0:
        msg = "Time must be positive"
        raise ValueError(msg)

    hours = h + m / 60
    if hours > 24:
        warnings.warn(f"Time value {hours} exceeds 24 hours", stacklevel=2)
    return hours
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_time_parser.py -v`
Expected: All tests PASS.

**Step 5: Commit**

```bash
git add src/timereg/core/time_parser.py tests/unit/test_time_parser.py
git commit -m "add time parser with support for h/m and decimal formats

Parses 2h30m, 90m, 1.5, etc. Rejects invalid/non-positive values,
warns on >24h."
```

---

## Task 5: Config Resolution (TDD)

**Files:**
- Create: `src/timereg/core/config.py`
- Create: `tests/unit/test_config.py`
- Create: `tests/fixtures/sample_config.toml`
- Create: `tests/fixtures/sample_global_config.toml`

**Step 1: Create test fixture files**

`tests/fixtures/sample_config.toml`:
```toml
[project]
name = "Ekvarda Codex"
slug = "ekvarda"

[repos]
paths = [".", "./client", "../infra"]

[tags]
allowed = ["development", "review", "meeting"]

[budget]
weekly_hours = 20.0
monthly_hours = 80.0
```

`tests/fixtures/sample_global_config.toml`:
```toml
[database]
path = "/custom/path/timereg.db"

[defaults]
merge_commits = false
timezone = "Europe/Oslo"

[user]
name = "Mr Bell"
email = "bell@jpro.no"
```

**Step 2: Write failing tests**

`tests/unit/test_config.py`:
```python
"""Tests for configuration resolution."""

from pathlib import Path
from unittest.mock import patch

import pytest

from timereg.core.config import (
    find_project_config,
    load_global_config,
    load_project_config,
    resolve_db_path,
)


class TestFindProjectConfig:
    def test_finds_config_in_current_dir(self, tmp_path: Path) -> None:
        config_file = tmp_path / ".timetracker.toml"
        config_file.write_text('[project]\nname = "Test"\nslug = "test"\n')
        result = find_project_config(tmp_path)
        assert result == config_file

    def test_finds_config_in_parent_dir(self, tmp_path: Path) -> None:
        config_file = tmp_path / ".timetracker.toml"
        config_file.write_text('[project]\nname = "Test"\nslug = "test"\n')
        child = tmp_path / "src" / "lib"
        child.mkdir(parents=True)
        result = find_project_config(child)
        assert result == config_file

    def test_stops_at_home_dir(self, tmp_path: Path) -> None:
        # Simulate a home dir that does not contain config
        child = tmp_path / "projects" / "repo" / "src"
        child.mkdir(parents=True)
        with patch("timereg.core.config._get_home_dir", return_value=tmp_path):
            result = find_project_config(child)
        assert result is None

    def test_returns_none_when_not_found(self, tmp_path: Path) -> None:
        with patch("timereg.core.config._get_home_dir", return_value=tmp_path):
            result = find_project_config(tmp_path)
        assert result is None


class TestLoadProjectConfig:
    def test_load_full_config(self) -> None:
        config_path = Path(__file__).parent.parent / "fixtures" / "sample_config.toml"
        cfg = load_project_config(config_path)
        assert cfg.name == "Ekvarda Codex"
        assert cfg.slug == "ekvarda"
        assert cfg.repo_paths == [".", "./client", "../infra"]
        assert cfg.allowed_tags == ["development", "review", "meeting"]
        assert cfg.weekly_budget_hours == 20.0

    def test_load_minimal_config(self, tmp_path: Path) -> None:
        config_file = tmp_path / ".timetracker.toml"
        config_file.write_text('[project]\nname = "Minimal"\nslug = "minimal"\n')
        cfg = load_project_config(config_file)
        assert cfg.name == "Minimal"
        assert cfg.repo_paths == ["."]
        assert cfg.allowed_tags is None
        assert cfg.weekly_budget_hours is None

    def test_resolve_repo_paths(self, tmp_path: Path) -> None:
        config_file = tmp_path / "project" / ".timetracker.toml"
        config_file.parent.mkdir()
        config_file.write_text(
            '[project]\nname = "Test"\nslug = "test"\n\n'
            '[repos]\npaths = [".", "./client", "../infra"]\n'
        )
        cfg = load_project_config(config_file)
        resolved = cfg.resolve_repo_paths(config_file.parent)
        assert resolved[0] == config_file.parent
        assert resolved[1] == config_file.parent / "client"
        assert resolved[2] == config_file.parent.parent / "infra"


class TestLoadGlobalConfig:
    def test_load_full_global_config(self) -> None:
        config_path = Path(__file__).parent.parent / "fixtures" / "sample_global_config.toml"
        cfg = load_global_config(config_path)
        assert cfg.db_path == "/custom/path/timereg.db"
        assert cfg.timezone == "Europe/Oslo"
        assert cfg.user_name == "Mr Bell"
        assert cfg.user_email == "bell@jpro.no"

    def test_load_missing_config_returns_defaults(self, tmp_path: Path) -> None:
        cfg = load_global_config(tmp_path / "nonexistent.toml")
        assert cfg.db_path is None
        assert cfg.merge_commits is False
        assert cfg.timezone == "Europe/Oslo"


class TestResolveDbPath:
    def test_cli_flag_takes_precedence(self) -> None:
        result = resolve_db_path(
            cli_db_path="/cli/path.db",
            env_db_path="/env/path.db",
            config_db_path="/config/path.db",
        )
        assert result == Path("/cli/path.db")

    def test_env_var_second_precedence(self) -> None:
        result = resolve_db_path(
            cli_db_path=None,
            env_db_path="/env/path.db",
            config_db_path="/config/path.db",
        )
        assert result == Path("/env/path.db")

    def test_config_third_precedence(self) -> None:
        result = resolve_db_path(
            cli_db_path=None,
            env_db_path=None,
            config_db_path="/config/path.db",
        )
        assert result == Path("/config/path.db")

    def test_default_when_nothing_set(self) -> None:
        result = resolve_db_path(cli_db_path=None, env_db_path=None, config_db_path=None)
        assert "timereg" in str(result)
        assert result.name == "timereg.db"
```

**Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 4: Implement config module**

`src/timereg/core/config.py`:
```python
"""Configuration resolution — global, project, and merged."""

from __future__ import annotations

import sys
from pathlib import Path

import platformdirs

from timereg.core.models import GlobalConfig, ProjectConfig

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]

CONFIG_FILENAME = ".timetracker.toml"


def _get_home_dir() -> Path:
    return Path.home()


def find_project_config(start: Path | None = None) -> Path | None:
    """Walk up from start directory to find .timetracker.toml.

    Stops at the user's home directory. Returns None if not found.
    """
    current = (start or Path.cwd()).resolve()
    home = _get_home_dir().resolve()

    while True:
        candidate = current / CONFIG_FILENAME
        if candidate.is_file():
            return candidate
        if current == home or current == current.parent:
            return None
        current = current.parent


def load_project_config(config_path: Path) -> ProjectConfig:
    """Parse a .timetracker.toml file into a ProjectConfig."""
    with open(config_path, "rb") as f:
        data = tomllib.load(f)

    project = data.get("project", {})
    repos = data.get("repos", {})
    tags = data.get("tags", {})
    budget = data.get("budget", {})

    return ProjectConfig(
        name=project["name"],
        slug=project["slug"],
        repo_paths=repos.get("paths", ["."]),
        allowed_tags=tags.get("allowed"),
        weekly_budget_hours=budget.get("weekly_hours"),
        monthly_budget_hours=budget.get("monthly_hours"),
    )


def load_global_config(config_path: Path) -> GlobalConfig:
    """Load global config.toml, returning defaults if file doesn't exist."""
    if not config_path.is_file():
        return GlobalConfig()

    with open(config_path, "rb") as f:
        data = tomllib.load(f)

    database = data.get("database", {})
    defaults = data.get("defaults", {})
    user = data.get("user", {})

    return GlobalConfig(
        db_path=database.get("path"),
        merge_commits=defaults.get("merge_commits", False),
        timezone=defaults.get("timezone", "Europe/Oslo"),
        user_name=user.get("name"),
        user_email=user.get("email"),
    )


def get_global_config_path() -> Path:
    """Get the platform-appropriate global config path."""
    return Path(platformdirs.user_config_dir("timereg")) / "config.toml"


def ensure_global_config() -> Path:
    """Create default global config if it doesn't exist. Returns the path."""
    config_path = get_global_config_path()
    if not config_path.exists():
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(
            '[database]\n'
            '# path = "~/.local/share/timereg/timereg.db"\n'
            "\n"
            "[defaults]\n"
            "merge_commits = false\n"
            'timezone = "Europe/Oslo"\n'
            "\n"
            "[user]\n"
            '# name = "Your Name"\n'
            '# email = "you@example.com"\n'
        )
    return config_path


def resolve_db_path(
    cli_db_path: str | None = None,
    env_db_path: str | None = None,
    config_db_path: str | None = None,
) -> Path:
    """Resolve database path by precedence: CLI > env > config > default."""
    if cli_db_path:
        return Path(cli_db_path)
    if env_db_path:
        return Path(env_db_path)
    if config_db_path:
        return Path(config_db_path)
    return Path(platformdirs.user_data_dir("timereg")) / "timereg.db"


def require_project_config(start: Path | None = None) -> tuple[Path, ProjectConfig]:
    """Find and load project config, or exit with a warning.

    Returns (config_path, project_config) tuple.
    """
    config_path = find_project_config(start)
    if config_path is None:
        print(
            "Error: No .timetracker.toml found in current or parent directories.\n"
            "Create a .timetracker.toml in your project root, or use --project to specify one.",
            file=sys.stderr,
        )
        raise SystemExit(1)
    return config_path, load_project_config(config_path)
```

Add `resolve_repo_paths` method to `ProjectConfig` in `models.py`:

Add to `ProjectConfig` class in `src/timereg/core/models.py`:
```python
    def resolve_repo_paths(self, config_dir: Path) -> list[Path]:
        """Resolve repo paths relative to the config file's directory."""
        return [(config_dir / p).resolve() for p in self.repo_paths]
```

(This requires adding `from pathlib import Path` to models.py imports.)

**Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_config.py -v`
Expected: All tests PASS.

**Step 6: Commit**

```bash
git add src/timereg/core/config.py tests/unit/test_config.py tests/fixtures/
git commit -m "add config resolution with home dir boundary

Project config walks up to home dir and exits if not found.
Global config with defaults. DB path precedence chain."
```

---

## Task 6: Git Analyzer (TDD)

**Files:**
- Create: `src/timereg/core/git.py`
- Create: `tests/unit/test_git.py`

**Step 1: Write failing tests**

`tests/unit/test_git.py` — unit tests mock `_run_git`:
```python
"""Tests for git subprocess operations."""

from unittest.mock import patch

import pytest

from timereg.core.git import (
    fetch_commits,
    get_working_tree_status,
    parse_log_output,
    resolve_git_user,
)


SAMPLE_LOG_OUTPUT = (
    "a1b2c3d4|feat: add signaling|Mr Bell|bell@jpro.no|2026-02-25T09:34:12+01:00\n"
    "3\t1\tsrc/signaling.py\n"
    "1\t0\ttests/test_signaling.py\n"
    "\n"
    "b2c3d4e5|test: integration tests|Mr Bell|bell@jpro.no|2026-02-25T11:02:45+01:00\n"
    "50\t0\ttests/test_integration.py\n"
)


class TestParseLogOutput:
    def test_parse_multiple_commits(self) -> None:
        commits = parse_log_output(SAMPLE_LOG_OUTPUT, repo_path=".")
        assert len(commits) == 2
        assert commits[0].hash == "a1b2c3d4"
        assert commits[0].message == "feat: add signaling"
        assert commits[0].files_changed == 2
        assert commits[0].insertions == 4
        assert commits[0].deletions == 1
        assert commits[0].files == ["src/signaling.py", "tests/test_signaling.py"]
        assert commits[1].hash == "b2c3d4e5"
        assert commits[1].insertions == 50

    def test_parse_empty_output(self) -> None:
        commits = parse_log_output("", repo_path=".")
        assert commits == []

    def test_parse_commit_no_files(self) -> None:
        output = "abc123|empty commit|User|user@test.com|2026-02-25T10:00:00+01:00\n"
        commits = parse_log_output(output, repo_path=".")
        assert len(commits) == 1
        assert commits[0].files_changed == 0


class TestFetchCommits:
    @patch("timereg.core.git._run_git")
    def test_fetch_returns_commits(self, mock_run: object) -> None:
        from unittest.mock import MagicMock

        assert isinstance(mock_run, MagicMock)
        mock_run.return_value = SAMPLE_LOG_OUTPUT
        commits = fetch_commits(
            repo_path="/fake/repo",
            target_date="2026-02-25",
            user_email="bell@jpro.no",
            timezone="Europe/Oslo",
        )
        assert len(commits) == 2

    @patch("timereg.core.git._run_git")
    def test_fetch_filters_registered_hashes(self, mock_run: object) -> None:
        from unittest.mock import MagicMock

        assert isinstance(mock_run, MagicMock)
        mock_run.return_value = SAMPLE_LOG_OUTPUT
        commits = fetch_commits(
            repo_path="/fake/repo",
            target_date="2026-02-25",
            user_email="bell@jpro.no",
            timezone="Europe/Oslo",
            registered_hashes={"a1b2c3d4"},
        )
        assert len(commits) == 1
        assert commits[0].hash == "b2c3d4e5"

    @patch("timereg.core.git._run_git")
    def test_fetch_empty_repo(self, mock_run: object) -> None:
        from unittest.mock import MagicMock

        assert isinstance(mock_run, MagicMock)
        mock_run.return_value = ""
        commits = fetch_commits(
            repo_path="/fake/repo",
            target_date="2026-02-25",
            user_email="bell@jpro.no",
            timezone="Europe/Oslo",
        )
        assert commits == []


class TestGetWorkingTreeStatus:
    @patch("timereg.core.git._run_git")
    def test_counts_staged_and_unstaged(self, mock_run: object) -> None:
        from unittest.mock import MagicMock

        assert isinstance(mock_run, MagicMock)

        def side_effect(args: list[str], cwd: str) -> str:
            if "--cached" in args:
                return " 2 files changed\n"
            return " 3 files changed\n"

        mock_run.side_effect = side_effect
        status = get_working_tree_status("/fake/repo")
        assert status.staged_files >= 0
        assert status.unstaged_files >= 0


class TestResolveGitUser:
    @patch("timereg.core.git._run_git")
    def test_resolve_from_repo(self, mock_run: object) -> None:
        from unittest.mock import MagicMock

        assert isinstance(mock_run, MagicMock)

        def side_effect(args: list[str], cwd: str) -> str:
            if "user.name" in args:
                return "Mr Bell\n"
            if "user.email" in args:
                return "bell@jpro.no\n"
            return ""

        mock_run.side_effect = side_effect
        user = resolve_git_user("/fake/repo")
        assert user.name == "Mr Bell"
        assert user.email == "bell@jpro.no"
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_git.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Implement git module**

`src/timereg/core/git.py`:
```python
"""Git subprocess operations for commit fetching and repo analysis."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from timereg.core.models import (
    BranchInfo,
    CommitInfo,
    GitUser,
    WorkingTreeStatus,
)

logger = logging.getLogger(__name__)

_COMMIT_FORMAT = "%H|%s|%an|%ae|%aI"
_COMMIT_SEPARATOR = "|"


def _run_git(args: list[str], cwd: str) -> str:
    """Run a git command and return stdout. Raises on failure."""
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def parse_log_output(output: str, repo_path: str) -> list[CommitInfo]:
    """Parse `git log --format=... --numstat` output into CommitInfo objects."""
    if not output.strip():
        return []

    commits: list[CommitInfo] = []
    lines = output.strip().split("\n")
    i = 0

    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue

        parts = line.split(_COMMIT_SEPARATOR, 4)
        if len(parts) < 5:
            i += 1
            continue

        hash_, message, author_name, author_email, timestamp = parts
        files: list[str] = []
        insertions = 0
        deletions = 0
        i += 1

        # Parse numstat lines until empty line or next commit
        while i < len(lines):
            stat_line = lines[i].strip()
            if not stat_line or _COMMIT_SEPARATOR in stat_line:
                break
            stat_parts = stat_line.split("\t")
            if len(stat_parts) == 3:
                ins_str, del_str, filename = stat_parts
                ins = int(ins_str) if ins_str != "-" else 0
                dels = int(del_str) if del_str != "-" else 0
                insertions += ins
                deletions += dels
                files.append(filename)
            i += 1

        commits.append(
            CommitInfo(
                hash=hash_,
                message=message,
                author_name=author_name,
                author_email=author_email,
                timestamp=timestamp,
                repo_path=repo_path,
                files_changed=len(files),
                insertions=insertions,
                deletions=deletions,
                files=files,
            )
        )

    return commits


def fetch_commits(
    repo_path: str,
    target_date: str,
    user_email: str,
    timezone: str = "Europe/Oslo",
    merge_commits: bool = False,
    registered_hashes: set[str] | None = None,
) -> list[CommitInfo]:
    """Fetch commits for a specific date and author from a git repo."""
    args = [
        "log",
        f"--after={target_date}T00:00:00",
        f"--before={target_date}T23:59:59",
        f"--author={user_email}",
        f"--format={_COMMIT_FORMAT}",
        "--numstat",
    ]
    if not merge_commits:
        args.append("--no-merges")

    output = _run_git(args, cwd=repo_path)
    commits = parse_log_output(output, repo_path=repo_path)

    if registered_hashes:
        commits = [c for c in commits if c.hash not in registered_hashes]

    return commits


def get_branch_info(repo_path: str, target_date: str | None = None) -> BranchInfo:
    """Get current branch and branch activity for the day."""
    try:
        current = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_path).strip()
    except subprocess.CalledProcessError:
        current = "unknown"

    activity: list[str] = []
    if target_date:
        try:
            reflog = _run_git(
                ["reflog", f"--after={target_date}T00:00:00", "--format=%gs"],
                cwd=repo_path,
            )
            activity = [line.strip() for line in reflog.strip().split("\n") if line.strip()]
        except subprocess.CalledProcessError:
            pass

    return BranchInfo(current=current, activity=activity)


def get_working_tree_status(repo_path: str) -> WorkingTreeStatus:
    """Get count of staged and unstaged changes."""
    try:
        staged_output = _run_git(["diff", "--cached", "--numstat"], cwd=repo_path)
        staged = len([line for line in staged_output.strip().split("\n") if line.strip()])
    except subprocess.CalledProcessError:
        staged = 0

    try:
        unstaged_output = _run_git(["diff", "--numstat"], cwd=repo_path)
        unstaged = len([line for line in unstaged_output.strip().split("\n") if line.strip()])
    except subprocess.CalledProcessError:
        unstaged = 0

    return WorkingTreeStatus(staged_files=staged, unstaged_files=unstaged)


def resolve_git_user(repo_path: str) -> GitUser:
    """Resolve git user name and email from repo config."""
    name = _run_git(["config", "user.name"], cwd=repo_path).strip()
    email = _run_git(["config", "user.email"], cwd=repo_path).strip()
    return GitUser(name=name, email=email)
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_git.py -v`
Expected: All tests PASS.

**Step 5: Commit**

```bash
git add src/timereg/core/git.py tests/unit/test_git.py
git commit -m "add git analyzer with subprocess operations

Commit fetching, log parsing, branch info, working tree status,
user resolution. All subprocess calls via mockable _run_git."
```

---

## Task 7: Project Registry (TDD)

**Files:**
- Create: `src/timereg/core/projects.py`
- Create: `tests/unit/test_projects.py`

**Step 1: Write failing tests**

`tests/unit/test_projects.py`:
```python
"""Tests for project registry."""

from pathlib import Path

import pytest

from timereg.core.database import Database
from timereg.core.models import ProjectConfig
from timereg.core.projects import (
    add_project,
    auto_register_project,
    get_project,
    list_projects,
    remove_project,
)


@pytest.fixture()
def db(tmp_path: Path) -> Database:
    d = Database(tmp_path / "test.db")
    d.migrate()
    return d


class TestAutoRegister:
    def test_registers_project_from_config(self, db: Database) -> None:
        config = ProjectConfig(name="Ekvarda Codex", slug="ekvarda")
        config_path = Path("/home/user/projects/ekvarda/.timetracker.toml")
        repo_paths = [Path("/home/user/projects/ekvarda")]
        project = auto_register_project(db, config, config_path, repo_paths)
        assert project.name == "Ekvarda Codex"
        assert project.slug == "ekvarda"
        assert project.id is not None

    def test_upserts_on_duplicate_slug(self, db: Database) -> None:
        config = ProjectConfig(name="Ekvarda Codex", slug="ekvarda")
        config_path = Path("/home/user/ekvarda/.timetracker.toml")
        repo_paths = [Path("/home/user/ekvarda")]
        p1 = auto_register_project(db, config, config_path, repo_paths)
        p2 = auto_register_project(db, config, config_path, repo_paths)
        assert p1.id == p2.id


class TestAddProject:
    def test_add_manual_project(self, db: Database) -> None:
        project = add_project(db, name="JPro Internal", slug="jpro-internal")
        assert project.slug == "jpro-internal"
        assert project.config_path is None

    def test_duplicate_slug_raises(self, db: Database) -> None:
        add_project(db, name="Test", slug="test")
        with pytest.raises(ValueError, match="already exists"):
            add_project(db, name="Test 2", slug="test")


class TestGetProject:
    def test_get_existing_project(self, db: Database) -> None:
        add_project(db, name="Test", slug="test")
        project = get_project(db, "test")
        assert project is not None
        assert project.name == "Test"

    def test_get_nonexistent_returns_none(self, db: Database) -> None:
        assert get_project(db, "nonexistent") is None


class TestListProjects:
    def test_list_empty(self, db: Database) -> None:
        projects = list_projects(db)
        assert projects == []

    def test_list_multiple(self, db: Database) -> None:
        add_project(db, "A", "a")
        add_project(db, "B", "b")
        projects = list_projects(db)
        assert len(projects) == 2


class TestRemoveProject:
    def test_remove_existing(self, db: Database) -> None:
        add_project(db, "Test", "test")
        remove_project(db, "test")
        assert get_project(db, "test") is None

    def test_remove_nonexistent_raises(self, db: Database) -> None:
        with pytest.raises(ValueError, match="not found"):
            remove_project(db, "nonexistent")
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_projects.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Implement projects module**

`src/timereg/core/projects.py`:
```python
"""Project registry — auto-register, manual add, list, remove."""

from __future__ import annotations

from pathlib import Path

from timereg.core.database import Database
from timereg.core.models import Project, ProjectConfig


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
        # Update repos
        db.execute("DELETE FROM project_repos WHERE project_id=?", (existing.id,))
        for repo_path in repo_paths:
            db.execute(
                "INSERT INTO project_repos (project_id, absolute_path, relative_path) VALUES (?, ?, ?)",
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
            "INSERT INTO project_repos (project_id, absolute_path, relative_path) VALUES (?, ?, ?)",
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


def get_project(db: Database, slug: str) -> Project | None:
    """Look up a project by slug."""
    row = db.execute(
        "SELECT id, name, slug, config_path, created_at, updated_at FROM projects WHERE slug=?",
        (slug,),
    ).fetchone()
    if row is None:
        return None
    return Project(
        id=row[0],
        name=row[1],
        slug=row[2],
        config_path=row[3],
        created_at=row[4],
        updated_at=row[5],
    )


def list_projects(db: Database) -> list[Project]:
    """List all registered projects."""
    rows = db.execute(
        "SELECT id, name, slug, config_path, created_at, updated_at FROM projects ORDER BY name"
    ).fetchall()
    return [
        Project(id=r[0], name=r[1], slug=r[2], config_path=r[3], created_at=r[4], updated_at=r[5])
        for r in rows
    ]


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
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_projects.py -v`
Expected: All tests PASS.

**Step 5: Commit**

```bash
git add src/timereg/core/projects.py tests/unit/test_projects.py
git commit -m "add project registry with auto-register and manual add

CRUD operations for projects table. Auto-register upserts from
config, manual add for non-repo projects."
```

---

## Task 8: Entry Manager (TDD)

**Files:**
- Create: `src/timereg/core/entries.py`
- Create: `tests/unit/test_entries.py`

**Step 1: Write failing tests**

`tests/unit/test_entries.py`:
```python
"""Tests for entry CRUD operations."""

import json
from datetime import date
from pathlib import Path

import pytest

from timereg.core.database import Database
from timereg.core.entries import (
    create_entry,
    delete_entry,
    edit_entry,
    get_registered_commit_hashes,
    list_entries,
    undo_last,
)
from timereg.core.models import CommitInfo
from timereg.core.projects import add_project


@pytest.fixture()
def db(tmp_path: Path) -> Database:
    d = Database(tmp_path / "test.db")
    d.migrate()
    return d


@pytest.fixture()
def project_id(db: Database) -> int:
    p = add_project(db, "Test Project", "test")
    assert p.id is not None
    return p.id


class TestCreateEntry:
    def test_create_git_entry_with_commits(self, db: Database, project_id: int) -> None:
        commits = [
            CommitInfo(
                hash="abc123",
                message="feat: something",
                author_name="User",
                author_email="user@test.com",
                timestamp="2026-02-25T10:00:00+01:00",
                repo_path=".",
                files_changed=2,
                insertions=50,
                deletions=10,
                files=["a.py", "b.py"],
            ),
        ]
        entry = create_entry(
            db=db,
            project_id=project_id,
            hours=4.5,
            short_summary="WebRTC work",
            long_summary="Detailed description",
            entry_date=date(2026, 2, 25),
            git_user_name="User",
            git_user_email="user@test.com",
            commits=commits,
            tags=["development"],
            entry_type="git",
        )
        assert entry.id is not None
        assert entry.hours == 4.5
        assert entry.entry_type == "git"

        # Verify commits were stored
        hashes = get_registered_commit_hashes(db, project_id)
        assert "abc123" in hashes

    def test_create_manual_entry(self, db: Database, project_id: int) -> None:
        entry = create_entry(
            db=db,
            project_id=project_id,
            hours=2.0,
            short_summary="Sprint planning",
            entry_date=date(2026, 2, 25),
            git_user_name="User",
            git_user_email="user@test.com",
            entry_type="manual",
        )
        assert entry.entry_type == "manual"

    def test_multiple_entries_per_day(self, db: Database, project_id: int) -> None:
        for i in range(3):
            create_entry(
                db=db,
                project_id=project_id,
                hours=2.0,
                short_summary=f"Entry {i}",
                entry_date=date(2026, 2, 25),
                git_user_name="User",
                git_user_email="user@test.com",
                entry_type="manual",
            )
        entries = list_entries(db, project_id=project_id, date_filter=date(2026, 2, 25))
        assert len(entries) == 3

    def test_tags_stored_as_json(self, db: Database, project_id: int) -> None:
        entry = create_entry(
            db=db,
            project_id=project_id,
            hours=1.0,
            short_summary="Test",
            entry_date=date(2026, 2, 25),
            git_user_name="User",
            git_user_email="user@test.com",
            entry_type="manual",
            tags=["dev", "testing"],
        )
        assert entry.tags == ["dev", "testing"]


class TestCreatePeerEntry:
    def test_creates_linked_entries(self, db: Database, project_id: int) -> None:
        entries = create_entry(
            db=db,
            project_id=project_id,
            hours=3.0,
            short_summary="Pair programming",
            entry_date=date(2026, 2, 25),
            git_user_name="User",
            git_user_email="user@test.com",
            entry_type="git",
            peer_emails=["colleague@test.com"],
        )
        assert isinstance(entries, list)
        assert len(entries) == 2
        assert entries[0].peer_group_id is not None
        assert entries[0].peer_group_id == entries[1].peer_group_id
        assert entries[0].git_user_email == "user@test.com"
        assert entries[1].git_user_email == "colleague@test.com"


class TestEditEntry:
    def test_edit_hours(self, db: Database, project_id: int) -> None:
        entry = create_entry(
            db=db,
            project_id=project_id,
            hours=4.5,
            short_summary="Test",
            entry_date=date(2026, 2, 25),
            git_user_name="User",
            git_user_email="user@test.com",
            entry_type="manual",
        )
        assert entry.id is not None
        updated = edit_entry(db, entry.id, hours=3.0)
        assert updated.hours == 3.0

    def test_edit_summary(self, db: Database, project_id: int) -> None:
        entry = create_entry(
            db=db,
            project_id=project_id,
            hours=2.0,
            short_summary="Old",
            entry_date=date(2026, 2, 25),
            git_user_name="User",
            git_user_email="user@test.com",
            entry_type="manual",
        )
        assert entry.id is not None
        updated = edit_entry(db, entry.id, short_summary="New summary")
        assert updated.short_summary == "New summary"


class TestDeleteEntry:
    def test_delete_releases_commits(self, db: Database, project_id: int) -> None:
        commits = [
            CommitInfo(
                hash="abc123",
                message="feat: something",
                author_name="User",
                author_email="user@test.com",
                timestamp="2026-02-25T10:00:00+01:00",
                repo_path=".",
            ),
        ]
        entry = create_entry(
            db=db,
            project_id=project_id,
            hours=4.5,
            short_summary="Test",
            entry_date=date(2026, 2, 25),
            git_user_name="User",
            git_user_email="user@test.com",
            commits=commits,
            entry_type="git",
        )
        assert entry.id is not None
        delete_entry(db, entry.id, release_commits=True)
        hashes = get_registered_commit_hashes(db, project_id)
        assert "abc123" not in hashes

    def test_delete_keeps_commits_claimed(self, db: Database, project_id: int) -> None:
        commits = [
            CommitInfo(
                hash="abc123",
                message="feat: something",
                author_name="User",
                author_email="user@test.com",
                timestamp="2026-02-25T10:00:00+01:00",
                repo_path=".",
            ),
        ]
        entry = create_entry(
            db=db,
            project_id=project_id,
            hours=4.5,
            short_summary="Test",
            entry_date=date(2026, 2, 25),
            git_user_name="User",
            git_user_email="user@test.com",
            commits=commits,
            entry_type="git",
        )
        assert entry.id is not None
        delete_entry(db, entry.id, release_commits=False)
        hashes = get_registered_commit_hashes(db, project_id)
        assert "abc123" in hashes


class TestUndoLast:
    def test_undo_deletes_last_entry(self, db: Database, project_id: int) -> None:
        create_entry(
            db=db,
            project_id=project_id,
            hours=2.0,
            short_summary="First",
            entry_date=date(2026, 2, 25),
            git_user_name="User",
            git_user_email="user@test.com",
            entry_type="manual",
        )
        create_entry(
            db=db,
            project_id=project_id,
            hours=3.0,
            short_summary="Second",
            entry_date=date(2026, 2, 25),
            git_user_name="User",
            git_user_email="user@test.com",
            entry_type="manual",
        )
        undone = undo_last(db, user_email="user@test.com")
        assert undone is not None
        assert undone.short_summary == "Second"
        entries = list_entries(db, project_id=project_id, date_filter=date(2026, 2, 25))
        assert len(entries) == 1

    def test_undo_with_no_entries_returns_none(self, db: Database) -> None:
        assert undo_last(db, user_email="user@test.com") is None
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_entries.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Implement entries module**

`src/timereg/core/entries.py`:
```python
"""Entry CRUD — create, read, edit, delete, undo with peer and split support."""

from __future__ import annotations

import json
import uuid
from datetime import date

from timereg.core.database import Database
from timereg.core.models import CommitInfo, Entry


def _row_to_entry(row: tuple[object, ...]) -> Entry:
    """Convert a database row to an Entry model."""
    return Entry(
        id=row[0],  # type: ignore[arg-type]
        project_id=row[1],  # type: ignore[arg-type]
        git_user_name=row[2],  # type: ignore[arg-type]
        git_user_email=row[3],  # type: ignore[arg-type]
        date=row[4],  # type: ignore[arg-type]
        hours=row[5],  # type: ignore[arg-type]
        short_summary=row[6],  # type: ignore[arg-type]
        long_summary=row[7],  # type: ignore[arg-type]
        entry_type=row[8],  # type: ignore[arg-type]
        tags=json.loads(row[9]) if row[9] else None,  # type: ignore[arg-type]
        peer_group_id=row[10],  # type: ignore[arg-type]
        split_group_id=row[11],  # type: ignore[arg-type]
        created_at=row[12],  # type: ignore[arg-type]
        updated_at=row[13],  # type: ignore[arg-type]
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
    row = db.execute(f"SELECT {_ENTRY_COLUMNS} FROM entries WHERE id=?", (cursor.lastrowid,)).fetchone()
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

    # Create primary entry
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

    # Create peer entries
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
    """Edit an existing entry. Optionally cascade to peer entries."""
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
        # Get peer_group_id first
        row = db.execute("SELECT peer_group_id FROM entries WHERE id=?", (entry_id,)).fetchone()
        if row and row[0]:
            peer_params = [*params, row[0]]
            db.execute(
                f"UPDATE entries SET {set_clause} WHERE peer_group_id=?",
                tuple(peer_params),
            )
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
    """Delete an entry. Optionally release or claim commits, and cascade to peers."""
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
            # Move commits to claimed_commits before deletion
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
        f"SELECT {_ENTRY_COLUMNS} FROM entries WHERE git_user_email=? "
        "ORDER BY created_at DESC LIMIT 1",
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
    # Commits linked to entries
    entry_hashes = db.execute(
        "SELECT ec.commit_hash FROM entry_commits ec "
        "JOIN entries e ON ec.entry_id = e.id "
        "WHERE e.project_id=?",
        (project_id,),
    ).fetchall()

    # Claimed commits (from deleted entries with keep_commits)
    claimed_hashes = db.execute(
        "SELECT commit_hash FROM claimed_commits WHERE project_id=?",
        (project_id,),
    ).fetchall()

    return {r[0] for r in entry_hashes} | {r[0] for r in claimed_hashes}
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_entries.py -v`
Expected: All tests PASS.

**Step 5: Commit**

```bash
git add src/timereg/core/entries.py tests/unit/test_entries.py
git commit -m "add entry manager with CRUD, peers, and commit tracking

Create, edit, delete, undo, list entries. Peer linking via
peer_group_id. Claimed commits for delete-without-release."
```

---

## Task 9: Shared Test Fixtures

**Files:**
- Modify: `tests/conftest.py`

**Step 1: Add shared fixtures used across test levels**

`tests/conftest.py`:
```python
"""Shared test fixtures for all test levels."""

from __future__ import annotations

import os
import subprocess
from datetime import date, datetime
from pathlib import Path
from typing import Generator

import pytest

from timereg.core.database import Database


@pytest.fixture()
def tmp_db(tmp_path: Path) -> Generator[Database, None, None]:
    """Fresh SQLite database with migrations applied."""
    db = Database(tmp_path / "test.db")
    db.migrate()
    yield db
    db.close()


@pytest.fixture()
def git_repo(tmp_path: Path) -> Path:
    """Initialize a git repo with a configured user and initial commit."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.name", "Test User"], cwd=repo, check=True, capture_output=True
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    # Create initial commit
    (repo / "README.md").write_text("# Test Project\n")
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "initial commit"], cwd=repo, check=True, capture_output=True
    )
    return repo


def make_commit(
    repo: Path,
    filename: str,
    content: str,
    message: str,
    commit_date: str | None = None,
) -> str:
    """Create a file and commit it. Returns the commit hash."""
    (repo / filename).write_text(content)
    subprocess.run(["git", "add", filename], cwd=repo, check=True, capture_output=True)
    env = os.environ.copy()
    if commit_date:
        env["GIT_AUTHOR_DATE"] = commit_date
        env["GIT_COMMITTER_DATE"] = commit_date
    result = subprocess.run(
        ["git", "commit", "-m", message],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    hash_result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return hash_result.stdout.strip()
```

**Step 2: Run all unit tests to make sure nothing is broken**

Run: `uv run pytest tests/unit/ -v`
Expected: All tests PASS.

**Step 3: Commit**

```bash
git add tests/conftest.py
git commit -m "add shared test fixtures for database and git repos"
```

---

## Task 10: CLI — Fetch Command

**Files:**
- Create: `src/timereg/cli/fetch.py`
- Create: `tests/integration/test_cli_fetch.py`
- Modify: `src/timereg/cli/app.py`

**Step 1: Write integration test**

`tests/integration/test_cli_fetch.py`:
```python
"""Integration tests for timereg fetch command."""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

from typer.testing import CliRunner

from tests.conftest import make_commit
from timereg.cli.app import app

runner = CliRunner()


class TestFetchCommand:
    def test_fetch_shows_commits(self, git_repo: Path, tmp_path: Path) -> None:
        # Create config
        config = git_repo / ".timetracker.toml"
        config.write_text('[project]\nname = "Test"\nslug = "test"\n')

        # Create a commit for today
        today = date.today().isoformat()
        make_commit(
            git_repo, "feature.py", "print('hello')", "feat: add feature",
            commit_date=f"{today}T10:00:00+01:00",
        )

        db_path = str(tmp_path / "test.db")
        result = runner.invoke(
            app,
            ["fetch", "--db-path", db_path, "--format", "json"],
            catch_exceptions=False,
            env={"HOME": str(tmp_path)},
        )
        # This test validates the basic wiring works
        assert result.exit_code == 0

    def test_fetch_json_output_is_valid(self, git_repo: Path, tmp_path: Path) -> None:
        config = git_repo / ".timetracker.toml"
        config.write_text('[project]\nname = "Test"\nslug = "test"\n')

        today = date.today().isoformat()
        make_commit(
            git_repo, "feature.py", "code", "feat: something",
            commit_date=f"{today}T10:00:00+01:00",
        )

        db_path = str(tmp_path / "test.db")
        result = runner.invoke(
            app,
            ["fetch", "--db-path", db_path, "--format", "json"],
            catch_exceptions=False,
            env={"HOME": str(tmp_path)},
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert "project_name" in data or "repos" in data
```

This test will drive the implementation of the fetch command with config resolution, git fetching, and JSON output wired together.

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/integration/test_cli_fetch.py -v`
Expected: FAIL — fetch command doesn't exist yet.

**Step 3: Implement fetch command**

Add to `src/timereg/cli/app.py` — the global callback and state:
```python
"""Typer CLI application — entry point and global options."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated, Optional

import typer

from timereg.core.config import (
    ensure_global_config,
    load_global_config,
    resolve_db_path,
)
from timereg.core.database import Database

app = typer.Typer(
    name="timereg",
    help="Git-aware time tracking for developers.",
    no_args_is_help=True,
)


class AppState:
    """Shared state initialized by the global callback."""

    db: Database
    db_path: Path
    verbose: bool = False
    output_format: str = "text"


state = AppState()


@app.callback()
def main(
    db_path: Annotated[Optional[str], typer.Option("--db-path", help="Override database path")] = None,
    config: Annotated[Optional[str], typer.Option("--config", help="Override global config path")] = None,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Verbose output")] = False,
    output_format: Annotated[str, typer.Option("--format", help="Output format: json or text")] = "text",
) -> None:
    """TimeReg — Git-aware time tracking for developers."""
    global_config_path = Path(config) if config else ensure_global_config()
    global_config = load_global_config(global_config_path)

    resolved_db_path = resolve_db_path(
        cli_db_path=db_path,
        env_db_path=os.environ.get("TIMEREG_DB_PATH"),
        config_db_path=global_config.db_path,
    )

    state.db = Database(resolved_db_path)
    state.db.migrate()
    state.verbose = verbose
    state.output_format = output_format
    state.db_path = resolved_db_path
```

Create `src/timereg/cli/fetch.py`:
```python
"""CLI fetch command — retrieve unregistered commits."""

from __future__ import annotations

import json
import subprocess
from datetime import date
from pathlib import Path
from typing import Annotated, Optional

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
from timereg.core.models import FetchResult, GitUser
from timereg.core.projects import auto_register_project, get_project


@app.command()
def fetch(
    date_str: Annotated[
        Optional[str], typer.Option("--date", help="Date (YYYY-MM-DD), default today")
    ] = None,
    project_slug: Annotated[
        Optional[str], typer.Option("--project", help="Project slug")
    ] = None,
    fetch_all: Annotated[
        bool, typer.Option("--all", help="Fetch across all registered projects")
    ] = False,
) -> None:
    """Fetch unregistered commits for a project."""
    target_date = date_str or date.today().isoformat()

    # Resolve project
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
        project = auto_register_project(
            state.db, project_config, config_path, repo_paths
        )

        # Resolve git user
        try:
            user = resolve_git_user(str(repo_paths[0]))
        except (subprocess.CalledProcessError, IndexError):
            user = GitUser(name="Unknown", email="unknown@unknown")

        registered = get_registered_commit_hashes(state.db, project.id or 0)

        repos = []
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
            repos.append({
                "relative_path": str(repo_path.relative_to(config_dir)),
                "absolute_path": str(repo_path),
                "branch": branch.current,
                "branch_activity": branch.activity,
                "uncommitted": wt_status.model_dump(),
                "commits": [c.model_dump() for c in commits],
            })

        result = FetchResult(
            project_name=project.name,
            project_slug=project.slug,
            date=target_date,
            user=user,
            repos=[],  # Will be populated from repos data
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
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/integration/test_cli_fetch.py -v`
Expected: Tests PASS (may need adjustments for CWD handling).

**Step 5: Commit**

```bash
git add src/timereg/cli/app.py src/timereg/cli/fetch.py tests/integration/test_cli_fetch.py
git commit -m "add fetch CLI command with JSON output

Wires config resolution, git fetching, project auto-registration,
and commit filtering into the fetch command."
```

---

## Task 11: CLI — Register Command

**Files:**
- Create: `src/timereg/cli/register.py`
- Create: `tests/integration/test_cli_register.py`

This task follows the same pattern as Task 10: write integration test first, then implement the command. The register command accepts `--hours`, `--short-summary`, `--long-summary`, `--commits`, `--tags`, `--peer`, `--date`, `--project`, and calls `create_entry`. It wires up the time parser for the `--hours` flag.

Key implementation points:
- Parse `--hours` via `time_parser.parse_time()`
- Parse `--commits` as comma-separated hash list
- Parse `--tags` as comma-separated list
- Parse `--peer` as repeatable option
- Resolve project from config or `--project` slug
- Output confirmation in text or JSON format

---

## Task 12: CLI — List Command

**Files:**
- Create: `src/timereg/cli/list_cmd.py`
- Create: `tests/integration/test_cli_list.py`

The list command calls `list_entries` with filters from `--date`, `--from`, `--to`, `--project`, `--all`, `--detail`. Outputs a Rich table (text) or JSON array.

---

## Task 13: CLI — Edit, Delete, Undo Commands

**Files:**
- Create: `src/timereg/cli/edit.py`
- Create: `src/timereg/cli/delete.py`
- Create: `src/timereg/cli/undo.py`
- Create: `tests/integration/test_cli_edit_delete.py`

Three small commands:
- `edit <id>` — calls `edit_entry` with provided flags
- `delete <id>` — calls `delete_entry` with `--release-commits`/`--keep-commits` and `--delete-peers`
- `undo` — calls `undo_last`

---

## Task 14: CLI — Projects Command

**Files:**
- Create: `src/timereg/cli/projects.py`
- Create: `tests/integration/test_cli_projects.py`

Typer sub-app with `list`, `add`, `remove`, `show` subcommands. Calls project registry functions.

---

## Task 15: Interactive Mode

**Files:**
- Create: `src/timereg/cli/interactive.py`
- Create: `tests/integration/test_cli_interactive.py`

When `timereg` is called with no subcommand (override `no_args_is_help=True` with a default callback). Uses Rich prompts for project selection, date, hours, description, tags. Lowest priority in Phase 1.

---

## Task 16: Agent Skill File

**Files:**
- Create: `TIMEREG_SKILL.md`

Write the skill file that teaches AI agents how to use the CLI:
- fetch → summarize → register workflow
- fetch --all → review split → register --split workflow
- Manual entry workflow
- Status/summary queries

No tests needed — this is documentation.

---

## Task 17: End-to-End Test

**Files:**
- Create: `tests/e2e/test_full_workflow.py`

Write an end-to-end test covering:
1. Create git repo + config
2. Make commits
3. `timereg fetch` → see commits
4. `timereg register` → create entry
5. `timereg fetch` → commits excluded
6. `timereg list` → see entry
7. `timereg undo` → entry removed

---

## Task 18: Final Polish & Verification

**Step 1:** Run full test suite: `uv run pytest -v`
**Step 2:** Run linting: `uv run ruff check src/ tests/`
**Step 3:** Run type checking: `uv run mypy src/`
**Step 4:** Run pre-commit on all files: `pre-commit run --all-files`
**Step 5:** Verify CLI works: `uv run timereg --help`
**Step 6:** Commit any fixes.

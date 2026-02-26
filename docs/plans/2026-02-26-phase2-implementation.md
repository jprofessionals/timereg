# Phase 2: Multi-Repo, Reporting & Advanced Features — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add multi-repo fetch with full context, summary/status/check/export commands, budget tracking, and constrained tags to TimeReg.

**Architecture:** Four new core modules (`reports.py`, `checks.py`, `export.py`) plus a migration adding budget/tag columns to `projects`. Existing modules (`git.py`, `entries.py`, `config.py`, `projects.py`, `models.py`) are extended. Four new CLI commands wire into the existing Typer app.

**Tech Stack:** Python 3.12+, uv, Typer, Rich, Pydantic, SQLite, stdlib `csv` module.

---

## Context for Implementers

**Existing codebase layout:**
- `src/timereg/core/` — Business logic (database.py, models.py, config.py, git.py, entries.py, projects.py, time_parser.py)
- `src/timereg/cli/` — Typer CLI commands (app.py, fetch.py, register.py, list_cmd.py, edit.py, delete.py, undo.py, projects.py, interactive.py)
- `src/timereg/cli/__init__.py` — Shared `entry_to_dict()` helper
- `src/timereg/migrations/` — Sequential SQL files (currently only `001_initial.sql`)
- `tests/unit/`, `tests/integration/`, `tests/e2e/` — Three test levels
- `tests/conftest.py` — Shared fixtures: `tmp_db`, `git_repo`, `make_commit()`

**Key patterns:**
- All CLI commands import `app` and `state` from `timereg.cli.app`
- `state.db` is the Database instance, `state.output_format` is "json" or "text"
- CLI modules register commands via `@app.command()` and are imported at the bottom of `app.py`
- Core functions take `Database` as first arg, return Pydantic models
- Tests use `tmp_db` fixture (Database with migrations applied) and `git_repo` fixture (temp git repo with user configured)

**What already exists that we build on:**
- `ProjectConfig` already parses `[tags] allowed`, `[budget] weekly_hours`, `[budget] monthly_hours` from `.timetracker.toml`
- `cli/fetch.py` already iterates all repo paths and queries branch info + working tree status per repo
- `FetchResult`, `RepoFetchResult` models exist but aren't used by the CLI
- `get_branch_info()`, `get_working_tree_status()` exist in `core/git.py`
- `list_entries()` in `core/entries.py` supports date range and project filtering

---

### Task 1: Migration — Add Budget & Tags Columns

**Files:**
- Create: `src/timereg/migrations/002_add_budget_and_tags.sql`
- Test: `tests/unit/test_database.py`

**What to build:** A migration that adds `weekly_hours`, `monthly_hours`, and `allowed_tags` columns to the `projects` table. These columns store budget configuration and constrained tag lists so they're accessible without requiring the `.timetracker.toml` file to be present.

**Step 1: Write the migration SQL**

Create `src/timereg/migrations/002_add_budget_and_tags.sql`:

```sql
-- Add budget tracking and tag constraints to projects
ALTER TABLE projects ADD COLUMN weekly_hours REAL;
ALTER TABLE projects ADD COLUMN monthly_hours REAL;
ALTER TABLE projects ADD COLUMN allowed_tags TEXT;
```

`weekly_hours` and `monthly_hours` are floats (NULL for no budget). `allowed_tags` is a JSON array string or NULL (NULL means freeform tags allowed).

**Step 2: Write tests for migration**

Add to `tests/unit/test_database.py` in the `TestMigrations` class:

```python
def test_migrate_adds_budget_columns(self, tmp_path: Path) -> None:
    db = Database(tmp_path / "test.db")
    db.migrate()
    # Insert a project and verify budget columns exist and are nullable
    db.execute(
        "INSERT INTO projects (name, slug, weekly_hours, monthly_hours) VALUES (?, ?, ?, ?)",
        ("Test", "test", 20.0, 80.0),
    )
    db.commit()
    row = db.execute(
        "SELECT weekly_hours, monthly_hours FROM projects WHERE slug='test'"
    ).fetchone()
    assert row is not None
    assert row[0] == 20.0
    assert row[1] == 80.0
    db.close()

def test_migrate_adds_allowed_tags_column(self, tmp_path: Path) -> None:
    db = Database(tmp_path / "test.db")
    db.migrate()
    db.execute(
        "INSERT INTO projects (name, slug, allowed_tags) VALUES (?, ?, ?)",
        ("Test", "test", '["dev","review"]'),
    )
    db.commit()
    row = db.execute(
        "SELECT allowed_tags FROM projects WHERE slug='test'"
    ).fetchone()
    assert row is not None
    assert row[0] == '["dev","review"]'
    db.close()
```

**Step 3: Run tests**

Run: `uv run pytest tests/unit/test_database.py -v`
Expected: All pass (migration applies automatically).

**Step 4: Commit**

```bash
git add src/timereg/migrations/002_add_budget_and_tags.sql tests/unit/test_database.py
git commit -m "add migration 002: budget and tag constraint columns on projects"
```

---

### Task 2: Update Models — New Report/Status/Check Models + GlobalConfig

**Files:**
- Modify: `src/timereg/core/models.py`
- Test: `tests/unit/test_models.py`

**What to build:** Add `max_daily_hours` to `GlobalConfig`. Add `weekly_hours`, `monthly_hours`, and `allowed_tags` fields to `Project`. Add all new Phase 2 Pydantic models: `DayDetail`, `ProjectSummary`, `SummaryReport`, `ProjectStatus`, `StatusReport`, `DayCheck`, `CheckReport`.

**Step 1: Write tests for new models**

Add to `tests/unit/test_models.py`:

```python
from datetime import date

from timereg.core.models import (
    CheckReport,
    DayCheck,
    DayDetail,
    Entry,
    GlobalConfig,
    Project,
    ProjectStatus,
    ProjectSummary,
    StatusReport,
    SummaryReport,
)


class TestGlobalConfigMaxDailyHours:
    def test_default_max_daily_hours(self) -> None:
        config = GlobalConfig()
        assert config.max_daily_hours == 12.0

    def test_custom_max_daily_hours(self) -> None:
        config = GlobalConfig(max_daily_hours=10.0)
        assert config.max_daily_hours == 10.0


class TestProjectBudgetFields:
    def test_project_with_budget(self) -> None:
        p = Project(name="Test", slug="test", weekly_hours=20.0, monthly_hours=80.0)
        assert p.weekly_hours == 20.0
        assert p.monthly_hours == 80.0

    def test_project_without_budget(self) -> None:
        p = Project(name="Test", slug="test")
        assert p.weekly_hours is None
        assert p.monthly_hours is None

    def test_project_with_allowed_tags(self) -> None:
        p = Project(name="Test", slug="test", allowed_tags=["dev", "review"])
        assert p.allowed_tags == ["dev", "review"]


class TestSummaryModels:
    def test_day_detail(self) -> None:
        d = DayDetail(date=date(2026, 2, 25), entries=[], total_hours=0.0)
        assert d.total_hours == 0.0

    def test_project_summary(self) -> None:
        p = Project(name="Test", slug="test")
        s = ProjectSummary(project=p, days=[], total_hours=7.5, budget_weekly=20.0)
        assert s.budget_percent is None  # not computed by model

    def test_summary_report(self) -> None:
        r = SummaryReport(
            period_start=date(2026, 2, 24),
            period_end=date(2026, 2, 28),
            period_label="Week 9, 2026 — Feb 24 – Feb 28",
            projects=[],
            total_hours=37.5,
        )
        assert r.total_hours == 37.5


class TestStatusModels:
    def test_project_status(self) -> None:
        p = Project(name="Test", slug="test")
        s = ProjectStatus(
            project=p,
            today_hours=6.5,
            today_entry_count=2,
            unregistered_commits=3,
            week_hours=14.0,
        )
        assert s.unregistered_commits == 3

    def test_status_report(self) -> None:
        r = StatusReport(date=date(2026, 2, 25), projects=[], warnings=[])
        assert r.warnings == []


class TestCheckModels:
    def test_day_check_ok(self) -> None:
        d = DayCheck(date=date(2026, 2, 25), total_hours=7.5, unregistered_commits=0, warnings=[], ok=True)
        assert d.ok

    def test_day_check_warning(self) -> None:
        d = DayCheck(
            date=date(2026, 2, 25), total_hours=0.0, unregistered_commits=5,
            warnings=["No hours registered", "5 unregistered commits"], ok=False,
        )
        assert not d.ok
        assert len(d.warnings) == 2

    def test_check_report(self) -> None:
        r = CheckReport(
            date_from=date(2026, 2, 24), date_to=date(2026, 2, 28),
            days=[], budget_warnings=[], summary_total=27.0,
        )
        assert r.summary_total == 27.0
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_models.py -v -k "MaxDailyHours or BudgetFields or SummaryModels or StatusModels or CheckModels"`
Expected: FAIL (models don't exist yet)

**Step 3: Add models to `src/timereg/core/models.py`**

Add `max_daily_hours` to `GlobalConfig`:

```python
class GlobalConfig(BaseModel):
    """Global config from ~/.config/timereg/config.toml."""
    db_path: str | None = None
    merge_commits: bool = False
    timezone: str = "Europe/Oslo"
    user_name: str | None = None
    user_email: str | None = None
    max_daily_hours: float = 12.0
```

Add budget and tag fields to `Project`:

```python
class Project(BaseModel):
    """A registered project."""
    id: int | None = None
    name: str
    slug: str
    config_path: str | None = None
    weekly_hours: float | None = None
    monthly_hours: float | None = None
    allowed_tags: list[str] | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    # ... keep existing slug_must_be_valid validator
```

Add new models at the bottom of the file (before configuration models section):

```python
# --- Report models ---

class DayDetail(BaseModel):
    """Entries for a single day in a summary."""
    date: date
    entries: list[Entry] = Field(default_factory=list)
    total_hours: float = 0.0

class ProjectSummary(BaseModel):
    """Per-project summary with budget comparison."""
    project: Project
    days: list[DayDetail] = Field(default_factory=list)
    total_hours: float = 0.0
    budget_weekly: float | None = None
    budget_monthly: float | None = None
    budget_percent: float | None = None

class SummaryReport(BaseModel):
    """Complete summary report for a period."""
    period_start: date
    period_end: date
    period_label: str
    projects: list[ProjectSummary] = Field(default_factory=list)
    total_hours: float = 0.0

# --- Status models ---

class ProjectStatus(BaseModel):
    """Per-project status with live git data."""
    project: Project
    today_hours: float = 0.0
    today_entry_count: int = 0
    unregistered_commits: int = 0
    week_hours: float = 0.0
    budget_weekly: float | None = None
    budget_percent: float | None = None

class StatusReport(BaseModel):
    """Status dashboard across all projects."""
    date: date
    projects: list[ProjectStatus] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

# --- Check models ---

class DayCheck(BaseModel):
    """Check result for a single day."""
    date: date
    total_hours: float = 0.0
    unregistered_commits: int = 0
    warnings: list[str] = Field(default_factory=list)
    ok: bool = True

class CheckReport(BaseModel):
    """Check report for a date range."""
    date_from: date
    date_to: date
    days: list[DayCheck] = Field(default_factory=list)
    budget_warnings: list[str] = Field(default_factory=list)
    summary_total: float = 0.0
```

**Step 4: Run tests**

Run: `uv run pytest tests/unit/test_models.py -v`
Expected: All pass.

**Step 5: Commit**

```bash
git add src/timereg/core/models.py tests/unit/test_models.py
git commit -m "add Phase 2 models: report, status, check, budget fields on Project"
```

---

### Task 3: Update Config — Parse max_daily_hours, Sync Budget/Tags to DB

**Files:**
- Modify: `src/timereg/core/config.py`
- Modify: `src/timereg/core/projects.py`
- Test: `tests/unit/test_config.py`
- Test: `tests/unit/test_projects.py`

**What to build:**
1. `load_global_config()` parses `max_daily_hours` from `[defaults]` section
2. `auto_register_project()` syncs `weekly_hours`, `monthly_hours`, and `allowed_tags` to the `projects` table
3. `_row_to_project()` reads the new columns
4. `_SELECT_PROJECT` includes the new columns

**Step 1: Write tests**

Add to `tests/unit/test_config.py`:

```python
class TestGlobalConfigMaxDailyHours:
    def test_parse_max_daily_hours(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.toml"
        config_file.write_text(
            "[defaults]\nmax_daily_hours = 10.0\n"
        )
        config = load_global_config(config_file)
        assert config.max_daily_hours == 10.0

    def test_default_max_daily_hours(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.toml"
        config_file.write_text("[defaults]\n")
        config = load_global_config(config_file)
        assert config.max_daily_hours == 12.0
```

Add to `tests/unit/test_projects.py`:

```python
class TestAutoRegisterBudgetAndTags:
    def test_syncs_budget_to_db(self, tmp_db: Database, tmp_path: Path) -> None:
        config = ProjectConfig(
            name="Test", slug="test-budget",
            weekly_budget_hours=20.0, monthly_budget_hours=80.0,
        )
        config_path = tmp_path / ".timetracker.toml"
        config_path.touch()
        project = auto_register_project(tmp_db, config, config_path, [])
        row = tmp_db.execute(
            "SELECT weekly_hours, monthly_hours FROM projects WHERE id=?", (project.id,)
        ).fetchone()
        assert row is not None
        assert row[0] == 20.0
        assert row[1] == 80.0

    def test_syncs_allowed_tags_to_db(self, tmp_db: Database, tmp_path: Path) -> None:
        config = ProjectConfig(
            name="Test", slug="test-tags",
            allowed_tags=["dev", "review"],
        )
        config_path = tmp_path / ".timetracker.toml"
        config_path.touch()
        project = auto_register_project(tmp_db, config, config_path, [])
        row = tmp_db.execute(
            "SELECT allowed_tags FROM projects WHERE id=?", (project.id,)
        ).fetchone()
        assert row is not None
        assert row[0] == '["dev", "review"]'

    def test_project_model_has_budget(self, tmp_db: Database, tmp_path: Path) -> None:
        config = ProjectConfig(
            name="Test", slug="test-model",
            weekly_budget_hours=15.0,
        )
        config_path = tmp_path / ".timetracker.toml"
        config_path.touch()
        project = auto_register_project(tmp_db, config, config_path, [])
        fetched = get_project(tmp_db, "test-model")
        assert fetched is not None
        assert fetched.weekly_hours == 15.0
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_config.py::TestGlobalConfigMaxDailyHours tests/unit/test_projects.py::TestAutoRegisterBudgetAndTags -v`
Expected: FAIL

**Step 3: Implement**

In `config.py`, update `load_global_config()` to parse `max_daily_hours`:

```python
return GlobalConfig(
    db_path=database.get("path"),
    merge_commits=defaults.get("merge_commits", False),
    timezone=defaults.get("timezone", "Europe/Oslo"),
    user_name=user.get("name"),
    user_email=user.get("email"),
    max_daily_hours=defaults.get("max_daily_hours", 12.0),
)
```

In `projects.py`, update `_SELECT_PROJECT` to include new columns:

```python
_SELECT_PROJECT = (
    "SELECT id, name, slug, config_path, weekly_hours, monthly_hours, "
    "allowed_tags, created_at, updated_at FROM projects"
)
```

Update `_row_to_project()` to read the new columns:

```python
def _row_to_project(row: tuple) -> Project:  # type: ignore[type-arg]
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
```

Add `import json` at the top of `projects.py`.

Update `auto_register_project()` to sync budget and tags. In the existing UPDATE branch:

```python
db.execute(
    "UPDATE projects SET name=?, config_path=?, weekly_hours=?, monthly_hours=?, "
    "allowed_tags=?, updated_at=datetime('now') WHERE slug=?",
    (config.name, str(config_path), config.weekly_budget_hours,
     config.monthly_budget_hours,
     json.dumps(config.allowed_tags) if config.allowed_tags else None,
     config.slug),
)
```

In the INSERT branch:

```python
cursor = db.execute(
    "INSERT INTO projects (name, slug, config_path, weekly_hours, monthly_hours, allowed_tags) "
    "VALUES (?, ?, ?, ?, ?, ?)",
    (config.name, config.slug, str(config_path), config.weekly_budget_hours,
     config.monthly_budget_hours,
     json.dumps(config.allowed_tags) if config.allowed_tags else None),
)
```

Return `Project` with the new fields populated in both branches.

**Step 4: Run tests**

Run: `uv run pytest tests/unit/test_config.py tests/unit/test_projects.py -v`
Expected: All pass.

**Step 5: Commit**

```bash
git add src/timereg/core/config.py src/timereg/core/projects.py tests/unit/test_config.py tests/unit/test_projects.py
git commit -m "sync budget and tag constraints from config to projects table"
```

---

### Task 4: Constrained Tag Validation in Entries

**Files:**
- Modify: `src/timereg/core/entries.py`
- Test: `tests/unit/test_entries.py`

**What to build:** Add `allowed_tags` parameter to `create_entry()` and `edit_entry()`. If set and any tag isn't in the list, raise `ValueError`.

**Step 1: Write tests**

Add to `tests/unit/test_entries.py`:

```python
class TestConstrainedTags:
    def test_create_entry_with_valid_tags(self, tmp_db: Database) -> None:
        _create_test_project(tmp_db)
        entry = create_entry(
            db=tmp_db, project_id=1, hours=2.0,
            short_summary="Test", entry_date=date(2026, 2, 25),
            git_user_name="Test", git_user_email="test@test.com",
            entry_type="manual", tags=["dev", "review"],
            allowed_tags=["dev", "review", "meeting"],
        )
        assert not isinstance(entry, list)
        assert entry.tags == ["dev", "review"]

    def test_create_entry_rejects_invalid_tags(self, tmp_db: Database) -> None:
        _create_test_project(tmp_db)
        with pytest.raises(ValueError, match="Invalid tags"):
            create_entry(
                db=tmp_db, project_id=1, hours=2.0,
                short_summary="Test", entry_date=date(2026, 2, 25),
                git_user_name="Test", git_user_email="test@test.com",
                entry_type="manual", tags=["dev", "invalid"],
                allowed_tags=["dev", "review", "meeting"],
            )

    def test_create_entry_no_constraint_allows_any(self, tmp_db: Database) -> None:
        _create_test_project(tmp_db)
        entry = create_entry(
            db=tmp_db, project_id=1, hours=2.0,
            short_summary="Test", entry_date=date(2026, 2, 25),
            git_user_name="Test", git_user_email="test@test.com",
            entry_type="manual", tags=["anything", "goes"],
        )
        assert not isinstance(entry, list)
        assert entry.tags == ["anything", "goes"]

    def test_edit_entry_rejects_invalid_tags(self, tmp_db: Database) -> None:
        _create_test_project(tmp_db)
        entry = create_entry(
            db=tmp_db, project_id=1, hours=2.0,
            short_summary="Test", entry_date=date(2026, 2, 25),
            git_user_name="Test", git_user_email="test@test.com",
            entry_type="manual",
        )
        assert not isinstance(entry, list)
        assert entry.id is not None
        with pytest.raises(ValueError, match="Invalid tags"):
            edit_entry(
                db=tmp_db, entry_id=entry.id,
                tags=["bad-tag"],
                allowed_tags=["dev", "review"],
            )
```

Note: `_create_test_project` is a helper that already exists in `test_entries.py` (or you may need to add one that inserts a project row). Check the existing test file for how projects are set up in tests.

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_entries.py::TestConstrainedTags -v`
Expected: FAIL (parameter doesn't exist yet)

**Step 3: Implement**

Add a private validation helper at the top of `entries.py`:

```python
def _validate_tags(tags: list[str] | None, allowed_tags: list[str] | None) -> None:
    """Validate tags against allowed list. Raises ValueError if invalid."""
    if tags is None or allowed_tags is None:
        return
    invalid = [t for t in tags if t not in allowed_tags]
    if invalid:
        msg = f"Invalid tags: {invalid}. Allowed: {allowed_tags}"
        raise ValueError(msg)
```

Add `allowed_tags: list[str] | None = None` parameter to `create_entry()`. Call `_validate_tags(tags, allowed_tags)` before `_insert_entry()`.

Add `allowed_tags: list[str] | None = None` parameter to `edit_entry()`. Call `_validate_tags(tags, allowed_tags)` before building the update query (only when `tags is not None`).

**Step 4: Run tests**

Run: `uv run pytest tests/unit/test_entries.py -v`
Expected: All pass.

**Step 5: Commit**

```bash
git add src/timereg/core/entries.py tests/unit/test_entries.py
git commit -m "add constrained tag validation to create_entry and edit_entry"
```

---

### Task 5: Multi-Repo Fetch — Refactor CLI to Use FetchResult Model

**Files:**
- Modify: `src/timereg/cli/fetch.py`
- Modify: `src/timereg/core/git.py`
- Test: `tests/unit/test_git.py`
- Test: `tests/integration/test_cli_fetch.py`

**What to build:** Add `fetch_project_commits()` to `core/git.py` that iterates all repos and returns a `FetchResult`. Refactor `cli/fetch.py` to use it. Update text output to show richer per-repo information.

**Step 1: Write tests for `fetch_project_commits`**

Add to `tests/unit/test_git.py`:

```python
from pathlib import Path
from timereg.core.git import fetch_project_commits
from timereg.core.models import FetchResult, GitUser

class TestFetchProjectCommits:
    @patch("timereg.core.git._run_git")
    def test_returns_fetch_result(self, mock_run: MagicMock) -> None:
        mock_run.return_value = SAMPLE_LOG_OUTPUT
        result = fetch_project_commits(
            repo_paths=[Path("/fake/repo")],
            target_date="2026-02-25",
            user_email="bell@jpro.no",
            registered_hashes=set(),
            user=GitUser(name="Mr Bell", email="bell@jpro.no"),
            project_name="Test",
            project_slug="test",
        )
        assert isinstance(result, FetchResult)
        assert result.project_name == "Test"
        assert len(result.repos) == 1
        assert len(result.repos[0].commits) == 2

    @patch("timereg.core.git._run_git")
    def test_skips_nonexistent_repos(self, mock_run: MagicMock) -> None:
        result = fetch_project_commits(
            repo_paths=[Path("/nonexistent/repo")],
            target_date="2026-02-25",
            user_email="bell@jpro.no",
            registered_hashes=set(),
            user=GitUser(name="Mr Bell", email="bell@jpro.no"),
            project_name="Test",
            project_slug="test",
        )
        assert len(result.repos) == 0

    @patch("timereg.core.git._run_git")
    def test_multiple_repos(self, mock_run: MagicMock) -> None:
        mock_run.return_value = SAMPLE_LOG_OUTPUT
        repo1 = Path("/fake/repo1")
        repo2 = Path("/fake/repo2")
        # Mock Path.is_dir to return True
        with patch.object(Path, "is_dir", return_value=True):
            result = fetch_project_commits(
                repo_paths=[repo1, repo2],
                target_date="2026-02-25",
                user_email="bell@jpro.no",
                registered_hashes=set(),
                user=GitUser(name="Mr Bell", email="bell@jpro.no"),
                project_name="Test",
                project_slug="test",
            )
        assert len(result.repos) == 2
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_git.py::TestFetchProjectCommits -v`
Expected: FAIL

**Step 3: Implement `fetch_project_commits` in `core/git.py`**

```python
def fetch_project_commits(
    repo_paths: list[Path],
    target_date: str,
    user_email: str,
    registered_hashes: set[str],
    user: GitUser,
    project_name: str,
    project_slug: str,
    config_dir: Path | None = None,
    timezone: str = "Europe/Oslo",
    merge_commits: bool = False,
) -> FetchResult:
    """Fetch commits across all repos for a project, with branch and tree status."""
    repo_results: list[RepoFetchResult] = []

    for repo_path in repo_paths:
        if not repo_path.is_dir():
            logger.warning("Repo path does not exist, skipping: %s", repo_path)
            continue

        repo_str = str(repo_path)
        try:
            commits = fetch_commits(
                repo_path=repo_str,
                target_date=target_date,
                user_email=user_email,
                timezone=timezone,
                merge_commits=merge_commits,
                registered_hashes=registered_hashes,
            )
        except subprocess.CalledProcessError:
            logger.warning("Failed to fetch commits from %s, skipping", repo_path)
            continue

        branch = get_branch_info(repo_str, target_date)
        wt_status = get_working_tree_status(repo_str)

        relative = str(repo_path.relative_to(config_dir)) if config_dir else str(repo_path)

        repo_results.append(
            RepoFetchResult(
                relative_path=relative,
                absolute_path=repo_str,
                branch=branch.current,
                branch_activity=branch.activity,
                uncommitted=wt_status,
                commits=commits,
            )
        )

    return FetchResult(
        project_name=project_name,
        project_slug=project_slug,
        date=target_date,
        user=user,
        repos=repo_results,
    )
```

Add required imports at the top of `git.py`: `from pathlib import Path` and add `FetchResult`, `RepoFetchResult` to the imports from models.

**Step 4: Refactor `cli/fetch.py`**

Replace the manual repo iteration with a call to `fetch_project_commits()`. For JSON output, use `result.model_dump()`. Update text output to show per-repo details with branch, working tree status, and commit stats:

```
  . (feat/webrtc-signaling) — 1 staged, 3 unstaged
    a1b2c3d  feat: add WebRTC signaling endpoint    (+87 -12, 4 files)
```

**Step 5: Run all tests**

Run: `uv run pytest tests/unit/test_git.py tests/integration/test_cli_fetch.py -v`
Expected: All pass.

**Step 6: Commit**

```bash
git add src/timereg/core/git.py src/timereg/cli/fetch.py tests/unit/test_git.py tests/integration/test_cli_fetch.py
git commit -m "add fetch_project_commits for multi-repo fetch with full context"
```

---

### Task 6: Summary Reports — Core Module

**Files:**
- Create: `src/timereg/core/reports.py`
- Test: `tests/unit/test_reports.py`

**What to build:** `generate_summary()` function that queries entries from the DB, groups by project and day, computes totals, and applies tag filtering and budget comparison.

**Step 1: Write tests**

Create `tests/unit/test_reports.py`:

```python
"""Tests for summary report generation."""

from datetime import date

import pytest

from timereg.core.database import Database
from timereg.core.entries import create_entry
from timereg.core.reports import generate_summary


def _setup_project(db: Database, slug: str = "test", name: str = "Test",
                    weekly_hours: float | None = None) -> int:
    """Insert a project and return its ID."""
    db.execute(
        "INSERT INTO projects (name, slug, weekly_hours) VALUES (?, ?, ?)",
        (name, slug, weekly_hours),
    )
    db.commit()
    row = db.execute("SELECT id FROM projects WHERE slug=?", (slug,)).fetchone()
    assert row is not None
    return row[0]


def _add_entry(db: Database, project_id: int, hours: float, entry_date: date,
               short_summary: str = "work", tags: list[str] | None = None) -> None:
    create_entry(
        db=db, project_id=project_id, hours=hours,
        short_summary=short_summary, entry_date=entry_date,
        git_user_name="Test", git_user_email="test@test.com",
        entry_type="manual", tags=tags,
    )


class TestGenerateSummary:
    def test_weekly_summary_single_project(self, tmp_db: Database) -> None:
        pid = _setup_project(tmp_db, weekly_hours=20.0)
        _add_entry(tmp_db, pid, 4.0, date(2026, 2, 24))
        _add_entry(tmp_db, pid, 3.5, date(2026, 2, 25))

        report = generate_summary(
            tmp_db, period="week",
            reference_date=date(2026, 2, 25),
        )
        assert report.total_hours == 7.5
        assert len(report.projects) == 1
        assert report.projects[0].total_hours == 7.5
        assert report.projects[0].budget_weekly == 20.0

    def test_monthly_summary_multiple_projects(self, tmp_db: Database) -> None:
        pid1 = _setup_project(tmp_db, slug="proj-a", name="Proj A")
        pid2 = _setup_project(tmp_db, slug="proj-b", name="Proj B")
        _add_entry(tmp_db, pid1, 4.0, date(2026, 2, 10))
        _add_entry(tmp_db, pid2, 3.0, date(2026, 2, 15))

        report = generate_summary(
            tmp_db, period="month",
            reference_date=date(2026, 2, 15),
        )
        assert report.total_hours == 7.0
        assert len(report.projects) == 2

    def test_explicit_date_range(self, tmp_db: Database) -> None:
        pid = _setup_project(tmp_db)
        _add_entry(tmp_db, pid, 2.0, date(2026, 2, 20))
        _add_entry(tmp_db, pid, 3.0, date(2026, 2, 25))
        _add_entry(tmp_db, pid, 1.0, date(2026, 3, 1))  # outside range

        report = generate_summary(
            tmp_db, date_from=date(2026, 2, 20), date_to=date(2026, 2, 28),
        )
        assert report.total_hours == 5.0

    def test_filter_by_project(self, tmp_db: Database) -> None:
        pid1 = _setup_project(tmp_db, slug="proj-a", name="Proj A")
        pid2 = _setup_project(tmp_db, slug="proj-b", name="Proj B")
        _add_entry(tmp_db, pid1, 4.0, date(2026, 2, 25))
        _add_entry(tmp_db, pid2, 3.0, date(2026, 2, 25))

        report = generate_summary(
            tmp_db, period="day", reference_date=date(2026, 2, 25),
            project_id=pid1,
        )
        assert report.total_hours == 4.0
        assert len(report.projects) == 1

    def test_filter_by_tags(self, tmp_db: Database) -> None:
        pid = _setup_project(tmp_db)
        _add_entry(tmp_db, pid, 4.0, date(2026, 2, 25), tags=["dev"])
        _add_entry(tmp_db, pid, 2.0, date(2026, 2, 25), tags=["meeting"])
        _add_entry(tmp_db, pid, 1.0, date(2026, 2, 25), tags=["dev", "meeting"])

        report = generate_summary(
            tmp_db, period="day", reference_date=date(2026, 2, 25),
            tag_filter=["meeting"],
        )
        # Should include entries that have "meeting" tag: 2.0 + 1.0
        assert report.total_hours == 3.0

    def test_daily_breakdown(self, tmp_db: Database) -> None:
        pid = _setup_project(tmp_db)
        _add_entry(tmp_db, pid, 4.0, date(2026, 2, 24))
        _add_entry(tmp_db, pid, 3.0, date(2026, 2, 24))
        _add_entry(tmp_db, pid, 5.0, date(2026, 2, 25))

        report = generate_summary(
            tmp_db, period="week", reference_date=date(2026, 2, 25),
        )
        proj = report.projects[0]
        # Only days with entries should appear
        days_with_entries = [d for d in proj.days if d.total_hours > 0]
        assert len(days_with_entries) == 2
        assert days_with_entries[0].total_hours == 7.0  # Feb 24
        assert days_with_entries[1].total_hours == 5.0  # Feb 25

    def test_period_label_week(self, tmp_db: Database) -> None:
        _setup_project(tmp_db)
        report = generate_summary(
            tmp_db, period="week", reference_date=date(2026, 2, 25),
        )
        assert "Week 9" in report.period_label
        assert "2026" in report.period_label

    def test_budget_percent_computed(self, tmp_db: Database) -> None:
        pid = _setup_project(tmp_db, weekly_hours=20.0)
        _add_entry(tmp_db, pid, 22.5, date(2026, 2, 25))

        report = generate_summary(
            tmp_db, period="week", reference_date=date(2026, 2, 25),
        )
        proj = report.projects[0]
        assert proj.budget_percent is not None
        assert proj.budget_percent == pytest.approx(112.5)

    def test_empty_period(self, tmp_db: Database) -> None:
        _setup_project(tmp_db)
        report = generate_summary(
            tmp_db, period="day", reference_date=date(2026, 2, 25),
        )
        assert report.total_hours == 0.0
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_reports.py -v`
Expected: FAIL (module doesn't exist)

**Step 3: Implement `core/reports.py`**

The function should:
1. Resolve the date range from `period` + `reference_date` (or `date_from`/`date_to`)
2. Query all entries in the range (optionally filtered by project_id)
3. If `tag_filter` is set, filter entries to those with at least one matching tag
4. Group entries by project, then by day
5. For each project, compute total hours and budget percentage
6. Generate `period_label` (e.g. "Week 9, 2026 — Feb 24 – Feb 28")
7. Return `SummaryReport`

Use `list_entries()` from `entries.py` to query, then filter and group in Python. Use `list_projects()` to get project metadata including budget. Use `datetime.date.isocalendar()` for week number. Use `calendar.monthrange()` for month boundaries.

Key: the function takes `reference_date: date | None = None` which defaults to `date.today()` and is used with `period` to compute the date range. If `date_from`/`date_to` are provided, they override the period.

**Step 4: Run tests**

Run: `uv run pytest tests/unit/test_reports.py -v`
Expected: All pass.

**Step 5: Commit**

```bash
git add src/timereg/core/reports.py tests/unit/test_reports.py
git commit -m "add report generation with budget comparison and tag filtering"
```

---

### Task 7: Summary CLI Command

**Files:**
- Create: `src/timereg/cli/summary.py`
- Modify: `src/timereg/cli/app.py` (add import)
- Test: `tests/integration/test_cli_summary.py`

**What to build:** `timereg summary` command with `--week`, `--month`, `--day`, `--from`, `--to`, `--project`, `--tags`, `--detail`, `--format` options. Text output uses Rich tables for full detail and simple text for brief. JSON output serializes the `SummaryReport`.

**Step 1: Write integration tests**

Create `tests/integration/test_cli_summary.py`:

```python
"""Integration tests for the summary CLI command."""

from datetime import date
from pathlib import Path

from typer.testing import CliRunner

from timereg.cli.app import app, state
from timereg.core.database import Database
from timereg.core.entries import create_entry

runner = CliRunner()


def _setup(tmp_path: Path) -> Database:
    db = Database(tmp_path / "test.db")
    db.migrate()
    state.db = db
    state.output_format = "text"
    state.db_path = tmp_path / "test.db"
    db.execute(
        "INSERT INTO projects (name, slug, weekly_hours) VALUES (?, ?, ?)",
        ("Test Project", "test", 20.0),
    )
    db.commit()
    return db


class TestSummaryCLI:
    def test_weekly_summary_text(self, tmp_path: Path) -> None:
        db = _setup(tmp_path)
        create_entry(
            db=db, project_id=1, hours=4.0, short_summary="Work",
            entry_date=date(2026, 2, 25), git_user_name="Test",
            git_user_email="test@test.com", entry_type="manual",
        )
        result = runner.invoke(
            app, ["summary", "--week", "--date", "2026-02-25",
                  "--db-path", str(tmp_path / "test.db")],
        )
        assert result.exit_code == 0
        assert "Test Project" in result.output
        assert "4.0" in result.output or "4.00" in result.output

    def test_weekly_summary_json(self, tmp_path: Path) -> None:
        db = _setup(tmp_path)
        create_entry(
            db=db, project_id=1, hours=4.0, short_summary="Work",
            entry_date=date(2026, 2, 25), git_user_name="Test",
            git_user_email="test@test.com", entry_type="manual",
        )
        result = runner.invoke(
            app, ["summary", "--week", "--date", "2026-02-25",
                  "--format", "json", "--db-path", str(tmp_path / "test.db")],
        )
        assert result.exit_code == 0
        import json
        data = json.loads(result.output)
        assert data["total_hours"] == 4.0

    def test_summary_no_entries(self, tmp_path: Path) -> None:
        _setup(tmp_path)
        result = runner.invoke(
            app, ["summary", "--week", "--date", "2026-02-25",
                  "--db-path", str(tmp_path / "test.db")],
        )
        assert result.exit_code == 0
```

**Step 2: Implement `cli/summary.py`**

Create the command with all options. The `--date` flag provides the reference date for period computation. Use Rich `Table` for full detail and simple `typer.echo` for brief. Include budget bars using Rich's `Progress` or simple text percentage. Register the import in `app.py`.

**Step 3: Run tests**

Run: `uv run pytest tests/integration/test_cli_summary.py -v`
Expected: All pass.

**Step 4: Commit**

```bash
git add src/timereg/cli/summary.py src/timereg/cli/app.py tests/integration/test_cli_summary.py
git commit -m "add summary CLI command with budget bars and tag filtering"
```

---

### Task 8: Status & Check — Core Module

**Files:**
- Create: `src/timereg/core/checks.py`
- Test: `tests/unit/test_checks.py`

**What to build:** `get_status()` for the status dashboard and `run_checks()` for gap/conflict detection. Both functions live in the same module since they share logic (querying entries, counting unregistered commits).

**Step 1: Write tests**

Create `tests/unit/test_checks.py`:

```python
"""Tests for status and check functionality."""

from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

from timereg.core.checks import get_status, run_checks
from timereg.core.database import Database
from timereg.core.entries import create_entry
from timereg.core.models import Project


def _setup_project(db: Database, slug: str = "test", name: str = "Test",
                    weekly_hours: float | None = None) -> tuple[int, Project]:
    db.execute(
        "INSERT INTO projects (name, slug, weekly_hours) VALUES (?, ?, ?)",
        (name, slug, weekly_hours),
    )
    db.commit()
    row = db.execute("SELECT id FROM projects WHERE slug=?", (slug,)).fetchone()
    assert row is not None
    pid = row[0]
    return pid, Project(id=pid, name=name, slug=slug, weekly_hours=weekly_hours)


def _add_entry(db: Database, project_id: int, hours: float, entry_date: date) -> None:
    create_entry(
        db=db, project_id=project_id, hours=hours,
        short_summary="work", entry_date=entry_date,
        git_user_name="Test", git_user_email="test@test.com",
        entry_type="manual",
    )


class TestGetStatus:
    def test_status_with_entries(self, tmp_db: Database) -> None:
        pid, project = _setup_project(tmp_db, weekly_hours=20.0)
        _add_entry(tmp_db, pid, 4.0, date(2026, 2, 25))
        _add_entry(tmp_db, pid, 2.5, date(2026, 2, 25))

        status = get_status(
            db=tmp_db, projects=[project],
            repo_paths_by_project={},
            user_email="test@test.com",
            target_date=date(2026, 2, 25),
        )
        assert len(status.projects) == 1
        assert status.projects[0].today_hours == 6.5
        assert status.projects[0].today_entry_count == 2

    def test_status_no_entries_generates_warning(self, tmp_db: Database) -> None:
        pid, project = _setup_project(tmp_db)
        status = get_status(
            db=tmp_db, projects=[project],
            repo_paths_by_project={},
            user_email="test@test.com",
            target_date=date(2026, 2, 25),
        )
        assert any("no hours" in w.lower() for w in status.warnings)

    def test_status_weekly_total(self, tmp_db: Database) -> None:
        pid, project = _setup_project(tmp_db, weekly_hours=20.0)
        _add_entry(tmp_db, pid, 4.0, date(2026, 2, 24))  # Mon
        _add_entry(tmp_db, pid, 3.0, date(2026, 2, 25))  # Tue

        status = get_status(
            db=tmp_db, projects=[project],
            repo_paths_by_project={},
            user_email="test@test.com",
            target_date=date(2026, 2, 25),
        )
        assert status.projects[0].week_hours == 7.0
        assert status.projects[0].budget_weekly == 20.0


class TestRunChecks:
    def test_check_detects_missing_day(self, tmp_db: Database) -> None:
        pid, project = _setup_project(tmp_db)
        # Register hours on Mon and Wed but not Tue
        _add_entry(tmp_db, pid, 4.0, date(2026, 2, 24))  # Mon
        _add_entry(tmp_db, pid, 5.0, date(2026, 2, 26))  # Wed

        report = run_checks(
            db=tmp_db, projects=[project],
            repo_paths_by_project={},
            user_email="test@test.com",
            date_from=date(2026, 2, 24),
            date_to=date(2026, 2, 26),
        )
        tue_check = [d for d in report.days if d.date == date(2026, 2, 25)]
        assert len(tue_check) == 1
        assert not tue_check[0].ok
        assert any("no hours" in w.lower() for w in tue_check[0].warnings)

    def test_check_detects_high_hours(self, tmp_db: Database) -> None:
        pid, project = _setup_project(tmp_db)
        _add_entry(tmp_db, pid, 14.0, date(2026, 2, 25))

        report = run_checks(
            db=tmp_db, projects=[project],
            repo_paths_by_project={},
            user_email="test@test.com",
            date_from=date(2026, 2, 25),
            date_to=date(2026, 2, 25),
            max_daily_hours=12.0,
        )
        assert len(report.days) == 1
        assert not report.days[0].ok
        assert any("high" in w.lower() or "seems" in w.lower() for w in report.days[0].warnings)

    def test_check_skips_weekends(self, tmp_db: Database) -> None:
        pid, project = _setup_project(tmp_db)
        # Feb 28 is Saturday, Mar 1 is Sunday
        report = run_checks(
            db=tmp_db, projects=[project],
            repo_paths_by_project={},
            user_email="test@test.com",
            date_from=date(2026, 2, 28),
            date_to=date(2026, 3, 1),
        )
        assert len(report.days) == 0  # weekend days excluded

    def test_check_normal_day_is_ok(self, tmp_db: Database) -> None:
        pid, project = _setup_project(tmp_db)
        _add_entry(tmp_db, pid, 7.5, date(2026, 2, 25))

        report = run_checks(
            db=tmp_db, projects=[project],
            repo_paths_by_project={},
            user_email="test@test.com",
            date_from=date(2026, 2, 25),
            date_to=date(2026, 2, 25),
        )
        assert len(report.days) == 1
        assert report.days[0].ok

    def test_check_budget_warning(self, tmp_db: Database) -> None:
        pid, project = _setup_project(tmp_db, weekly_hours=20.0)
        _add_entry(tmp_db, pid, 12.0, date(2026, 2, 25))

        report = run_checks(
            db=tmp_db, projects=[project],
            repo_paths_by_project={},
            user_email="test@test.com",
            date_from=date(2026, 2, 24),
            date_to=date(2026, 2, 28),
        )
        assert report.summary_total == 12.0
        # Budget warning about being under budget
        assert any("test" in w.lower() or "60" in w for w in report.budget_warnings)
```

**Step 2: Implement `core/checks.py`**

`get_status()`:
1. For each project, query today's entries and compute totals
2. Compute week hours (Monday to target_date)
3. If `repo_paths_by_project` has paths for the project, count unregistered commits via `fetch_commits()` + `get_registered_commit_hashes()`
4. Generate warnings for projects with no hours today
5. Return `StatusReport`

`run_checks()`:
1. Iterate each weekday in the date range
2. For each day, sum hours across all projects
3. Count unregistered commits if repo paths available
4. Flag: no hours, high hours (> max_daily_hours), unregistered commits
5. Compute budget warnings at the end
6. Return `CheckReport`

**Step 3: Run tests**

Run: `uv run pytest tests/unit/test_checks.py -v`
Expected: All pass.

**Step 4: Commit**

```bash
git add src/timereg/core/checks.py tests/unit/test_checks.py
git commit -m "add status and check core logic with gap and budget detection"
```

---

### Task 9: Status CLI Command

**Files:**
- Create: `src/timereg/cli/status.py`
- Modify: `src/timereg/cli/app.py` (add import)
- Test: `tests/integration/test_cli_status.py`

**What to build:** `timereg status` command that shows a Rich panel with per-project stats. Queries all registered projects, resolves their repo paths from `project_repos` table, and calls `get_status()`.

**Step 1: Write integration tests**

Test text output contains project name, hours, and entry count. Test JSON output is valid JSON with expected structure. Test with no entries shows warning.

**Step 2: Implement `cli/status.py`**

The command needs to:
1. Query all projects from DB using `list_projects()`
2. Query repo paths per project from `project_repos` table
3. Resolve git user (from first available repo, or fall back to global config)
4. Call `get_status()`
5. Render with Rich panel (text) or JSON dump

Add import to `app.py`.

**Step 3: Run tests**

Run: `uv run pytest tests/integration/test_cli_status.py -v`
Expected: All pass.

**Step 4: Commit**

```bash
git add src/timereg/cli/status.py src/timereg/cli/app.py tests/integration/test_cli_status.py
git commit -m "add status CLI command with live dashboard"
```

---

### Task 10: Check CLI Command

**Files:**
- Create: `src/timereg/cli/check.py`
- Modify: `src/timereg/cli/app.py` (add import)
- Test: `tests/integration/test_cli_check.py`

**What to build:** `timereg check` command with `--week` (default), `--month`, `--day`, `--from`, `--to`, `--date` flags. Text output shows checkmarks/warnings per day. JSON output serializes `CheckReport`.

The command reads `max_daily_hours` from global config (via `load_global_config()`).

**Step 1: Write integration tests**

Test that check output shows warnings for missing days and normal days show ok. Test JSON output.

**Step 2: Implement `cli/check.py`**

Similar pattern to status — query all projects and their repos, resolve user, call `run_checks()`, render output. Add import to `app.py`.

**Step 3: Run tests**

Run: `uv run pytest tests/integration/test_cli_check.py -v`
Expected: All pass.

**Step 4: Commit**

```bash
git add src/timereg/cli/check.py src/timereg/cli/app.py tests/integration/test_cli_check.py
git commit -m "add check CLI command with gap and budget detection"
```

---

### Task 11: CSV/JSON Export — Core Module

**Files:**
- Create: `src/timereg/core/export.py`
- Test: `tests/unit/test_export.py`

**What to build:** `export_entries()` function that returns a formatted string in CSV or JSON format.

**Step 1: Write tests**

Create `tests/unit/test_export.py`:

```python
"""Tests for export functionality."""

import csv
import io
import json
from datetime import date

from timereg.core.database import Database
from timereg.core.entries import create_entry
from timereg.core.export import export_entries


def _setup_project(db: Database) -> int:
    db.execute("INSERT INTO projects (name, slug) VALUES (?, ?)", ("Test", "test"))
    db.commit()
    row = db.execute("SELECT id FROM projects WHERE slug='test'").fetchone()
    assert row is not None
    return row[0]


class TestExportCSV:
    def test_csv_header(self, tmp_db: Database) -> None:
        _setup_project(tmp_db)
        output = export_entries(tmp_db, format="csv")
        reader = csv.reader(io.StringIO(output))
        header = next(reader)
        assert "date" in header
        assert "project" in header
        assert "hours" in header
        assert "tags" in header
        assert "commits" in header

    def test_csv_with_entries(self, tmp_db: Database) -> None:
        pid = _setup_project(tmp_db)
        create_entry(
            db=tmp_db, project_id=pid, hours=4.5,
            short_summary="Test work", entry_date=date(2026, 2, 25),
            git_user_name="Test", git_user_email="test@test.com",
            entry_type="git", tags=["dev", "testing"],
        )
        output = export_entries(tmp_db, format="csv")
        reader = csv.reader(io.StringIO(output))
        header = next(reader)
        rows = list(reader)
        assert len(rows) == 1
        # Tags should be semicolon-separated
        tags_col = header.index("tags")
        assert rows[0][tags_col] == "dev;testing"

    def test_csv_filters_by_project(self, tmp_db: Database) -> None:
        pid = _setup_project(tmp_db)
        tmp_db.execute("INSERT INTO projects (name, slug) VALUES (?, ?)", ("Other", "other"))
        tmp_db.commit()
        create_entry(
            db=tmp_db, project_id=pid, hours=4.0,
            short_summary="Test", entry_date=date(2026, 2, 25),
            git_user_name="Test", git_user_email="test@test.com",
            entry_type="manual",
        )
        create_entry(
            db=tmp_db, project_id=2, hours=3.0,
            short_summary="Other", entry_date=date(2026, 2, 25),
            git_user_name="Test", git_user_email="test@test.com",
            entry_type="manual",
        )
        output = export_entries(tmp_db, format="csv", project_id=pid)
        reader = csv.reader(io.StringIO(output))
        next(reader)  # skip header
        rows = list(reader)
        assert len(rows) == 1

    def test_csv_filters_by_date_range(self, tmp_db: Database) -> None:
        pid = _setup_project(tmp_db)
        create_entry(
            db=tmp_db, project_id=pid, hours=2.0,
            short_summary="In range", entry_date=date(2026, 2, 25),
            git_user_name="Test", git_user_email="test@test.com",
            entry_type="manual",
        )
        create_entry(
            db=tmp_db, project_id=pid, hours=3.0,
            short_summary="Out of range", entry_date=date(2026, 3, 5),
            git_user_name="Test", git_user_email="test@test.com",
            entry_type="manual",
        )
        output = export_entries(
            tmp_db, format="csv",
            date_from=date(2026, 2, 1), date_to=date(2026, 2, 28),
        )
        reader = csv.reader(io.StringIO(output))
        next(reader)
        rows = list(reader)
        assert len(rows) == 1


class TestExportJSON:
    def test_json_output(self, tmp_db: Database) -> None:
        pid = _setup_project(tmp_db)
        create_entry(
            db=tmp_db, project_id=pid, hours=4.5,
            short_summary="Test", entry_date=date(2026, 2, 25),
            git_user_name="Test", git_user_email="test@test.com",
            entry_type="manual", tags=["dev"],
        )
        output = export_entries(tmp_db, format="json")
        data = json.loads(output)
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["hours"] == 4.5
        assert data[0]["project"] == "Test"

    def test_empty_export(self, tmp_db: Database) -> None:
        _setup_project(tmp_db)
        output = export_entries(tmp_db, format="csv")
        reader = csv.reader(io.StringIO(output))
        header = next(reader)
        rows = list(reader)
        assert len(rows) == 0
        assert len(header) > 0  # header still present
```

**Step 2: Implement `core/export.py`**

Use `list_entries()` to query, join with project names. For CSV, use `csv.writer` with `io.StringIO`. For JSON, build dicts and `json.dumps()`. Include commit hashes from `entry_commits` table (semicolon-separated in CSV, array in JSON).

**Step 3: Run tests**

Run: `uv run pytest tests/unit/test_export.py -v`
Expected: All pass.

**Step 4: Commit**

```bash
git add src/timereg/core/export.py tests/unit/test_export.py
git commit -m "add CSV and JSON export with project and date filtering"
```

---

### Task 12: Export CLI Command

**Files:**
- Create: `src/timereg/cli/export.py`
- Modify: `src/timereg/cli/app.py` (add import)
- Test: `tests/integration/test_cli_export.py`

**What to build:** `timereg export` command with `--project`, `--from`, `--to`, `--format csv|json` flags. Default format is `csv`. Output goes to stdout.

**Step 1: Write integration tests**

Test CSV and JSON output via CLI runner. Test project and date filtering.

**Step 2: Implement `cli/export.py`**

Simple command that resolves project (optional), parses date flags, calls `export_entries()`, and prints the result. Add import to `app.py`.

**Step 3: Run tests**

Run: `uv run pytest tests/integration/test_cli_export.py -v`
Expected: All pass.

**Step 4: Commit**

```bash
git add src/timereg/cli/export.py src/timereg/cli/app.py tests/integration/test_cli_export.py
git commit -m "add export CLI command for CSV and JSON output"
```

---

### Task 13: Wire Tag Validation into CLI

**Files:**
- Modify: `src/timereg/cli/register.py`
- Modify: `src/timereg/cli/edit.py`
- Test: `tests/integration/test_cli_register.py`

**What to build:** Pass `allowed_tags` from the resolved project through to `create_entry()` and `edit_entry()` in the CLI commands. This ensures tag constraints are enforced when registering or editing via CLI.

**Step 1: Write tests**

Add to `tests/integration/test_cli_register.py`:

```python
class TestConstrainedTagsCLI:
    def test_register_rejects_invalid_tag(self, tmp_path: Path) -> None:
        # Set up project with allowed_tags in DB
        db = _setup(tmp_path)  # use existing setup helper
        db.execute(
            "UPDATE projects SET allowed_tags=? WHERE slug='test'",
            ('["dev", "review"]',),
        )
        db.commit()
        result = runner.invoke(
            app, ["register", "--hours", "2h", "--short-summary", "Test",
                  "--project", "test", "--tags", "dev,invalid",
                  "--db-path", str(tmp_path / "test.db")],
        )
        assert result.exit_code != 0
        assert "invalid" in result.output.lower() or "Invalid" in result.output
```

**Step 2: Implement**

In `register.py`: after resolving the project, read `project.allowed_tags` (may need to fetch via `get_project()` which now returns tags). Pass it to `create_entry()`.

In `edit.py`: look up the entry's project to get `allowed_tags`, pass to `edit_entry()`.

**Step 3: Run tests**

Run: `uv run pytest tests/integration/test_cli_register.py tests/integration/test_cli_edit_delete.py -v`
Expected: All pass.

**Step 4: Commit**

```bash
git add src/timereg/cli/register.py src/timereg/cli/edit.py tests/integration/test_cli_register.py
git commit -m "wire tag constraint validation into register and edit CLI commands"
```

---

### Task 14: Update TIMEREG_SKILL.md for New Commands

**Files:**
- Modify: `TIMEREG_SKILL.md`

**What to build:** Add documentation for the new `summary`, `status`, `check`, and `export` commands to the agent skill file.

Add sections:
- **Checking status:** `timereg status --format json`
- **Weekly/monthly summaries:** `timereg summary --week --format json`
- **Checking for gaps:** `timereg check --week --format json`
- **Exporting data:** `timereg export --project <slug> --from <date> --to <date> --format csv`

**Commit:**

```bash
git add TIMEREG_SKILL.md
git commit -m "update agent skill file with summary, status, check, and export commands"
```

---

### Task 15: End-to-End Test — Full Phase 2 Workflow

**Files:**
- Modify: `tests/e2e/test_full_workflow.py`

**What to build:** An E2E test that exercises the Phase 2 features: multi-repo fetch, summary, status, check, export, and tag constraints.

**Test scenario:**
1. Create a git repo with commits
2. Set up `.timetracker.toml` with budget and allowed tags
3. Fetch → verify multi-repo output with branch info
4. Register entry with valid tags
5. Try to register with invalid tag → error
6. Summary → verify budget percentage
7. Status → verify hours and commit counts
8. Check → verify no warnings for covered day
9. Export CSV → verify format
10. Export JSON → verify structure

**Commit:**

```bash
git add tests/e2e/test_full_workflow.py
git commit -m "add end-to-end test for Phase 2 reporting and budget workflow"
```

---

### Task 16: Final Verification

**What to do:**
1. Run full test suite: `uv run pytest -v`
2. Run ruff: `uv run ruff check src/ tests/`
3. Run mypy: `uv run mypy src/`
4. Verify all new CLI commands appear in `timereg --help`
5. Run `uv run pytest --cov=timereg --cov-report=term-missing` and review coverage

**Fix any issues found.**

**Commit:**

```bash
git add -A
git commit -m "Phase 2 complete: multi-repo, reporting, budget, tags, export"
```

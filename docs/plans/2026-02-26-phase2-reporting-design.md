# Phase 2: Multi-Repo, Reporting & Advanced Features — Design Document

**Date:** 2026-02-26
**Status:** Approved

## Overview

Phase 2 builds on the Phase 1 foundation to add multi-repo fetch, summary reports, status dashboard, gap/conflict detection, budget tracking, constrained tags, and CSV/JSON export.

## Scope

1. **Multi-repo fetch** — iterate all repos in `project_repos`, include branch info and working tree status per repo
2. **Summary reports** — `timereg summary` with `--week`, `--month`, `--from/--to`, `--tags`, `--detail brief|full`, budget bars, JSON output
3. **Status command** — `timereg status` with live git queries across all projects
4. **Check command** — `timereg check` detecting missing days, unregistered commits, and high hours (configurable threshold)
5. **Budget tracking** — `[budget]` section in `.timetracker.toml`, comparison in reports/status/check
6. **Constrained tags** — `[tags] allowed = [...]` in project config, validated in core create/edit
7. **CSV/JSON export** — `timereg export` with date/project filtering

### Already Done in Phase 1

- Peer registration (complete)
- Freeform tags (complete)
- `get_branch_info()` and `get_working_tree_status()` (exist but unwired)
- `project_repos` table and multi-repo config parsing (exist but only first repo used)
- `RepoFetchResult`, `FetchResult` models (exist)

## Migration

`002_add_budget_and_tags.sql`:

```sql
ALTER TABLE projects ADD COLUMN weekly_hours REAL;
ALTER TABLE projects ADD COLUMN monthly_hours REAL;
ALTER TABLE projects ADD COLUMN allowed_tags TEXT;  -- JSON array or NULL
```

Budget and allowed_tags are synced from `.timetracker.toml` by `auto_register_project()` on every upsert. Manual-only projects have NULL values.

## Config Changes

### Project Config (`.timetracker.toml`)

New sections:

```toml
[tags]
allowed = ["development", "review", "meeting", "planning", "documentation", "bugfix", "devops", "testing", "support"]

[budget]
weekly_hours = 20.0
monthly_hours = 80.0
```

Both are optional. When `[tags] allowed` is unset, freeform tags are allowed.

### Global Config

New field in `[defaults]`:

```toml
[defaults]
max_daily_hours = 12.0
```

Default is `12.0`. Used by the `check` command to flag unusually high daily hours.

## Multi-Repo Fetch

New function in `core/git.py`:

```python
def fetch_project_commits(
    repo_paths: list[Path],
    target_date: str,
    user_email: str,
    registered_hashes: set[str],
    timezone: str = "Europe/Oslo",
    merge_commits: bool = False,
) -> FetchResult
```

Iterates all repo paths. Per repo: calls `fetch_commits()`, `get_branch_info()`, `get_working_tree_status()`. Skips non-existent repos with a warning. Assembles a `FetchResult` containing `RepoFetchResult` objects.

`cli/fetch.py` is updated to use this function and display results grouped by repo with branch and working tree status.

Text output:

```
Unregistered commits for Ekvarda Codex (2026-02-25):

  . (feat/webrtc-signaling) — 1 staged, 3 unstaged
    a1b2c3d  feat: add WebRTC signaling endpoint    (+87 -12, 4 files)
    b2c3d4e  test: integration tests for handshake   (+134, 2 files)

  ./ekvarda-client (main) — clean
    (no commits)
```

JSON output uses existing `FetchResult` / `RepoFetchResult` Pydantic models.

## Summary Reports

### New Module: `core/reports.py`

```python
def generate_summary(
    db: Database,
    period: str | None = None,       # "day", "week", "month"
    date_from: date | None = None,
    date_to: date | None = None,
    project_id: int | None = None,
    tag_filter: list[str] | None = None,
    detail: str = "brief",
) -> SummaryReport
```

Period resolves to a date range:
- `day` — today (or `--date`)
- `week` — Monday through Sunday of current week
- `month` — first to last day of current month
- `--from/--to` — explicit range (overrides period)

### New Models

```python
class DayDetail:
    date: date
    entries: list[Entry]
    total_hours: float

class ProjectSummary:
    project: Project
    days: list[DayDetail]
    total_hours: float
    budget_weekly: float | None
    budget_monthly: float | None
    budget_percent: float | None

class SummaryReport:
    period_start: date
    period_end: date
    period_label: str          # "Week 9, 2026 — Feb 24 – Feb 28"
    projects: list[ProjectSummary]
    total_hours: float
```

Tag filtering: when set, only entries with at least one matching tag are included.

Budget comparison: if the project has `weekly_hours` or `monthly_hours`, `ProjectSummary` includes the percentage.

### CLI: `timereg summary`

```
timereg summary [--week|--month|--day] [--from DATE] [--to DATE]
                [--project SLUG] [--tags TAGS] [--detail brief|full]
                [--format json|text]
```

Brief text output shows per-project totals with budget percentages. Full text output shows daily breakdown with entries, tags, long summaries, and Rich budget bars.

## Status Command

### `core/checks.py` — Status Function

```python
def get_status(
    db: Database,
    projects: list[Project],
    repo_paths_by_project: dict[int, list[Path]],
    user_email: str,
    target_date: date,
) -> StatusReport
```

Performs live git queries per project to count unregistered commits. Combines with DB data for registered hours and weekly totals.

### New Models

```python
class ProjectStatus:
    project: Project
    today_hours: float
    today_entry_count: int
    unregistered_commits: int
    week_hours: float
    budget_weekly: float | None
    budget_percent: float | None

class StatusReport:
    date: date
    projects: list[ProjectStatus]
    warnings: list[str]
```

### CLI: `timereg status`

```
timereg status [--date DATE] [--format json|text]
```

Always shows all registered projects (no `--project` flag). Uses Rich panel for text output.

## Check Command

### `core/checks.py` — Check Function

```python
def run_checks(
    db: Database,
    projects: list[Project],
    repo_paths_by_project: dict[int, list[Path]],
    user_email: str,
    date_from: date,
    date_to: date,
    max_daily_hours: float = 12.0,
) -> CheckReport
```

### New Models

```python
class DayCheck:
    date: date
    total_hours: float
    unregistered_commits: int
    warnings: list[str]
    ok: bool

class CheckReport:
    date_from: date
    date_to: date
    days: list[DayCheck]
    budget_warnings: list[str]
    summary_total: float
    summary_potential_missing: str
```

### Check Logic (weekdays only, skips weekends)

- No hours at all → "No hours registered"
- Has unregistered commits → "N unregistered commits on Project"
- Hours exceed `max_daily_hours` → "Nh registered (seems high)"
- Otherwise → ok

Budget warnings at the end compare each project's total against weekly/monthly targets.

### CLI: `timereg check`

```
timereg check [--week|--month|--day] [--from DATE] [--to DATE]
              [--format json|text]
```

Default is `--week`.

## Constrained Tags

`ProjectConfig` gains `allowed_tags: list[str] | None`. Stored in `projects.allowed_tags` (JSON) via `auto_register_project()`.

`create_entry()` and `edit_entry()` gain `allowed_tags: list[str] | None` parameter. If set and any provided tag is not in the list, raises `ValueError` listing invalid tags and the allowed set.

CLI passes `allowed_tags` from the project record through to core.

## CSV/JSON Export

### New Module: `core/export.py`

```python
def export_entries(
    db: Database,
    format: str,                    # "csv" or "json"
    project_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> str
```

CSV format:
```
date,project,hours,short_summary,long_summary,tags,entry_type,git_user_email,commits
```

Multi-value fields (tags, commits) use semicolons. Uses Python stdlib `csv` module.

JSON format: array of entry objects with project name included. Pydantic serialization.

### CLI: `timereg export`

```
timereg export [--project SLUG] [--from DATE] [--to DATE]
               [--format csv|json]
```

Default format is `csv`. Output to stdout for piping.

## New Dependencies

None. CSV uses stdlib. Rich formatting uses existing dependency.

## Out of Scope

- MCP server (Phase 3)
- Google Sheets / Tripletex sync (Phase 4)
- `export_targets` table (Phase 4)

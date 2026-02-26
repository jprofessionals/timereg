# Phase 1: Core MVP — Design Document

**Date:** 2026-02-26
**Status:** Approved

## Overview

Implement the core MVP of TimeReg: a Git-aware CLI time-tracking tool for consulting teams. Phase 1 delivers the foundation layer (database, models, config, git, entries, projects) and CLI commands, with agent integration via a skill file and subprocess calls.

## Tooling & Development Setup

- **Python 3.12+** with **uv** for project/package management
- **Ruff** for linting and formatting
- **mypy** in strict mode with targeted exceptions for third-party libs (Typer, Rich)
- **pre-commit** hooks: trailing-whitespace, end-of-file-fixer, check-toml, Ruff (lint + format), mypy, pytest (unit tests only)
- **pytest** with `pytest-cov` for coverage reporting (no threshold enforcement)
- No `pytest-tmp-files` — use pytest's built-in `tmp_path`

### Dependencies

**Runtime:** typer, rich, platformdirs, pydantic

**Dev:** pytest, pytest-cov, mypy, ruff, pre-commit

All pinned to recent versions at time of scaffolding.

## Architecture

Three layers, all in `src/timereg/`:

```
core/    — Business logic (no CLI or protocol concerns)
cli/     — Typer CLI commands (thin layer over core)
mcp/     — Deferred to Phase 3
```

## Foundation Layer

### Database (`core/database.py`)

- `Database` class taking `db_path: str | Path`
- Creates parent directories if needed
- Enables WAL mode on connection
- `migrate()` reads SQL files from `src/timereg/migrations/`, checks `schema_version` table, applies pending migrations in order
- Connection exposed via context manager for transaction safety

### Migrations

`001_initial.sql` creates all Phase 1 tables:

- `schema_version` — migration tracking
- `projects` — project registry (name, slug, config_path)
- `project_repos` — repo paths per project
- `entries` — time entries (hours, summaries, dates, tags, peer_group_id, split_group_id)
- `entry_commits` — commit associations per entry
- `claimed_commits` — commit hashes retained when deleting entries with release_commits=False

No `002_add_export_targets.sql` — that's Phase 2 scope.

### Models (`core/models.py`)

Pydantic models with strict validation:

- `Project`, `ProjectRepo` — DB entities
- `Entry`, `EntryCommit` — DB entities with JSON tag serialization
- `CommitInfo` — structured commit data from git (pre-persistence)
- `RepoFetchResult` — per-repo fetch results (commits, branch, uncommitted status)
- `FetchResult` — top-level fetch response wrapping multiple repos
- `AllProjectsFetchResult` — cross-project fetch with suggested split
- `GitUser`, `BranchInfo`, `WorkingTreeStatus` — git data types
- `GlobalConfig`, `ProjectConfig`, `ResolvedConfig` — configuration models

### Time Parser (`core/time_parser.py`)

`parse_time(input: str) -> float` — pure function.

Supports: `2h30m`, `2h`, `30m`, `90m`, `1.5`, `4.25`. Rejects empty, non-positive, non-numeric. Warns but allows values > 24h.

### Config Resolution (`core/config.py`)

**Global config:**
- Located via `platformdirs.user_config_dir("timereg")`
- Created with defaults on first run if absent
- `GlobalConfig` model: database path, merge_commits, timezone, user name/email

**Project config:**
- Walks up from CWD looking for `.timetracker.toml`
- **Stops at `Path.home()`** — will not traverse beyond the user's home directory
- **If not found: emits warning and exits**
- Resolves repo paths relative to config file location

**Precedence:** CLI flags > env vars > project config > global config > defaults

**DB path resolution:** `--db-path` > `TIMEREG_DB_PATH` env > global config > `platformdirs.user_data_dir("timereg") / "timereg.db"`

### Git Analyzer (`core/git.py`)

- `fetch_commits(repo_path, date, user_email, merge_commits=False) -> list[CommitInfo]`
- `get_branch_info(repo_path) -> BranchInfo`
- `get_working_tree_status(repo_path) -> WorkingTreeStatus`
- `resolve_git_user(repo_path) -> GitUser`

All subprocess calls through `_run_git(args, cwd) -> str` for easy mocking. Non-existent repos are warned and skipped. Empty repos return empty lists. Date boundaries are timezone-aware.

### Entry Manager (`core/entries.py`)

- `create_entry(...)` — creates entry + commits in transaction, handles peers and split groups
- `edit_entry(...)` — partial updates, optional peer cascade
- `delete_entry(...)` — release or claim commits, optional peer/split cascade
- `delete_split_group(...)` — atomic group deletion
- `undo_last(...)` — deletes most recent entry, always releases commits, reports split group membership
- `list_entries(...)` — flexible date/project filtering
- `get_registered_commit_hashes(...)` — for fetch exclusion

### Project Registry (`core/projects.py`)

- `auto_register_project(db, config)` — upsert from config file
- `add_project(db, name, slug)` — manual project (no repos)
- `list_projects(db)` — all projects with weekly stats
- `get_project(db, slug)` — lookup
- `remove_project(db, slug, keep_entries=True)` — deregister

## CLI Layer

### Global Options

`--db-path`, `--config`, `--verbose/-v`, `--format json|text`

Global callback resolves config, initializes DB, runs migrations.

### Commands

| Command | Description |
|---------|-------------|
| `fetch` | Unregistered commits for current project. `--date`, `--from/--to`, `--project` |
| `fetch --all` | Across all registered projects with suggested split |
| `register` | Create time entry. `--hours`, `--short-summary`, `--long-summary`, `--commits`, `--tags`, `--peer`, `--date` |
| `register --split` | Multi-project linked registration |
| `list` | List entries. `--date`, `--from/--to`, `--project`, `--all`, `--detail` |
| `edit <id>` | Edit entry fields. `--hours`, `--short-summary`, `--tags`, `--date` |
| `delete <id>` | Delete entry. `--release-commits/--keep-commits`, `--delete-peers` |
| `undo` | Undo last registration |
| `projects` | Subcommands: `list`, `add`, `remove`, `show` |
| (no args) | Interactive mode — project selection, prompts for time/description |

### Output

- `--format json` or piped stdout → JSON via Pydantic serialization
- `--format text` (default for terminal) → Rich tables/panels
- Errors to stderr, data to stdout

## New Concepts (vs Original Design)

| Change | Rationale |
|--------|-----------|
| `split_group_id` on entries | Multi-project time distribution as linked group |
| `fetch --all` with suggested split | Enables agent to propose time distribution across projects |
| `claimed_commits` table | Clean separation for delete-without-release |
| Config traversal stops at home dir | Security — don't walk into system directories |
| Exit if no `.timetracker.toml` found | Clear failure mode, no ambiguous "unattached" state |
| No MCP server | Deferred to Phase 3; agent uses CLI via subprocess + skill file |
| No `pytest-tmp-files` | Built-in `tmp_path` is sufficient |
| No export_targets migration | Phase 2 scope |

## Agent Integration

A skill file (e.g. `TIMEREG_SKILL.md`) teaches agents the CLI workflow:

1. Call `timereg fetch --format json` to get unregistered commits
2. Generate short + long summaries from commit data
3. Call `timereg register --hours ... --short-summary ... --commits ...`
4. For multi-project: `timereg fetch --all --format json` → review suggested split → `timereg register --split ...`

No MCP server required — agent calls CLI as subprocess, parses JSON output.

## Implementation Approach

Hybrid: build the foundation layer first (fully TDD), then vertical slices for each CLI command.

1. Project scaffolding + tooling (pyproject.toml, pre-commit, package structure)
2. Database + migrations + models + time parser (TDD)
3. Config resolution (TDD)
4. Vertical slices: fetch, register, list, edit/delete/undo, projects
5. Interactive mode + JSON output polish
6. Agent skill file

## Out of Scope (Later Phases)

- MCP server (Phase 3)
- Multi-repo submodule handling (Phase 2)
- Summary reports, budget tracking, gap detection (Phase 2)
- Tags with constraints (Phase 2)
- CSV/JSON export (Phase 2)
- Google Sheets, Tripletex, PostgreSQL (Phase 4)

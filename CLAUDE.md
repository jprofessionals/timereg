# TimeReg — Development Instructions

## Project Overview

TimeReg is a Git-aware CLI time-tracking tool for consulting teams. It integrates with AI coding agents via MCP and tracks billable hours across multiple projects and repositories.

**Tech stack:** Python 3.12+, uv, Typer, Rich, Pydantic, SQLite, MCP SDK.

## Quick Start

```bash
# Install dependencies
uv sync

# Run tests
uv run pytest

# Run the CLI
uv run timereg --help

# Install globally (for MCP testing)
uv tool install -e .
```

## Architecture

The codebase is organized into three layers:

- `src/timereg/core/` — Business logic (config, database, git, entries, projects, reports, budget, checks, export)
- `src/timereg/cli/` — Typer CLI commands that call into core
- `src/timereg/mcp/` — MCP server that exposes core as agent tools

All state is in a local SQLite database (WAL mode). Configuration is via `.timereg.toml` (per-project) and `~/.config/timereg/config.toml` (global).

## Development Approach

**TDD:** Write tests first, then implement. Test scenarios are documented in `TEST_SCENARIOS.md`.

**Test levels:**
- `tests/unit/` — Core logic, no filesystem or git dependencies (mocked)
- `tests/integration/` — CLI commands against real temp git repos and databases
- `tests/e2e/` — Full workflows from repo setup through reporting

**Run specific test files:**
```bash
uv run pytest tests/unit/test_time_parser.py -v
uv run pytest tests/integration/ -v
```

## Key Design Patterns

**Config resolution:** Walk up from CWD to find `.timereg.toml`. Merge with global config. Precedence: CLI flags > env vars > project config > global config > defaults.

**Two-phase registration:** `fetch` returns unregistered commits → agent generates summaries → `register` persists the entry with commit associations.

**Commit tracking:** Once commits are associated with an entry via `entry_commits`, they are excluded from future `fetch` results. Deleting an entry can either release or keep commits claimed.

**Peer linking:** Multiple entries share a `peer_group_id` UUID. Edit/delete operations can optionally cascade to peer entries.

## Database Migrations

Sequential SQL files in `src/timereg/migrations/`. Tracked via `schema_version` table. Applied automatically on startup.

## Configuration Precedence

1. CLI flags (`--db-path`, `--date`, etc.)
2. Environment variables (`TIMEREG_DB_PATH`)
3. Project config (`.timereg.toml`)
4. Global config (`config.toml`)
5. Built-in defaults

## Time Registration (MCP Agent Usage)

When the user says "register 4h30m", "logg 3 timer", or "register time":

1. Call `timereg_fetch` to get unregistered commits for today
2. Review the commit data returned
3. Generate TWO summaries:
   - `short_summary`: 2-10 words capturing the essence
   - `long_summary`: 20-100 words with more detail
4. Call `timereg_register` with hours, both summaries, and commit hashes
5. Confirm to the user what was registered

For manual entries (meetings, planning): call `timereg_register` with `entry_type="manual"`.

For status checks: call `timereg_status` and present conversationally.

For summaries/reports: call `timereg_summary` with appropriate period and detail level.

## Development Phases

### Phase 1: Core MVP
- Global config creation and resolution
- Project config resolution (walk up directories)
- SQLite database with migration system
- Pydantic models for all entities
- Time parser (2h30m, 1.5, 90m → float)
- Git commit fetching (single repo)
- Entry CRUD (create, read, edit, delete, undo)
- Project registry (auto-register, manual add)
- CLI: `fetch`, `register`, `list`, `edit`, `delete`, `undo`, `projects`
- Interactive mode
- JSON output for all commands

### Phase 2: Multi-Repo, Reporting & Advanced Features
- Multi-repo support (submodules, grouped repos)
- Peer registration
- Summary reports (day, week, month)
- Budget tracking
- Gap/conflict detection (`check`, `status`)
- Tags (freeform + constrained)
- CSV/JSON export
- Branch activity collection

### Phase 3: Agent Integration
- MCP server implementation (stdio)
- MCP tool definitions for all commands
- End-to-end testing with Claude Code
- Testing with Codex CLI

### Phase 4: External Backends
- Google Sheets export/sync
- Tripletex integration
- PostgreSQL backend option
- Shared database for team usage

## Reference Documents

- `docs/plan/DESIGN.md` — Full architecture, data model, CLI interface, MCP tools
- `docs/plan/TEST_SCENARIOS.md` — Complete test scenarios for TDD

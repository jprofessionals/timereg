# TimeReg — Project Summary & Design Document

## 1. Project Summary

**TimeReg** is a developer-focused CLI time-tracking tool that integrates with Git repositories and AI coding agents (Claude Code, Codex CLI, etc.). It is designed for consulting teams who need to accurately track billable hours across multiple projects and repositories.

The tool solves a common problem: developers forget to log hours, and when they do, the descriptions are vague. TimeReg addresses this by collecting git commit data automatically, letting AI agents generate meaningful work summaries, and persisting everything to a local SQLite database for later reporting, export, or synchronization to external systems.

**Key characteristics:**

- Installed globally via `uv tool install` and available on the system PATH
- Two interaction modes: direct CLI and MCP server (for AI agent integration)
- Git-aware: fetches commit data across multiple repos per project, filtered by date and user
- Two-phase registration: tool serves data → agent summarizes → agent calls back to persist
- Manual registration supported for non-code work (meetings, planning, documentation)
- Peer programming support: register time for multiple developers from one session
- Per-project configuration via `.timetracker.toml` in the repository
- Global configuration for database location, defaults, and user identity
- Reporting with budget tracking, gap detection, and structured export (JSON, CSV)
- Cross-platform: Linux (primary), macOS, Windows

**Technology stack:** Python 3.12+, uv for project/package management, Typer (CLI), Rich (terminal UI), Pydantic (models), SQLite (storage), MCP SDK (agent integration), subprocess-based git operations.

**Target users:** Software consultants at JPro (70 developers), working across multiple client projects, who need to register hours daily and export to Tripletex or Google Sheets.

---

## 2. Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     Agent Layer                          │
│           (Claude Code / Codex CLI / other)               │
│                                                           │
│  1. User says "register 4h30m"                           │
│  2. Agent calls timereg_fetch → gets unregistered commits │
│  3. Agent generates short summary (2-10 words)            │
│  4. Agent generates long summary (20-100 words)           │
│  5. Agent calls timereg_register with hours + summaries   │
│  6. Tool persists entry — job done                        │
└────────────────┬────────────────────┬─────────────────────┘
                 │ CLI (subprocess)    │ MCP (stdio)
                 ▼                    ▼
┌─────────────────────────────────────────────────────────┐
│                     TimeReg Core                         │
│                                                           │
│  ┌────────────┐  ┌────────────┐  ┌─────────────────────┐ │
│  │ Config     │  │ Git        │  │ Entry               │ │
│  │ Resolver   │  │ Analyzer   │  │ Manager             │ │
│  │            │  │            │  │ (CRUD + peers)      │ │
│  └────────────┘  └────────────┘  └─────────────────────┘ │
│  ┌────────────┐  ┌────────────┐  ┌─────────────────────┐ │
│  │ Project    │  │ Report     │  │ Export              │ │
│  │ Registry   │  │ Engine     │  │ Module              │ │
│  └────────────┘  └────────────┘  └─────────────────────┘ │
│  ┌────────────┐  ┌────────────┐                          │
│  │ Budget     │  │ Checks     │                          │
│  │ Tracker    │  │ (gaps/     │                          │
│  │            │  │  conflicts)│                          │
│  └────────────┘  └────────────┘                          │
│                       │                                   │
│                       ▼                                   │
│                ┌─────────────┐                            │
│                │   SQLite    │                            │
│                │   (WAL mode)│                            │
│                └─────────────┘                            │
└─────────────────────────────────────────────────────────┘
```

### Component Responsibilities

**Config Resolver** — Finds and parses `.timetracker.toml` by walking up from CWD. Loads global config. Merges settings with precedence: CLI flags > env vars > project config > global config > defaults.

**Git Analyzer** — Executes git commands via subprocess against declared repos. Fetches commits by date range and author. Collects branch activity. Filters out already-registered commit hashes. Returns structured data.

**Entry Manager** — CRUD operations on time entries. Handles two-phase registration, peer linking, commit association, and the delete-with-release-option flow.

**Project Registry** — Maintains the list of known projects in the database. Projects are auto-registered when a config file is first encountered, or manually added for non-repo projects.

**Report Engine** — Generates day/week/month summaries grouped by project. Includes budget comparison when configured.

**Budget Tracker** — Compares registered hours against configured weekly/monthly targets.

**Checks** — Detects gaps (days with no registration), conflicts (unusually high hours), and unregistered commits.

**Export Module** — Outputs data as JSON or CSV. Stage 2 will add Google Sheets and Tripletex sync.

---

## 3. Global Configuration

**Location (created on first run if absent):**

| Platform | Path |
|----------|------|
| Linux | `~/.config/timereg/config.toml` |
| macOS | `~/Library/Application Support/timereg/config.toml` |
| Windows | `%APPDATA%\timereg\config.toml` |

**Resolved using `platformdirs.user_config_dir("timereg")`.**

**Contents:**

```toml
[database]
# Override database location (important during development)
# Default is platform-appropriate data directory
# Can also be overridden via TIMEREG_DB_PATH env var or --db-path flag
path = "~/.local/share/timereg/timereg.db"

[defaults]
# Include merge commits in fetch results
merge_commits = false

# Default timezone for display and commit filtering
timezone = "Europe/Oslo"

# Default tags applied to new entries (can be overridden per entry)
# default_tags = []

[user]
# Default git identity (used when not resolvable from repo)
# name = "Mr Bell"
# email = "bell@jpro.no"
```

**Configuration precedence (highest to lowest):**

1. CLI flags (`--db-path`, `--date`, etc.)
2. Environment variables (`TIMEREG_DB_PATH`)
3. Project config (`.timetracker.toml`)
4. Global config (`config.toml`)
5. Built-in defaults

---

## 4. Project Configuration

**Filename:** `.timetracker.toml`

**Resolution:** Starting from current working directory, walk up the directory tree until found. If not found, the tool operates in "unattached" mode (interactive project selection or explicit `--project` flag required).

```toml
[project]
name = "Ekvarda Codex"
slug = "ekvarda"

[repos]
# All paths relative to this config file's location
paths = [
    ".",
    "./ekvarda-client",
    "./ekvarda-signaling",
    "../ekvarda-infra",
]

[tags]
# Optional: constrain allowed tags for this project
# If set, only these tags are accepted. If unset, freeform tags allowed.
allowed = ["development", "review", "meeting", "planning", "documentation", "bugfix", "devops", "testing", "support"]

[budget]
# Optional: hour targets for budget tracking
weekly_hours = 20.0
monthly_hours = 80.0

[export]
# Stage 2: external sync targets
# type = "google_sheets"
# sheet_id = "1abc..."
# tab_name = "Hours 2026"
#
# type = "tripletex"
# api_key_env = "TRIPLETEX_API_KEY"
# activity_id = 12345
```

---

## 5. Data Model

### 5.1 Tables

#### `projects`

```sql
CREATE TABLE projects (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    slug        TEXT NOT NULL UNIQUE,
    config_path TEXT,                  -- absolute path, nullable for manual-only projects
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE UNIQUE INDEX idx_projects_slug ON projects(slug);
```

#### `project_repos`

```sql
CREATE TABLE project_repos (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id    INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    absolute_path TEXT NOT NULL,
    relative_path TEXT NOT NULL
);
CREATE INDEX idx_project_repos_project ON project_repos(project_id);
```

#### `entries`

```sql
CREATE TABLE entries (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id      INTEGER NOT NULL REFERENCES projects(id),
    git_user_name   TEXT NOT NULL,
    git_user_email  TEXT NOT NULL,
    date            TEXT NOT NULL,       -- YYYY-MM-DD
    hours           REAL NOT NULL,
    short_summary   TEXT NOT NULL,       -- 2-10 words
    long_summary    TEXT,                -- 20-100 words, nullable for manual entries
    entry_type      TEXT NOT NULL CHECK(entry_type IN ('git', 'manual')),
    tags            TEXT,                -- JSON array, e.g. '["development","review"]'
    peer_group_id   TEXT,                -- UUID, links peer entries together
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_entries_project_date ON entries(project_id, date);
CREATE INDEX idx_entries_user ON entries(git_user_email, date);
CREATE INDEX idx_entries_peer ON entries(peer_group_id);
```

#### `entry_commits`

```sql
CREATE TABLE entry_commits (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id      INTEGER NOT NULL REFERENCES entries(id) ON DELETE CASCADE,
    commit_hash   TEXT NOT NULL,
    repo_path     TEXT NOT NULL,        -- relative path within project
    message       TEXT NOT NULL,
    author_name   TEXT NOT NULL,
    author_email  TEXT NOT NULL,
    timestamp     TEXT NOT NULL,        -- ISO 8601 with timezone
    files_changed INTEGER DEFAULT 0,
    insertions    INTEGER DEFAULT 0,
    deletions     INTEGER DEFAULT 0
);
CREATE INDEX idx_entry_commits_hash ON entry_commits(commit_hash);
CREATE INDEX idx_entry_commits_entry ON entry_commits(entry_id);
```

#### `export_targets` (stage 2, schema reserved)

```sql
CREATE TABLE export_targets (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id  INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    target_type TEXT NOT NULL CHECK(target_type IN ('google_sheets', 'tripletex', 'postgresql')),
    config      TEXT NOT NULL,          -- JSON configuration blob
    last_synced TEXT,                   -- ISO 8601 timestamp of last successful sync
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
```

### 5.2 Migrations

Database migrations are managed via sequential SQL files in `src/timereg/migrations/`:

```
001_initial.sql
002_add_peer_group.sql
003_add_export_targets.sql
```

A `schema_version` table tracks applied migrations:

```sql
CREATE TABLE schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

On startup, the tool checks current version and applies pending migrations.

---

## 6. Git Analysis

### 6.1 Commit Fetching Algorithm

```
FUNCTION fetch_unregistered_commits(project, date, user_email):
    results = []
    
    # Get all commit hashes already registered for this project
    registered_hashes = SELECT commit_hash FROM entry_commits
                        JOIN entries ON entry_commits.entry_id = entries.id
                        WHERE entries.project_id = project.id
    
    FOR EACH repo IN project.repos:
        # Get commits for the given date range and author
        commits = git log
            --after="{date}T00:00:00"
            --before="{date}T23:59:59"
            --author="{user_email}"
            --no-merges                    # exclude merge commits by default
            --format="%H|%s|%an|%ae|%aI"   # hash, subject, name, email, ISO date
            --numstat                       # file stats
        
        # Filter out already-registered commits
        unregistered = [c for c in commits if c.hash not in registered_hashes]
        
        # Get branch info
        current_branch = git rev-parse --abbrev-ref HEAD
        branches_today = git reflog --after="{date}T00:00:00"
                         --format="%gs" | extract branch operations
        
        # Get working tree status
        staged = git diff --cached --stat
        unstaged = git diff --stat
        
        results.append({
            repo_path: repo.relative_path,
            commits: unregistered,
            branch: current_branch,
            branch_activity: branches_today,
            uncommitted: {staged_files: len(staged), unstaged_files: len(unstaged)}
        })
    
    RETURN results
```

### 6.2 Git User Resolution

Order of precedence:

1. `--git-user-email` / `--git-user-name` CLI flags
2. `git config user.email` / `user.name` from the first repo in the project
3. `[user]` section in global config
4. Error if none found

### 6.3 Submodule Handling

When a repo path in the config contains git submodules, the tool traverses into them if they are also listed in `repos.paths`. Submodules not explicitly listed are ignored. This gives full control over which sub-repos are tracked.

---

## 7. CLI Interface

### 7.1 Installation

```bash
uv tool install timereg
```

This places `timereg` on the user's PATH. The tool is then available globally.

### 7.2 Global Flags

All commands accept:

```
--db-path PATH      Override database location
--config PATH       Override global config location
--verbose / -v      Verbose output
--format json|text  Output format (default: text for terminal, json when piped)
```

### 7.3 Commands

#### `timereg fetch`

Fetch unregistered commits for the current project and date.

```bash
# Today's unregistered commits (project resolved from CWD)
timereg fetch

# Specific date
timereg fetch --date 2026-02-24

# Date range
timereg fetch --from 2026-02-24 --to 2026-02-25

# Specific project (when not in a project directory)
timereg fetch --project ekvarda --date 2026-02-24

# Force JSON output
timereg fetch --format json
```

**JSON output:**

```json
{
    "project": {
        "name": "Ekvarda Codex",
        "slug": "ekvarda"
    },
    "date": "2026-02-25",
    "user": {
        "name": "Mr Bell",
        "email": "bell@jpro.no"
    },
    "repos": [
        {
            "relative_path": ".",
            "absolute_path": "/home/bell/projects/ekvarda",
            "branch": "feat/webrtc-signaling",
            "branch_activity": ["checkout feat/webrtc-signaling", "merge main"],
            "uncommitted": {"staged_files": 1, "unstaged_files": 3},
            "commits": [
                {
                    "hash": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
                    "message": "feat: add WebRTC signaling endpoint",
                    "author_name": "Mr Bell",
                    "author_email": "bell@jpro.no",
                    "timestamp": "2026-02-25T09:34:12+01:00",
                    "files_changed": 4,
                    "insertions": 87,
                    "deletions": 12,
                    "files": [
                        "src/signaling.py",
                        "src/auth.py",
                        "tests/test_signaling.py",
                        "pyproject.toml"
                    ]
                },
                {
                    "hash": "b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3",
                    "message": "test: integration tests for signaling handshake",
                    "author_name": "Mr Bell",
                    "author_email": "bell@jpro.no",
                    "timestamp": "2026-02-25T11:02:45+01:00",
                    "files_changed": 2,
                    "insertions": 134,
                    "deletions": 0,
                    "files": [
                        "tests/test_integration.py",
                        "tests/conftest.py"
                    ]
                }
            ]
        },
        {
            "relative_path": "./ekvarda-client",
            "absolute_path": "/home/bell/projects/ekvarda/ekvarda-client",
            "branch": "main",
            "branch_activity": [],
            "uncommitted": {"staged_files": 0, "unstaged_files": 0},
            "commits": []
        }
    ],
    "already_registered_today": {
        "total_hours": 2.0,
        "entry_count": 1,
        "entries": [
            {
                "id": 42,
                "hours": 2.0,
                "short_summary": "Auth module refactor",
                "long_summary": "Refactored the authentication module to support JWT-based tokens for WebRTC signaling connections. Updated middleware and added token refresh logic.",
                "tags": ["development"],
                "created_at": "2026-02-25T08:15:00+01:00"
            }
        ]
    }
}
```

#### `timereg register`

Persist a time entry. Called by agents after summarization or directly for manual entries.

```bash
# Git-aware registration (agent calls this after summarizing)
timereg register \
    --project ekvarda \
    --hours 4.5 \
    --short-summary "WebRTC signaling and auth" \
    --long-summary "Implemented WebRTC signaling endpoint with STUN/TURN configuration. Added JWT-based authentication for signaling connections. Wrote integration tests for the full handshake flow covering both happy path and error scenarios." \
    --commits a1b2c3d4,b2c3d4e5 \
    --date 2026-02-25 \
    --tags development,testing

# Manual registration (no commits)
timereg register \
    --project ekvarda \
    --hours 2.5 \
    --short-summary "Sprint planning" \
    --long-summary "Sprint planning session with team. Discussed WebRTC milestone priorities, assigned stories for photo frame client and backup integration. Reviewed velocity from last sprint." \
    --date 2026-02-25 \
    --tags meeting,planning

# Quick manual from anywhere (project by slug)
timereg register \
    --project jpro-internal \
    --hours 1.0 \
    --short-summary "Standup and admin"

# With peer (creates entries for both users)
timereg register \
    --project ekvarda \
    --hours 3.0 \
    --short-summary "Pair: auth flow debugging" \
    --long-summary "Paired with colleague on debugging JWT token refresh race condition in the signaling auth flow. Found and fixed timing issue in token validation middleware." \
    --commits c3d4e5f6 \
    --peer "colleague@jpro.no" \
    --tags development
```

**Peer registration behavior:**

- Creates two entries with identical hours, summaries, tags, and commit associations
- Both entries share the same `peer_group_id` (UUID)
- The primary entry uses the current git user; the peer entry uses the provided email
- `--peer` can be specified multiple times for group sessions

**Output:**

```
✓ Registered 4h30m on Ekvarda Codex for 2026-02-25 (Mr Bell)
  Short: "WebRTC signaling and auth"
  Commits: 2 across 1 repo
  Tags: development, testing
  Total today: 6h30m (budget: 4.0h/day)
```

#### `timereg` (interactive mode)

When called with no subcommand. Works from any directory.

```
$ timereg

TimeReg — Select a project:
  1. Ekvarda Codex         32.5h this week (budget: 20.0h)
  2. LNS Mobile PoC       12.0h this week (budget: 15.0h)
  3. JPro Internal          4.0h this week
  4. + Add new project

Project [1-4]: 1

Date [2026-02-25]:             (press Enter for today)
Hours (e.g. 2h30m, 1.5, 90m): 2h30m
Description: jobbet med planlegging og arkitektur
Tags (optional, comma-separated): planning
Peer (optional, email): 

✓ Registered 2h30m on Ekvarda Codex for 2026-02-25
  "jobbet med planlegging og arkitektur"
```

#### `timereg edit <id>`

```bash
# Edit hours
timereg edit 42 --hours 3.0

# Edit summary
timereg edit 42 --short-summary "Updated auth module"

# Edit tags
timereg edit 42 --tags development,security

# Edit date (moves the entry)
timereg edit 42 --date 2026-02-24
```

When editing a peer-linked entry:

```
This entry is linked to a peer registration (colleague@jpro.no).
Apply changes to peer entry as well? [Y/n]: Y
✓ Updated entry #42 and peer entry #43
```

#### `timereg delete <id>`

```bash
timereg delete 42

# Output:
# Entry #42: 4h30m on Ekvarda Codex (2026-02-25)
#   "WebRTC signaling and auth"
#   3 associated commits
#
# What should happen to the associated commits?
#   1. Release commits (they will appear in next fetch)
#   2. Keep commits claimed (they won't be re-fetched)
# > 1
#
# This entry is linked to a peer (colleague@jpro.no).
# Delete peer entry #43 as well? [Y/n]: Y
#
# ✓ Deleted entry #42 and peer entry #43. 3 commits released.
```

#### `timereg undo`

```bash
timereg undo

# ✓ Undone entry #43: 2h30m on Ekvarda Codex (2026-02-25)
#   "jobbet med planlegging og arkitektur"
#   Commits released for re-registration.
```

Always releases commits. If the undone entry was peer-linked, prompts about the peer entry.

#### `timereg list`

List entries with filtering.

```bash
# Today's entries for current project
timereg list

# Specific project and date
timereg list --project ekvarda --date 2026-02-25

# Date range
timereg list --from 2026-02-20 --to 2026-02-25

# All projects
timereg list --all --date 2026-02-25

# With full commit details
timereg list --date 2026-02-25 --detail full
```

#### `timereg summary`

```bash
# Today's summary for current project
timereg summary

# Weekly summary across all projects
timereg summary --week

# Monthly summary for specific project
timereg summary --month --project ekvarda

# Custom date range
timereg summary --from 2026-02-01 --to 2026-02-28

# Filter by tags
timereg summary --week --tags meeting,planning

# Brief or detailed
timereg summary --week --detail brief
timereg summary --week --detail full

# JSON output for agent consumption
timereg summary --week --format json
```

**Text output (weekly, full detail):**

```
═══════════════════════════════════════════════════════════
 Week 9, 2026 — Feb 24 – Feb 28                Mr Bell
═══════════════════════════════════════════════════════════

 Ekvarda Codex                           22.5h / 20.0h ██████████░ 112%
 ─────────────────────────────────────────────────────────
 Mon Feb 24
   4.5h  WebRTC signaling and auth                    [development, testing]
         Implemented WebRTC signaling endpoint with STUN/TURN
         configuration. Added JWT-based auth for signaling
         connections. Wrote integration tests for handshake flow.
   2.5h  Sprint planning                              [meeting, planning]
         Sprint planning session with team. Discussed WebRTC
         milestone priorities and backup integration timeline.

 Tue Feb 25
   3.0h  Photo frame client prototype                 [development]
   2.0h  Auth module refactor                         [development]

 Wed Feb 26
   5.0h  Backup integration to Jottacloud             [development]

 Thu Feb 27
   4.5h  ML pipeline setup                            [development, devops]

 Fri Feb 28
   1.0h  Code review                                  [review]

 LNS Mobile PoC                          12.0h / 15.0h ████████░░░ 80%
 ─────────────────────────────────────────────────────────
 Mon Feb 24
   4.0h  MQTT sync implementation                     [development]
 Tue Feb 25
   4.0h  Offline data collection                      [development]
 Wed Feb 26
   4.0h  AEMP 2.0 API integration                     [development]

 JPro Internal                            3.0h
 ─────────────────────────────────────────────────────────
 Mon Feb 24
   1.0h  Standup and admin                             [meeting]
 Fri Feb 28
   2.0h  Onboarding new developer                      [support]

═══════════════════════════════════════════════════════════
 TOTAL                                    37.5h
═══════════════════════════════════════════════════════════
```

**Brief output:**

```
Week 9, 2026 — Feb 24 – Feb 28

Ekvarda Codex       22.5h / 20.0h (112%)
LNS Mobile PoC      12.0h / 15.0h (80%)
JPro Internal         3.0h

Total: 37.5h
```

#### `timereg status`

```bash
timereg status

# ┌─────────────────────────────────────────────────────┐
# │ TimeReg Status — Wed Feb 25, 2026                    │
# ├─────────────────────────────────────────────────────┤
# │ Ekvarda Codex                                        │
# │   Today: 6.5h registered (2 entries)                 │
# │   Unregistered: 3 commits across 2 repos             │
# │   Week: 14.0h / 20.0h                               │
# │                                                       │
# │ LNS Mobile PoC                                       │
# │   Today: 4.0h registered (1 entry)                   │
# │   Unregistered: 0 commits                            │
# │   Week: 8.0h / 15.0h                                │
# │                                                       │
# │ ⚠ JPro Internal: no hours registered today           │
# └─────────────────────────────────────────────────────┘
```

#### `timereg projects`

```bash
# List all known projects
timereg projects
# NAME               SLUG              CONFIG     REPOS  THIS WEEK
# Ekvarda Codex      ekvarda           ✓ (3 repos) 3     22.5h
# LNS Mobile PoC     lns-mobile        ✓ (1 repo)  1     12.0h
# JPro Internal      jpro-internal     —           0      3.0h

# Add a manual-only project
timereg projects add --name "JPro Internal" --slug jpro-internal

# Show project details
timereg projects show ekvarda

# Remove from registry (does not delete entries)
timereg projects remove jpro-internal --keep-entries
```

#### `timereg export`

```bash
# CSV export
timereg export --project ekvarda --month --format csv > hours.csv

# JSON export for all projects
timereg export --from 2026-02-01 --to 2026-02-28 --format json

# Stage 2: sync to configured target
# timereg sync --project ekvarda
```

**CSV format:**

```csv
date,project,hours,short_summary,long_summary,tags,entry_type,git_user_email,commits
2026-02-25,Ekvarda Codex,4.5,"WebRTC signaling and auth","Implemented WebRTC...",development;testing,git,bell@jpro.no,a1b2c3d4;b2c3d4e5
2026-02-25,Ekvarda Codex,2.5,"Sprint planning","Sprint planning session...",meeting;planning,manual,bell@jpro.no,
```

#### `timereg check`

```bash
timereg check --week

# Week 9 (Feb 24 - Feb 28) — Mr Bell
#
# ✓ Mon Feb 24:  7.0h registered across 2 projects
# ⚠ Tue Feb 25:  6.5h registered, 3 unregistered commits on Ekvarda Codex
# ✓ Wed Feb 26:  9.0h registered across 2 projects
# ⚠ Thu Feb 27:  4.5h registered (below typical day)
# ⚠ Fri Feb 28:  No hours registered yet
#   ↳ 5 unregistered commits on Ekvarda Codex
#
# Summary:
#   Total registered: 27.0h
#   Potential missing: ~2-4h estimated from unregistered commits
#   Budget gaps: LNS Mobile PoC at 80% (12/15h)
```

#### `timereg mcp-serve`

Starts the MCP server on stdio. Not intended for direct human use.

```bash
timereg mcp-serve
```

---

## 8. MCP Server

### 8.1 Tool Definitions

The MCP server exposes these tools:

**`timereg_fetch`**
- Input: `{ project?: string, date?: string, from?: string, to?: string }`
- Output: JSON (same as CLI `fetch --format json`)
- Description: "Fetch unregistered git commits for a project. Returns commit data for agent summarization."

**`timereg_register`**
- Input: `{ project: string, hours: number, short_summary: string, long_summary?: string, commits?: string[], date?: string, tags?: string[], peer?: string, entry_type?: "git"|"manual" }`
- Output: `{ entry_id: number, message: string }`
- Description: "Register time for a project. For git-aware entries, call timereg_fetch first to get commits."

**`timereg_edit`**
- Input: `{ entry_id: number, hours?: number, short_summary?: string, long_summary?: string, tags?: string[], apply_to_peer?: boolean }`
- Output: `{ message: string }`

**`timereg_delete`**
- Input: `{ entry_id: number, release_commits: boolean, delete_peer?: boolean }`
- Output: `{ message: string }`

**`timereg_undo`**
- Input: `{}`
- Output: `{ message: string, undone_entry: object }`

**`timereg_summary`**
- Input: `{ period?: "day"|"week"|"month", project?: string, from?: string, to?: string, tags?: string[], detail?: "brief"|"full" }`
- Output: JSON summary report

**`timereg_status`**
- Input: `{}`
- Output: JSON status overview

**`timereg_projects`**
- Input: `{ action: "list"|"add"|"remove"|"show", name?: string, slug?: string }`
- Output: JSON project data

**`timereg_check`**
- Input: `{ period?: "day"|"week"|"month" }`
- Output: JSON with warnings and gaps

**`timereg_export`**
- Input: `{ project?: string, from?: string, to?: string, format: "json"|"csv" }`
- Output: Formatted data

### 8.2 MCP Configuration

```json
{
    "mcpServers": {
        "timereg": {
            "command": "timereg",
            "args": ["mcp-serve"],
            "env": {}
        }
    }
}
```

### 8.3 Agent Skill File

To be placed in project's `CLAUDE.md` or as a dedicated skill:

```markdown
## Time Registration (TimeReg)

You have access to a time registration tool via MCP. Use it when the user
asks to register time, check hours, or review time entries.

### Registering time with git commits

When the user says something like "register 4h30m", "logg 3 timer", or
"register time":

1. Call `timereg_fetch` to get unregistered commits for today
2. Review the commit data returned
3. Generate TWO summaries of the work done:
   - short_summary: 2-10 words capturing the essence
   - long_summary: 20-100 words with more detail
4. Call `timereg_register` with the hours, both summaries, and commit hashes
5. Confirm to the user what was registered

### Manual time registration

When the user says "register 2h on projectname for meetings" or similar
without git context:

1. Call `timereg_register` with entry_type="manual", the hours, project
   slug, and use the user's description as short_summary
2. Confirm to the user

### Checking status

When asked "how many hours have I logged" or "what's my status":
1. Call `timereg_status`
2. Present the overview conversationally

### Weekly/monthly summaries

When asked for a summary or report:
1. Call `timereg_summary` with appropriate period and detail level
2. Present the data in a readable format
```

---

## 9. Database Location

**Default paths (resolved via `platformdirs.user_data_dir("timereg")`):**

| Platform | Path |
|----------|------|
| Linux | `~/.local/share/timereg/timereg.db` |
| macOS | `~/Library/Application Support/timereg/timereg.db` |
| Windows | `%APPDATA%\timereg\timereg.db` |

**Override order:**

1. `--db-path` CLI flag
2. `TIMEREG_DB_PATH` environment variable
3. `[database] path` in global config
4. Default platform path

The database uses **WAL mode** for better concurrent access.

---

## 10. Project Structure

```
timereg/
├── pyproject.toml
├── uv.lock
├── README.md
├── LICENSE
├── CLAUDE.md                           # Agent development instructions
├── src/
│   └── timereg/
│       ├── __init__.py                 # Version
│       ├── __main__.py                 # python -m timereg
│       ├── cli/
│       │   ├── __init__.py
│       │   ├── app.py                  # Typer app, global flags
│       │   ├── fetch.py                # timereg fetch
│       │   ├── register.py             # timereg register
│       │   ├── interactive.py          # timereg (no args)
│       │   ├── edit.py                 # timereg edit
│       │   ├── delete.py               # timereg delete
│       │   ├── undo.py                 # timereg undo
│       │   ├── list_cmd.py             # timereg list
│       │   ├── summary.py              # timereg summary
│       │   ├── status.py               # timereg status
│       │   ├── projects.py             # timereg projects
│       │   ├── export.py               # timereg export
│       │   ├── check.py                # timereg check
│       │   └── mcp_serve.py            # timereg mcp-serve
│       ├── core/
│       │   ├── __init__.py
│       │   ├── config.py               # Global + project config resolution
│       │   ├── database.py             # SQLite connection, migrations, WAL
│       │   ├── models.py               # Pydantic models
│       │   ├── git.py                  # Git subprocess operations
│       │   ├── entries.py              # Entry CRUD + peer logic
│       │   ├── projects.py             # Project registry
│       │   ├── reports.py              # Summary generation
│       │   ├── budget.py               # Budget comparison
│       │   ├── checks.py               # Gap/conflict detection
│       │   ├── export.py               # JSON/CSV formatting
│       │   └── time_parser.py          # Parse "2h30m", "1.5", "90m" → float
│       ├── mcp/
│       │   ├── __init__.py
│       │   └── server.py               # MCP tool definitions + stdio server
│       └── migrations/
│           ├── 001_initial.sql
│           └── 002_add_export_targets.sql
├── tests/
│   ├── __init__.py
│   ├── conftest.py                     # Shared fixtures
│   ├── fixtures/                       # Test data
│   │   ├── sample_config.toml
│   │   └── sample_global_config.toml
│   ├── unit/
│   │   ├── __init__.py
│   │   ├── test_config.py
│   │   ├── test_time_parser.py
│   │   ├── test_models.py
│   │   ├── test_database.py
│   │   ├── test_entries.py
│   │   ├── test_projects.py
│   │   ├── test_git.py
│   │   ├── test_reports.py
│   │   ├── test_budget.py
│   │   ├── test_checks.py
│   │   └── test_export.py
│   ├── integration/
│   │   ├── __init__.py
│   │   ├── test_cli_fetch.py
│   │   ├── test_cli_register.py
│   │   ├── test_cli_interactive.py
│   │   ├── test_cli_edit_delete.py
│   │   ├── test_cli_summary.py
│   │   ├── test_cli_status.py
│   │   ├── test_cli_check.py
│   │   ├── test_cli_export.py
│   │   ├── test_peer_registration.py
│   │   ├── test_multi_repo.py
│   │   └── test_mcp_server.py
│   └── e2e/
│       ├── __init__.py
│       └── test_full_workflow.py
└── examples/
    ├── ekvarda/.timetracker.toml
    └── internal-project/.timetracker.toml
```

### Dependencies (pyproject.toml)

```toml
[project]
name = "timereg"
version = "0.1.0"
description = "Git-aware time tracking for developers"
requires-python = ">=3.12"
license = "MIT"

dependencies = [
    "typer>=0.12",
    "rich>=13.0",
    "platformdirs>=4.0",
    "pydantic>=2.0",
    "mcp>=1.0",
]

[project.scripts]
timereg = "timereg.cli.app:app"

[tool.uv]
dev-dependencies = [
    "pytest>=8.0",
    "pytest-cov>=5.0",
    "pytest-tmp-files>=0.1",
]
```

---

## 11. Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Language | Python 3.12+ with uv | Fastest development, mature MCP SDK, team can use uv tool install |
| Package manager | uv (mandatory) | Team standard, handles global install via `uv tool install` |
| Database | SQLite (WAL mode) | Zero infrastructure, cross-platform, sufficient for local use |
| Git integration | subprocess | No gitpython dependency, maximum compatibility, simpler |
| CLI framework | Typer + Rich | Modern, type-hinted, excellent terminal output |
| Data models | Pydantic | Validation, serialization, clear schema documentation |
| Config format | TOML | Python ecosystem standard, human-readable |
| MCP transport | stdio | Standard for CLI-integrated MCP servers |
| Timezone | UTC storage, local display | Avoids ambiguity, correct across time zones |
| Merge commits | Excluded by default | Usually noise, flag to include when needed |
| Branch activity | Included | Gives agents better context even with few commits |

---

## 12. Open Questions (Resolved)

| Question | Resolution |
|----------|-----------|
| Timezone handling | Store UTC with offset, display in local timezone |
| Merge commits | Exclude by default, `--merge-commits` flag to include |
| Squashed commits | Branch activity for local user included, covers this case |
| Concurrent access | SQLite WAL mode sufficient for local use |

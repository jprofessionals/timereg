# TimeReg

Git-aware time tracking for consulting teams. TimeReg automatically discovers your daily commits across repositories and turns them into billable time entries — either through the CLI or by letting an AI coding agent do it for you.

## Why TimeReg?

If you bill hours to clients, you know the pain: reconstruct what you did at the end of the day from memory, git logs, and calendar entries. TimeReg solves this by:

- **Pulling commits automatically** from your project repositories for any given day
- **Tracking which commits are already registered** so you never double-count
- **Supporting AI agents** (Claude Code, Codex, etc.) that can summarize your work and register time with a single conversational command
- **Handling multiple projects** with suggested time splits based on commit activity
- **Storing everything locally** in SQLite — your time data stays on your machine

## Quick Start

### Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
- Git (for commit-based time tracking)

### Install

```bash
# Clone the repository
git clone <repo-url>
cd timereg

# Install with uv (adds `timereg` to your PATH)
uv tool install -e .

# After pulling changes, reinstall to pick up new code
uv tool install -e . --force
```

### Set Up a Project

Create a `.timereg.toml` in your project root (or any parent directory):

```toml
[project]
name = "Client Project"
slug = "client-project"

[repos]
main = "."
# Or track multiple repos:
# api = "../client-api"
# frontend = "../client-frontend"
```

### Basic Workflow

```bash
# See what you've done today (unregistered commits)
timereg fetch

# Register time with a summary
timereg register --hours 2h30m --short-summary "Auth system implementation" \
  --commits abc1234,def5678

# Register time for meetings (no commits)
timereg register --hours 1h --short-summary "Sprint planning" --entry-type manual

# Check your entries
timereg list
timereg list --date 2026-02-25
timereg list --from 2026-02-20 --to 2026-02-26

# Fix mistakes
timereg edit 3 --hours 3h
timereg undo
timereg delete 5 --release-commits
```

### Time Formats

TimeReg accepts flexible time input:

| Input | Interpreted as |
|-------|---------------|
| `2h30m` | 2.5 hours |
| `2h` | 2.0 hours |
| `90m` | 1.5 hours |
| `1.5` | 1.5 hours |
| `4.25` | 4.25 hours |

## AI Agent Integration

TimeReg is designed to work with AI coding agents. A skill file is bundled with the package that teaches agents how to use the CLI. Install it to your agent's skill directory:

```bash
# Claude Code
mkdir -p ~/.claude/skills/timereg
timereg skill > ~/.claude/skills/timereg/SKILL.md

# Other agents — pipe to wherever your agent reads skills from
timereg skill > /path/to/agent/skills/timereg.md

# Show the path to the bundled file (useful for symlinking)
timereg skill --path
```

After installing the skill, the agent can:

1. Fetch your unregistered commits
2. Generate meaningful summaries from the commit data
3. Register the time entry — all from a conversational prompt like "register my hours for today"

Re-run `timereg skill > ...` after updating timereg to keep the skill in sync with the CLI.

All commands support `--format json` for structured output that agents can parse:

```bash
timereg --format json fetch
timereg --format json list --all
```

## Commands

| Command | Description |
|---------|-------------|
| `timereg fetch` | Show unregistered commits for today |
| `timereg fetch --all --hours 8h` | Fetch across all projects with time split |
| `timereg register` | Create a time entry |
| `timereg list` | List time entries with filters |
| `timereg edit <id>` | Modify an existing entry |
| `timereg delete <id> [<id>...]` | Remove one or more entries |
| `timereg undo` | Undo the last registration |
| `timereg projects list` | List registered projects |
| `timereg projects add .` | Add project from .timereg.toml in directory |
| `timereg projects add --name --slug` | Manually add a project |
| `timereg projects remove` | Remove a project |
| `timereg skill` | Output bundled agent skill file |
| `timereg init` | Initialize .timereg.toml in current directory |
| `timereg` | Interactive mode (no subcommand) |

Run `timereg <command> --help` for full option details.

## Configuration

### Project Config (`.timereg.toml`)

Placed in your project directory (or any parent up to your home directory). TimeReg walks up from the current working directory to find it.

```toml
[project]
name = "My Project"
slug = "my-project"

[repos]
main = "."

[options]
merge_commits = false    # Include merge commits in fetch results
```

### Global Config (`~/.config/timereg/config.toml`)

Created automatically on first run with sensible defaults.

```toml
[global]
db_path = ""             # Empty = default location
timezone = "Europe/Oslo"
user_name = ""
user_email = ""
merge_commits = false
```

### Precedence

Settings resolve in this order (first wins):

1. CLI flags (`--db-path`, `--date`, etc.)
2. Environment variables (`TIMEREG_DB_PATH`)
3. Project config (`.timereg.toml`)
4. Global config (`config.toml`)
5. Built-in defaults

## Development

### Setup

```bash
# Install all dependencies (runtime + dev)
uv sync

# Install pre-commit hooks
uv run pre-commit install
```

### Running Tests

```bash
# Full test suite with coverage
uv run pytest

# Specific test file
uv run pytest tests/unit/test_time_parser.py -v

# Only unit tests (fast)
uv run pytest tests/unit/ -v

# Integration tests (uses temp git repos and databases)
uv run pytest tests/integration/ -v

# End-to-end tests
uv run pytest tests/e2e/ -v
```

### Code Quality

Pre-commit hooks run automatically on each commit:

- **Ruff** — linting and formatting
- **mypy** — strict type checking
- **pytest** — unit tests

Run manually:

```bash
uv run ruff check src/ tests/
uv run ruff format src/ tests/
uv run mypy src/
```

### Architecture

```
src/timereg/
  core/       Business logic (no CLI or protocol concerns)
    config.py     Config file discovery and resolution
    database.py   SQLite with WAL mode and migration system
    entries.py    Entry CRUD with peer and split group support
    git.py        Git subprocess operations
    models.py     Pydantic models for all entities
    projects.py   Project registry
    time_parser.py  Flexible time input parsing
  cli/        Typer CLI commands (thin layer over core)
  mcp/        MCP server (planned for Phase 3)
  migrations/ Sequential SQL migration files
```

All state lives in a local SQLite database. The CLI layer is deliberately thin — it parses arguments, calls into `core/`, and formats output.

### Test Structure

```
tests/
  unit/          Core logic tests (mocked git/filesystem)
  integration/   CLI commands against real temp repos and databases
  e2e/           Full workflows from repo setup through reporting
  fixtures/      Sample config files
  conftest.py    Shared fixtures (tmp_db, git_repo, make_commit)
```

## License

MIT

# TimeReg — Test Scenarios

This document contains all test scenarios for TDD development of TimeReg. Start with unit tests, then integration, then end-to-end.

---

## 1. Test Infrastructure (conftest.py)

```python
"""
Key fixtures needed for TDD:

- tmp_db: Fresh SQLite database in temp directory
- tmp_git_repo: Initialized git repo with configurable commits
- tmp_multi_repo: Multiple git repos simulating a project with sub-repos
- tmp_config: .timetracker.toml in a temp directory
- tmp_global_config: Global config.toml in temp directory
- cli_runner: Typer CliRunner with isolated environment
- sample_commits: Pre-built commit data for testing
"""

@pytest.fixture
def tmp_db(tmp_path):
    """Create a fresh SQLite database."""
    db_path = tmp_path / "test.db"
    db = Database(str(db_path))
    db.migrate()
    return db

@pytest.fixture
def tmp_git_repo(tmp_path):
    """Create a git repo with sample commits."""
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    # git init, configure user, create commits
    # Returns a helper object for creating commits with specific dates/authors
    return GitRepoHelper(repo_path)

@pytest.fixture
def tmp_multi_repo(tmp_path):
    """Create a project with multiple repos."""
    # Creates main repo + 2 sub-repos + config file
    return MultiRepoHelper(tmp_path)

@pytest.fixture
def cli_runner(tmp_db, tmp_path):
    """CLI runner with isolated DB and config."""
    runner = CliRunner()
    env = {"TIMEREG_DB_PATH": str(tmp_db.path)}
    return runner, env
```

---

## 2. Unit Tests

### `test_time_parser.py`

```
SCENARIO: Parse various time formats
  "2h30m"    → 2.5
  "2h"       → 2.0
  "30m"      → 0.5
  "90m"      → 1.5
  "1.5"      → 1.5
  "4.25"     → 4.25
  "0.5"      → 0.5
  "1h45m"    → 1.75
  "8h"       → 8.0

SCENARIO: Reject invalid time formats
  ""         → ValueError
  "abc"      → ValueError
  "-1h"      → ValueError
  "0h"       → ValueError (must be positive)
  "25h"      → Warning (but allow — might be a week total)
  "0m"       → ValueError
```

### `test_config.py`

```
SCENARIO: Find config file by walking up directory tree
  GIVEN: .timetracker.toml exists at /home/user/projects/ekvarda/
  WHEN: CWD is /home/user/projects/ekvarda/src/lib/
  THEN: Config resolves to /home/user/projects/ekvarda/.timetracker.toml

SCENARIO: No config file found
  GIVEN: No .timetracker.toml in any parent directory
  WHEN: Resolving config from CWD
  THEN: Returns None (not an error)

SCENARIO: Parse config file with all fields
  GIVEN: Valid .timetracker.toml with project, repos, tags, budget, export
  WHEN: Parsing the config
  THEN: All fields are correctly populated in ProjectConfig model

SCENARIO: Parse config file with minimal fields
  GIVEN: .timetracker.toml with only [project] name and slug
  WHEN: Parsing the config
  THEN: Repos defaults to ["."], no tags constraint, no budget

SCENARIO: Resolve repo paths relative to config file
  GIVEN: Config at /home/user/projects/ekvarda/.timetracker.toml
  AND: repos.paths = [".", "./client", "../infra"]
  WHEN: Resolving absolute repo paths
  THEN: Paths are /home/user/projects/ekvarda,
        /home/user/projects/ekvarda/client,
        /home/user/projects/infra

SCENARIO: Global config created on first run
  GIVEN: No global config exists
  WHEN: Application starts
  THEN: Default config.toml is created at platform-appropriate location

SCENARIO: Global config DB path override
  GIVEN: Global config with database.path = "/custom/path/timereg.db"
  WHEN: Resolving DB location
  THEN: Database uses /custom/path/timereg.db

SCENARIO: Environment variable overrides global config
  GIVEN: TIMEREG_DB_PATH="/env/path/timereg.db"
  AND: Global config has database.path = "/config/path/timereg.db"
  WHEN: Resolving DB location
  THEN: Database uses /env/path/timereg.db
```

### `test_database.py`

```
SCENARIO: Initialize fresh database
  GIVEN: No database file exists
  WHEN: Database is initialized
  THEN: All tables are created
  AND: Schema version is set to latest migration
  AND: WAL mode is enabled

SCENARIO: Run migrations on existing database
  GIVEN: Database at migration version 1
  WHEN: Application starts with migrations up to version 3
  THEN: Migrations 2 and 3 are applied
  AND: Schema version is updated to 3

SCENARIO: Skip already-applied migrations
  GIVEN: Database at migration version 3
  WHEN: Application starts with migrations up to version 3
  THEN: No migrations are applied
```

### `test_entries.py`

```
SCENARIO: Create git-aware entry with commits
  GIVEN: Project "ekvarda" exists in registry
  WHEN: Creating entry with hours=4.5, commits=[hash1, hash2], date=2026-02-25
  THEN: Entry is created in entries table with entry_type="git"
  AND: 2 rows are created in entry_commits table
  AND: entry.created_at is set

SCENARIO: Create manual entry without commits
  GIVEN: Project "jpro-internal" exists in registry
  WHEN: Creating entry with hours=2.0, short_summary="Sprint planning", no commits
  THEN: Entry is created with entry_type="manual"
  AND: No rows in entry_commits

SCENARIO: Create peer-linked entries
  GIVEN: Project "ekvarda" exists
  WHEN: Creating entry with hours=3.0 and peer="colleague@jpro.no"
  THEN: Two entries are created with same peer_group_id
  AND: First entry has git_user_email from current user
  AND: Second entry has git_user_email="colleague@jpro.no"
  AND: Both entries have identical hours, summaries, tags, and commits

SCENARIO: Edit entry updates timestamp
  GIVEN: Entry #42 exists with hours=4.5
  WHEN: Editing to hours=3.0
  THEN: Entry hours are updated to 3.0
  AND: updated_at is refreshed

SCENARIO: Delete entry with commit release
  GIVEN: Entry #42 with commits [hash1, hash2]
  WHEN: Deleting with release_commits=True
  THEN: Entry is deleted (CASCADE removes entry_commits)
  AND: hash1 and hash2 are no longer in entry_commits table
  AND: They appear in subsequent fetch results

SCENARIO: Delete entry keeping commits claimed
  GIVEN: Entry #42 with commits [hash1, hash2]
  WHEN: Deleting with release_commits=False
  THEN: Entry is deleted
  BUT: Commit hashes are moved to a "claimed_commits" record (or separate table)
  AND: They do NOT appear in subsequent fetch results

SCENARIO: Undo last registration
  GIVEN: Last created entry is #43 with 2 commits
  WHEN: Calling undo
  THEN: Entry #43 is deleted
  AND: Commits are released

SCENARIO: Multiple entries per day are separate
  GIVEN: Entry #42 for ekvarda on 2026-02-25 (4.5h)
  WHEN: Creating another entry for ekvarda on 2026-02-25 (2.0h)
  THEN: Both entries exist independently
  AND: Total for day is 6.5h

SCENARIO: Tags are stored as JSON array
  GIVEN: Creating entry with tags=["development", "testing"]
  WHEN: Retrieving the entry
  THEN: tags field contains '["development", "testing"]'
  AND: Tags can be deserialized back to list
```

### `test_git.py`

```
SCENARIO: Fetch commits for a specific date
  GIVEN: Repo with commits on Feb 24, Feb 25, and Feb 26
  WHEN: Fetching commits for date=2026-02-25
  THEN: Only Feb 25 commits are returned

SCENARIO: Fetch commits filtered by author email
  GIVEN: Repo with commits from "bell@jpro.no" and "other@jpro.no"
  WHEN: Fetching for user_email="bell@jpro.no"
  THEN: Only bell@jpro.no commits are returned

SCENARIO: Exclude already-registered commits
  GIVEN: Repo with commits [hash1, hash2, hash3]
  AND: hash1 is already in entry_commits table
  WHEN: Fetching unregistered commits
  THEN: Only hash2 and hash3 are returned

SCENARIO: Exclude merge commits by default
  GIVEN: Repo with regular commit and a merge commit
  WHEN: Fetching with merge_commits=False (default)
  THEN: Only regular commit is returned

SCENARIO: Include merge commits when flagged
  GIVEN: Repo with regular commit and a merge commit
  WHEN: Fetching with merge_commits=True
  THEN: Both commits are returned

SCENARIO: Fetch across multiple repos
  GIVEN: Project with repos [".", "./client", "../infra"]
  AND: Commits exist in all three repos for target date
  WHEN: Fetching for the project
  THEN: Results contain commits grouped by repo with correct relative paths

SCENARIO: Get commit file statistics
  GIVEN: Commit that changes 3 files, adds 50 lines, removes 10 lines
  WHEN: Fetching commit details
  THEN: files_changed=3, insertions=50, deletions=10
  AND: File list contains the 3 changed files

SCENARIO: Get branch activity
  GIVEN: User created and switched branches during the day
  WHEN: Fetching for that date
  THEN: branch_activity contains branch operations
  AND: current branch name is included

SCENARIO: Get uncommitted work status
  GIVEN: Repo with 2 staged files and 3 unstaged modified files
  WHEN: Fetching
  THEN: uncommitted.staged_files=2, uncommitted.unstaged_files=3

SCENARIO: Handle empty repo (no commits)
  GIVEN: Initialized repo with no commits
  WHEN: Fetching commits
  THEN: Returns empty commit list (no error)

SCENARIO: Handle repo path that doesn't exist
  GIVEN: Config references "./nonexistent-repo"
  WHEN: Fetching commits
  THEN: Warning is logged, repo is skipped, other repos still processed

SCENARIO: Commits spanning midnight
  GIVEN: Commit at 2026-02-24T23:50:00 and 2026-02-25T00:10:00
  WHEN: Fetching for date=2026-02-25
  THEN: Only the 00:10 commit is included (date boundary is clean)
```

### `test_projects.py`

```
SCENARIO: Auto-register project from config file
  GIVEN: .timetracker.toml with name="Ekvarda Codex", slug="ekvarda"
  WHEN: First interaction with this project (fetch or register)
  THEN: Project is added to projects table with config_path set
  AND: Repo paths are added to project_repos table

SCENARIO: Manually add project
  GIVEN: No config file
  WHEN: Adding project with name="JPro Internal", slug="jpro-internal"
  THEN: Project is created with config_path=NULL
  AND: No entries in project_repos

SCENARIO: List known projects with stats
  GIVEN: 3 projects with varying entries this week
  WHEN: Listing projects
  THEN: Returns all 3 with weekly hour totals and repo counts

SCENARIO: Slug uniqueness enforced
  GIVEN: Project "ekvarda" already exists
  WHEN: Adding another project with slug="ekvarda"
  THEN: Error is raised

SCENARIO: Remove project keeps entries
  GIVEN: Project "ekvarda" with 10 entries
  WHEN: Removing project with keep_entries=True
  THEN: Project is removed from registry
  AND: Entries remain in database (orphaned but queryable)

SCENARIO: Project lookup by partial name
  GIVEN: Projects "Ekvarda Codex" and "Ekvarda Mobile"
  WHEN: Looking up "ekvarda" in interactive mode
  THEN: Both are shown for selection
```

### `test_reports.py`

```
SCENARIO: Daily summary single project
  GIVEN: 3 entries for "ekvarda" on 2026-02-25 totaling 7.5h
  WHEN: Generating daily summary
  THEN: Shows project name, total hours, and each entry with summary

SCENARIO: Weekly summary with budget
  GIVEN: Entries across 5 days for "ekvarda" with budget of 20h/week
  WHEN: Generating weekly summary
  THEN: Shows daily breakdown and budget comparison (e.g., "22.5h / 20.0h = 112%")

SCENARIO: Monthly summary across projects
  GIVEN: Entries for 3 projects across February
  WHEN: Generating monthly summary for all projects
  THEN: Shows per-project totals and grand total
  AND: Budget comparison where configured

SCENARIO: Filter summary by tags
  GIVEN: Entries tagged "meeting", "development", "review"
  WHEN: Generating summary with tags=["meeting"]
  THEN: Only meeting-tagged entries are included in totals

SCENARIO: Brief vs full detail
  GIVEN: Entries with long summaries
  WHEN: Generating with detail="brief"
  THEN: Only short summaries and totals are shown
  WHEN: Generating with detail="full"
  THEN: Long summaries are included
```

### `test_budget.py`

```
SCENARIO: Under budget shows remaining
  GIVEN: Budget of 20h/week, 15h registered so far
  WHEN: Checking budget
  THEN: Shows "15.0h / 20.0h (75%) — 5.0h remaining"

SCENARIO: Over budget shows excess
  GIVEN: Budget of 20h/week, 24h registered
  WHEN: Checking budget
  THEN: Shows "24.0h / 20.0h (120%) — 4.0h over budget"

SCENARIO: No budget configured
  GIVEN: Project without budget settings
  WHEN: Checking budget
  THEN: Only shows total hours (no comparison)
```

### `test_checks.py`

```
SCENARIO: Detect unregistered commits
  GIVEN: 5 unregistered commits for "ekvarda" on Tuesday
  WHEN: Running check for the week
  THEN: Warning for Tuesday mentions 5 unregistered commits

SCENARIO: Detect missing days
  GIVEN: No entries for Wednesday at all
  WHEN: Running check for the week
  THEN: Warning for Wednesday: "No hours registered"

SCENARIO: Detect high daily hours
  GIVEN: 14h registered across projects on Monday
  WHEN: Running check
  THEN: Warning for Monday: "14h registered (seems high)"

SCENARIO: No warnings for normal week
  GIVEN: 7-9h registered each day, no unregistered commits
  WHEN: Running check
  THEN: All days show ✓

SCENARIO: Weekend days ignored by default
  GIVEN: No entries on Saturday and Sunday
  WHEN: Running check for the week
  THEN: No warnings for weekend days
```

### `test_export.py`

```
SCENARIO: Export to JSON
  GIVEN: 5 entries for "ekvarda" in February
  WHEN: Exporting as JSON for Feb 2026
  THEN: Valid JSON array with all 5 entries
  AND: Each entry has date, project, hours, summaries, tags, commits

SCENARIO: Export to CSV
  GIVEN: Same 5 entries
  WHEN: Exporting as CSV
  THEN: Valid CSV with header row and 5 data rows
  AND: Multi-value fields (tags, commits) are semicolon-separated

SCENARIO: Export filters by project
  GIVEN: Entries across 3 projects
  WHEN: Exporting with project="ekvarda"
  THEN: Only ekvarda entries are included

SCENARIO: Export filters by date range
  GIVEN: Entries from Jan through March
  WHEN: Exporting from=2026-02-01, to=2026-02-28
  THEN: Only February entries are included
```

---

## 3. Integration Tests

### `test_cli_fetch.py`

```
SCENARIO: Fetch from a project directory
  GIVEN: Git repo with 3 commits today and .timetracker.toml
  WHEN: Running "timereg fetch" from repo directory
  THEN: Output contains all 3 commits with details

SCENARIO: Fetch shows already-registered entries
  GIVEN: 1 entry already registered for today
  AND: 2 new unregistered commits
  WHEN: Running "timereg fetch"
  THEN: Output shows 2 unregistered commits
  AND: Shows 1 already-registered entry with hours/summary

SCENARIO: Fetch for yesterday
  GIVEN: 3 commits from yesterday, 2 from today
  WHEN: Running "timereg fetch --date 2026-02-24"
  THEN: Only yesterday's 3 commits are returned

SCENARIO: Fetch JSON output
  GIVEN: Commits exist for today
  WHEN: Running "timereg fetch --format json"
  THEN: Output is valid JSON matching the defined schema
```

### `test_cli_register.py`

```
SCENARIO: Full git-aware registration
  GIVEN: 3 unregistered commits today
  WHEN: Running "timereg register --project ekvarda --hours 4.5
        --short-summary 'WebRTC work' --long-summary 'Detailed...'
        --commits hash1,hash2,hash3 --tags development"
  THEN: Entry is created in DB
  AND: 3 entries in entry_commits
  AND: CLI outputs confirmation with total for today

SCENARIO: Manual registration from any directory
  GIVEN: Known project "jpro-internal"
  WHEN: Running "timereg register --project jpro-internal --hours 1.0
        --short-summary 'Standup'" from /tmp
  THEN: Manual entry is created

SCENARIO: Registration with peer
  GIVEN: Known project "ekvarda"
  WHEN: Running "timereg register --project ekvarda --hours 3.0
        --short-summary 'Pair programming'
        --peer colleague@jpro.no"
  THEN: Two entries exist with matching peer_group_id
```

### `test_cli_edit_delete.py`

```
SCENARIO: Edit entry hours
  GIVEN: Entry #42 with hours=4.5
  WHEN: Running "timereg edit 42 --hours 3.0"
  THEN: Entry #42 now has hours=3.0

SCENARIO: Delete with commit release
  GIVEN: Entry #42 with 2 commits
  WHEN: Running "timereg delete 42" and selecting "release commits"
  THEN: Entry deleted, commits appear in next fetch

SCENARIO: Delete keeping commits
  GIVEN: Entry #42 with 2 commits
  WHEN: Running "timereg delete 42" and selecting "keep claimed"
  THEN: Entry deleted, commits do NOT appear in next fetch

SCENARIO: Undo last entry
  GIVEN: Last entry is #43 (2h30m, 1 commit)
  WHEN: Running "timereg undo"
  THEN: Entry #43 is deleted, commit released
  AND: Output shows what was undone
```

### `test_peer_registration.py`

```
SCENARIO: Peer entries share same data
  GIVEN: Registration with --peer colleague@jpro.no
  WHEN: Fetching both entries
  THEN: Identical hours, summaries, tags, and commit associations
  AND: Different git_user_email values
  AND: Same peer_group_id

SCENARIO: Edit peer entry propagates when confirmed
  GIVEN: Peer-linked entries #42 and #43
  WHEN: Editing #42 --hours 4.0 with apply_to_peer=True
  THEN: Both entries have hours=4.0

SCENARIO: Delete peer entry with cascade
  GIVEN: Peer-linked entries #42 and #43
  WHEN: Deleting #42 with delete_peer=True
  THEN: Both entries are deleted

SCENARIO: Multiple peers (group session)
  GIVEN: Registration with --peer a@jpro.no --peer b@jpro.no
  WHEN: Checking entries
  THEN: 3 entries exist (self + 2 peers) with same peer_group_id
```

### `test_multi_repo.py`

```
SCENARIO: Fetch commits across multiple repos
  GIVEN: Project with 3 repos, commits in 2 of them today
  WHEN: Fetching
  THEN: Results contain commits from both repos
  AND: Third repo shows empty commit list (not an error)

SCENARIO: Register with commits from multiple repos
  GIVEN: Commits hash1 (main repo) and hash2 (client repo)
  WHEN: Registering with --commits hash1,hash2
  THEN: entry_commits has both with correct repo_path values

SCENARIO: Non-existent repo path in config
  GIVEN: Config lists "./missing-repo" that doesn't exist
  WHEN: Fetching
  THEN: Warning about missing repo
  AND: Other repos still processed successfully
```

### `test_mcp_server.py`

```
SCENARIO: MCP timereg_fetch returns valid schema
  GIVEN: MCP server running, project with commits
  WHEN: Calling timereg_fetch tool
  THEN: Response matches the JSON output schema

SCENARIO: MCP timereg_register creates entry
  GIVEN: MCP server running
  WHEN: Calling timereg_register with hours, summaries, commits
  THEN: Entry is persisted to DB
  AND: Response contains entry_id

SCENARIO: MCP two-phase workflow
  GIVEN: MCP server running, unregistered commits exist
  WHEN: Call timereg_fetch → get commits → call timereg_register with results
  THEN: Entry is created with all commit associations
  AND: Subsequent timereg_fetch excludes those commits
```

---

## 4. End-to-End Tests

### `test_full_workflow.py`

```
SCENARIO: Complete day workflow
  1. Initialize: create git repo with config file
  2. Make 3 commits with different messages
  3. Run "timereg fetch" → verify 3 commits returned
  4. Run "timereg register" with hours and summaries for 2 commits
  5. Run "timereg fetch" → verify only 1 unregistered commit
  6. Run "timereg register" for remaining commit
  7. Run "timereg fetch" → verify 0 unregistered commits
  8. Run "timereg list" → verify 2 entries totaling correct hours
  9. Run "timereg summary" → verify daily report
  10. Run "timereg status" → verify no unregistered commits

SCENARIO: Multi-day with yesterday backfill
  1. Create repo, make commits dated yesterday and today
  2. Register today's work
  3. Run "timereg fetch --date yesterday" → see yesterday's commits
  4. Register yesterday's work
  5. Run "timereg summary --week" → see both days

SCENARIO: Edit and delete flow
  1. Register 4h entry
  2. Edit to 3h
  3. Verify updated
  4. Delete with commit release
  5. Fetch → commits reappear
  6. Re-register with correct hours

SCENARIO: Peer programming flow
  1. Both developers make commits (different emails)
  2. Register with --peer for colleague
  3. Verify both entries exist
  4. Edit one → propagates to peer
  5. Summary shows both users' time

SCENARIO: Manual + git mixed workflow
  1. Register 2h manual entry for "sprint planning"
  2. Make commits, register 4h git-aware entry
  3. Register 1h manual entry for "code review"
  4. Summary shows all 3 entries (7h total)
  5. Export as CSV → all entries present

SCENARIO: Budget tracking across the week
  1. Configure project with weekly_hours=20
  2. Register entries across Mon-Thu totaling 18h
  3. Status shows 18/20h (90%)
  4. Check shows no warnings
  5. Register 8h on Friday (total now 26h)
  6. Check warns about exceeding budget

SCENARIO: First-run experience
  1. No global config, no database exists
  2. Run "timereg status"
  3. Global config is created with defaults
  4. Database is initialized
  5. Output shows "no projects registered"
  6. Create a .timetracker.toml
  7. Run "timereg fetch" from that directory
  8. Project is auto-registered
```

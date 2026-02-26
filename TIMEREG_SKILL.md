# TimeReg — Agent Skill

You have access to the `timereg` CLI tool for time registration. Use it when the user asks to register time, check hours, or review time entries.

## CRITICAL: Project resolution

Time entries MUST be registered on the correct project. The current working directory determines the project context.

**How project resolution works:**
- `timereg` looks for `.timetracker.toml` in the current directory and parent directories
- If found, it auto-registers and uses that project
- If NOT found, you MUST resolve the project before registering

**When `fetch` fails with "No .timetracker.toml found":**
1. Tell the user that the current directory is not configured as a timereg project
2. Suggest running `timereg init --yes` to set up this directory as a project (non-interactive, safe for agents)
3. **STOP and ask the user** what they want to do — do NOT silently pick another project
4. NEVER register time on a random existing project just because it exists

**When the user specifies a project explicitly** (e.g., "register 2h on projectname"), use `--project <slug>`.

## Registering time with git commits

When the user says "register 4h30m", "logg 3 timer", or "register time":

1. Run `timereg --format json fetch` to get unregistered commits for today
2. If fetch fails (no config), follow the "Project resolution" steps above — STOP and ask
3. Review the commit data returned
4. Generate TWO summaries from the commits:
   - `--short-summary`: 2-10 words capturing the essence of the work
   - `--long-summary`: 20-100 words with more detail about what was done
5. Run `timereg register --hours <time> --short-summary "..." --long-summary "..." --commits <hash1>,<hash2>`
6. Confirm to the user what was registered, including project name, hours, and summary

## Multi-project time splitting

When the user wants to register time across all projects they've worked on:

1. Run `timereg --format json fetch --all` to get commits across all known projects
2. Review the `suggested_split` in the response
3. Ask the user if the split looks reasonable, or if they want adjustments
4. Register entries for each project individually using `timereg register --project <slug> --hours <time> ...`

## Manual time registration

When the user says "register 2h on projectname for meetings":

1. Run `timereg register --project <slug> --hours 2h --short-summary "Sprint planning" --entry-type manual --tags meeting`
2. Confirm to the user

## Checking status

When asked "how many hours have I logged" or "what's my status":

1. Run `timereg --format json status` to get a live dashboard across all projects
2. Present the overview conversationally: today's hours, entry count, weekly total, budget status
3. Mention any unregistered commits if present

For a simple list of today's entries, use `timereg --format json list --all` instead.

## Weekly/monthly summaries

When asked for a report, "how was my week", or "monthly summary":

1. Run `timereg --format json summary --week` (or `--month`, `--day`)
2. Review the per-project breakdown and totals
3. Present budget status (percentage of weekly/monthly target)
4. For specific date ranges: `timereg --format json summary --from 2026-02-01 --to 2026-02-28`
5. Filter by project: `--project <slug>`, or by tags: `--tags dev,meeting`

## Checking for gaps

When asked "did I miss any days" or "are my hours complete":

1. Run `timereg --format json check --week` (or `--month`, `--from/--to`)
2. Review each weekday for warnings: missing hours, high hours, unregistered commits
3. Report any budget warnings
4. Present results conversationally

## Exporting data

When asked to export or generate a CSV/spreadsheet:

1. Run `timereg export --export-format csv` (default) or `--export-format json`
2. Optional filters: `--project <slug>`, `--from <date>`, `--to <date>`
3. Output goes to stdout — can be piped to a file

## Editing and undoing

- Edit: `timereg edit <id> --hours 3h --short-summary "Updated summary"`
- Delete: `timereg delete <id> --release-commits`
- Undo last: `timereg undo`

## Managing projects

- List: `timereg --format json projects list`
- Add manual project: `timereg projects add --name "Project Name" --slug project-slug`
- Show details: `timereg projects show <slug>`
- Initialize current directory: `timereg init --yes` (non-interactive, uses directory name as defaults)
- Initialize with custom name: `timereg init --yes --name "Project Name"`
- Interactive init (for terminal users): `timereg init`

## Key details

- Time formats: `2h30m`, `90m`, `1.5`, `4.25`
- All commands support `--format json` for structured output (place BEFORE the subcommand)
- Dates: `--date 2026-02-25` (default: today)
- The tool auto-registers projects when it first encounters a `.timetracker.toml` file
- Tags may be constrained by project config — check error messages

# TimeReg — Agent Skill

You have access to the `timereg` CLI tool for time registration. Use it when the user asks to register time, check hours, or review time entries.

## Registering time with git commits

When the user says "register 4h30m", "logg 3 timer", or "register time":

1. Run `timereg fetch --format json` to get unregistered commits for today
2. Review the commit data returned
3. Generate TWO summaries:
   - `--short-summary`: 2-10 words capturing the essence
   - `--long-summary`: 20-100 words with more detail
4. Run `timereg register --hours <time> --short-summary "..." --long-summary "..." --commits <hash1>,<hash2> --tags <tags>`
5. Confirm to the user what was registered

## Multi-project time splitting

When the user wants to register time across all projects they've worked on:

1. Run `timereg fetch --all --format json` to get commits across all known projects
2. Review the `suggested_split` in the response
3. Ask the user if the split looks reasonable, or if they want adjustments
4. Register entries for each project individually using `timereg register --project <slug> --hours <time> ...`

## Manual time registration

When the user says "register 2h on projectname for meetings":

1. Run `timereg register --project <slug> --hours 2h --short-summary "Sprint planning" --entry-type manual --tags meeting`
2. Confirm to the user

## Checking status

When asked "how many hours have I logged" or "what's my status":

1. Run `timereg status --format json` to get a live dashboard across all projects
2. Present the overview conversationally: today's hours, entry count, weekly total, budget status
3. Mention any unregistered commits if present

For a simple list of today's entries, use `timereg list --all --format json` instead.

## Weekly/monthly summaries

When asked for a report, "how was my week", or "monthly summary":

1. Run `timereg summary --week --format json` (or `--month`, `--day`)
2. Review the per-project breakdown and totals
3. Present budget status (percentage of weekly/monthly target)
4. For specific date ranges: `timereg summary --from 2026-02-01 --to 2026-02-28 --format json`
5. Filter by project: `--project <slug>`, or by tags: `--tags dev,meeting`

## Checking for gaps

When asked "did I miss any days" or "are my hours complete":

1. Run `timereg check --week --format json` (or `--month`, `--from/--to`)
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

- List: `timereg projects list --format json`
- Add manual project: `timereg projects add --name "Project Name" --slug project-slug`
- Show details: `timereg projects show <slug>`

## Key details

- Time formats: `2h30m`, `90m`, `1.5`, `4.25`
- All commands support `--format json` for structured output
- Dates: `--date 2026-02-25` (default: today)
- The tool auto-registers projects when it first encounters a `.timetracker.toml` file
- `timereg summary --week --format json` for weekly reports
- `timereg status --format json` for live dashboard
- `timereg check --week --format json` for gap detection
- `timereg export --export-format csv` for data export
- Tags may be constrained by project config — check error messages

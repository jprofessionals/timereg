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

1. Run `timereg list --all --format json` to see today's entries
2. Present the overview conversationally

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

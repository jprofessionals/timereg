"""Typer CLI application — entry point and global options."""

from __future__ import annotations

import atexit
import os
from pathlib import Path
from typing import Annotated

import typer

from timereg.core.config import (
    ensure_global_config,
    load_global_config,
    resolve_db_path,
)
from timereg.core.database import Database

app = typer.Typer(
    name="timereg",
    help="Git-aware time tracking for developers.",
    invoke_without_command=True,
)


class AppState:
    """Shared state initialized by the global callback."""

    db: Database
    db_path: Path
    verbose: bool = False
    output_format: str = "text"
    rounding_minutes: int = 30


state = AppState()


@app.callback()
def main(
    ctx: typer.Context,
    db_path: Annotated[str | None, typer.Option("--db-path", help="Override database path")] = None,
    config: Annotated[
        str | None, typer.Option("--config", help="Override global config path")
    ] = None,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Verbose output")] = False,
    output_format: Annotated[
        str, typer.Option("--format", help="Output format: json or text")
    ] = "text",
) -> None:
    """TimeReg — Git-aware time tracking for developers."""
    global_config_path = Path(config) if config else ensure_global_config()
    global_config = load_global_config(global_config_path)

    resolved_db_path = resolve_db_path(
        cli_db_path=db_path,
        env_db_path=os.environ.get("TIMEREG_DB_PATH"),
        config_db_path=global_config.db_path,
    )

    state.db = Database(resolved_db_path)
    atexit.register(state.db.close)
    state.db.migrate()
    state.verbose = verbose
    state.output_format = output_format
    state.db_path = resolved_db_path
    state.rounding_minutes = global_config.rounding_minutes

    if ctx.invoked_subcommand is None:
        from timereg.cli.interactive import run_interactive

        run_interactive(state.db)


# Import subcommands so they register on the app
import timereg.cli.check as _check  # noqa: E402, F401
import timereg.cli.delete as _delete  # noqa: E402, F401
import timereg.cli.edit as _edit  # noqa: E402, F401
import timereg.cli.export as _export  # noqa: E402, F401
import timereg.cli.fetch as _fetch  # noqa: E402, F401
import timereg.cli.init as _init  # noqa: E402, F401
import timereg.cli.list_cmd as _list_cmd  # noqa: E402, F401
import timereg.cli.projects as _projects  # noqa: E402, F401
import timereg.cli.register as _register  # noqa: E402, F401
import timereg.cli.skill as _skill  # noqa: E402, F401
import timereg.cli.status as _status  # noqa: E402, F401
import timereg.cli.summary as _summary  # noqa: E402, F401
import timereg.cli.undo as _undo  # noqa: E402, F401

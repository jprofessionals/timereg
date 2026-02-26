"""Typer CLI application — entry point and global options."""

import typer

app = typer.Typer(
    name="timereg",
    help="Git-aware time tracking for developers.",
    no_args_is_help=True,
)


@app.callback()
def main() -> None:
    """Git-aware time tracking for developers."""

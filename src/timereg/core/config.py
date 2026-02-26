"""Configuration resolution — global, project, and merged."""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

import platformdirs

from timereg.core.models import GlobalConfig, ProjectConfig

CONFIG_FILENAME = ".timetracker.toml"


def _get_home_dir() -> Path:
    return Path.home()


def find_project_config(start: Path | None = None) -> Path | None:
    """Walk up from start directory to find .timetracker.toml.

    Stops at the user's home directory. Returns None if not found.
    """
    current = (start or Path.cwd()).resolve()
    home = _get_home_dir().resolve()

    while True:
        candidate = current / CONFIG_FILENAME
        if candidate.is_file():
            return candidate
        if current == home or current == current.parent:
            return None
        current = current.parent


def load_project_config(config_path: Path) -> ProjectConfig:
    """Parse a .timetracker.toml file into a ProjectConfig."""
    with open(config_path, "rb") as f:
        data = tomllib.load(f)

    project = data.get("project", {})
    repos = data.get("repos", {})
    tags = data.get("tags", {})
    budget = data.get("budget", {})

    return ProjectConfig(
        name=project["name"],
        slug=project["slug"],
        repo_paths=repos.get("paths", ["."]),
        allowed_tags=tags.get("allowed"),
        weekly_budget_hours=budget.get("weekly_hours"),
        monthly_budget_hours=budget.get("monthly_hours"),
    )


def load_global_config(config_path: Path) -> GlobalConfig:
    """Load global config.toml, returning defaults if file doesn't exist."""
    if not config_path.is_file():
        return GlobalConfig()

    with open(config_path, "rb") as f:
        data = tomllib.load(f)

    database = data.get("database", {})
    defaults = data.get("defaults", {})
    user = data.get("user", {})

    return GlobalConfig(
        db_path=database.get("path"),
        merge_commits=defaults.get("merge_commits", False),
        timezone=defaults.get("timezone", "Europe/Oslo"),
        user_name=user.get("name"),
        user_email=user.get("email"),
    )


def get_global_config_path() -> Path:
    """Get the platform-appropriate global config path."""
    return Path(platformdirs.user_config_dir("timereg")) / "config.toml"


def ensure_global_config() -> Path:
    """Create default global config if it doesn't exist. Returns the path."""
    config_path = get_global_config_path()
    if not config_path.exists():
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(
            "[database]\n"
            '# path = "~/.local/share/timereg/timereg.db"\n'
            "\n"
            "[defaults]\n"
            "merge_commits = false\n"
            'timezone = "Europe/Oslo"\n'
            "\n"
            "[user]\n"
            '# name = "Your Name"\n'
            '# email = "you@example.com"\n'
        )
    return config_path


def resolve_db_path(
    cli_db_path: str | None = None,
    env_db_path: str | None = None,
    config_db_path: str | None = None,
) -> Path:
    """Resolve database path by precedence: CLI > env > config > default."""
    if cli_db_path:
        return Path(cli_db_path)
    if env_db_path:
        return Path(env_db_path)
    if config_db_path:
        return Path(config_db_path)
    return Path(platformdirs.user_data_dir("timereg")) / "timereg.db"


def require_project_config(start: Path | None = None) -> tuple[Path, ProjectConfig]:
    """Find and load project config, or exit with a warning."""
    config_path = find_project_config(start)
    if config_path is None:
        print(
            "Error: No .timetracker.toml found in current or parent directories.\n"
            "Create a .timetracker.toml in your project root, or use --project to specify one.",
            file=sys.stderr,
        )
        raise SystemExit(1)
    return config_path, load_project_config(config_path)

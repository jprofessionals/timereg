"""Tests for configuration resolution."""

from pathlib import Path
from unittest.mock import patch

from timereg.core.config import (
    find_project_config,
    load_global_config,
    load_project_config,
    resolve_db_path,
)


class TestFindProjectConfig:
    def test_finds_config_in_current_dir(self, tmp_path: Path) -> None:
        config_file = tmp_path / ".timetracker.toml"
        config_file.write_text('[project]\nname = "Test"\nslug = "test"\n')
        result = find_project_config(tmp_path)
        assert result == config_file

    def test_finds_config_in_parent_dir(self, tmp_path: Path) -> None:
        config_file = tmp_path / ".timetracker.toml"
        config_file.write_text('[project]\nname = "Test"\nslug = "test"\n')
        child = tmp_path / "src" / "lib"
        child.mkdir(parents=True)
        result = find_project_config(child)
        assert result == config_file

    def test_stops_at_home_dir(self, tmp_path: Path) -> None:
        child = tmp_path / "projects" / "repo" / "src"
        child.mkdir(parents=True)
        with patch("timereg.core.config._get_home_dir", return_value=tmp_path):
            result = find_project_config(child)
        assert result is None

    def test_returns_none_when_not_found(self, tmp_path: Path) -> None:
        with patch("timereg.core.config._get_home_dir", return_value=tmp_path):
            result = find_project_config(tmp_path)
        assert result is None


class TestLoadProjectConfig:
    def test_load_full_config(self) -> None:
        config_path = Path(__file__).parent.parent / "fixtures" / "sample_config.toml"
        cfg = load_project_config(config_path)
        assert cfg.name == "Ekvarda Codex"
        assert cfg.slug == "ekvarda"
        assert cfg.repo_paths == [".", "./client", "../infra"]
        assert cfg.allowed_tags == ["development", "review", "meeting"]
        assert cfg.weekly_budget_hours == 20.0

    def test_load_minimal_config(self, tmp_path: Path) -> None:
        config_file = tmp_path / ".timetracker.toml"
        config_file.write_text('[project]\nname = "Minimal"\nslug = "minimal"\n')
        cfg = load_project_config(config_file)
        assert cfg.name == "Minimal"
        assert cfg.repo_paths == ["."]
        assert cfg.allowed_tags is None
        assert cfg.weekly_budget_hours is None

    def test_resolve_repo_paths(self, tmp_path: Path) -> None:
        config_file = tmp_path / "project" / ".timetracker.toml"
        config_file.parent.mkdir()
        config_file.write_text(
            '[project]\nname = "Test"\nslug = "test"\n\n'
            '[repos]\npaths = [".", "./client", "../infra"]\n'
        )
        cfg = load_project_config(config_file)
        resolved = cfg.resolve_repo_paths(config_file.parent)
        assert resolved[0] == config_file.parent
        assert resolved[1] == config_file.parent / "client"
        assert resolved[2] == config_file.parent.parent / "infra"


class TestLoadGlobalConfig:
    def test_load_full_global_config(self) -> None:
        config_path = Path(__file__).parent.parent / "fixtures" / "sample_global_config.toml"
        cfg = load_global_config(config_path)
        assert cfg.db_path == "/custom/path/timereg.db"
        assert cfg.timezone == "Europe/Oslo"
        assert cfg.user_name == "Mr Bell"
        assert cfg.user_email == "bell@jpro.no"

    def test_load_missing_config_returns_defaults(self, tmp_path: Path) -> None:
        cfg = load_global_config(tmp_path / "nonexistent.toml")
        assert cfg.db_path is None
        assert cfg.merge_commits is False
        assert cfg.timezone == "Europe/Oslo"


class TestResolveDbPath:
    def test_cli_flag_takes_precedence(self) -> None:
        result = resolve_db_path(
            cli_db_path="/cli/path.db",
            env_db_path="/env/path.db",
            config_db_path="/config/path.db",
        )
        assert result == Path("/cli/path.db")

    def test_env_var_second_precedence(self) -> None:
        result = resolve_db_path(
            cli_db_path=None,
            env_db_path="/env/path.db",
            config_db_path="/config/path.db",
        )
        assert result == Path("/env/path.db")

    def test_config_third_precedence(self) -> None:
        result = resolve_db_path(
            cli_db_path=None,
            env_db_path=None,
            config_db_path="/config/path.db",
        )
        assert result == Path("/config/path.db")

    def test_default_when_nothing_set(self) -> None:
        result = resolve_db_path(cli_db_path=None, env_db_path=None, config_db_path=None)
        assert "timereg" in str(result)
        assert result.name == "timereg.db"

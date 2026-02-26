"""Integration tests for timereg list command."""

from __future__ import annotations

import json
from datetime import date
from typing import TYPE_CHECKING

from typer.testing import CliRunner

from timereg.cli.app import app

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

runner = CliRunner()


def _register_entry(
    db_path: str,
    hours: str = "2",
    short_summary: str = "Test entry",
    date_str: str | None = None,
    env: dict[str, str] | None = None,
) -> dict:
    """Helper: register an entry and return the JSON response."""
    today = date_str or date.today().isoformat()
    result = runner.invoke(
        app,
        [
            "--db-path",
            db_path,
            "--format",
            "json",
            "register",
            "--hours",
            hours,
            "--short-summary",
            short_summary,
            "--date",
            today,
        ],
        catch_exceptions=False,
        env=env,
    )
    assert result.exit_code == 0
    return json.loads(result.stdout)


class TestListCommand:
    def test_list_empty(
        self, git_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Listing with no entries shows empty result."""
        config = git_repo / ".timetracker.toml"
        config.write_text('[project]\nname = "Test"\nslug = "test"\n')

        monkeypatch.chdir(git_repo)
        db_path = str(tmp_path / "test.db")

        result = runner.invoke(
            app,
            ["--db-path", db_path, "--format", "json", "list"],
            catch_exceptions=False,
            env={"HOME": str(tmp_path / "fakehome")},
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data == []

    def test_list_shows_registered_entries(
        self, git_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """List entries after registering some."""
        config = git_repo / ".timetracker.toml"
        config.write_text('[project]\nname = "Test"\nslug = "test"\n')

        monkeypatch.chdir(git_repo)
        db_path = str(tmp_path / "test.db")
        env = {"HOME": str(tmp_path / "fakehome")}
        today = date.today().isoformat()

        _register_entry(
            db_path, hours="2h30m", short_summary="Morning work", date_str=today, env=env
        )
        _register_entry(
            db_path, hours="1.5", short_summary="Afternoon work", date_str=today, env=env
        )

        result = runner.invoke(
            app,
            ["--db-path", db_path, "--format", "json", "list", "--date", today],
            catch_exceptions=False,
            env=env,
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert len(data) == 2
        assert data[0]["short_summary"] == "Morning work"
        assert data[1]["short_summary"] == "Afternoon work"

    def test_list_text_output_with_table(
        self, git_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """List entries in text format shows a table."""
        config = git_repo / ".timetracker.toml"
        config.write_text('[project]\nname = "Test"\nslug = "test"\n')

        monkeypatch.chdir(git_repo)
        db_path = str(tmp_path / "test.db")
        env = {"HOME": str(tmp_path / "fakehome")}
        today = date.today().isoformat()

        _register_entry(db_path, hours="3", short_summary="Feature work", date_str=today, env=env)

        result = runner.invoke(
            app,
            ["--db-path", db_path, "list", "--date", today],
            catch_exceptions=False,
            env=env,
        )
        assert result.exit_code == 0
        assert "Feature work" in result.stdout
        assert "3.00" in result.stdout

    def test_list_no_entries_text(
        self, git_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """List with no entries in text mode shows message."""
        config = git_repo / ".timetracker.toml"
        config.write_text('[project]\nname = "Test"\nslug = "test"\n')

        monkeypatch.chdir(git_repo)
        db_path = str(tmp_path / "test.db")

        result = runner.invoke(
            app,
            ["--db-path", db_path, "list"],
            catch_exceptions=False,
            env={"HOME": str(tmp_path / "fakehome")},
        )
        assert result.exit_code == 0
        assert "No entries found" in result.stdout

    def test_list_all_projects(
        self, git_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """List with --all shows entries from all projects."""
        config = git_repo / ".timetracker.toml"
        config.write_text('[project]\nname = "Test"\nslug = "test"\n')

        monkeypatch.chdir(git_repo)
        db_path = str(tmp_path / "test.db")
        env = {"HOME": str(tmp_path / "fakehome")}
        today = date.today().isoformat()

        _register_entry(db_path, hours="2", short_summary="Work A", date_str=today, env=env)

        result = runner.invoke(
            app,
            ["--db-path", db_path, "--format", "json", "list", "--all"],
            catch_exceptions=False,
            env=env,
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert len(data) >= 1

    def test_list_date_range(
        self, git_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """List with --from and --to filters by date range."""
        config = git_repo / ".timetracker.toml"
        config.write_text('[project]\nname = "Test"\nslug = "test"\n')

        monkeypatch.chdir(git_repo)
        db_path = str(tmp_path / "test.db")
        env = {"HOME": str(tmp_path / "fakehome")}

        _register_entry(db_path, hours="1", short_summary="Day 1", date_str="2025-01-15", env=env)
        _register_entry(db_path, hours="2", short_summary="Day 2", date_str="2025-01-16", env=env)
        _register_entry(db_path, hours="3", short_summary="Day 3", date_str="2025-01-17", env=env)

        result = runner.invoke(
            app,
            [
                "--db-path",
                db_path,
                "--format",
                "json",
                "list",
                "--from",
                "2025-01-15",
                "--to",
                "2025-01-16",
                "--all",
            ],
            catch_exceptions=False,
            env=env,
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert len(data) == 2
        summaries = [d["short_summary"] for d in data]
        assert "Day 1" in summaries
        assert "Day 2" in summaries

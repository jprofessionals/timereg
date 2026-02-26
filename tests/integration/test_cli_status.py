"""Integration tests for the status CLI command."""

from __future__ import annotations

import json
from datetime import date
from typing import TYPE_CHECKING

from typer.testing import CliRunner

from timereg.cli.app import app, state
from timereg.core.database import Database
from timereg.core.entries import create_entry

if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()


def _setup(tmp_path: Path) -> Database:
    db = Database(tmp_path / "test.db")
    db.migrate()
    state.db = db
    state.output_format = "text"
    state.db_path = tmp_path / "test.db"
    db.execute(
        "INSERT INTO projects (name, slug, weekly_hours) VALUES (?, ?, ?)",
        ("Test Project", "test", 20.0),
    )
    db.commit()
    return db


def _db_args(tmp_path: Path) -> list[str]:
    """Return global --db-path args (must precede the subcommand)."""
    return ["--db-path", str(tmp_path / "test.db")]


class TestStatusCLI:
    def test_status_with_entries(self, tmp_path: Path) -> None:
        db = _setup(tmp_path)
        create_entry(
            db=db,
            project_id=1,
            hours=4.0,
            short_summary="Work",
            entry_date=date(2026, 2, 25),
            git_user_name="Test",
            git_user_email="test@test.com",
            entry_type="manual",
        )
        result = runner.invoke(
            app,
            [*_db_args(tmp_path), "status", "--date", "2026-02-25"],
        )
        assert result.exit_code == 0
        assert "Test Project" in result.output
        assert "4.0" in result.output or "4.00" in result.output

    def test_status_json(self, tmp_path: Path) -> None:
        db = _setup(tmp_path)
        create_entry(
            db=db,
            project_id=1,
            hours=3.5,
            short_summary="Work",
            entry_date=date(2026, 2, 25),
            git_user_name="Test",
            git_user_email="test@test.com",
            entry_type="manual",
        )
        result = runner.invoke(
            app,
            [*_db_args(tmp_path), "--format", "json", "status", "--date", "2026-02-25"],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "projects" in data
        assert data["projects"][0]["today_hours"] == 3.5

    def test_status_no_entries(self, tmp_path: Path) -> None:
        _setup(tmp_path)
        result = runner.invoke(
            app,
            [*_db_args(tmp_path), "status", "--date", "2026-02-25"],
        )
        assert result.exit_code == 0

    def test_status_no_projects(self, tmp_path: Path) -> None:
        db = Database(tmp_path / "test.db")
        db.migrate()
        state.db = db
        state.output_format = "text"
        state.db_path = tmp_path / "test.db"
        result = runner.invoke(
            app,
            [*_db_args(tmp_path), "status", "--date", "2026-02-25"],
        )
        assert result.exit_code == 0

    def test_status_budget_percent_in_json(self, tmp_path: Path) -> None:
        db = _setup(tmp_path)
        create_entry(
            db=db,
            project_id=1,
            hours=10.0,
            short_summary="Half budget",
            entry_date=date(2026, 2, 25),
            git_user_name="Test",
            git_user_email="test@test.com",
            entry_type="manual",
        )
        result = runner.invoke(
            app,
            [*_db_args(tmp_path), "--format", "json", "status", "--date", "2026-02-25"],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["projects"][0]["budget_percent"] == 50.0

    def test_status_week_hours(self, tmp_path: Path) -> None:
        db = _setup(tmp_path)
        # Add entries across multiple days in the same week
        create_entry(
            db=db,
            project_id=1,
            hours=4.0,
            short_summary="Monday",
            entry_date=date(2026, 2, 23),  # Monday
            git_user_name="Test",
            git_user_email="test@test.com",
            entry_type="manual",
        )
        create_entry(
            db=db,
            project_id=1,
            hours=3.0,
            short_summary="Wednesday",
            entry_date=date(2026, 2, 25),  # Wednesday
            git_user_name="Test",
            git_user_email="test@test.com",
            entry_type="manual",
        )
        result = runner.invoke(
            app,
            [*_db_args(tmp_path), "--format", "json", "status", "--date", "2026-02-25"],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["projects"][0]["week_hours"] == 7.0
        assert data["projects"][0]["today_hours"] == 3.0

    def test_status_warnings_shown(self, tmp_path: Path) -> None:
        _setup(tmp_path)
        result = runner.invoke(
            app,
            [*_db_args(tmp_path), "--format", "json", "status", "--date", "2026-02-25"],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        # No hours registered should generate a warning
        assert len(data["warnings"]) > 0

"""Integration tests for the check CLI command."""

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


class TestCheckCLI:
    def test_check_normal_day(self, tmp_path: Path) -> None:
        db = _setup(tmp_path)
        create_entry(
            db=db,
            project_id=1,
            hours=7.5,
            short_summary="Work",
            entry_date=date(2026, 2, 25),
            git_user_name="Test",
            git_user_email="test@test.com",
            entry_type="manual",
        )
        result = runner.invoke(
            app,
            [*_db_args(tmp_path), "check", "--day", "--date", "2026-02-25"],
        )
        assert result.exit_code == 0

    def test_check_missing_day(self, tmp_path: Path) -> None:
        db = _setup(tmp_path)
        # Register hours on Mon only, check Mon-Wed
        create_entry(
            db=db,
            project_id=1,
            hours=7.5,
            short_summary="Work",
            entry_date=date(2026, 2, 24),
            git_user_name="Test",
            git_user_email="test@test.com",
            entry_type="manual",
        )
        result = runner.invoke(
            app,
            [*_db_args(tmp_path), "check", "--from", "2026-02-24", "--to", "2026-02-26"],
        )
        assert result.exit_code == 0
        # Should show warnings for Tue and Wed
        output_lower = result.output.lower()
        assert "no hours" in output_lower or "warning" in output_lower or "!" in result.output

    def test_check_json(self, tmp_path: Path) -> None:
        db = _setup(tmp_path)
        create_entry(
            db=db,
            project_id=1,
            hours=7.5,
            short_summary="Work",
            entry_date=date(2026, 2, 25),
            git_user_name="Test",
            git_user_email="test@test.com",
            entry_type="manual",
        )
        result = runner.invoke(
            app,
            [
                *_db_args(tmp_path),
                "--format",
                "json",
                "check",
                "--day",
                "--date",
                "2026-02-25",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "days" in data
        assert "summary_total" in data

    def test_check_weekly_default(self, tmp_path: Path) -> None:
        _setup(tmp_path)
        result = runner.invoke(
            app,
            [*_db_args(tmp_path), "check", "--date", "2026-02-25"],
        )
        assert result.exit_code == 0

    def test_check_high_hours_warning(self, tmp_path: Path) -> None:
        db = _setup(tmp_path)
        create_entry(
            db=db,
            project_id=1,
            hours=14.0,
            short_summary="Long day",
            entry_date=date(2026, 2, 25),
            git_user_name="Test",
            git_user_email="test@test.com",
            entry_type="manual",
        )
        result = runner.invoke(
            app,
            [*_db_args(tmp_path), "check", "--day", "--date", "2026-02-25"],
        )
        assert result.exit_code == 0
        assert "!" in result.output or "high" in result.output.lower()

    def test_check_budget_over(self, tmp_path: Path) -> None:
        db = _setup(tmp_path)
        # 25h against 20h weekly budget
        create_entry(
            db=db,
            project_id=1,
            hours=25.0,
            short_summary="Over budget",
            entry_date=date(2026, 2, 24),
            git_user_name="Test",
            git_user_email="test@test.com",
            entry_type="manual",
        )
        result = runner.invoke(
            app,
            [*_db_args(tmp_path), "check", "--day", "--date", "2026-02-24"],
        )
        assert result.exit_code == 0
        output_lower = result.output.lower()
        assert "over budget" in output_lower or "125%" in result.output

    def test_check_mutually_exclusive_periods(self, tmp_path: Path) -> None:
        _setup(tmp_path)
        result = runner.invoke(
            app,
            [*_db_args(tmp_path), "check", "--day", "--week"],
        )
        assert result.exit_code != 0

    def test_check_json_budget_warnings(self, tmp_path: Path) -> None:
        db = _setup(tmp_path)
        create_entry(
            db=db,
            project_id=1,
            hours=25.0,
            short_summary="Over budget",
            entry_date=date(2026, 2, 24),
            git_user_name="Test",
            git_user_email="test@test.com",
            entry_type="manual",
        )
        result = runner.invoke(
            app,
            [
                *_db_args(tmp_path),
                "--format",
                "json",
                "check",
                "--day",
                "--date",
                "2026-02-24",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "budget_warnings" in data
        assert len(data["budget_warnings"]) > 0

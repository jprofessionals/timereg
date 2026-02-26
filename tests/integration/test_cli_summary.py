"""Integration tests for the summary CLI command."""

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


class TestSummaryCLI:
    def test_weekly_summary_text(self, tmp_path: Path) -> None:
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
            [*_db_args(tmp_path), "summary", "--week", "--date", "2026-02-25"],
        )
        assert result.exit_code == 0
        assert "Test Project" in result.output
        assert "4.0" in result.output or "4.00" in result.output

    def test_weekly_summary_json(self, tmp_path: Path) -> None:
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
            [
                *_db_args(tmp_path),
                "--format",
                "json",
                "summary",
                "--week",
                "--date",
                "2026-02-25",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["total_hours"] == 4.0

    def test_summary_no_entries(self, tmp_path: Path) -> None:
        _setup(tmp_path)
        result = runner.invoke(
            app,
            [*_db_args(tmp_path), "summary", "--week", "--date", "2026-02-25"],
        )
        assert result.exit_code == 0

    def test_monthly_summary(self, tmp_path: Path) -> None:
        db = _setup(tmp_path)
        create_entry(
            db=db,
            project_id=1,
            hours=3.0,
            short_summary="Feb work",
            entry_date=date(2026, 2, 10),
            git_user_name="Test",
            git_user_email="test@test.com",
            entry_type="manual",
        )
        create_entry(
            db=db,
            project_id=1,
            hours=5.0,
            short_summary="More Feb work",
            entry_date=date(2026, 2, 20),
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
                "summary",
                "--month",
                "--date",
                "2026-02-15",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["total_hours"] == 8.0

    def test_daily_summary(self, tmp_path: Path) -> None:
        db = _setup(tmp_path)
        create_entry(
            db=db,
            project_id=1,
            hours=2.0,
            short_summary="Morning",
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
                "summary",
                "--day",
                "--date",
                "2026-02-25",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["total_hours"] == 2.0

    def test_explicit_date_range(self, tmp_path: Path) -> None:
        db = _setup(tmp_path)
        create_entry(
            db=db,
            project_id=1,
            hours=1.0,
            short_summary="Day 1",
            entry_date=date(2026, 2, 10),
            git_user_name="Test",
            git_user_email="test@test.com",
            entry_type="manual",
        )
        create_entry(
            db=db,
            project_id=1,
            hours=2.0,
            short_summary="Day 2",
            entry_date=date(2026, 2, 15),
            git_user_name="Test",
            git_user_email="test@test.com",
            entry_type="manual",
        )
        create_entry(
            db=db,
            project_id=1,
            hours=3.0,
            short_summary="Day 3 outside range",
            entry_date=date(2026, 2, 28),
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
                "summary",
                "--from",
                "2026-02-01",
                "--to",
                "2026-02-20",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["total_hours"] == 3.0

    def test_project_filter(self, tmp_path: Path) -> None:
        db = _setup(tmp_path)
        # Add second project
        db.execute(
            "INSERT INTO projects (name, slug, weekly_hours) VALUES (?, ?, ?)",
            ("Other Project", "other", 10.0),
        )
        db.commit()
        create_entry(
            db=db,
            project_id=1,
            hours=4.0,
            short_summary="Test work",
            entry_date=date(2026, 2, 25),
            git_user_name="Test",
            git_user_email="test@test.com",
            entry_type="manual",
        )
        create_entry(
            db=db,
            project_id=2,
            hours=6.0,
            short_summary="Other work",
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
                "summary",
                "--week",
                "--date",
                "2026-02-25",
                "--project",
                "test",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["total_hours"] == 4.0
        assert len(data["projects"]) == 1

    def test_full_detail_text(self, tmp_path: Path) -> None:
        db = _setup(tmp_path)
        create_entry(
            db=db,
            project_id=1,
            hours=4.0,
            short_summary="Work",
            long_summary="Detailed work description for the day",
            entry_date=date(2026, 2, 25),
            git_user_name="Test",
            git_user_email="test@test.com",
            entry_type="manual",
        )
        result = runner.invoke(
            app,
            [
                *_db_args(tmp_path),
                "summary",
                "--week",
                "--date",
                "2026-02-25",
                "--detail",
                "full",
            ],
        )
        assert result.exit_code == 0
        assert "Test Project" in result.output
        assert "2026-02-25" in result.output

    def test_budget_percentage_shown(self, tmp_path: Path) -> None:
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
            [
                *_db_args(tmp_path),
                "--format",
                "json",
                "summary",
                "--week",
                "--date",
                "2026-02-25",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["projects"][0]["budget_percent"] == 50.0

    def test_invalid_project_slug(self, tmp_path: Path) -> None:
        _setup(tmp_path)
        result = runner.invoke(
            app,
            [
                *_db_args(tmp_path),
                "summary",
                "--week",
                "--project",
                "nonexistent",
            ],
        )
        assert result.exit_code == 1

    def test_tag_filter(self, tmp_path: Path) -> None:
        db = _setup(tmp_path)
        create_entry(
            db=db,
            project_id=1,
            hours=3.0,
            short_summary="Tagged work",
            entry_date=date(2026, 2, 25),
            git_user_name="Test",
            git_user_email="test@test.com",
            entry_type="manual",
            tags=["frontend"],
        )
        create_entry(
            db=db,
            project_id=1,
            hours=5.0,
            short_summary="Other work",
            entry_date=date(2026, 2, 25),
            git_user_name="Test",
            git_user_email="test@test.com",
            entry_type="manual",
            tags=["backend"],
        )
        result = runner.invoke(
            app,
            [
                *_db_args(tmp_path),
                "--format",
                "json",
                "summary",
                "--week",
                "--date",
                "2026-02-25",
                "--tags",
                "frontend",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["total_hours"] == 3.0

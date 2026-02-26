"""Integration tests for the export CLI command."""

import csv
import io
import json
from datetime import date
from pathlib import Path

from typer.testing import CliRunner

from timereg.cli.app import app, state
from timereg.core.database import Database
from timereg.core.entries import create_entry

runner = CliRunner()


def _setup(tmp_path: Path) -> Database:
    db = Database(tmp_path / "test.db")
    db.migrate()
    state.db = db
    state.output_format = "text"
    state.db_path = tmp_path / "test.db"
    db.execute(
        "INSERT INTO projects (name, slug) VALUES (?, ?)",
        ("Test Project", "test"),
    )
    db.commit()
    return db


def _db_args(tmp_path: Path) -> list[str]:
    """Return global --db-path args (must precede the subcommand)."""
    return ["--db-path", str(tmp_path / "test.db")]


class TestExportCLI:
    def test_export_csv_default(self, tmp_path: Path) -> None:
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
            [*_db_args(tmp_path), "export"],
        )
        assert result.exit_code == 0
        reader = csv.reader(io.StringIO(result.output))
        header = next(reader)
        assert "date" in header
        assert "hours" in header
        rows = list(reader)
        assert len(rows) == 1

    def test_export_json(self, tmp_path: Path) -> None:
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
            [*_db_args(tmp_path), "export", "--export-format", "json"],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) == 1

    def test_export_project_filter(self, tmp_path: Path) -> None:
        db = _setup(tmp_path)
        db.execute("INSERT INTO projects (name, slug) VALUES (?, ?)", ("Other", "other"))
        db.commit()
        create_entry(
            db=db,
            project_id=1,
            hours=4.0,
            short_summary="Test",
            entry_date=date(2026, 2, 25),
            git_user_name="Test",
            git_user_email="test@test.com",
            entry_type="manual",
        )
        create_entry(
            db=db,
            project_id=2,
            hours=3.0,
            short_summary="Other",
            entry_date=date(2026, 2, 25),
            git_user_name="Test",
            git_user_email="test@test.com",
            entry_type="manual",
        )
        result = runner.invoke(
            app,
            [*_db_args(tmp_path), "export", "--project", "test"],
        )
        assert result.exit_code == 0
        reader = csv.reader(io.StringIO(result.output))
        next(reader)
        rows = list(reader)
        assert len(rows) == 1

    def test_export_date_range(self, tmp_path: Path) -> None:
        db = _setup(tmp_path)
        create_entry(
            db=db,
            project_id=1,
            hours=2.0,
            short_summary="In",
            entry_date=date(2026, 2, 25),
            git_user_name="Test",
            git_user_email="test@test.com",
            entry_type="manual",
        )
        create_entry(
            db=db,
            project_id=1,
            hours=3.0,
            short_summary="Out",
            entry_date=date(2026, 3, 5),
            git_user_name="Test",
            git_user_email="test@test.com",
            entry_type="manual",
        )
        result = runner.invoke(
            app,
            [*_db_args(tmp_path), "export", "--from", "2026-02-01", "--to", "2026-02-28"],
        )
        assert result.exit_code == 0
        reader = csv.reader(io.StringIO(result.output))
        next(reader)
        rows = list(reader)
        assert len(rows) == 1

    def test_export_empty(self, tmp_path: Path) -> None:
        _setup(tmp_path)
        result = runner.invoke(
            app,
            [*_db_args(tmp_path), "export"],
        )
        assert result.exit_code == 0

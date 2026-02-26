"""Tests for export functionality."""

import csv
import io
import json
from datetime import date

from timereg.core.database import Database
from timereg.core.entries import create_entry
from timereg.core.export import export_entries


def _setup_project(db: Database) -> int:
    db.execute("INSERT INTO projects (name, slug) VALUES (?, ?)", ("Test", "test"))
    db.commit()
    row = db.execute("SELECT id FROM projects WHERE slug='test'").fetchone()
    assert row is not None
    return row[0]


class TestExportCSV:
    def test_csv_header(self, tmp_db: Database) -> None:
        _setup_project(tmp_db)
        output = export_entries(tmp_db, format="csv")
        reader = csv.reader(io.StringIO(output))
        header = next(reader)
        assert "date" in header
        assert "project" in header
        assert "hours" in header
        assert "tags" in header
        assert "commits" in header

    def test_csv_with_entries(self, tmp_db: Database) -> None:
        pid = _setup_project(tmp_db)
        create_entry(
            db=tmp_db,
            project_id=pid,
            hours=4.5,
            short_summary="Test work",
            entry_date=date(2026, 2, 25),
            git_user_name="Test",
            git_user_email="test@test.com",
            entry_type="git",
            tags=["dev", "testing"],
        )
        output = export_entries(tmp_db, format="csv")
        reader = csv.reader(io.StringIO(output))
        header = next(reader)
        rows = list(reader)
        assert len(rows) == 1
        # Tags should be semicolon-separated
        tags_col = header.index("tags")
        assert rows[0][tags_col] == "dev;testing"

    def test_csv_filters_by_project(self, tmp_db: Database) -> None:
        pid = _setup_project(tmp_db)
        tmp_db.execute("INSERT INTO projects (name, slug) VALUES (?, ?)", ("Other", "other"))
        tmp_db.commit()
        create_entry(
            db=tmp_db,
            project_id=pid,
            hours=4.0,
            short_summary="Test",
            entry_date=date(2026, 2, 25),
            git_user_name="Test",
            git_user_email="test@test.com",
            entry_type="manual",
        )
        create_entry(
            db=tmp_db,
            project_id=2,
            hours=3.0,
            short_summary="Other",
            entry_date=date(2026, 2, 25),
            git_user_name="Test",
            git_user_email="test@test.com",
            entry_type="manual",
        )
        output = export_entries(tmp_db, format="csv", project_id=pid)
        reader = csv.reader(io.StringIO(output))
        next(reader)  # skip header
        rows = list(reader)
        assert len(rows) == 1

    def test_csv_filters_by_date_range(self, tmp_db: Database) -> None:
        pid = _setup_project(tmp_db)
        create_entry(
            db=tmp_db,
            project_id=pid,
            hours=2.0,
            short_summary="In range",
            entry_date=date(2026, 2, 25),
            git_user_name="Test",
            git_user_email="test@test.com",
            entry_type="manual",
        )
        create_entry(
            db=tmp_db,
            project_id=pid,
            hours=3.0,
            short_summary="Out of range",
            entry_date=date(2026, 3, 5),
            git_user_name="Test",
            git_user_email="test@test.com",
            entry_type="manual",
        )
        output = export_entries(
            tmp_db,
            format="csv",
            date_from=date(2026, 2, 1),
            date_to=date(2026, 2, 28),
        )
        reader = csv.reader(io.StringIO(output))
        next(reader)
        rows = list(reader)
        assert len(rows) == 1


class TestExportJSON:
    def test_json_output(self, tmp_db: Database) -> None:
        pid = _setup_project(tmp_db)
        create_entry(
            db=tmp_db,
            project_id=pid,
            hours=4.5,
            short_summary="Test",
            entry_date=date(2026, 2, 25),
            git_user_name="Test",
            git_user_email="test@test.com",
            entry_type="manual",
            tags=["dev"],
        )
        output = export_entries(tmp_db, format="json")
        data = json.loads(output)
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["hours"] == 4.5
        assert data[0]["project"] == "Test"

    def test_empty_export(self, tmp_db: Database) -> None:
        _setup_project(tmp_db)
        output = export_entries(tmp_db, format="csv")
        reader = csv.reader(io.StringIO(output))
        header = next(reader)
        rows = list(reader)
        assert len(rows) == 0
        assert len(header) > 0  # header still present

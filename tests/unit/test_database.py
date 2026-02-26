"""Tests for database initialization and migration system."""

import sqlite3
from pathlib import Path

import pytest

from timereg.core.database import Database


class TestDatabaseInit:
    def test_creates_database_file(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        db = Database(db_path)
        db.close()
        assert db_path.exists()

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        db_path = tmp_path / "subdir" / "nested" / "test.db"
        db = Database(db_path)
        db.close()
        assert db_path.exists()

    def test_enables_wal_mode(self, tmp_path: Path) -> None:
        db = Database(tmp_path / "test.db")
        result = db.execute("PRAGMA journal_mode").fetchone()
        assert result is not None
        assert result[0] == "wal"
        db.close()

    def test_enables_foreign_keys(self, tmp_path: Path) -> None:
        db = Database(tmp_path / "test.db")
        result = db.execute("PRAGMA foreign_keys").fetchone()
        assert result is not None
        assert result[0] == 1
        db.close()


class TestMigrations:
    def test_migrate_creates_schema_version_table(self, tmp_path: Path) -> None:
        db = Database(tmp_path / "test.db")
        db.migrate()
        result = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
        ).fetchone()
        assert result is not None
        db.close()

    def test_migrate_creates_all_tables(self, tmp_path: Path) -> None:
        db = Database(tmp_path / "test.db")
        db.migrate()
        tables = {
            row[0]
            for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name != 'sqlite_sequence'"
            ).fetchall()
        }
        expected = {
            "schema_version",
            "projects",
            "project_repos",
            "entries",
            "entry_commits",
            "claimed_commits",
        }
        assert expected == tables
        db.close()

    def test_migrate_records_version(self, tmp_path: Path) -> None:
        db = Database(tmp_path / "test.db")
        db.migrate()
        result = db.execute("SELECT MAX(version) FROM schema_version").fetchone()
        assert result is not None
        assert result[0] == 2
        db.close()

    def test_migrate_is_idempotent(self, tmp_path: Path) -> None:
        db = Database(tmp_path / "test.db")
        db.migrate()
        db.migrate()  # should not raise
        result = db.execute("SELECT COUNT(*) FROM schema_version").fetchone()
        assert result is not None
        assert result[0] == 2
        db.close()

    def test_migrate_applies_pending_only(self, tmp_path: Path) -> None:
        db = Database(tmp_path / "test.db")
        db.migrate()
        version = db.execute("SELECT MAX(version) FROM schema_version").fetchone()
        assert version is not None
        assert version[0] >= 1
        db.close()

    def test_migrate_adds_budget_columns(self, tmp_path: Path) -> None:
        db = Database(tmp_path / "test.db")
        db.migrate()
        # Insert a project and verify budget columns exist and are nullable
        db.execute(
            "INSERT INTO projects (name, slug, weekly_hours, monthly_hours) VALUES (?, ?, ?, ?)",
            ("Test", "test", 20.0, 80.0),
        )
        db.commit()
        row = db.execute(
            "SELECT weekly_hours, monthly_hours FROM projects WHERE slug='test'"
        ).fetchone()
        assert row is not None
        assert row[0] == 20.0
        assert row[1] == 80.0
        db.close()

    def test_migrate_adds_allowed_tags_column(self, tmp_path: Path) -> None:
        db = Database(tmp_path / "test.db")
        db.migrate()
        db.execute(
            "INSERT INTO projects (name, slug, allowed_tags) VALUES (?, ?, ?)",
            ("Test", "test", '["dev","review"]'),
        )
        db.commit()
        row = db.execute("SELECT allowed_tags FROM projects WHERE slug='test'").fetchone()
        assert row is not None
        assert row[0] == '["dev","review"]'
        db.close()


class TestContextManager:
    def test_database_as_context_manager(self, tmp_path: Path) -> None:
        with Database(tmp_path / "test.db") as db:
            db.migrate()
            result = db.execute("SELECT 1").fetchone()
            assert result is not None
            assert result[0] == 1

    def test_context_manager_closes_connection(self, tmp_path: Path) -> None:
        db_instance: Database | None = None
        with Database(tmp_path / "test.db") as db:
            db_instance = db
        assert db_instance is not None
        with pytest.raises(sqlite3.ProgrammingError):
            db_instance.execute("SELECT 1")

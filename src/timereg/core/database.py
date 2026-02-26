"""SQLite database connection and migration system."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


class Database:
    """SQLite database with WAL mode and migration support."""

    def __init__(self, db_path: str | Path) -> None:
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path))
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Cursor:
        return self._conn.execute(sql, params)

    def executemany(self, sql: str, params: list[tuple[Any, ...]]) -> sqlite3.Cursor:
        return self._conn.executemany(sql, params)

    def executescript(self, sql: str) -> None:
        self._conn.executescript(sql)

    def commit(self) -> None:
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> Database:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _get_current_version(self) -> int:
        """Get the current schema version, or 0 if no migrations applied."""
        try:
            result = self.execute("SELECT MAX(version) FROM schema_version").fetchone()
            return result[0] if result and result[0] is not None else 0
        except sqlite3.OperationalError:
            return 0

    def _get_migration_files(self) -> list[tuple[int, str]]:
        """Read migration SQL files from the migrations package directory."""
        migrations: list[tuple[int, str]] = []
        migration_dir = Path(__file__).parent.parent / "migrations"
        for sql_file in sorted(migration_dir.glob("*.sql")):
            version = int(sql_file.name.split("_")[0])
            migrations.append((version, sql_file.read_text()))
        return migrations

    def migrate(self) -> None:
        """Apply pending database migrations."""
        self.execute(
            "CREATE TABLE IF NOT EXISTS schema_version ("
            "    version INTEGER PRIMARY KEY,"
            "    applied_at TEXT NOT NULL DEFAULT (datetime('now'))"
            ")"
        )
        self.commit()

        current_version = self._get_current_version()

        for version, sql in self._get_migration_files():
            if version > current_version:
                self.executescript(sql)
                self.execute("INSERT INTO schema_version (version) VALUES (?)", (version,))
                self.commit()

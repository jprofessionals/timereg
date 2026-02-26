"""Integration tests for timereg register command."""

from __future__ import annotations

import json
from datetime import date
from typing import TYPE_CHECKING

from typer.testing import CliRunner

from tests.conftest import make_commit
from timereg.cli.app import app, state
from timereg.core.database import Database

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

runner = CliRunner()


def _setup(tmp_path: Path) -> Database:
    """Create a migrated database with a test project, wired into CLI state."""
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


class TestRegisterCommand:
    def test_register_manual_entry(
        self, git_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Register a manual entry and verify it appears in the database."""
        config = git_repo / ".timetracker.toml"
        config.write_text('[project]\nname = "Test"\nslug = "test"\n')

        monkeypatch.chdir(git_repo)
        db_path = str(tmp_path / "test.db")
        today = date.today().isoformat()

        result = runner.invoke(
            app,
            [
                "--db-path",
                db_path,
                "--format",
                "json",
                "register",
                "--hours",
                "2h30m",
                "--short-summary",
                "Team standup and planning",
                "--date",
                today,
            ],
            catch_exceptions=False,
            env={"HOME": str(tmp_path / "fakehome")},
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["hours"] == 2.5
        assert data["short_summary"] == "Team standup and planning"
        assert data["entry_type"] == "manual"
        assert data["date"] == today

    def test_register_with_commits(
        self, git_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Register with commits and verify they are tracked."""
        config = git_repo / ".timetracker.toml"
        config.write_text('[project]\nname = "Test"\nslug = "test"\n')

        today = date.today().isoformat()
        commit_hash = make_commit(
            git_repo,
            "feature.py",
            "print('hello')",
            "feat: add feature",
            commit_date=f"{today}T10:00:00+01:00",
        )

        monkeypatch.chdir(git_repo)
        db_path = str(tmp_path / "test.db")

        result = runner.invoke(
            app,
            [
                "--db-path",
                db_path,
                "--format",
                "json",
                "register",
                "--hours",
                "3",
                "--short-summary",
                "Implement feature",
                "--commits",
                commit_hash,
                "--date",
                today,
            ],
            catch_exceptions=False,
            env={"HOME": str(tmp_path / "fakehome")},
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["hours"] == 3.0
        assert data["entry_type"] == "git"

        # Verify commit is tracked by fetching — it should no longer appear
        fetch_result = runner.invoke(
            app,
            ["--db-path", db_path, "--format", "json", "fetch", "--date", today],
            catch_exceptions=False,
            env={"HOME": str(tmp_path / "fakehome")},
        )
        assert fetch_result.exit_code == 0
        fetch_data = json.loads(fetch_result.stdout)
        all_commits = []
        for repo in fetch_data["repos"]:
            all_commits.extend(repo["commits"])
        commit_hashes = [c["hash"] for c in all_commits]
        assert commit_hash not in commit_hashes

    def test_register_with_tags(
        self, git_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Register an entry with tags."""
        config = git_repo / ".timetracker.toml"
        config.write_text('[project]\nname = "Test"\nslug = "test"\n')

        monkeypatch.chdir(git_repo)
        db_path = str(tmp_path / "test.db")
        today = date.today().isoformat()

        result = runner.invoke(
            app,
            [
                "--db-path",
                db_path,
                "--format",
                "json",
                "register",
                "--hours",
                "1h",
                "--short-summary",
                "Code review",
                "--tags",
                "review,code",
                "--date",
                today,
            ],
            catch_exceptions=False,
            env={"HOME": str(tmp_path / "fakehome")},
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["tags"] == ["review", "code"]

    def test_register_text_output(
        self, git_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Register an entry with text output format."""
        config = git_repo / ".timetracker.toml"
        config.write_text('[project]\nname = "Test"\nslug = "test"\n')

        monkeypatch.chdir(git_repo)
        db_path = str(tmp_path / "test.db")
        today = date.today().isoformat()

        result = runner.invoke(
            app,
            [
                "--db-path",
                db_path,
                "register",
                "--hours",
                "4.5",
                "--short-summary",
                "Feature development",
                "--date",
                today,
            ],
            catch_exceptions=False,
            env={"HOME": str(tmp_path / "fakehome")},
        )
        assert result.exit_code == 0
        assert "Registered 4.5h" in result.stdout
        assert "Feature development" in result.stdout

    def test_register_invalid_hours_fails(
        self, git_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Invalid time format should fail."""
        config = git_repo / ".timetracker.toml"
        config.write_text('[project]\nname = "Test"\nslug = "test"\n')

        monkeypatch.chdir(git_repo)
        db_path = str(tmp_path / "test.db")

        result = runner.invoke(
            app,
            [
                "--db-path",
                db_path,
                "register",
                "--hours",
                "abc",
                "--short-summary",
                "test",
            ],
            catch_exceptions=False,
            env={"HOME": str(tmp_path / "fakehome")},
        )
        assert result.exit_code == 1

    def test_register_no_project_fails(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Register without a project config or --project should fail."""
        monkeypatch.chdir(tmp_path)
        db_path = str(tmp_path / "test.db")

        result = runner.invoke(
            app,
            [
                "--db-path",
                db_path,
                "register",
                "--hours",
                "1",
                "--short-summary",
                "test",
            ],
            catch_exceptions=False,
            env={"HOME": str(tmp_path / "fakehome")},
        )
        assert result.exit_code == 1

    def test_register_with_long_summary(
        self, git_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Register an entry with both short and long summary."""
        config = git_repo / ".timetracker.toml"
        config.write_text('[project]\nname = "Test"\nslug = "test"\n')

        monkeypatch.chdir(git_repo)
        db_path = str(tmp_path / "test.db")
        today = date.today().isoformat()

        result = runner.invoke(
            app,
            [
                "--db-path",
                db_path,
                "--format",
                "json",
                "register",
                "--hours",
                "2",
                "--short-summary",
                "API implementation",
                "--long-summary",
                "Implemented REST API endpoints for user management"
                " including CRUD operations and auth middleware.",
                "--date",
                today,
            ],
            catch_exceptions=False,
            env={"HOME": str(tmp_path / "fakehome")},
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["long_summary"].startswith("Implemented REST API")


class TestConstrainedTagsCLI:
    def test_register_rejects_invalid_tag(self, tmp_path: Path) -> None:
        """Register with a tag not in the allowed list should fail."""
        db = _setup(tmp_path)
        db.execute(
            "UPDATE projects SET allowed_tags=? WHERE slug='test'",
            ('["dev", "review"]',),
        )
        db.commit()
        result = runner.invoke(
            app,
            [
                "--db-path",
                str(tmp_path / "test.db"),
                "register",
                "--hours",
                "2h",
                "--short-summary",
                "Test",
                "--project",
                "test",
                "--tags",
                "dev,invalid",
                "--entry-type",
                "manual",
            ],
        )
        assert result.exit_code != 0
        assert "invalid" in result.output.lower()

    def test_register_accepts_valid_tags(self, tmp_path: Path) -> None:
        """Register with tags that are all in the allowed list should succeed."""
        db = _setup(tmp_path)
        db.execute(
            "UPDATE projects SET allowed_tags=? WHERE slug='test'",
            ('["dev", "review"]',),
        )
        db.commit()
        result = runner.invoke(
            app,
            [
                "--db-path",
                str(tmp_path / "test.db"),
                "register",
                "--hours",
                "2h",
                "--short-summary",
                "Test",
                "--project",
                "test",
                "--tags",
                "dev,review",
                "--entry-type",
                "manual",
            ],
        )
        assert result.exit_code == 0

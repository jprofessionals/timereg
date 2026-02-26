"""Integration tests for timereg fetch command."""

from __future__ import annotations

import json
from datetime import date
from typing import TYPE_CHECKING

from typer.testing import CliRunner

from tests.conftest import make_commit
from timereg.cli.app import app

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

runner = CliRunner()


class TestFetchCommand:
    def test_fetch_shows_commits(
        self, git_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        config = git_repo / ".timereg.toml"
        config.write_text('[project]\nname = "Test"\nslug = "test"\n')

        today = date.today().isoformat()
        make_commit(
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
            ["--db-path", db_path, "--format", "json", "fetch", "--date", today],
            catch_exceptions=False,
            env={"HOME": str(tmp_path / "fakehome")},
        )
        assert result.exit_code == 0

    def test_fetch_json_output_is_valid(
        self, git_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        config = git_repo / ".timereg.toml"
        config.write_text('[project]\nname = "Test"\nslug = "test"\n')

        today = date.today().isoformat()
        make_commit(
            git_repo,
            "feature.py",
            "code",
            "feat: something",
            commit_date=f"{today}T10:00:00+01:00",
        )

        monkeypatch.chdir(git_repo)
        db_path = str(tmp_path / "test.db")
        result = runner.invoke(
            app,
            ["--db-path", db_path, "--format", "json", "fetch", "--date", today],
            catch_exceptions=False,
            env={"HOME": str(tmp_path / "fakehome")},
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert "project_name" in data
        assert "repos" in data

    def test_fetch_no_config_exits_with_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        db_path = str(tmp_path / "test.db")
        result = runner.invoke(
            app,
            ["--db-path", db_path, "fetch"],
            catch_exceptions=False,
            env={"HOME": str(tmp_path / "fakehome")},
        )
        assert result.exit_code == 1

    def test_fetch_all_requires_hours(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """fetch --all without --hours should fail."""
        monkeypatch.chdir(tmp_path)
        db_path = str(tmp_path / "test.db")
        result = runner.invoke(
            app,
            ["--db-path", db_path, "fetch", "--all"],
            catch_exceptions=False,
            env={"HOME": str(tmp_path / "fakehome")},
        )
        assert result.exit_code == 1
        assert "--hours is required" in result.output

    def test_hours_without_all_is_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """--hours without --all should fail."""
        monkeypatch.chdir(tmp_path)
        db_path = str(tmp_path / "test.db")
        result = runner.invoke(
            app,
            ["--db-path", db_path, "fetch", "--hours", "8h"],
            catch_exceptions=False,
            env={"HOME": str(tmp_path / "fakehome")},
        )
        assert result.exit_code == 1
        assert "--hours can only be used with --all" in result.output

    def test_fetch_all_json_output(
        self, git_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """fetch --all --hours returns JSON with projects and suggested_split."""
        config = git_repo / ".timereg.toml"
        config.write_text('[project]\nname = "Test"\nslug = "test"\n')

        today = date.today().isoformat()
        make_commit(
            git_repo,
            "f.py",
            "x",
            "feat: work",
            commit_date=f"{today}T10:00:00+01:00",
        )

        # First register the project via a regular fetch
        monkeypatch.chdir(git_repo)
        db_path = str(tmp_path / "test.db")
        env = {"HOME": str(tmp_path / "fakehome")}
        runner.invoke(
            app,
            ["--db-path", db_path, "--format", "json", "fetch", "--date", today],
            catch_exceptions=False,
            env=env,
        )

        # Now fetch --all
        result = runner.invoke(
            app,
            [
                "--db-path",
                db_path,
                "--format",
                "json",
                "fetch",
                "--all",
                "--hours",
                "8h",
                "--date",
                today,
            ],
            catch_exceptions=False,
            env=env,
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert "projects" in data
        assert "suggested_split" in data
        assert data["total_hours"] == 8.0
        assert len(data["suggested_split"]) >= 1
        # The single project should get all 8 hours
        assert data["suggested_split"][0]["suggested_hours"] == 8.0

    def test_fetch_all_no_projects(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """fetch --all with no registered projects should fail."""
        monkeypatch.chdir(tmp_path)
        db_path = str(tmp_path / "test.db")
        result = runner.invoke(
            app,
            ["--db-path", db_path, "fetch", "--all", "--hours", "8h"],
            catch_exceptions=False,
            env={"HOME": str(tmp_path / "fakehome")},
        )
        assert result.exit_code == 1
        assert "No projects registered" in result.output

    def test_fetch_no_config_suggests_init_in_git_repo(
        self, git_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When in a git repo without .timereg.toml, suggest timereg init."""
        monkeypatch.chdir(git_repo)
        db_path = str(tmp_path / "test.db")
        result = runner.invoke(
            app,
            ["--db-path", db_path, "fetch"],
            catch_exceptions=False,
            env={"HOME": str(tmp_path / "fakehome")},
        )
        assert result.exit_code == 1
        assert "timereg init" in result.output

"""Integration tests for timereg projects subcommands."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from typer.testing import CliRunner

from timereg.cli.app import app

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

runner = CliRunner()


class TestProjectsAdd:
    def test_add_project(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Add a project manually."""
        monkeypatch.chdir(tmp_path)
        db_path = str(tmp_path / "test.db")

        result = runner.invoke(
            app,
            [
                "--db-path",
                db_path,
                "--format",
                "json",
                "projects",
                "add",
                "--name",
                "My Project",
                "--slug",
                "my-project",
            ],
            catch_exceptions=False,
            env={"HOME": str(tmp_path / "fakehome")},
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["name"] == "My Project"
        assert data["slug"] == "my-project"
        assert data["id"] is not None

    def test_add_duplicate_fails(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Adding a project with a duplicate slug should fail."""
        monkeypatch.chdir(tmp_path)
        db_path = str(tmp_path / "test.db")
        env = {"HOME": str(tmp_path / "fakehome")}

        runner.invoke(
            app,
            [
                "--db-path",
                db_path,
                "projects",
                "add",
                "--name",
                "First",
                "--slug",
                "my-proj",
            ],
            catch_exceptions=False,
            env=env,
        )

        result = runner.invoke(
            app,
            [
                "--db-path",
                db_path,
                "projects",
                "add",
                "--name",
                "Second",
                "--slug",
                "my-proj",
            ],
            catch_exceptions=False,
            env=env,
        )
        assert result.exit_code == 1

    def test_add_text_output(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Add a project in text format."""
        monkeypatch.chdir(tmp_path)
        db_path = str(tmp_path / "test.db")

        result = runner.invoke(
            app,
            [
                "--db-path",
                db_path,
                "projects",
                "add",
                "--name",
                "Test",
                "--slug",
                "test",
            ],
            catch_exceptions=False,
            env={"HOME": str(tmp_path / "fakehome")},
        )
        assert result.exit_code == 0
        assert "Added project" in result.stdout
        assert "test" in result.stdout


class TestProjectsList:
    def test_list_empty(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Listing with no projects returns empty."""
        monkeypatch.chdir(tmp_path)
        db_path = str(tmp_path / "test.db")

        result = runner.invoke(
            app,
            ["--db-path", db_path, "--format", "json", "projects", "list"],
            catch_exceptions=False,
            env={"HOME": str(tmp_path / "fakehome")},
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data == []

    def test_list_shows_added_projects(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """List shows previously added projects."""
        monkeypatch.chdir(tmp_path)
        db_path = str(tmp_path / "test.db")
        env = {"HOME": str(tmp_path / "fakehome")}

        runner.invoke(
            app,
            ["--db-path", db_path, "projects", "add", "--name", "Alpha", "--slug", "alpha"],
            catch_exceptions=False,
            env=env,
        )
        runner.invoke(
            app,
            ["--db-path", db_path, "projects", "add", "--name", "Beta", "--slug", "beta"],
            catch_exceptions=False,
            env=env,
        )

        result = runner.invoke(
            app,
            ["--db-path", db_path, "--format", "json", "projects", "list"],
            catch_exceptions=False,
            env=env,
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        slugs = [p["slug"] for p in data]
        assert "alpha" in slugs
        assert "beta" in slugs

    def test_list_text_no_projects(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Listing with no projects in text mode shows message."""
        monkeypatch.chdir(tmp_path)
        db_path = str(tmp_path / "test.db")

        result = runner.invoke(
            app,
            ["--db-path", db_path, "projects", "list"],
            catch_exceptions=False,
            env={"HOME": str(tmp_path / "fakehome")},
        )
        assert result.exit_code == 0
        assert "No projects registered" in result.stdout


class TestProjectsShow:
    def test_show_project(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Show details for a project."""
        monkeypatch.chdir(tmp_path)
        db_path = str(tmp_path / "test.db")
        env = {"HOME": str(tmp_path / "fakehome")}

        runner.invoke(
            app,
            ["--db-path", db_path, "projects", "add", "--name", "Show Me", "--slug", "show-me"],
            catch_exceptions=False,
            env=env,
        )

        result = runner.invoke(
            app,
            ["--db-path", db_path, "--format", "json", "projects", "show", "show-me"],
            catch_exceptions=False,
            env=env,
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["name"] == "Show Me"
        assert data["slug"] == "show-me"

    def test_show_nonexistent_fails(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Showing a non-existent project should fail."""
        monkeypatch.chdir(tmp_path)
        db_path = str(tmp_path / "test.db")

        result = runner.invoke(
            app,
            ["--db-path", db_path, "projects", "show", "nope"],
            catch_exceptions=False,
            env={"HOME": str(tmp_path / "fakehome")},
        )
        assert result.exit_code == 1

    def test_show_text_output(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Show project in text mode."""
        monkeypatch.chdir(tmp_path)
        db_path = str(tmp_path / "test.db")
        env = {"HOME": str(tmp_path / "fakehome")}

        runner.invoke(
            app,
            ["--db-path", db_path, "projects", "add", "--name", "My App", "--slug", "my-app"],
            catch_exceptions=False,
            env=env,
        )

        result = runner.invoke(
            app,
            ["--db-path", db_path, "projects", "show", "my-app"],
            catch_exceptions=False,
            env=env,
        )
        assert result.exit_code == 0
        assert "My App" in result.stdout
        assert "my-app" in result.stdout


class TestProjectsRemove:
    def test_remove_project(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Remove a project and verify it is gone."""
        monkeypatch.chdir(tmp_path)
        db_path = str(tmp_path / "test.db")
        env = {"HOME": str(tmp_path / "fakehome")}

        runner.invoke(
            app,
            ["--db-path", db_path, "projects", "add", "--name", "Doomed", "--slug", "doomed"],
            catch_exceptions=False,
            env=env,
        )

        result = runner.invoke(
            app,
            ["--db-path", db_path, "--format", "json", "projects", "remove", "doomed"],
            catch_exceptions=False,
            env=env,
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["removed"] == "doomed"

        # Verify gone
        list_result = runner.invoke(
            app,
            ["--db-path", db_path, "--format", "json", "projects", "list"],
            catch_exceptions=False,
            env=env,
        )
        projects = json.loads(list_result.stdout)
        slugs = [p["slug"] for p in projects]
        assert "doomed" not in slugs

    def test_remove_nonexistent_fails(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Removing a non-existent project should fail."""
        monkeypatch.chdir(tmp_path)
        db_path = str(tmp_path / "test.db")

        result = runner.invoke(
            app,
            ["--db-path", db_path, "projects", "remove", "nope"],
            catch_exceptions=False,
            env={"HOME": str(tmp_path / "fakehome")},
        )
        assert result.exit_code == 1

    def test_remove_text_output(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Remove in text mode shows confirmation."""
        monkeypatch.chdir(tmp_path)
        db_path = str(tmp_path / "test.db")
        env = {"HOME": str(tmp_path / "fakehome")}

        runner.invoke(
            app,
            ["--db-path", db_path, "projects", "add", "--name", "Bye", "--slug", "bye"],
            catch_exceptions=False,
            env=env,
        )

        result = runner.invoke(
            app,
            ["--db-path", db_path, "projects", "remove", "bye"],
            catch_exceptions=False,
            env=env,
        )
        assert result.exit_code == 0
        assert "Removed project" in result.stdout

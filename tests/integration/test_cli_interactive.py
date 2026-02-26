"""Integration tests for timereg interactive mode (no subcommand)."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from typer.testing import CliRunner

from timereg.cli.app import app

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

runner = CliRunner()


class TestInteractiveMode:
    def test_interactive_with_existing_project(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Interactive mode with a pre-created project registers an entry."""
        monkeypatch.chdir(tmp_path)
        db_path = str(tmp_path / "test.db")
        env = {"HOME": str(tmp_path / "fakehome")}
        today = date.today().isoformat()

        # First, create a project so interactive mode can select it
        result = runner.invoke(
            app,
            [
                "--db-path",
                db_path,
                "projects",
                "add",
                "--name",
                "My Project",
                "--slug",
                "my-project",
            ],
            catch_exceptions=False,
            env=env,
        )
        assert result.exit_code == 0

        # Run interactive mode with stdin providing answers:
        # - project number: 1 (single project, auto-selected)
        # - date: <enter> (default today)
        # - hours: 2h30m
        # - description: Worked on feature
        # - tags: <enter> (none)
        # With a single project it is auto-selected, so prompts are:
        # date, hours, description, tags
        interactive_input = f"{today}\n2h30m\nWorked on feature\n\n"

        result = runner.invoke(
            app,
            ["--db-path", db_path],
            input=interactive_input,
            catch_exceptions=False,
            env=env,
        )
        assert result.exit_code == 0
        assert "Registered 2.5h" in result.output
        assert "My Project" in result.output
        assert "Worked on feature" in result.output

        # Verify the entry was actually created by listing
        list_result = runner.invoke(
            app,
            ["--db-path", db_path, "--format", "json", "list", "--all"],
            catch_exceptions=False,
            env=env,
        )
        assert list_result.exit_code == 0
        import json

        entries = json.loads(list_result.stdout)
        assert len(entries) == 1
        assert entries[0]["short_summary"] == "Worked on feature"
        assert entries[0]["hours"] == 2.5

    def test_interactive_create_project_when_none_exist(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Interactive mode prompts to create a project when none exist."""
        monkeypatch.chdir(tmp_path)
        db_path = str(tmp_path / "test.db")
        env = {"HOME": str(tmp_path / "fakehome")}
        today = date.today().isoformat()

        # Prompts: project name, project slug (Enter accepts default "new-project"),
        # date, hours, description, tags
        interactive_input = f"New Project\n\n{today}\n1h\nInitial setup\n\n"

        result = runner.invoke(
            app,
            ["--db-path", db_path],
            input=interactive_input,
            catch_exceptions=False,
            env=env,
        )
        assert result.exit_code == 0
        assert "Created project" in result.output
        assert "Registered 1.0h" in result.output
        assert "Initial setup" in result.output

    def test_interactive_multiple_projects_select(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Interactive mode shows numbered list when multiple projects exist."""
        monkeypatch.chdir(tmp_path)
        db_path = str(tmp_path / "test.db")
        env = {"HOME": str(tmp_path / "fakehome")}
        today = date.today().isoformat()

        # Create two projects
        for name, slug in [("Alpha", "alpha"), ("Beta", "beta")]:
            runner.invoke(
                app,
                ["--db-path", db_path, "projects", "add", "--name", name, "--slug", slug],
                catch_exceptions=False,
                env=env,
            )

        # Prompts: project number, date, hours, description, tags
        interactive_input = f"2\n{today}\n3h\nBeta work\ndev,backend\n"

        result = runner.invoke(
            app,
            ["--db-path", db_path],
            input=interactive_input,
            catch_exceptions=False,
            env=env,
        )
        assert result.exit_code == 0
        assert "Registered 3.0h" in result.output
        assert "Tags: dev, backend" in result.output

    def test_interactive_with_tags(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Interactive mode correctly handles tags."""
        monkeypatch.chdir(tmp_path)
        db_path = str(tmp_path / "test.db")
        env = {"HOME": str(tmp_path / "fakehome")}
        today = date.today().isoformat()

        runner.invoke(
            app,
            ["--db-path", db_path, "projects", "add", "--name", "Tagged", "--slug", "tagged"],
            catch_exceptions=False,
            env=env,
        )

        interactive_input = f"{today}\n45m\nCode review\nreview, pr\n"

        result = runner.invoke(
            app,
            ["--db-path", db_path],
            input=interactive_input,
            catch_exceptions=False,
            env=env,
        )
        assert result.exit_code == 0
        assert "Registered 0.75h" in result.output
        assert "Tags: review, pr" in result.output

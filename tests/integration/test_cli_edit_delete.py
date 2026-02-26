"""Integration tests for timereg edit, delete, and undo commands."""

from __future__ import annotations

import json
from datetime import date
from typing import TYPE_CHECKING

from typer.testing import CliRunner

from timereg.cli.app import app

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

runner = CliRunner()


def _register_entry(
    db_path: str,
    hours: str = "2",
    short_summary: str = "Test entry",
    date_str: str | None = None,
    env: dict[str, str] | None = None,
) -> dict:
    """Helper: register an entry and return the JSON response."""
    today = date_str or date.today().isoformat()
    result = runner.invoke(
        app,
        [
            "--db-path",
            db_path,
            "--format",
            "json",
            "register",
            "--hours",
            hours,
            "--short-summary",
            short_summary,
            "--date",
            today,
        ],
        catch_exceptions=False,
        env=env,
    )
    assert result.exit_code == 0
    return json.loads(result.stdout)


class TestEditCommand:
    def test_edit_hours(
        self, git_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Edit the hours of an existing entry."""
        config = git_repo / ".timereg.toml"
        config.write_text('[project]\nname = "Test"\nslug = "test"\n')

        monkeypatch.chdir(git_repo)
        db_path = str(tmp_path / "test.db")
        env = {"HOME": str(tmp_path / "fakehome")}
        today = date.today().isoformat()

        entry = _register_entry(db_path, hours="2", short_summary="Work", date_str=today, env=env)
        entry_id = entry["id"]

        result = runner.invoke(
            app,
            [
                "--db-path",
                db_path,
                "--format",
                "json",
                "edit",
                str(entry_id),
                "--hours",
                "3h30m",
            ],
            catch_exceptions=False,
            env=env,
        )
        assert result.exit_code == 0
        updated = json.loads(result.stdout)
        assert updated["hours"] == 3.5

    def test_edit_summary(
        self, git_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Edit the summary of an existing entry."""
        config = git_repo / ".timereg.toml"
        config.write_text('[project]\nname = "Test"\nslug = "test"\n')

        monkeypatch.chdir(git_repo)
        db_path = str(tmp_path / "test.db")
        env = {"HOME": str(tmp_path / "fakehome")}
        today = date.today().isoformat()

        entry = _register_entry(
            db_path, hours="2", short_summary="Old summary", date_str=today, env=env
        )
        entry_id = entry["id"]

        result = runner.invoke(
            app,
            [
                "--db-path",
                db_path,
                "--format",
                "json",
                "edit",
                str(entry_id),
                "--short-summary",
                "New summary",
            ],
            catch_exceptions=False,
            env=env,
        )
        assert result.exit_code == 0
        updated = json.loads(result.stdout)
        assert updated["short_summary"] == "New summary"

    def test_edit_text_output(
        self, git_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Edit in text mode shows confirmation."""
        config = git_repo / ".timereg.toml"
        config.write_text('[project]\nname = "Test"\nslug = "test"\n')

        monkeypatch.chdir(git_repo)
        db_path = str(tmp_path / "test.db")
        env = {"HOME": str(tmp_path / "fakehome")}
        today = date.today().isoformat()

        entry = _register_entry(db_path, hours="2", short_summary="Work", date_str=today, env=env)
        entry_id = entry["id"]

        result = runner.invoke(
            app,
            [
                "--db-path",
                db_path,
                "edit",
                str(entry_id),
                "--hours",
                "4",
            ],
            catch_exceptions=False,
            env=env,
        )
        assert result.exit_code == 0
        assert f"Updated entry {entry_id}" in result.stdout

    def test_edit_no_fields_fails(
        self, git_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Edit with no fields to update should fail."""
        config = git_repo / ".timereg.toml"
        config.write_text('[project]\nname = "Test"\nslug = "test"\n')

        monkeypatch.chdir(git_repo)
        db_path = str(tmp_path / "test.db")
        env = {"HOME": str(tmp_path / "fakehome")}
        today = date.today().isoformat()

        entry = _register_entry(db_path, hours="2", short_summary="Work", date_str=today, env=env)
        entry_id = entry["id"]

        result = runner.invoke(
            app,
            ["--db-path", db_path, "edit", str(entry_id)],
            catch_exceptions=False,
            env=env,
        )
        assert result.exit_code == 1


class TestDeleteCommand:
    def test_delete_entry(
        self, git_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Delete an entry and verify it is gone."""
        config = git_repo / ".timereg.toml"
        config.write_text('[project]\nname = "Test"\nslug = "test"\n')

        monkeypatch.chdir(git_repo)
        db_path = str(tmp_path / "test.db")
        env = {"HOME": str(tmp_path / "fakehome")}
        today = date.today().isoformat()

        entry = _register_entry(
            db_path, hours="2", short_summary="To delete", date_str=today, env=env
        )
        entry_id = entry["id"]

        # Delete
        result = runner.invoke(
            app,
            ["--db-path", db_path, "--format", "json", "delete", str(entry_id)],
            catch_exceptions=False,
            env=env,
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["deleted"] == [entry_id]

        # Verify gone
        list_result = runner.invoke(
            app,
            ["--db-path", db_path, "--format", "json", "list", "--date", today],
            catch_exceptions=False,
            env=env,
        )
        assert list_result.exit_code == 0
        entries = json.loads(list_result.stdout)
        assert all(e["id"] != entry_id for e in entries)

    def test_delete_nonexistent_fails(
        self, git_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Deleting a non-existent entry should fail."""
        config = git_repo / ".timereg.toml"
        config.write_text('[project]\nname = "Test"\nslug = "test"\n')

        monkeypatch.chdir(git_repo)
        db_path = str(tmp_path / "test.db")

        result = runner.invoke(
            app,
            ["--db-path", db_path, "delete", "9999"],
            catch_exceptions=False,
            env={"HOME": str(tmp_path / "fakehome")},
        )
        assert result.exit_code == 1

    def test_delete_text_output(
        self, git_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Delete in text mode shows confirmation."""
        config = git_repo / ".timereg.toml"
        config.write_text('[project]\nname = "Test"\nslug = "test"\n')

        monkeypatch.chdir(git_repo)
        db_path = str(tmp_path / "test.db")
        env = {"HOME": str(tmp_path / "fakehome")}
        today = date.today().isoformat()

        entry = _register_entry(db_path, hours="1", short_summary="Gone", date_str=today, env=env)
        entry_id = entry["id"]

        result = runner.invoke(
            app,
            ["--db-path", db_path, "delete", str(entry_id)],
            input="y\n",
            catch_exceptions=False,
            env=env,
        )
        assert result.exit_code == 0
        assert "This will delete 1 entry" in result.stdout
        assert "Gone" in result.stdout
        assert f"Deleted 1 entry: {entry_id}" in result.stdout

    def test_delete_aborted_by_user(
        self, git_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Delete aborted when user says no."""
        config = git_repo / ".timereg.toml"
        config.write_text('[project]\nname = "Test"\nslug = "test"\n')

        monkeypatch.chdir(git_repo)
        db_path = str(tmp_path / "test.db")
        env = {"HOME": str(tmp_path / "fakehome")}
        today = date.today().isoformat()

        entry = _register_entry(
            db_path, hours="1", short_summary="Keep me", date_str=today, env=env
        )
        entry_id = entry["id"]

        result = runner.invoke(
            app,
            ["--db-path", db_path, "delete", str(entry_id)],
            input="n\n",
            catch_exceptions=False,
            env=env,
        )
        assert result.exit_code == 0
        assert "Aborted" in result.stdout

        # Verify entry still exists
        list_result = runner.invoke(
            app,
            ["--db-path", db_path, "--format", "json", "list", "--date", today],
            catch_exceptions=False,
            env=env,
        )
        entries = json.loads(list_result.stdout)
        assert any(e["id"] == entry_id for e in entries)

    def test_delete_yes_flag_skips_prompt(
        self, git_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """--yes flag skips the confirmation prompt."""
        config = git_repo / ".timereg.toml"
        config.write_text('[project]\nname = "Test"\nslug = "test"\n')

        monkeypatch.chdir(git_repo)
        db_path = str(tmp_path / "test.db")
        env = {"HOME": str(tmp_path / "fakehome")}
        today = date.today().isoformat()

        entry = _register_entry(db_path, hours="1", short_summary="Bye", date_str=today, env=env)
        entry_id = entry["id"]

        result = runner.invoke(
            app,
            ["--db-path", db_path, "delete", "--yes", str(entry_id)],
            catch_exceptions=False,
            env=env,
        )
        assert result.exit_code == 0
        assert "Are you sure" not in result.stdout
        assert f"Deleted 1 entry: {entry_id}" in result.stdout

    def test_delete_multiple_entries(
        self, git_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Delete multiple entries in a single command."""
        config = git_repo / ".timereg.toml"
        config.write_text('[project]\nname = "Test"\nslug = "test"\n')

        monkeypatch.chdir(git_repo)
        db_path = str(tmp_path / "test.db")
        env = {"HOME": str(tmp_path / "fakehome")}
        today = date.today().isoformat()

        e1 = _register_entry(db_path, hours="1", short_summary="First", date_str=today, env=env)
        e2 = _register_entry(db_path, hours="2", short_summary="Second", date_str=today, env=env)
        e3 = _register_entry(db_path, hours="3", short_summary="Keep", date_str=today, env=env)

        result = runner.invoke(
            app,
            ["--db-path", db_path, "--format", "json", "delete", str(e1["id"]), str(e2["id"])],
            catch_exceptions=False,
            env=env,
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["deleted"] == [e1["id"], e2["id"]]

        # Verify only the third entry remains
        list_result = runner.invoke(
            app,
            ["--db-path", db_path, "--format", "json", "list", "--date", today],
            catch_exceptions=False,
            env=env,
        )
        entries = json.loads(list_result.stdout)
        assert len(entries) == 1
        assert entries[0]["id"] == e3["id"]

    def test_delete_multiple_text_output(
        self, git_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Delete multiple entries shows correct text output."""
        config = git_repo / ".timereg.toml"
        config.write_text('[project]\nname = "Test"\nslug = "test"\n')

        monkeypatch.chdir(git_repo)
        db_path = str(tmp_path / "test.db")
        env = {"HOME": str(tmp_path / "fakehome")}
        today = date.today().isoformat()

        e1 = _register_entry(db_path, hours="1", short_summary="A", date_str=today, env=env)
        e2 = _register_entry(db_path, hours="2", short_summary="B", date_str=today, env=env)

        result = runner.invoke(
            app,
            ["--db-path", db_path, "delete", str(e1["id"]), str(e2["id"])],
            input="y\n",
            catch_exceptions=False,
            env=env,
        )
        assert result.exit_code == 0
        assert "This will delete 2 entries" in result.stdout
        assert "Deleted 2 entries" in result.stdout


class TestUndoCommand:
    def test_undo_last_entry(
        self, git_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Undo removes the most recent entry by the current user."""
        config = git_repo / ".timereg.toml"
        config.write_text('[project]\nname = "Test"\nslug = "test"\n')

        monkeypatch.chdir(git_repo)
        db_path = str(tmp_path / "test.db")
        env = {"HOME": str(tmp_path / "fakehome")}
        today = date.today().isoformat()

        entry = _register_entry(
            db_path, hours="2", short_summary="Undo me", date_str=today, env=env
        )
        entry_id = entry["id"]

        result = runner.invoke(
            app,
            ["--db-path", db_path, "--format", "json", "undo"],
            catch_exceptions=False,
            env=env,
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["undone"]["id"] == entry_id

        # Verify entry is gone
        list_result = runner.invoke(
            app,
            ["--db-path", db_path, "--format", "json", "list", "--date", today],
            catch_exceptions=False,
            env=env,
        )
        entries = json.loads(list_result.stdout)
        assert all(e["id"] != entry_id for e in entries)

    def test_undo_nothing(
        self, git_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Undo with no entries returns nothing."""
        config = git_repo / ".timereg.toml"
        config.write_text('[project]\nname = "Test"\nslug = "test"\n')

        monkeypatch.chdir(git_repo)
        db_path = str(tmp_path / "test.db")

        result = runner.invoke(
            app,
            ["--db-path", db_path, "--format", "json", "undo"],
            catch_exceptions=False,
            env={"HOME": str(tmp_path / "fakehome")},
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["undone"] is None

    def test_undo_text_output(
        self, git_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Undo in text mode shows confirmation."""
        config = git_repo / ".timereg.toml"
        config.write_text('[project]\nname = "Test"\nslug = "test"\n')

        monkeypatch.chdir(git_repo)
        db_path = str(tmp_path / "test.db")
        env = {"HOME": str(tmp_path / "fakehome")}
        today = date.today().isoformat()

        _register_entry(db_path, hours="1", short_summary="Undone", date_str=today, env=env)

        result = runner.invoke(
            app,
            ["--db-path", db_path, "undo"],
            catch_exceptions=False,
            env=env,
        )
        assert result.exit_code == 0
        assert "Undone entry" in result.stdout

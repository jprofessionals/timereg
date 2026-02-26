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
        config = git_repo / ".timetracker.toml"
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
        config = git_repo / ".timetracker.toml"
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

"""Integration tests for timereg skill command."""

from __future__ import annotations

from typing import TYPE_CHECKING

from typer.testing import CliRunner

from timereg.cli.app import app

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

runner = CliRunner()


class TestSkillCommand:
    def test_skill_outputs_content(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """'timereg skill' prints the skill file content."""
        monkeypatch.chdir(tmp_path)
        db_path = str(tmp_path / "test.db")

        result = runner.invoke(
            app,
            ["--db-path", db_path, "skill"],
            catch_exceptions=False,
            env={"HOME": str(tmp_path / "fakehome")},
        )
        assert result.exit_code == 0
        assert "TimeReg" in result.stdout
        assert "timereg" in result.stdout
        assert "## " in result.stdout

    def test_skill_contains_yaml_frontmatter(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Skill file starts with YAML frontmatter."""
        monkeypatch.chdir(tmp_path)
        db_path = str(tmp_path / "test.db")

        result = runner.invoke(
            app,
            ["--db-path", db_path, "skill"],
            catch_exceptions=False,
            env={"HOME": str(tmp_path / "fakehome")},
        )
        assert result.exit_code == 0
        assert result.stdout.startswith("---\n")

    def test_skill_path_flag(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """'timereg skill --path' prints the file path."""
        monkeypatch.chdir(tmp_path)
        db_path = str(tmp_path / "test.db")

        result = runner.invoke(
            app,
            ["--db-path", db_path, "skill", "--path"],
            catch_exceptions=False,
            env={"HOME": str(tmp_path / "fakehome")},
        )
        assert result.exit_code == 0
        assert result.stdout.strip().endswith("SKILL.md")

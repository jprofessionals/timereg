"""Integration tests for timereg init command."""

from __future__ import annotations

from typing import TYPE_CHECKING

from typer.testing import CliRunner

from timereg.cli.app import app
from timereg.core.config import CONFIG_FILENAME

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

runner = CliRunner()


class TestInitCommand:
    def test_creates_config_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """init creates .timereg.toml with prompted values."""
        monkeypatch.chdir(tmp_path)
        env = {"HOME": str(tmp_path / "fakehome")}

        result = runner.invoke(
            app,
            ["--db-path", str(tmp_path / "test.db"), "init"],
            input="My Project\nmy-project\n",
            catch_exceptions=False,
            env=env,
        )
        assert result.exit_code == 0
        assert f"Created {CONFIG_FILENAME}" in result.output

        config_path = tmp_path / CONFIG_FILENAME
        assert config_path.exists()
        content = config_path.read_text()
        assert 'name = "My Project"' in content
        assert 'slug = "my-project"' in content
        assert "[repos]" in content

    def test_defaults_from_directory_name(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """init derives defaults from the current directory name."""
        project_dir = tmp_path / "Cool Project"
        project_dir.mkdir()
        monkeypatch.chdir(project_dir)
        env = {"HOME": str(tmp_path / "fakehome")}

        # Press Enter twice to accept both defaults
        result = runner.invoke(
            app,
            ["--db-path", str(tmp_path / "test.db"), "init"],
            input="\n\n",
            catch_exceptions=False,
            env=env,
        )
        assert result.exit_code == 0

        content = (project_dir / CONFIG_FILENAME).read_text()
        assert 'name = "Cool Project"' in content
        assert 'slug = "cool-project"' in content

    def test_slug_derived_from_custom_name(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When user types a custom name, slug default derives from that name."""
        monkeypatch.chdir(tmp_path)
        env = {"HOME": str(tmp_path / "fakehome")}

        # Type custom name, press Enter for slug default
        result = runner.invoke(
            app,
            ["--db-path", str(tmp_path / "test.db"), "init"],
            input="Ølsalg Prosjekt\n\n",
            catch_exceptions=False,
            env=env,
        )
        assert result.exit_code == 0

        content = (tmp_path / CONFIG_FILENAME).read_text()
        assert 'name = "Ølsalg Prosjekt"' in content
        assert 'slug = "lsalg-prosjekt"' in content

    def test_errors_if_config_exists(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """init refuses to overwrite an existing config file."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / CONFIG_FILENAME).write_text("[project]\n")
        env = {"HOME": str(tmp_path / "fakehome")}

        result = runner.invoke(
            app,
            ["--db-path", str(tmp_path / "test.db"), "init"],
            catch_exceptions=False,
            env=env,
        )
        assert result.exit_code == 1
        assert "already exists" in result.output

    def test_generated_config_has_commented_budget_and_tags(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Generated config includes commented-out budget and tags sections."""
        monkeypatch.chdir(tmp_path)
        env = {"HOME": str(tmp_path / "fakehome")}

        runner.invoke(
            app,
            ["--db-path", str(tmp_path / "test.db"), "init"],
            input="Test\n\n",
            catch_exceptions=False,
            env=env,
        )

        content = (tmp_path / CONFIG_FILENAME).read_text()
        assert "# [budget]" in content
        assert "# weekly_hours" in content
        assert "# [tags]" in content
        assert "# allowed" in content

    def test_yes_flag_skips_prompts(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """--yes creates config without prompting, using directory name as defaults."""
        project_dir = tmp_path / "my-app"
        project_dir.mkdir()
        monkeypatch.chdir(project_dir)
        env = {"HOME": str(tmp_path / "fakehome")}

        result = runner.invoke(
            app,
            ["--db-path", str(tmp_path / "test.db"), "init", "--yes"],
            catch_exceptions=False,
            env=env,
        )
        assert result.exit_code == 0

        content = (project_dir / CONFIG_FILENAME).read_text()
        assert 'name = "my-app"' in content
        assert 'slug = "my-app"' in content

    def test_name_and_slug_flags(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """--name and --slug flags override defaults in non-interactive mode."""
        monkeypatch.chdir(tmp_path)
        env = {"HOME": str(tmp_path / "fakehome")}

        result = runner.invoke(
            app,
            [
                "--db-path",
                str(tmp_path / "test.db"),
                "init",
                "--yes",
                "--name",
                "Cool Project",
                "--slug",
                "cool-proj",
            ],
            catch_exceptions=False,
            env=env,
        )
        assert result.exit_code == 0

        content = (tmp_path / CONFIG_FILENAME).read_text()
        assert 'name = "Cool Project"' in content
        assert 'slug = "cool-proj"' in content

    def test_name_flag_without_slug_derives_slug(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """--name without --slug auto-derives slug from the name."""
        monkeypatch.chdir(tmp_path)
        env = {"HOME": str(tmp_path / "fakehome")}

        result = runner.invoke(
            app,
            [
                "--db-path",
                str(tmp_path / "test.db"),
                "init",
                "--yes",
                "--name",
                "My Great Project",
            ],
            catch_exceptions=False,
            env=env,
        )
        assert result.exit_code == 0

        content = (tmp_path / CONFIG_FILENAME).read_text()
        assert 'name = "My Great Project"' in content
        assert 'slug = "my-great-project"' in content

    def test_flags_used_as_defaults_in_interactive_mode(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """--name flag sets the default in interactive prompts (Enter accepts)."""
        monkeypatch.chdir(tmp_path)
        env = {"HOME": str(tmp_path / "fakehome")}

        # Press Enter twice to accept flag-provided defaults
        result = runner.invoke(
            app,
            [
                "--db-path",
                str(tmp_path / "test.db"),
                "init",
                "--name",
                "Flag Name",
            ],
            input="\n\n",
            catch_exceptions=False,
            env=env,
        )
        assert result.exit_code == 0

        content = (tmp_path / CONFIG_FILENAME).read_text()
        assert 'name = "Flag Name"' in content
        assert 'slug = "flag-name"' in content

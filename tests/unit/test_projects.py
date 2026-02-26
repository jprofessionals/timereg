"""Tests for project registry."""

from pathlib import Path

import pytest

from timereg.core.database import Database
from timereg.core.models import ProjectConfig
from timereg.core.projects import (
    add_project,
    auto_register_project,
    get_project,
    list_projects,
    remove_project,
)


@pytest.fixture()
def db(tmp_path: Path) -> Database:
    d = Database(tmp_path / "test.db")
    d.migrate()
    return d


class TestAutoRegister:
    def test_registers_project_from_config(self, db: Database) -> None:
        config = ProjectConfig(name="Ekvarda Codex", slug="ekvarda")
        config_path = Path("/home/user/projects/ekvarda/.timetracker.toml")
        repo_paths = [Path("/home/user/projects/ekvarda")]
        project = auto_register_project(db, config, config_path, repo_paths)
        assert project.name == "Ekvarda Codex"
        assert project.slug == "ekvarda"
        assert project.id is not None

    def test_upserts_on_duplicate_slug(self, db: Database) -> None:
        config = ProjectConfig(name="Ekvarda Codex", slug="ekvarda")
        config_path = Path("/home/user/ekvarda/.timetracker.toml")
        repo_paths = [Path("/home/user/ekvarda")]
        p1 = auto_register_project(db, config, config_path, repo_paths)
        p2 = auto_register_project(db, config, config_path, repo_paths)
        assert p1.id == p2.id


class TestAddProject:
    def test_add_manual_project(self, db: Database) -> None:
        project = add_project(db, name="JPro Internal", slug="jpro-internal")
        assert project.slug == "jpro-internal"
        assert project.config_path is None

    def test_duplicate_slug_raises(self, db: Database) -> None:
        add_project(db, name="Test", slug="test")
        with pytest.raises(ValueError, match="already exists"):
            add_project(db, name="Test 2", slug="test")


class TestGetProject:
    def test_get_existing_project(self, db: Database) -> None:
        add_project(db, name="Test", slug="test")
        project = get_project(db, "test")
        assert project is not None
        assert project.name == "Test"

    def test_get_nonexistent_returns_none(self, db: Database) -> None:
        assert get_project(db, "nonexistent") is None


class TestListProjects:
    def test_list_empty(self, db: Database) -> None:
        projects = list_projects(db)
        assert projects == []

    def test_list_multiple(self, db: Database) -> None:
        add_project(db, "A", "a")
        add_project(db, "B", "b")
        projects = list_projects(db)
        assert len(projects) == 2


class TestRemoveProject:
    def test_remove_existing(self, db: Database) -> None:
        add_project(db, "Test", "test")
        remove_project(db, "test")
        assert get_project(db, "test") is None

    def test_remove_nonexistent_raises(self, db: Database) -> None:
        with pytest.raises(ValueError, match="not found"):
            remove_project(db, "nonexistent")


class TestAutoRegisterBudgetAndTags:
    def test_syncs_budget_to_db(self, tmp_db: Database, tmp_path: Path) -> None:
        config = ProjectConfig(
            name="Test",
            slug="test-budget",
            weekly_budget_hours=20.0,
            monthly_budget_hours=80.0,
        )
        config_path = tmp_path / ".timetracker.toml"
        config_path.touch()
        project = auto_register_project(tmp_db, config, config_path, [])
        row = tmp_db.execute(
            "SELECT weekly_hours, monthly_hours FROM projects WHERE id=?", (project.id,)
        ).fetchone()
        assert row is not None
        assert row[0] == 20.0
        assert row[1] == 80.0

    def test_syncs_allowed_tags_to_db(self, tmp_db: Database, tmp_path: Path) -> None:
        config = ProjectConfig(
            name="Test",
            slug="test-tags",
            allowed_tags=["dev", "review"],
        )
        config_path = tmp_path / ".timetracker.toml"
        config_path.touch()
        project = auto_register_project(tmp_db, config, config_path, [])
        row = tmp_db.execute(
            "SELECT allowed_tags FROM projects WHERE id=?", (project.id,)
        ).fetchone()
        assert row is not None
        assert row[0] == '["dev", "review"]'

    def test_project_model_has_budget(self, tmp_db: Database, tmp_path: Path) -> None:
        config = ProjectConfig(
            name="Test",
            slug="test-model",
            weekly_budget_hours=15.0,
        )
        config_path = tmp_path / ".timetracker.toml"
        config_path.touch()
        auto_register_project(tmp_db, config, config_path, [])
        fetched = get_project(tmp_db, "test-model")
        assert fetched is not None
        assert fetched.weekly_hours == 15.0

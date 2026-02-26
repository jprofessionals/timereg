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

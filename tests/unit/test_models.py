"""Tests for Pydantic data models."""

from datetime import date

import pytest
from pydantic import ValidationError

from timereg.core.models import (
    CommitInfo,
    Entry,
    GlobalConfig,
    Project,
    ProjectConfig,
    RepoFetchResult,
    WorkingTreeStatus,
)


class TestProject:
    def test_create_project(self) -> None:
        p = Project(id=1, name="Ekvarda Codex", slug="ekvarda")
        assert p.slug == "ekvarda"

    def test_slug_must_be_lowercase_alphanumeric(self) -> None:
        with pytest.raises(ValidationError):
            Project(id=1, name="Test", slug="UPPER CASE")


class TestEntry:
    def test_create_git_entry(self) -> None:
        entry = Entry(
            id=1,
            project_id=1,
            git_user_name="Mr Bell",
            git_user_email="bell@jpro.no",
            date=date(2026, 2, 25),
            hours=4.5,
            short_summary="WebRTC signaling",
            entry_type="git",
        )
        assert entry.hours == 4.5
        assert entry.entry_type == "git"

    def test_entry_type_must_be_valid(self) -> None:
        with pytest.raises(ValidationError):
            Entry(
                id=1,
                project_id=1,
                git_user_name="Mr Bell",
                git_user_email="bell@jpro.no",
                date=date(2026, 2, 25),
                hours=4.5,
                short_summary="Test",
                entry_type="invalid",
            )

    def test_hours_must_be_positive(self) -> None:
        with pytest.raises(ValidationError):
            Entry(
                id=1,
                project_id=1,
                git_user_name="Mr Bell",
                git_user_email="bell@jpro.no",
                date=date(2026, 2, 25),
                hours=0,
                short_summary="Test",
                entry_type="manual",
            )

    def test_tags_round_trip(self) -> None:
        entry = Entry(
            id=1,
            project_id=1,
            git_user_name="Mr Bell",
            git_user_email="bell@jpro.no",
            date=date(2026, 2, 25),
            hours=2.0,
            short_summary="Test",
            entry_type="manual",
            tags=["development", "testing"],
        )
        assert entry.tags == ["development", "testing"]


class TestCommitInfo:
    def test_create_commit_info(self) -> None:
        c = CommitInfo(
            hash="a1b2c3d4e5f6",
            message="feat: add signaling",
            author_name="Mr Bell",
            author_email="bell@jpro.no",
            timestamp="2026-02-25T09:34:12+01:00",
            repo_path=".",
            files_changed=4,
            insertions=87,
            deletions=12,
            files=["src/signaling.py"],
        )
        assert c.files_changed == 4


class TestRepoFetchResult:
    def test_create_fetch_result(self) -> None:
        r = RepoFetchResult(
            relative_path=".",
            absolute_path="/home/user/project",
            branch="main",
            branch_activity=[],
            uncommitted=WorkingTreeStatus(staged_files=0, unstaged_files=0),
            commits=[],
        )
        assert r.branch == "main"


class TestProjectConfig:
    def test_minimal_config(self) -> None:
        cfg = ProjectConfig(name="Test", slug="test")
        assert cfg.repo_paths == ["."]

    def test_full_config(self) -> None:
        cfg = ProjectConfig(
            name="Ekvarda",
            slug="ekvarda",
            repo_paths=[".", "./client"],
            allowed_tags=["development", "meeting"],
            weekly_budget_hours=20.0,
            monthly_budget_hours=80.0,
        )
        assert len(cfg.repo_paths) == 2


class TestGlobalConfig:
    def test_defaults(self) -> None:
        cfg = GlobalConfig()
        assert cfg.merge_commits is False
        assert cfg.timezone == "Europe/Oslo"

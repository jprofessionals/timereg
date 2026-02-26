"""Tests for Pydantic data models."""

from datetime import date

import pytest
from pydantic import ValidationError

from timereg.core.models import (
    CheckReport,
    CommitInfo,
    DayCheck,
    DayDetail,
    Entry,
    GlobalConfig,
    Project,
    ProjectConfig,
    ProjectStatus,
    ProjectSummary,
    RepoFetchResult,
    StatusReport,
    SummaryReport,
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


class TestGlobalConfigMaxDailyHours:
    def test_default_max_daily_hours(self) -> None:
        config = GlobalConfig()
        assert config.max_daily_hours == 12.0

    def test_custom_max_daily_hours(self) -> None:
        config = GlobalConfig(max_daily_hours=10.0)
        assert config.max_daily_hours == 10.0


class TestProjectBudgetFields:
    def test_project_with_budget(self) -> None:
        p = Project(name="Test", slug="test", weekly_hours=20.0, monthly_hours=80.0)
        assert p.weekly_hours == 20.0
        assert p.monthly_hours == 80.0

    def test_project_without_budget(self) -> None:
        p = Project(name="Test", slug="test")
        assert p.weekly_hours is None
        assert p.monthly_hours is None

    def test_project_with_allowed_tags(self) -> None:
        p = Project(name="Test", slug="test", allowed_tags=["dev", "review"])
        assert p.allowed_tags == ["dev", "review"]


class TestSummaryModels:
    def test_day_detail(self) -> None:
        d = DayDetail(date=date(2026, 2, 25), entries=[], total_hours=0.0)
        assert d.total_hours == 0.0

    def test_project_summary(self) -> None:
        p = Project(name="Test", slug="test")
        s = ProjectSummary(project=p, days=[], total_hours=7.5, budget_weekly=20.0)
        assert s.budget_percent is None  # not computed by model

    def test_summary_report(self) -> None:
        r = SummaryReport(
            period_start=date(2026, 2, 24),
            period_end=date(2026, 2, 28),
            period_label="Week 9, 2026 - Feb 24 - Feb 28",
            projects=[],
            total_hours=37.5,
        )
        assert r.total_hours == 37.5


class TestStatusModels:
    def test_project_status(self) -> None:
        p = Project(name="Test", slug="test")
        s = ProjectStatus(
            project=p,
            today_hours=6.5,
            today_entry_count=2,
            unregistered_commits=3,
            week_hours=14.0,
        )
        assert s.unregistered_commits == 3

    def test_status_report(self) -> None:
        r = StatusReport(date=date(2026, 2, 25), projects=[], warnings=[])
        assert r.warnings == []


class TestCheckModels:
    def test_day_check_ok(self) -> None:
        d = DayCheck(
            date=date(2026, 2, 25),
            total_hours=7.5,
            unregistered_commits=0,
            warnings=[],
            ok=True,
        )
        assert d.ok

    def test_day_check_warning(self) -> None:
        d = DayCheck(
            date=date(2026, 2, 25),
            total_hours=0.0,
            unregistered_commits=5,
            warnings=["No hours registered", "5 unregistered commits"],
            ok=False,
        )
        assert not d.ok
        assert len(d.warnings) == 2

    def test_check_report(self) -> None:
        r = CheckReport(
            date_from=date(2026, 2, 24),
            date_to=date(2026, 2, 28),
            days=[],
            budget_warnings=[],
            summary_total=27.0,
        )
        assert r.summary_total == 27.0

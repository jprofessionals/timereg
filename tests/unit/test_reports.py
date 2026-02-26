"""Tests for summary report generation."""

from datetime import date

import pytest

from timereg.core.database import Database
from timereg.core.entries import create_entry
from timereg.core.reports import generate_summary


def _setup_project(
    db: Database, slug: str = "test", name: str = "Test", weekly_hours: float | None = None
) -> int:
    """Insert a project and return its ID."""
    db.execute(
        "INSERT INTO projects (name, slug, weekly_hours) VALUES (?, ?, ?)",
        (name, slug, weekly_hours),
    )
    db.commit()
    row = db.execute("SELECT id FROM projects WHERE slug=?", (slug,)).fetchone()
    assert row is not None
    return row[0]


def _add_entry(
    db: Database,
    project_id: int,
    hours: float,
    entry_date: date,
    short_summary: str = "work",
    tags: list[str] | None = None,
) -> None:
    create_entry(
        db=db,
        project_id=project_id,
        hours=hours,
        short_summary=short_summary,
        entry_date=entry_date,
        git_user_name="Test",
        git_user_email="test@test.com",
        entry_type="manual",
        tags=tags,
    )


class TestGenerateSummary:
    def test_weekly_summary_single_project(self, tmp_db: Database) -> None:
        pid = _setup_project(tmp_db, weekly_hours=20.0)
        _add_entry(tmp_db, pid, 4.0, date(2026, 2, 24))
        _add_entry(tmp_db, pid, 3.5, date(2026, 2, 25))

        report = generate_summary(
            tmp_db,
            period="week",
            reference_date=date(2026, 2, 25),
        )
        assert report.total_hours == 7.5
        assert len(report.projects) == 1
        assert report.projects[0].total_hours == 7.5
        assert report.projects[0].budget_weekly == 20.0

    def test_monthly_summary_multiple_projects(self, tmp_db: Database) -> None:
        pid1 = _setup_project(tmp_db, slug="proj-a", name="Proj A")
        pid2 = _setup_project(tmp_db, slug="proj-b", name="Proj B")
        _add_entry(tmp_db, pid1, 4.0, date(2026, 2, 10))
        _add_entry(tmp_db, pid2, 3.0, date(2026, 2, 15))

        report = generate_summary(
            tmp_db,
            period="month",
            reference_date=date(2026, 2, 15),
        )
        assert report.total_hours == 7.0
        assert len(report.projects) == 2

    def test_explicit_date_range(self, tmp_db: Database) -> None:
        pid = _setup_project(tmp_db)
        _add_entry(tmp_db, pid, 2.0, date(2026, 2, 20))
        _add_entry(tmp_db, pid, 3.0, date(2026, 2, 25))
        _add_entry(tmp_db, pid, 1.0, date(2026, 3, 1))  # outside range

        report = generate_summary(
            tmp_db,
            date_from=date(2026, 2, 20),
            date_to=date(2026, 2, 28),
        )
        assert report.total_hours == 5.0

    def test_filter_by_project(self, tmp_db: Database) -> None:
        pid1 = _setup_project(tmp_db, slug="proj-a", name="Proj A")
        pid2 = _setup_project(tmp_db, slug="proj-b", name="Proj B")
        _add_entry(tmp_db, pid1, 4.0, date(2026, 2, 25))
        _add_entry(tmp_db, pid2, 3.0, date(2026, 2, 25))

        report = generate_summary(
            tmp_db,
            period="day",
            reference_date=date(2026, 2, 25),
            project_id=pid1,
        )
        assert report.total_hours == 4.0
        assert len(report.projects) == 1

    def test_filter_by_tags(self, tmp_db: Database) -> None:
        pid = _setup_project(tmp_db)
        _add_entry(tmp_db, pid, 4.0, date(2026, 2, 25), tags=["dev"])
        _add_entry(tmp_db, pid, 2.0, date(2026, 2, 25), tags=["meeting"])
        _add_entry(tmp_db, pid, 1.0, date(2026, 2, 25), tags=["dev", "meeting"])

        report = generate_summary(
            tmp_db,
            period="day",
            reference_date=date(2026, 2, 25),
            tag_filter=["meeting"],
        )
        # Should include entries that have "meeting" tag: 2.0 + 1.0
        assert report.total_hours == 3.0

    def test_daily_breakdown(self, tmp_db: Database) -> None:
        pid = _setup_project(tmp_db)
        _add_entry(tmp_db, pid, 4.0, date(2026, 2, 24))
        _add_entry(tmp_db, pid, 3.0, date(2026, 2, 24))
        _add_entry(tmp_db, pid, 5.0, date(2026, 2, 25))

        report = generate_summary(
            tmp_db,
            period="week",
            reference_date=date(2026, 2, 25),
        )
        proj = report.projects[0]
        # Only days with entries should appear
        days_with_entries = [d for d in proj.days if d.total_hours > 0]
        assert len(days_with_entries) == 2
        assert days_with_entries[0].total_hours == 7.0  # Feb 24
        assert days_with_entries[1].total_hours == 5.0  # Feb 25

    def test_period_label_week(self, tmp_db: Database) -> None:
        _setup_project(tmp_db)
        report = generate_summary(
            tmp_db,
            period="week",
            reference_date=date(2026, 2, 25),
        )
        assert "Week 9" in report.period_label
        assert "2026" in report.period_label

    def test_budget_percent_computed(self, tmp_db: Database) -> None:
        pid = _setup_project(tmp_db, weekly_hours=20.0)
        _add_entry(tmp_db, pid, 22.5, date(2026, 2, 25))

        report = generate_summary(
            tmp_db,
            period="week",
            reference_date=date(2026, 2, 25),
        )
        proj = report.projects[0]
        assert proj.budget_percent is not None
        assert proj.budget_percent == pytest.approx(112.5)

    def test_empty_period(self, tmp_db: Database) -> None:
        _setup_project(tmp_db)
        report = generate_summary(
            tmp_db,
            period="day",
            reference_date=date(2026, 2, 25),
        )
        assert report.total_hours == 0.0

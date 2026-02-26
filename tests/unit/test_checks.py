"""Tests for status and check functionality."""

from datetime import date

from timereg.core.checks import get_status, run_checks
from timereg.core.database import Database
from timereg.core.entries import create_entry
from timereg.core.models import Project


def _setup_project(
    db: Database, slug: str = "test", name: str = "Test", weekly_hours: float | None = None
) -> tuple[int, Project]:
    db.execute(
        "INSERT INTO projects (name, slug, weekly_hours) VALUES (?, ?, ?)",
        (name, slug, weekly_hours),
    )
    db.commit()
    row = db.execute("SELECT id FROM projects WHERE slug=?", (slug,)).fetchone()
    assert row is not None
    pid = row[0]
    return pid, Project(id=pid, name=name, slug=slug, weekly_hours=weekly_hours)


def _add_entry(db: Database, project_id: int, hours: float, entry_date: date) -> None:
    create_entry(
        db=db,
        project_id=project_id,
        hours=hours,
        short_summary="work",
        entry_date=entry_date,
        git_user_name="Test",
        git_user_email="test@test.com",
        entry_type="manual",
    )


class TestGetStatus:
    def test_status_with_entries(self, tmp_db: Database) -> None:
        pid, project = _setup_project(tmp_db, weekly_hours=20.0)
        _add_entry(tmp_db, pid, 4.0, date(2026, 2, 25))
        _add_entry(tmp_db, pid, 2.5, date(2026, 2, 25))

        status = get_status(
            db=tmp_db,
            projects=[project],
            repo_paths_by_project={},
            user_email="test@test.com",
            target_date=date(2026, 2, 25),
        )
        assert len(status.projects) == 1
        assert status.projects[0].today_hours == 6.5
        assert status.projects[0].today_entry_count == 2

    def test_status_no_entries_generates_warning(self, tmp_db: Database) -> None:
        _pid, project = _setup_project(tmp_db)
        status = get_status(
            db=tmp_db,
            projects=[project],
            repo_paths_by_project={},
            user_email="test@test.com",
            target_date=date(2026, 2, 25),
        )
        assert any("no hours" in w.lower() for w in status.warnings)

    def test_status_weekly_total(self, tmp_db: Database) -> None:
        pid, project = _setup_project(tmp_db, weekly_hours=20.0)
        _add_entry(tmp_db, pid, 4.0, date(2026, 2, 24))  # Mon
        _add_entry(tmp_db, pid, 3.0, date(2026, 2, 25))  # Tue

        status = get_status(
            db=tmp_db,
            projects=[project],
            repo_paths_by_project={},
            user_email="test@test.com",
            target_date=date(2026, 2, 25),
        )
        assert status.projects[0].week_hours == 7.0
        assert status.projects[0].budget_weekly == 20.0


class TestRunChecks:
    def test_check_detects_missing_day(self, tmp_db: Database) -> None:
        pid, project = _setup_project(tmp_db)
        # Register hours on Mon and Wed but not Tue
        _add_entry(tmp_db, pid, 4.0, date(2026, 2, 24))  # Mon
        _add_entry(tmp_db, pid, 5.0, date(2026, 2, 26))  # Wed

        report = run_checks(
            db=tmp_db,
            projects=[project],
            repo_paths_by_project={},
            user_email="test@test.com",
            date_from=date(2026, 2, 24),
            date_to=date(2026, 2, 26),
        )
        tue_check = [d for d in report.days if d.date == date(2026, 2, 25)]
        assert len(tue_check) == 1
        assert not tue_check[0].ok
        assert any("no hours" in w.lower() for w in tue_check[0].warnings)

    def test_check_detects_high_hours(self, tmp_db: Database) -> None:
        pid, project = _setup_project(tmp_db)
        _add_entry(tmp_db, pid, 14.0, date(2026, 2, 25))

        report = run_checks(
            db=tmp_db,
            projects=[project],
            repo_paths_by_project={},
            user_email="test@test.com",
            date_from=date(2026, 2, 25),
            date_to=date(2026, 2, 25),
            max_daily_hours=12.0,
        )
        assert len(report.days) == 1
        assert not report.days[0].ok
        assert any("high" in w.lower() or "seems" in w.lower() for w in report.days[0].warnings)

    def test_check_skips_weekends(self, tmp_db: Database) -> None:
        _pid, project = _setup_project(tmp_db)
        # Feb 28, 2026 is Saturday, Mar 1 is Sunday
        report = run_checks(
            db=tmp_db,
            projects=[project],
            repo_paths_by_project={},
            user_email="test@test.com",
            date_from=date(2026, 2, 28),
            date_to=date(2026, 3, 1),
        )
        assert len(report.days) == 0  # weekend days excluded

    def test_check_normal_day_is_ok(self, tmp_db: Database) -> None:
        pid, project = _setup_project(tmp_db)
        _add_entry(tmp_db, pid, 7.5, date(2026, 2, 25))

        report = run_checks(
            db=tmp_db,
            projects=[project],
            repo_paths_by_project={},
            user_email="test@test.com",
            date_from=date(2026, 2, 25),
            date_to=date(2026, 2, 25),
        )
        assert len(report.days) == 1
        assert report.days[0].ok

    def test_check_budget_warning(self, tmp_db: Database) -> None:
        pid, project = _setup_project(tmp_db, weekly_hours=20.0)
        _add_entry(tmp_db, pid, 12.0, date(2026, 2, 25))

        report = run_checks(
            db=tmp_db,
            projects=[project],
            repo_paths_by_project={},
            user_email="test@test.com",
            date_from=date(2026, 2, 24),
            date_to=date(2026, 2, 28),
        )
        assert report.summary_total == 12.0
        # Budget warning about being under budget
        assert any("test" in w.lower() or "60" in w for w in report.budget_warnings)

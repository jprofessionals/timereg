"""Tests for entry CRUD operations."""

from datetime import date
from pathlib import Path

import pytest

from timereg.core.database import Database
from timereg.core.entries import (
    create_entry,
    delete_entry,
    edit_entry,
    get_registered_commit_hashes,
    list_entries,
    undo_last,
)
from timereg.core.models import CommitInfo
from timereg.core.projects import add_project


@pytest.fixture()
def db(tmp_path: Path) -> Database:
    d = Database(tmp_path / "test.db")
    d.migrate()
    return d


@pytest.fixture()
def project_id(db: Database) -> int:
    p = add_project(db, "Test Project", "test")
    assert p.id is not None
    return p.id


class TestCreateEntry:
    def test_create_git_entry_with_commits(self, db: Database, project_id: int) -> None:
        commits = [
            CommitInfo(
                hash="abc123",
                message="feat: something",
                author_name="User",
                author_email="user@test.com",
                timestamp="2026-02-25T10:00:00+01:00",
                repo_path=".",
                files_changed=2,
                insertions=50,
                deletions=10,
                files=["a.py", "b.py"],
            ),
        ]
        entry = create_entry(
            db=db,
            project_id=project_id,
            hours=4.5,
            short_summary="WebRTC work",
            long_summary="Detailed description",
            entry_date=date(2026, 2, 25),
            git_user_name="User",
            git_user_email="user@test.com",
            commits=commits,
            tags=["development"],
            entry_type="git",
        )
        assert entry.id is not None
        assert entry.hours == 4.5
        assert entry.entry_type == "git"
        hashes = get_registered_commit_hashes(db, project_id)
        assert "abc123" in hashes

    def test_create_manual_entry(self, db: Database, project_id: int) -> None:
        entry = create_entry(
            db=db,
            project_id=project_id,
            hours=2.0,
            short_summary="Sprint planning",
            entry_date=date(2026, 2, 25),
            git_user_name="User",
            git_user_email="user@test.com",
            entry_type="manual",
        )
        assert entry.entry_type == "manual"

    def test_multiple_entries_per_day(self, db: Database, project_id: int) -> None:
        for i in range(3):
            create_entry(
                db=db,
                project_id=project_id,
                hours=2.0,
                short_summary=f"Entry {i}",
                entry_date=date(2026, 2, 25),
                git_user_name="User",
                git_user_email="user@test.com",
                entry_type="manual",
            )
        entries = list_entries(db, project_id=project_id, date_filter=date(2026, 2, 25))
        assert len(entries) == 3

    def test_tags_stored_as_json(self, db: Database, project_id: int) -> None:
        entry = create_entry(
            db=db,
            project_id=project_id,
            hours=1.0,
            short_summary="Test",
            entry_date=date(2026, 2, 25),
            git_user_name="User",
            git_user_email="user@test.com",
            entry_type="manual",
            tags=["dev", "testing"],
        )
        assert entry.tags == ["dev", "testing"]


class TestCreatePeerEntry:
    def test_creates_linked_entries(self, db: Database, project_id: int) -> None:
        entries = create_entry(
            db=db,
            project_id=project_id,
            hours=3.0,
            short_summary="Pair programming",
            entry_date=date(2026, 2, 25),
            git_user_name="User",
            git_user_email="user@test.com",
            entry_type="git",
            peer_emails=["colleague@test.com"],
        )
        assert isinstance(entries, list)
        assert len(entries) == 2
        assert entries[0].peer_group_id is not None
        assert entries[0].peer_group_id == entries[1].peer_group_id
        assert entries[0].git_user_email == "user@test.com"
        assert entries[1].git_user_email == "colleague@test.com"


class TestEditEntry:
    def test_edit_hours(self, db: Database, project_id: int) -> None:
        entry = create_entry(
            db=db,
            project_id=project_id,
            hours=4.5,
            short_summary="Test",
            entry_date=date(2026, 2, 25),
            git_user_name="User",
            git_user_email="user@test.com",
            entry_type="manual",
        )
        assert entry.id is not None
        updated = edit_entry(db, entry.id, hours=3.0)
        assert updated.hours == 3.0

    def test_edit_summary(self, db: Database, project_id: int) -> None:
        entry = create_entry(
            db=db,
            project_id=project_id,
            hours=2.0,
            short_summary="Old",
            entry_date=date(2026, 2, 25),
            git_user_name="User",
            git_user_email="user@test.com",
            entry_type="manual",
        )
        assert entry.id is not None
        updated = edit_entry(db, entry.id, short_summary="New summary")
        assert updated.short_summary == "New summary"


class TestDeleteEntry:
    def test_delete_releases_commits(self, db: Database, project_id: int) -> None:
        commits = [
            CommitInfo(
                hash="abc123",
                message="feat: something",
                author_name="User",
                author_email="user@test.com",
                timestamp="2026-02-25T10:00:00+01:00",
                repo_path=".",
            ),
        ]
        entry = create_entry(
            db=db,
            project_id=project_id,
            hours=4.5,
            short_summary="Test",
            entry_date=date(2026, 2, 25),
            git_user_name="User",
            git_user_email="user@test.com",
            commits=commits,
            entry_type="git",
        )
        assert entry.id is not None
        delete_entry(db, entry.id, release_commits=True)
        hashes = get_registered_commit_hashes(db, project_id)
        assert "abc123" not in hashes

    def test_delete_keeps_commits_claimed(self, db: Database, project_id: int) -> None:
        commits = [
            CommitInfo(
                hash="abc123",
                message="feat: something",
                author_name="User",
                author_email="user@test.com",
                timestamp="2026-02-25T10:00:00+01:00",
                repo_path=".",
            ),
        ]
        entry = create_entry(
            db=db,
            project_id=project_id,
            hours=4.5,
            short_summary="Test",
            entry_date=date(2026, 2, 25),
            git_user_name="User",
            git_user_email="user@test.com",
            commits=commits,
            entry_type="git",
        )
        assert entry.id is not None
        delete_entry(db, entry.id, release_commits=False)
        hashes = get_registered_commit_hashes(db, project_id)
        assert "abc123" in hashes


class TestUndoLast:
    def test_undo_deletes_last_entry(self, db: Database, project_id: int) -> None:
        create_entry(
            db=db,
            project_id=project_id,
            hours=2.0,
            short_summary="First",
            entry_date=date(2026, 2, 25),
            git_user_name="User",
            git_user_email="user@test.com",
            entry_type="manual",
        )
        create_entry(
            db=db,
            project_id=project_id,
            hours=3.0,
            short_summary="Second",
            entry_date=date(2026, 2, 25),
            git_user_name="User",
            git_user_email="user@test.com",
            entry_type="manual",
        )
        undone = undo_last(db, user_email="user@test.com")
        assert undone is not None
        assert undone.short_summary == "Second"
        entries = list_entries(db, project_id=project_id, date_filter=date(2026, 2, 25))
        assert len(entries) == 1

    def test_undo_with_no_entries_returns_none(self, db: Database) -> None:
        assert undo_last(db, user_email="user@test.com") is None


class TestConstrainedTags:
    def test_create_entry_with_valid_tags(self, db: Database, project_id: int) -> None:
        entry = create_entry(
            db=db,
            project_id=project_id,
            hours=2.0,
            short_summary="Test",
            entry_date=date(2026, 2, 25),
            git_user_name="Test",
            git_user_email="test@test.com",
            entry_type="manual",
            tags=["dev", "review"],
            allowed_tags=["dev", "review", "meeting"],
        )
        assert not isinstance(entry, list)
        assert entry.tags == ["dev", "review"]

    def test_create_entry_rejects_invalid_tags(self, db: Database, project_id: int) -> None:
        with pytest.raises(ValueError, match="Invalid tags"):
            create_entry(
                db=db,
                project_id=project_id,
                hours=2.0,
                short_summary="Test",
                entry_date=date(2026, 2, 25),
                git_user_name="Test",
                git_user_email="test@test.com",
                entry_type="manual",
                tags=["dev", "invalid"],
                allowed_tags=["dev", "review", "meeting"],
            )

    def test_create_entry_no_constraint_allows_any(self, db: Database, project_id: int) -> None:
        entry = create_entry(
            db=db,
            project_id=project_id,
            hours=2.0,
            short_summary="Test",
            entry_date=date(2026, 2, 25),
            git_user_name="Test",
            git_user_email="test@test.com",
            entry_type="manual",
            tags=["anything", "goes"],
        )
        assert not isinstance(entry, list)
        assert entry.tags == ["anything", "goes"]

    def test_edit_entry_rejects_invalid_tags(self, db: Database, project_id: int) -> None:
        entry = create_entry(
            db=db,
            project_id=project_id,
            hours=2.0,
            short_summary="Test",
            entry_date=date(2026, 2, 25),
            git_user_name="Test",
            git_user_email="test@test.com",
            entry_type="manual",
        )
        assert not isinstance(entry, list)
        assert entry.id is not None
        with pytest.raises(ValueError, match="Invalid tags"):
            edit_entry(
                db=db,
                entry_id=entry.id,
                tags=["bad-tag"],
                allowed_tags=["dev", "review"],
            )

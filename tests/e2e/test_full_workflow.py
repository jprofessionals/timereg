"""End-to-end test: complete registration workflow.

Covers the full lifecycle from git repo setup through fetch, register,
list, and undo — verifying commit tracking across the entire flow.
"""

from __future__ import annotations

import json
import subprocess
from datetime import date
from typing import TYPE_CHECKING

from typer.testing import CliRunner

from tests.conftest import make_commit
from timereg.cli.app import app

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

runner = CliRunner()


class TestFullRegistrationWorkflow:
    """Complete workflow: init repo -> commits -> fetch -> register -> list -> undo."""

    def test_full_workflow(
        self, git_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """End-to-end test covering the complete time registration lifecycle.

        Steps:
        1. Set up git repo with .timetracker.toml
        2. Make 3 commits
        3. Fetch — verify 3 unregistered commits
        4. Register 2 commits as one entry
        5. Fetch — verify 1 unregistered commit remains
        6. Register the remaining commit
        7. Fetch — verify 0 unregistered commits
        8. List — verify 2 entries with correct total hours
        9. Undo — remove last entry
        10. List — verify 1 entry remains
        """
        # -- Setup --
        config = git_repo / ".timetracker.toml"
        config.write_text('[project]\nname = "Test Project"\nslug = "test-project"\n')

        monkeypatch.chdir(git_repo)
        db_path = str(tmp_path / "test.db")
        env = {"HOME": str(tmp_path / "fakehome")}
        today = date.today().isoformat()

        # Capture the initial commit hash created by the git_repo fixture.
        # It was made today so fetch will include it.
        initial_hash = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=git_repo,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

        # -- Step 2: Make 3 commits --
        hash1 = make_commit(
            git_repo,
            "feature_a.py",
            "def feature_a(): pass\n",
            "feat: add feature A",
            commit_date=f"{today}T09:00:00+01:00",
        )
        hash2 = make_commit(
            git_repo,
            "feature_b.py",
            "def feature_b(): pass\n",
            "feat: add feature B",
            commit_date=f"{today}T10:30:00+01:00",
        )
        hash3 = make_commit(
            git_repo,
            "feature_c.py",
            "def feature_c(): pass\n",
            "fix: bug in feature C",
            commit_date=f"{today}T14:00:00+01:00",
        )

        # -- Step 3: Fetch — all commits should be unregistered --
        # The git_repo fixture creates an initial commit (today), so we
        # expect 4 total: initial + 3 feature commits.
        result = runner.invoke(
            app,
            ["--db-path", db_path, "--format", "json", "fetch", "--date", today],
            catch_exceptions=False,
            env=env,
        )
        assert result.exit_code == 0
        fetch_data = json.loads(result.stdout)
        all_commits = []
        for repo in fetch_data["repos"]:
            all_commits.extend(repo["commits"])
        commit_hashes = [c["hash"] for c in all_commits]
        assert len(commit_hashes) == 4
        assert initial_hash in commit_hashes
        assert hash1 in commit_hashes
        assert hash2 in commit_hashes
        assert hash3 in commit_hashes

        # -- Step 4: Register entry #1 with 3 commits (initial, hash1, hash2) --
        result = runner.invoke(
            app,
            [
                "--db-path",
                db_path,
                "--format",
                "json",
                "register",
                "--hours",
                "3h30m",
                "--short-summary",
                "Feature A and B implementation",
                "--long-summary",
                "Implemented feature A and feature B including initial scaffolding and core logic.",
                "--commits",
                f"{initial_hash},{hash1},{hash2}",
                "--date",
                today,
            ],
            catch_exceptions=False,
            env=env,
        )
        assert result.exit_code == 0
        entry1 = json.loads(result.stdout)
        assert entry1["hours"] == 3.5
        assert entry1["short_summary"] == "Feature A and B implementation"
        assert entry1["entry_type"] == "git"
        entry1_id = entry1["id"]

        # -- Step 5: Fetch again — only 1 unregistered commit should remain --
        result = runner.invoke(
            app,
            ["--db-path", db_path, "--format", "json", "fetch", "--date", today],
            catch_exceptions=False,
            env=env,
        )
        assert result.exit_code == 0
        fetch_data = json.loads(result.stdout)
        remaining_commits = []
        for repo in fetch_data["repos"]:
            remaining_commits.extend(repo["commits"])
        remaining_hashes = [c["hash"] for c in remaining_commits]
        assert len(remaining_hashes) == 1
        assert hash3 in remaining_hashes
        assert hash1 not in remaining_hashes
        assert hash2 not in remaining_hashes
        assert initial_hash not in remaining_hashes

        # -- Step 6: Register entry #2 with the remaining commit --
        result = runner.invoke(
            app,
            [
                "--db-path",
                db_path,
                "--format",
                "json",
                "register",
                "--hours",
                "1h30m",
                "--short-summary",
                "Bug fix in feature C",
                "--commits",
                hash3,
                "--date",
                today,
            ],
            catch_exceptions=False,
            env=env,
        )
        assert result.exit_code == 0
        entry2 = json.loads(result.stdout)
        assert entry2["hours"] == 1.5
        assert entry2["short_summary"] == "Bug fix in feature C"
        entry2_id = entry2["id"]

        # -- Step 7: Fetch again — 0 unregistered commits --
        result = runner.invoke(
            app,
            ["--db-path", db_path, "--format", "json", "fetch", "--date", today],
            catch_exceptions=False,
            env=env,
        )
        assert result.exit_code == 0
        fetch_data = json.loads(result.stdout)
        final_commits = []
        for repo in fetch_data["repos"]:
            final_commits.extend(repo["commits"])
        assert len(final_commits) == 0

        # -- Step 8: List — verify 2 entries with correct total hours --
        result = runner.invoke(
            app,
            ["--db-path", db_path, "--format", "json", "list", "--date", today],
            catch_exceptions=False,
            env=env,
        )
        assert result.exit_code == 0
        entries = json.loads(result.stdout)
        assert len(entries) == 2
        total_hours = sum(e["hours"] for e in entries)
        assert total_hours == 5.0  # 3.5 + 1.5
        summaries = [e["short_summary"] for e in entries]
        assert "Feature A and B implementation" in summaries
        assert "Bug fix in feature C" in summaries

        # -- Step 9: Undo — removes the last entry (entry #2) --
        result = runner.invoke(
            app,
            ["--db-path", db_path, "--format", "json", "undo"],
            catch_exceptions=False,
            env=env,
        )
        assert result.exit_code == 0
        undo_data = json.loads(result.stdout)
        assert undo_data["undone"]["id"] == entry2_id

        # -- Step 10: Verify only 1 entry remains --
        result = runner.invoke(
            app,
            ["--db-path", db_path, "--format", "json", "list", "--date", today],
            catch_exceptions=False,
            env=env,
        )
        assert result.exit_code == 0
        entries = json.loads(result.stdout)
        assert len(entries) == 1
        assert entries[0]["id"] == entry1_id
        assert entries[0]["hours"] == 3.5
        assert entries[0]["short_summary"] == "Feature A and B implementation"

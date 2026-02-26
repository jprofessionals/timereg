"""Tests for git subprocess operations."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from timereg.core.git import (
    fetch_commits,
    fetch_project_commits,
    get_working_tree_status,
    parse_log_output,
    resolve_git_user,
)
from timereg.core.models import FetchResult, GitUser

SAMPLE_LOG_OUTPUT = (
    "a1b2c3d4\x00feat: add signaling\x00Mr Bell\x00bell@jpro.no\x002026-02-25T09:34:12+01:00\n"
    "3\t1\tsrc/signaling.py\n"
    "1\t0\ttests/test_signaling.py\n"
    "\n"
    "b2c3d4e5\x00test: integration tests\x00Mr Bell\x00bell@jpro.no\x002026-02-25T11:02:45+01:00\n"
    "50\t0\ttests/test_integration.py\n"
)


class TestParseLogOutput:
    def test_parse_multiple_commits(self) -> None:
        commits = parse_log_output(SAMPLE_LOG_OUTPUT, repo_path=".")
        assert len(commits) == 2
        assert commits[0].hash == "a1b2c3d4"
        assert commits[0].message == "feat: add signaling"
        assert commits[0].files_changed == 2
        assert commits[0].insertions == 4
        assert commits[0].deletions == 1
        assert commits[0].files == ["src/signaling.py", "tests/test_signaling.py"]
        assert commits[1].hash == "b2c3d4e5"
        assert commits[1].insertions == 50

    def test_parse_empty_output(self) -> None:
        commits = parse_log_output("", repo_path=".")
        assert commits == []

    def test_parse_commit_no_files(self) -> None:
        output = "abc123\x00empty commit\x00User\x00user@test.com\x002026-02-25T10:00:00+01:00\n"
        commits = parse_log_output(output, repo_path=".")
        assert len(commits) == 1
        assert commits[0].files_changed == 0


class TestFetchCommits:
    @patch("timereg.core.git._run_git")
    def test_fetch_returns_commits(self, mock_run: MagicMock) -> None:
        mock_run.return_value = SAMPLE_LOG_OUTPUT
        commits = fetch_commits(
            repo_path="/fake/repo",
            target_date="2026-02-25",
            user_email="bell@jpro.no",
            timezone="Europe/Oslo",
        )
        assert len(commits) == 2

    @patch("timereg.core.git._run_git")
    def test_fetch_filters_registered_hashes(self, mock_run: MagicMock) -> None:
        mock_run.return_value = SAMPLE_LOG_OUTPUT
        commits = fetch_commits(
            repo_path="/fake/repo",
            target_date="2026-02-25",
            user_email="bell@jpro.no",
            timezone="Europe/Oslo",
            registered_hashes={"a1b2c3d4"},
        )
        assert len(commits) == 1
        assert commits[0].hash == "b2c3d4e5"

    @patch("timereg.core.git._run_git")
    def test_fetch_empty_repo(self, mock_run: MagicMock) -> None:
        mock_run.return_value = ""
        commits = fetch_commits(
            repo_path="/fake/repo",
            target_date="2026-02-25",
            user_email="bell@jpro.no",
            timezone="Europe/Oslo",
        )
        assert commits == []


class TestGetWorkingTreeStatus:
    @patch("timereg.core.git._run_git")
    def test_counts_staged_and_unstaged(self, mock_run: MagicMock) -> None:
        def side_effect(args: list[str], cwd: str) -> str:
            if "--cached" in args:
                return "1\t0\tfile1.py\n2\t1\tfile2.py\n"
            return "3\t0\tfile3.py\n"

        mock_run.side_effect = side_effect
        status = get_working_tree_status("/fake/repo")
        assert status.staged_files == 2
        assert status.unstaged_files == 1


class TestResolveGitUser:
    @patch("timereg.core.git._run_git")
    def test_resolve_from_repo(self, mock_run: MagicMock) -> None:
        def side_effect(args: list[str], cwd: str) -> str:
            if "user.name" in args:
                return "Mr Bell\n"
            if "user.email" in args:
                return "bell@jpro.no\n"
            return ""

        mock_run.side_effect = side_effect
        user = resolve_git_user("/fake/repo")
        assert user.name == "Mr Bell"
        assert user.email == "bell@jpro.no"


def _git_side_effect(args: list[str], cwd: str) -> str:
    """Side effect for _run_git that handles log, branch, and diff commands."""
    if "log" in args and "--format" in " ".join(args):
        return SAMPLE_LOG_OUTPUT
    if "rev-parse" in args and "--abbrev-ref" in args:
        return "feat/webrtc\n"
    if "reflog" in args:
        return ""
    if "diff" in args and "--cached" in args:
        return "1\t0\tstaged_file.py\n"
    if "diff" in args:
        return "3\t0\tunstaged1.py\n2\t1\tunstaged2.py\n0\t5\tunstaged3.py\n"
    return ""


class TestFetchProjectCommits:
    @patch("timereg.core.git._run_git")
    def test_returns_fetch_result(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = _git_side_effect
        with patch.object(Path, "is_dir", return_value=True):
            result = fetch_project_commits(
                repo_paths=[Path("/fake/repo")],
                target_date="2026-02-25",
                user_email="bell@jpro.no",
                registered_hashes=set(),
                user=GitUser(name="Mr Bell", email="bell@jpro.no"),
                project_name="Test",
                project_slug="test",
            )
        assert isinstance(result, FetchResult)
        assert result.project_name == "Test"
        assert result.project_slug == "test"
        assert result.date == "2026-02-25"
        assert result.user.name == "Mr Bell"
        assert len(result.repos) == 1
        assert len(result.repos[0].commits) == 2
        assert result.repos[0].branch == "feat/webrtc"
        assert result.repos[0].uncommitted.staged_files == 1
        assert result.repos[0].uncommitted.unstaged_files == 3

    def test_skips_nonexistent_repos(self) -> None:
        result = fetch_project_commits(
            repo_paths=[Path("/nonexistent/repo")],
            target_date="2026-02-25",
            user_email="bell@jpro.no",
            registered_hashes=set(),
            user=GitUser(name="Mr Bell", email="bell@jpro.no"),
            project_name="Test",
            project_slug="test",
        )
        assert isinstance(result, FetchResult)
        assert len(result.repos) == 0

    @patch("timereg.core.git._run_git")
    def test_multiple_repos(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = _git_side_effect
        repo1 = Path("/fake/repo1")
        repo2 = Path("/fake/repo2")
        with patch.object(Path, "is_dir", return_value=True):
            result = fetch_project_commits(
                repo_paths=[repo1, repo2],
                target_date="2026-02-25",
                user_email="bell@jpro.no",
                registered_hashes=set(),
                user=GitUser(name="Mr Bell", email="bell@jpro.no"),
                project_name="Test",
                project_slug="test",
            )
        assert len(result.repos) == 2
        assert result.repos[0].absolute_path == "/fake/repo1"
        assert result.repos[1].absolute_path == "/fake/repo2"

    @patch("timereg.core.git._run_git")
    def test_skips_repos_on_git_error(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = subprocess.CalledProcessError(128, "git")
        with patch.object(Path, "is_dir", return_value=True):
            result = fetch_project_commits(
                repo_paths=[Path("/broken/repo")],
                target_date="2026-02-25",
                user_email="bell@jpro.no",
                registered_hashes=set(),
                user=GitUser(name="Mr Bell", email="bell@jpro.no"),
                project_name="Test",
                project_slug="test",
            )
        assert len(result.repos) == 0

    @patch("timereg.core.git._run_git")
    def test_relative_path_with_config_dir(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = _git_side_effect
        with patch.object(Path, "is_dir", return_value=True):
            result = fetch_project_commits(
                repo_paths=[Path("/project/root/subrepo")],
                target_date="2026-02-25",
                user_email="bell@jpro.no",
                registered_hashes=set(),
                user=GitUser(name="Mr Bell", email="bell@jpro.no"),
                project_name="Test",
                project_slug="test",
                config_dir=Path("/project/root"),
            )
        assert result.repos[0].relative_path == "subrepo"

    @patch("timereg.core.git._run_git")
    def test_filters_registered_hashes(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = _git_side_effect
        with patch.object(Path, "is_dir", return_value=True):
            result = fetch_project_commits(
                repo_paths=[Path("/fake/repo")],
                target_date="2026-02-25",
                user_email="bell@jpro.no",
                registered_hashes={"a1b2c3d4"},
                user=GitUser(name="Mr Bell", email="bell@jpro.no"),
                project_name="Test",
                project_slug="test",
            )
        assert len(result.repos[0].commits) == 1
        assert result.repos[0].commits[0].hash == "b2c3d4e5"

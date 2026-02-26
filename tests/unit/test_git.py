"""Tests for git subprocess operations."""

from unittest.mock import MagicMock, patch

from timereg.core.git import (
    fetch_commits,
    get_working_tree_status,
    parse_log_output,
    resolve_git_user,
)

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

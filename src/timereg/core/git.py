"""Git subprocess operations for commit fetching and repo analysis."""

from __future__ import annotations

import logging
import subprocess
from typing import TYPE_CHECKING

from timereg.core.models import (
    BranchInfo,
    CommitInfo,
    FetchResult,
    GitUser,
    RepoFetchResult,
    WorkingTreeStatus,
)

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)

_COMMIT_FORMAT = "%H%x00%s%x00%an%x00%ae%x00%aI"
_COMMIT_SEPARATOR = "\x00"


def _run_git(args: list[str], cwd: str) -> str:
    """Run a git command and return stdout. Raises on failure."""
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def parse_log_output(output: str, repo_path: str) -> list[CommitInfo]:
    """Parse `git log --format=... --numstat` output into CommitInfo objects."""
    if not output.strip():
        return []

    commits: list[CommitInfo] = []
    lines = output.strip().split("\n")
    i = 0

    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue

        parts = line.split(_COMMIT_SEPARATOR, 4)
        if len(parts) < 5:
            i += 1
            continue

        hash_, message, author_name, author_email, timestamp = parts
        files: list[str] = []
        insertions = 0
        deletions = 0
        i += 1

        while i < len(lines):
            stat_line = lines[i].strip()
            if "\x00" in stat_line:
                break
            if not stat_line:
                i += 1
                continue
            stat_parts = stat_line.split("\t")
            if len(stat_parts) == 3:
                ins_str, del_str, filename = stat_parts
                ins = int(ins_str) if ins_str != "-" else 0
                dels = int(del_str) if del_str != "-" else 0
                insertions += ins
                deletions += dels
                files.append(filename)
            i += 1

        commits.append(
            CommitInfo(
                hash=hash_,
                message=message,
                author_name=author_name,
                author_email=author_email,
                timestamp=timestamp,
                repo_path=repo_path,
                files_changed=len(files),
                insertions=insertions,
                deletions=deletions,
                files=files,
            )
        )

    return commits


def fetch_commits(
    repo_path: str,
    target_date: str,
    user_email: str,
    timezone: str = "Europe/Oslo",
    merge_commits: bool = False,
    registered_hashes: set[str] | None = None,
) -> list[CommitInfo]:
    """Fetch commits for a specific date and author from a git repo."""
    args = [
        "log",
        f"--after={target_date}T00:00:00",
        f"--before={target_date}T23:59:59",
        f"--author={user_email}",
        f"--format={_COMMIT_FORMAT}",
        "--numstat",
    ]
    if not merge_commits:
        args.append("--no-merges")

    output = _run_git(args, cwd=repo_path)
    commits = parse_log_output(output, repo_path=repo_path)

    if registered_hashes:
        commits = [c for c in commits if c.hash not in registered_hashes]

    return commits


def get_branch_info(repo_path: str, target_date: str | None = None) -> BranchInfo:
    """Get current branch and branch activity for the day."""
    try:
        current = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_path).strip()
    except subprocess.CalledProcessError:
        current = "unknown"

    activity: list[str] = []
    if target_date:
        try:
            reflog = _run_git(
                ["reflog", f"--after={target_date}T00:00:00", "--format=%gs"],
                cwd=repo_path,
            )
            activity = [line.strip() for line in reflog.strip().split("\n") if line.strip()]
        except subprocess.CalledProcessError:
            pass

    return BranchInfo(current=current, activity=activity)


def get_working_tree_status(repo_path: str) -> WorkingTreeStatus:
    """Get count of staged and unstaged changes."""
    try:
        staged_output = _run_git(["diff", "--cached", "--numstat"], cwd=repo_path)
        staged = len([line for line in staged_output.strip().split("\n") if line.strip()])
    except subprocess.CalledProcessError:
        staged = 0

    try:
        unstaged_output = _run_git(["diff", "--numstat"], cwd=repo_path)
        unstaged = len([line for line in unstaged_output.strip().split("\n") if line.strip()])
    except subprocess.CalledProcessError:
        unstaged = 0

    return WorkingTreeStatus(staged_files=staged, unstaged_files=unstaged)


def resolve_git_user(repo_path: str) -> GitUser:
    """Resolve git user name and email from repo config."""
    name = _run_git(["config", "user.name"], cwd=repo_path).strip()
    email = _run_git(["config", "user.email"], cwd=repo_path).strip()
    return GitUser(name=name, email=email)


def fetch_project_commits(
    repo_paths: list[Path],
    target_date: str,
    user_email: str,
    registered_hashes: set[str],
    user: GitUser,
    project_name: str,
    project_slug: str,
    config_dir: Path | None = None,
    timezone: str = "Europe/Oslo",
    merge_commits: bool = False,
) -> FetchResult:
    """Fetch commits across all repos for a project, with branch and tree status."""
    repo_results: list[RepoFetchResult] = []

    for repo_path in repo_paths:
        if not repo_path.is_dir():
            logger.warning("Repo path does not exist, skipping: %s", repo_path)
            continue

        repo_str = str(repo_path)
        try:
            commits = fetch_commits(
                repo_path=repo_str,
                target_date=target_date,
                user_email=user_email,
                timezone=timezone,
                merge_commits=merge_commits,
                registered_hashes=registered_hashes,
            )
        except subprocess.CalledProcessError:
            logger.warning("Failed to fetch commits from %s, skipping", repo_path)
            continue

        branch = get_branch_info(repo_str, target_date)
        wt_status = get_working_tree_status(repo_str)

        relative = str(repo_path.relative_to(config_dir)) if config_dir else str(repo_path)

        repo_results.append(
            RepoFetchResult(
                relative_path=relative,
                absolute_path=repo_str,
                branch=branch.current,
                branch_activity=branch.activity,
                uncommitted=wt_status,
                commits=commits,
            )
        )

    return FetchResult(
        project_name=project_name,
        project_slug=project_slug,
        date=target_date,
        user=user,
        repos=repo_results,
    )

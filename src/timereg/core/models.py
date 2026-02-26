"""Pydantic models for all TimeReg entities."""

from __future__ import annotations

import re
from datetime import date, datetime  # noqa: TC003
from pathlib import Path  # noqa: TC003
from typing import Literal

from pydantic import BaseModel, Field, field_validator

# --- Database entities ---


class Project(BaseModel):
    """A registered project."""

    id: int | None = None
    name: str
    slug: str
    config_path: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @field_validator("slug")
    @classmethod
    def slug_must_be_valid(cls, v: str) -> str:
        if not re.match(r"^[a-z0-9][a-z0-9-]*$", v):
            msg = "Slug must be lowercase alphanumeric with hyphens"
            raise ValueError(msg)
        return v


class ProjectRepo(BaseModel):
    """A git repo associated with a project."""

    id: int | None = None
    project_id: int
    absolute_path: str
    relative_path: str


class Entry(BaseModel):
    """A time registration entry."""

    id: int | None = None
    project_id: int
    git_user_name: str
    git_user_email: str
    date: date
    hours: float = Field(gt=0)
    short_summary: str
    long_summary: str | None = None
    entry_type: Literal["git", "manual"]
    tags: list[str] | None = None
    peer_group_id: str | None = None
    split_group_id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class EntryCommit(BaseModel):
    """A git commit associated with a time entry."""

    id: int | None = None
    entry_id: int
    commit_hash: str
    repo_path: str
    message: str
    author_name: str
    author_email: str
    timestamp: str
    files_changed: int = 0
    insertions: int = 0
    deletions: int = 0


# --- Git data types ---


class CommitInfo(BaseModel):
    """Structured commit data from git (pre-persistence)."""

    hash: str
    message: str
    author_name: str
    author_email: str
    timestamp: str
    repo_path: str
    files_changed: int = 0
    insertions: int = 0
    deletions: int = 0
    files: list[str] = Field(default_factory=list)


class WorkingTreeStatus(BaseModel):
    """Git working tree status counts."""

    staged_files: int = 0
    unstaged_files: int = 0


class BranchInfo(BaseModel):
    """Current branch and recent branch activity."""

    current: str
    activity: list[str] = Field(default_factory=list)


class GitUser(BaseModel):
    """Git user identity."""

    name: str
    email: str


class RepoFetchResult(BaseModel):
    """Per-repo fetch results."""

    relative_path: str
    absolute_path: str
    branch: str
    branch_activity: list[str] = Field(default_factory=list)
    uncommitted: WorkingTreeStatus
    commits: list[CommitInfo] = Field(default_factory=list)


class FetchResult(BaseModel):
    """Top-level fetch response for a single project."""

    project_name: str
    project_slug: str
    date: str
    user: GitUser
    repos: list[RepoFetchResult] = Field(default_factory=list)
    already_registered_today: list[Entry] = Field(default_factory=list)


class SuggestedSplitEntry(BaseModel):
    """Suggested time allocation for one project in a split."""

    project_slug: str
    project_name: str
    suggested_hours: float
    commit_count: int
    total_insertions: int
    total_deletions: int


class AllProjectsFetchResult(BaseModel):
    """Cross-project fetch with suggested time split."""

    date: str
    user: GitUser
    projects: list[FetchResult] = Field(default_factory=list)
    suggested_split: list[SuggestedSplitEntry] = Field(default_factory=list)


# --- Configuration models ---


class GlobalConfig(BaseModel):
    """Global config from ~/.config/timereg/config.toml."""

    db_path: str | None = None
    merge_commits: bool = False
    timezone: str = "Europe/Oslo"
    user_name: str | None = None
    user_email: str | None = None


class ProjectConfig(BaseModel):
    """Project config from .timetracker.toml."""

    name: str
    slug: str
    repo_paths: list[str] = Field(default_factory=lambda: ["."])
    allowed_tags: list[str] | None = None
    weekly_budget_hours: float | None = None
    monthly_budget_hours: float | None = None

    def resolve_repo_paths(self, config_dir: Path) -> list[Path]:
        """Resolve repo paths relative to the config file's directory."""
        return [(config_dir / p).resolve() for p in self.repo_paths]


class ResolvedConfig(BaseModel):
    """Merged configuration from all sources."""

    db_path: str
    project: ProjectConfig | None = None
    project_config_path: str | None = None
    user: GitUser | None = None
    merge_commits: bool = False
    timezone: str = "Europe/Oslo"
    verbose: bool = False

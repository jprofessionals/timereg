-- Initial schema: projects, entries, commits, claimed_commits

CREATE TABLE projects (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    slug        TEXT NOT NULL UNIQUE,
    config_path TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE UNIQUE INDEX idx_projects_slug ON projects(slug);

CREATE TABLE project_repos (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id    INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    absolute_path TEXT NOT NULL,
    relative_path TEXT NOT NULL
);

CREATE INDEX idx_project_repos_project ON project_repos(project_id);

CREATE TABLE entries (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id      INTEGER NOT NULL REFERENCES projects(id),
    git_user_name   TEXT NOT NULL,
    git_user_email  TEXT NOT NULL,
    date            TEXT NOT NULL,
    hours           REAL NOT NULL,
    short_summary   TEXT NOT NULL,
    long_summary    TEXT,
    entry_type      TEXT NOT NULL CHECK(entry_type IN ('git', 'manual')),
    tags            TEXT,
    peer_group_id   TEXT,
    split_group_id  TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_entries_project_date ON entries(project_id, date);
CREATE INDEX idx_entries_user ON entries(git_user_email, date);
CREATE INDEX idx_entries_peer ON entries(peer_group_id);
CREATE INDEX idx_entries_split ON entries(split_group_id);

CREATE TABLE entry_commits (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id      INTEGER NOT NULL REFERENCES entries(id) ON DELETE CASCADE,
    commit_hash   TEXT NOT NULL,
    repo_path     TEXT NOT NULL,
    message       TEXT NOT NULL,
    author_name   TEXT NOT NULL,
    author_email  TEXT NOT NULL,
    timestamp     TEXT NOT NULL,
    files_changed INTEGER DEFAULT 0,
    insertions    INTEGER DEFAULT 0,
    deletions     INTEGER DEFAULT 0
);

CREATE INDEX idx_entry_commits_hash ON entry_commits(commit_hash);
CREATE INDEX idx_entry_commits_entry ON entry_commits(entry_id);

CREATE TABLE claimed_commits (
    commit_hash TEXT NOT NULL,
    project_id  INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    claimed_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_claimed_commits_hash ON claimed_commits(commit_hash);

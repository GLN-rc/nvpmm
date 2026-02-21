"""
SQLite database setup for socialEars.
Tables: runs, posts, reports
"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "socialears.db")


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS runs (
            id          TEXT PRIMARY KEY,
            keywords    TEXT NOT NULL,       -- JSON array of strings
            subreddits  TEXT NOT NULL,       -- JSON array
            sources     TEXT NOT NULL,       -- JSON array: ["reddit","hackernews"]
            time_filter TEXT NOT NULL DEFAULT 'month',
            status      TEXT NOT NULL DEFAULT 'pending',
                                             -- pending | running | done | error
            error_msg   TEXT,
            post_count  INTEGER DEFAULT 0,
            created_at  REAL NOT NULL,
            finished_at REAL
        );

        CREATE TABLE IF NOT EXISTS posts (
            id           TEXT PRIMARY KEY,   -- source:source_id
            run_id       TEXT NOT NULL REFERENCES runs(id),
            source       TEXT NOT NULL,      -- reddit | hackernews
            source_id    TEXT NOT NULL,
            subreddit    TEXT,
            title        TEXT,
            text         TEXT,
            url          TEXT,
            score        INTEGER DEFAULT 0,
            num_comments INTEGER DEFAULT 0,
            created_at   TEXT,
            author       TEXT,
            post_type    TEXT DEFAULT 'post',-- post | comment
            parent_id    TEXT
        );

        CREATE TABLE IF NOT EXISTS reports (
            id          TEXT PRIMARY KEY,
            run_id      TEXT NOT NULL REFERENCES runs(id),
            pain_points TEXT,    -- JSON
            language    TEXT,    -- JSON
            competitive TEXT,    -- JSON
            summary     TEXT,
            top_topics  TEXT,    -- JSON
            post_count  INTEGER DEFAULT 0,
            created_at  REAL NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_posts_run   ON posts(run_id);
        CREATE INDEX IF NOT EXISTS idx_reports_run ON reports(run_id);
        """)

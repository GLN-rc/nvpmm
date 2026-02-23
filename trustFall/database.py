"""
trustFall — SQLite database setup and helpers.
"""
from __future__ import annotations

import aiosqlite
import asyncio
import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent / "trustfall.db"


from contextlib import asynccontextmanager

@asynccontextmanager
async def get_db():
    """Async context manager for a configured database connection."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA foreign_keys=ON")
        yield db


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA foreign_keys=ON")
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS vendors (
                id          TEXT PRIMARY KEY,
                name        TEXT NOT NULL,
                website     TEXT,
                notes       TEXT,
                created_at  INTEGER NOT NULL DEFAULT (strftime('%s','now'))
            );

            CREATE TABLE IF NOT EXISTS watched_pages (
                id                  TEXT PRIMARY KEY,
                vendor_id           TEXT NOT NULL REFERENCES vendors(id),
                url                 TEXT NOT NULL,
                label               TEXT NOT NULL,
                suggested_by        TEXT NOT NULL DEFAULT 'user',
                status              TEXT NOT NULL DEFAULT 'active',
                fingerprint_phrases TEXT,
                last_checked        INTEGER,
                last_changed        INTEGER,
                page_moved_flag     INTEGER NOT NULL DEFAULT 0,
                created_at          INTEGER NOT NULL DEFAULT (strftime('%s','now')),
                UNIQUE(vendor_id, url)
            );

            CREATE TABLE IF NOT EXISTS snapshots (
                id            TEXT PRIMARY KEY,
                page_id       TEXT NOT NULL REFERENCES watched_pages(id),
                captured_at   INTEGER NOT NULL DEFAULT (strftime('%s','now')),
                content_hash  TEXT NOT NULL,
                text_content  TEXT NOT NULL,
                source        TEXT NOT NULL DEFAULT 'live'
            );

            CREATE TABLE IF NOT EXISTS change_events (
                id              TEXT PRIMARY KEY,
                page_id         TEXT NOT NULL REFERENCES watched_pages(id),
                detected_at     INTEGER NOT NULL DEFAULT (strftime('%s','now')),
                prev_snapshot_id TEXT REFERENCES snapshots(id),
                curr_snapshot_id TEXT REFERENCES snapshots(id),
                diff_summary    TEXT,
                llm_score       TEXT,
                llm_reasoning   TEXT,
                user_verdict    TEXT NOT NULL DEFAULT 'pending',
                prev_text       TEXT,
                curr_text       TEXT
            );
        """)
        await db.commit()
        log.info("Database initialized at %s", DB_PATH)

"""
Storage helpers — read/write runs, posts, and reports to SQLite.
"""

import json
import time
import uuid
import logging
from typing import Optional
from database import get_conn

log = logging.getLogger(__name__)


# ── Runs ──────────────────────────────────────────────────────────────────────

def create_run(keywords: list, subreddits: list, sources: list, time_filter: str) -> str:
    run_id = str(uuid.uuid4())
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO runs (id, keywords, subreddits, sources, time_filter, status, created_at)
               VALUES (?, ?, ?, ?, ?, 'pending', ?)""",
            (run_id, json.dumps(keywords), json.dumps(subreddits),
             json.dumps(sources), time_filter, time.time()),
        )
    return run_id


def set_run_status(run_id: str, status: str, error_msg: str = None, post_count: int = None):
    updates = ["status = ?"]
    params  = [status]
    if error_msg is not None:
        updates.append("error_msg = ?")
        params.append(error_msg)
    if post_count is not None:
        updates.append("post_count = ?")
        params.append(post_count)
    if status in ("done", "error"):
        updates.append("finished_at = ?")
        params.append(time.time())
    params.append(run_id)
    with get_conn() as conn:
        conn.execute(f"UPDATE runs SET {', '.join(updates)} WHERE id = ?", params)


def get_run(run_id: str) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
    return dict(row) if row else None


def list_runs(limit: int = 20) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM runs ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["keywords"]   = json.loads(d["keywords"])
        d["subreddits"] = json.loads(d["subreddits"])
        d["sources"]    = json.loads(d["sources"])
        result.append(d)
    return result


# ── Posts ─────────────────────────────────────────────────────────────────────

def save_posts(run_id: str, posts: list[dict]):
    """Bulk-insert posts, ignoring duplicates across runs."""
    with get_conn() as conn:
        for p in posts:
            pid = f"{p['source']}:{p['source_id']}"
            try:
                conn.execute(
                    """INSERT OR IGNORE INTO posts
                       (id, run_id, source, source_id, subreddit, title, text,
                        url, score, num_comments, created_at, author, post_type, parent_id)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        pid, run_id,
                        p.get("source"), p.get("source_id"),
                        p.get("subreddit"), p.get("title"), p.get("text"),
                        p.get("url"), p.get("score", 0), p.get("num_comments", 0),
                        p.get("created_at"), p.get("author"),
                        p.get("post_type", "post"), p.get("parent_id"),
                    ),
                )
            except Exception as e:
                log.warning(f"Failed to save post {pid}: {e}")


def get_posts(run_id: str) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM posts WHERE run_id = ? ORDER BY score DESC", (run_id,)
        ).fetchall()
    return [dict(r) for r in rows]


# ── Reports ───────────────────────────────────────────────────────────────────

def save_report(run_id: str, analysis: dict) -> str:
    report_id = str(uuid.uuid4())
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO reports
               (id, run_id, pain_points, language, competitive, summary, top_topics, post_count, created_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                report_id, run_id,
                json.dumps(analysis.get("pain_points", [])),
                json.dumps(analysis.get("language", [])),
                json.dumps(analysis.get("competitive_signals", [])),
                analysis.get("summary", ""),
                json.dumps(analysis.get("top_topics", [])),
                analysis.get("post_count", 0),
                time.time(),
            ),
        )
    return report_id


def get_report(run_id: str) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM reports WHERE run_id = ? ORDER BY created_at DESC LIMIT 1",
            (run_id,),
        ).fetchone()
    if not row:
        return None
    d = dict(row)
    d["pain_points"] = json.loads(d["pain_points"] or "[]")
    d["language"]    = json.loads(d["language"]    or "[]")
    d["competitive"] = json.loads(d["competitive"] or "[]")
    d["top_topics"]  = json.loads(d["top_topics"]  or "[]")
    return d

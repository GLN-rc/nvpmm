"""
tryMe — SQLite database layer
All schema init and query functions live here. No ORM — plain sqlite3.
"""
import sqlite3
import time
import uuid
import json
import os
from typing import Optional, List, Dict, Any

DB_PATH = os.path.join(os.path.dirname(__file__), "demos.db")


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db():
    """Create tables if they don't exist. Called once on app startup."""
    conn = _get_conn()
    with conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS demos (
                id          TEXT PRIMARY KEY,
                title       TEXT NOT NULL,
                description TEXT DEFAULT '',
                personas    TEXT DEFAULT '[]',
                created_at  REAL NOT NULL,
                updated_at  REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS steps (
                id          TEXT PRIMARY KEY,
                demo_id     TEXT NOT NULL REFERENCES demos(id) ON DELETE CASCADE,
                position    INTEGER NOT NULL,
                title       TEXT NOT NULL DEFAULT '',
                tooltip     TEXT DEFAULT '',
                image_path  TEXT DEFAULT '',
                created_at  REAL NOT NULL,
                updated_at  REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS hotspots (
                id             TEXT PRIMARY KEY,
                step_id        TEXT NOT NULL REFERENCES steps(id) ON DELETE CASCADE,
                label          TEXT DEFAULT '',
                x              REAL NOT NULL,
                y              REAL NOT NULL,
                width          REAL NOT NULL,
                height         REAL NOT NULL,
                action_type    TEXT NOT NULL DEFAULT 'next',
                action_target  TEXT DEFAULT NULL,
                created_at     REAL NOT NULL
            );
        """)
    conn.close()


# ══════════════════════════════════════════════════════════════════
# DEMO queries
# ══════════════════════════════════════════════════════════════════

def create_demo(title: str, description: str = "", personas: Optional[List[str]] = None) -> Dict[str, Any]:
    demo_id = str(uuid.uuid4())
    now = time.time()
    personas_json = json.dumps(personas or [])
    conn = _get_conn()
    with conn:
        conn.execute(
            "INSERT INTO demos (id, title, description, personas, created_at, updated_at) VALUES (?,?,?,?,?,?)",
            (demo_id, title, description, personas_json, now, now)
        )
    conn.close()
    return get_demo(demo_id)


def get_demo(demo_id: str) -> Optional[Dict[str, Any]]:
    conn = _get_conn()
    row = conn.execute(
        "SELECT d.*, COUNT(s.id) as step_count FROM demos d LEFT JOIN steps s ON s.demo_id = d.id WHERE d.id = ? GROUP BY d.id",
        (demo_id,)
    ).fetchone()
    conn.close()
    if not row:
        return None
    return _demo_row(row)


def list_demos() -> List[Dict[str, Any]]:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT d.*, COUNT(s.id) as step_count FROM demos d LEFT JOIN steps s ON s.demo_id = d.id GROUP BY d.id ORDER BY d.updated_at DESC"
    ).fetchall()
    conn.close()
    return [_demo_row(r) for r in rows]


def update_demo(demo_id: str, title: Optional[str] = None, description: Optional[str] = None,
                personas: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
    fields, vals = [], []
    if title is not None:
        fields.append("title = ?"); vals.append(title)
    if description is not None:
        fields.append("description = ?"); vals.append(description)
    if personas is not None:
        fields.append("personas = ?"); vals.append(json.dumps(personas))
    if not fields:
        return get_demo(demo_id)
    fields.append("updated_at = ?"); vals.append(time.time())
    vals.append(demo_id)
    conn = _get_conn()
    with conn:
        conn.execute(f"UPDATE demos SET {', '.join(fields)} WHERE id = ?", vals)
    conn.close()
    return get_demo(demo_id)


def delete_demo(demo_id: str) -> bool:
    conn = _get_conn()
    with conn:
        cur = conn.execute("DELETE FROM demos WHERE id = ?", (demo_id,))
    conn.close()
    return cur.rowcount > 0


def _demo_row(row) -> Dict[str, Any]:
    d = dict(row)
    d["personas"] = json.loads(d.get("personas") or "[]")
    return d


# ══════════════════════════════════════════════════════════════════
# STEP queries
# ══════════════════════════════════════════════════════════════════

def create_step(demo_id: str, title: str, tooltip: str = "", position: Optional[int] = None) -> Dict[str, Any]:
    step_id = str(uuid.uuid4())
    now = time.time()
    if position is None:
        conn = _get_conn()
        row = conn.execute("SELECT MAX(position) as mp FROM steps WHERE demo_id = ?", (demo_id,)).fetchone()
        conn.close()
        position = (row["mp"] or 0) + 1
    conn = _get_conn()
    with conn:
        conn.execute(
            "INSERT INTO steps (id, demo_id, position, title, tooltip, image_path, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)",
            (step_id, demo_id, position, title, tooltip, "", now, now)
        )
        # bump demo updated_at
        conn.execute("UPDATE demos SET updated_at = ? WHERE id = ?", (now, demo_id))
    conn.close()
    return get_step(step_id)


def get_step(step_id: str) -> Optional[Dict[str, Any]]:
    conn = _get_conn()
    row = conn.execute("SELECT * FROM steps WHERE id = ?", (step_id,)).fetchone()
    conn.close()
    if not row:
        return None
    s = dict(row)
    s["hotspots"] = get_hotspots_for_step(step_id)
    return s


def get_steps_for_demo(demo_id: str) -> List[Dict[str, Any]]:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM steps WHERE demo_id = ? ORDER BY position ASC", (demo_id,)
    ).fetchall()
    conn.close()
    steps = []
    for row in rows:
        s = dict(row)
        s["hotspots"] = get_hotspots_for_step(s["id"])
        steps.append(s)
    return steps


def update_step(step_id: str, title: Optional[str] = None, tooltip: Optional[str] = None,
                image_path: Optional[str] = None, position: Optional[int] = None) -> Optional[Dict[str, Any]]:
    fields, vals = [], []
    if title is not None:
        fields.append("title = ?"); vals.append(title)
    if tooltip is not None:
        fields.append("tooltip = ?"); vals.append(tooltip)
    if image_path is not None:
        fields.append("image_path = ?"); vals.append(image_path)
    if position is not None:
        fields.append("position = ?"); vals.append(position)
    if not fields:
        return get_step(step_id)
    now = time.time()
    fields.append("updated_at = ?"); vals.append(now)
    vals.append(step_id)
    conn = _get_conn()
    with conn:
        conn.execute(f"UPDATE steps SET {', '.join(fields)} WHERE id = ?", vals)
    conn.close()
    return get_step(step_id)


def delete_step(step_id: str) -> bool:
    conn = _get_conn()
    with conn:
        cur = conn.execute("DELETE FROM steps WHERE id = ?", (step_id,))
    conn.close()
    return cur.rowcount > 0


def reorder_steps(demo_id: str, ordered_ids: List[str]) -> bool:
    """Set position = index+1 for each step_id in ordered_ids."""
    now = time.time()
    conn = _get_conn()
    with conn:
        for i, step_id in enumerate(ordered_ids):
            conn.execute(
                "UPDATE steps SET position = ?, updated_at = ? WHERE id = ? AND demo_id = ?",
                (i + 1, now, step_id, demo_id)
            )
        conn.execute("UPDATE demos SET updated_at = ? WHERE id = ?", (now, demo_id))
    conn.close()
    return True


# ══════════════════════════════════════════════════════════════════
# HOTSPOT queries
# ══════════════════════════════════════════════════════════════════

def create_hotspot(step_id: str, label: str, x: float, y: float, width: float, height: float,
                   action_type: str = "next", action_target: Optional[str] = None) -> Dict[str, Any]:
    hotspot_id = str(uuid.uuid4())
    now = time.time()
    conn = _get_conn()
    with conn:
        conn.execute(
            "INSERT INTO hotspots (id, step_id, label, x, y, width, height, action_type, action_target, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (hotspot_id, step_id, label, x, y, width, height, action_type, action_target, now)
        )
    conn.close()
    return get_hotspot(hotspot_id)


def get_hotspot(hotspot_id: str) -> Optional[Dict[str, Any]]:
    conn = _get_conn()
    row = conn.execute("SELECT * FROM hotspots WHERE id = ?", (hotspot_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_hotspots_for_step(step_id: str) -> List[Dict[str, Any]]:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM hotspots WHERE step_id = ? ORDER BY created_at ASC", (step_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_hotspot(hotspot_id: str, label: Optional[str] = None, x: Optional[float] = None,
                   y: Optional[float] = None, width: Optional[float] = None, height: Optional[float] = None,
                   action_type: Optional[str] = None, action_target: Optional[str] = None) -> Optional[Dict[str, Any]]:
    fields, vals = [], []
    for col, val in [("label", label), ("x", x), ("y", y), ("width", width), ("height", height),
                     ("action_type", action_type), ("action_target", action_target)]:
        if val is not None:
            fields.append(f"{col} = ?"); vals.append(val)
    if not fields:
        return get_hotspot(hotspot_id)
    vals.append(hotspot_id)
    conn = _get_conn()
    with conn:
        conn.execute(f"UPDATE hotspots SET {', '.join(fields)} WHERE id = ?", vals)
    conn.close()
    return get_hotspot(hotspot_id)


def delete_hotspot(hotspot_id: str) -> bool:
    conn = _get_conn()
    with conn:
        cur = conn.execute("DELETE FROM hotspots WHERE id = ?", (hotspot_id,))
    conn.close()
    return cur.rowcount > 0


# ══════════════════════════════════════════════════════════════════
# FULL DEMO (viewer payload)
# ══════════════════════════════════════════════════════════════════

def get_demo_full(demo_id: str) -> Optional[Dict[str, Any]]:
    demo = get_demo(demo_id)
    if not demo:
        return None
    demo["steps"] = get_steps_for_demo(demo_id)
    return demo

"""
trustFall — FastAPI backend.
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger(__name__)

from database import init_db, get_db
from analyzer import score_diff
from sources.fetcher import fetch_page
from sources.suggester import suggest_urls

app = FastAPI(title="trustFall")

# ── Static files ──────────────────────────────────────────────────────────────
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def root():
    return FileResponse("static/index.html")

# ── Startup ───────────────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup():
    await init_db()
    log.info("trustFall ready")

# ── Pydantic models ───────────────────────────────────────────────────────────
class VendorCreate(BaseModel):
    name: str
    website: str
    notes: Optional[str] = None

class PageCreate(BaseModel):
    vendor_id: str
    url: str
    label: str
    fingerprint_phrases: Optional[list[str]] = None
    suggested_by: str = "user"

class VerdictUpdate(BaseModel):
    verdict: str   # "confirmed" | "dismissed"

# ── Vendors ───────────────────────────────────────────────────────────────────
@app.get("/api/vendors")
async def list_vendors():
    async with get_db() as db:
        rows = await db.execute_fetchall("""
            SELECT v.*,
                   COUNT(DISTINCT wp.id) as page_count,
                   COUNT(DISTINCT ce.id) as pending_count
            FROM vendors v
            LEFT JOIN watched_pages wp ON wp.vendor_id = v.id AND wp.status = 'active'
            LEFT JOIN change_events ce ON ce.page_id = wp.id AND ce.user_verdict = 'pending'
            GROUP BY v.id
            ORDER BY v.name
        """)
        return [dict(r) for r in rows]


@app.post("/api/vendors", status_code=201)
async def create_vendor(body: VendorCreate):
    vid = str(uuid.uuid4())
    async with get_db() as db:
        await db.execute(
            "INSERT INTO vendors (id, name, website, notes) VALUES (?,?,?,?)",
            (vid, body.name, body.website, body.notes)
        )
        await db.commit()
    return {"id": vid, "name": body.name, "website": body.website}


@app.delete("/api/vendors/{vendor_id}")
async def delete_vendor(vendor_id: str):
    async with get_db() as db:
        await db.execute("DELETE FROM vendors WHERE id=?", (vendor_id,))
        await db.commit()
    return {"ok": True}


# ── URL Suggestions ───────────────────────────────────────────────────────────
@app.get("/api/vendors/{vendor_id}/suggest")
async def suggest_vendor_urls(vendor_id: str):
    async with get_db() as db:
        row = await db.execute_fetchall("SELECT * FROM vendors WHERE id=?", (vendor_id,))
        if not row:
            raise HTTPException(404, "Vendor not found")
        vendor = dict(row[0])

        existing = await db.execute_fetchall(
            "SELECT url FROM watched_pages WHERE vendor_id=?", (vendor_id,)
        )
        known_urls = {r["url"] for r in existing}

    suggestions = await suggest_urls(
        vendor_name=vendor["name"],
        website=vendor["website"],
    )
    # Filter out already-watched URLs
    suggestions = [s for s in suggestions if s["url"] not in known_urls]
    return suggestions


# ── Watched Pages ─────────────────────────────────────────────────────────────
@app.get("/api/vendors/{vendor_id}/pages")
async def list_pages(vendor_id: str):
    async with get_db() as db:
        rows = await db.execute_fetchall("""
            SELECT wp.*,
                   COUNT(ce.id) as pending_changes
            FROM watched_pages wp
            LEFT JOIN change_events ce ON ce.page_id = wp.id AND ce.user_verdict = 'pending'
            WHERE wp.vendor_id = ?
            GROUP BY wp.id
            ORDER BY wp.label
        """, (vendor_id,))
        return [dict(r) for r in rows]


@app.post("/api/pages", status_code=201)
async def add_page(body: PageCreate):
    pid = str(uuid.uuid4())
    fps = ",".join(body.fingerprint_phrases) if body.fingerprint_phrases else None
    async with get_db() as db:
        try:
            await db.execute("""
                INSERT INTO watched_pages
                  (id, vendor_id, url, label, fingerprint_phrases, suggested_by)
                VALUES (?,?,?,?,?,?)
            """, (pid, body.vendor_id, body.url, body.label, fps, body.suggested_by))
            await db.commit()
        except Exception as e:
            if "UNIQUE" in str(e):
                raise HTTPException(409, "This URL is already being watched for this vendor")
            raise
    return {"id": pid, "url": body.url, "label": body.label}


@app.delete("/api/pages/{page_id}")
async def delete_page(page_id: str):
    async with get_db() as db:
        await db.execute("DELETE FROM watched_pages WHERE id=?", (page_id,))
        await db.commit()
    return {"ok": True}


@app.patch("/api/pages/{page_id}/pause")
async def toggle_pause(page_id: str):
    async with get_db() as db:
        row = await db.execute_fetchall("SELECT status FROM watched_pages WHERE id=?", (page_id,))
        if not row:
            raise HTTPException(404)
        current = row[0]["status"]
        new_status = "paused" if current == "active" else "active"
        await db.execute("UPDATE watched_pages SET status=? WHERE id=?", (new_status, page_id))
        await db.commit()
    return {"status": new_status}


# ── Check (manual run) ────────────────────────────────────────────────────────
@app.post("/api/pages/{page_id}/check")
async def check_page(page_id: str):
    """Fetch current content of a page and compare to last snapshot."""
    async with get_db() as db:
        rows = await db.execute_fetchall("SELECT * FROM watched_pages WHERE id=?", (page_id,))
        if not rows:
            raise HTTPException(404, "Page not found")
        page = dict(rows[0])

        vendor_rows = await db.execute_fetchall(
            "SELECT * FROM vendors WHERE id=?", (page["vendor_id"],)
        )
        vendor = dict(vendor_rows[0])

        # Get last snapshot
        snap_rows = await db.execute_fetchall("""
            SELECT * FROM snapshots WHERE page_id=?
            ORDER BY captured_at DESC LIMIT 1
        """, (page_id,))
        last_snap = dict(snap_rows[0]) if snap_rows else None

    fps = [p.strip() for p in page["fingerprint_phrases"].split(",")] \
          if page.get("fingerprint_phrases") else None

    result = await fetch_page(page["url"], fingerprint_phrases=fps)

    now_ts = int(datetime.now(tz=timezone.utc).timestamp())

    async with get_db() as db:
        # Update last_checked regardless
        await db.execute(
            "UPDATE watched_pages SET last_checked=?, page_moved_flag=? WHERE id=?",
            (now_ts, 1 if result.page_moved else 0, page_id)
        )

        if not result.success:
            await db.commit()
            return {
                "changed": False,
                "blocked": result.blocked,
                "page_moved": result.page_moved,
                "error": result.error,
            }

        # No previous snapshot — save as baseline
        if not last_snap:
            snap_id = str(uuid.uuid4())
            await db.execute("""
                INSERT INTO snapshots (id, page_id, content_hash, text_content, source)
                VALUES (?,?,?,?,'live')
            """, (snap_id, page_id, result.content_hash, result.text))
            await db.commit()
            return {"changed": False, "baseline": True, "message": "First snapshot saved."}

        # Same content
        if result.content_hash == last_snap["content_hash"]:
            await db.commit()
            return {"changed": False, "message": "No changes detected."}

        # Content changed — save new snapshot and score diff
        new_snap_id = str(uuid.uuid4())
        await db.execute("""
            INSERT INTO snapshots (id, page_id, content_hash, text_content, source)
            VALUES (?,?,?,?,'live')
        """, (new_snap_id, page_id, result.content_hash, result.text))

        diff = await score_diff(
            vendor_name=vendor["name"],
            page_label=page["label"],
            prev_text=last_snap["text_content"],
            curr_text=result.text,
        )

        event_id = str(uuid.uuid4())
        await db.execute("""
            INSERT INTO change_events
              (id, page_id, prev_snapshot_id, curr_snapshot_id,
               diff_summary, llm_score, llm_reasoning, prev_text, curr_text)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, (
            event_id, page_id, last_snap["id"], new_snap_id,
            diff.summary, diff.score, diff.reasoning,
            last_snap["text_content"], result.text,
        ))

        await db.execute(
            "UPDATE watched_pages SET last_changed=? WHERE id=?", (now_ts, page_id)
        )
        await db.commit()

    return {
        "changed": True,
        "score": diff.score,
        "summary": diff.summary,
        "reasoning": diff.reasoning,
        "high_signal_hits": diff.high_signal_hits,
        "page_moved": result.page_moved,
        "event_id": event_id,
    }


@app.post("/api/vendors/{vendor_id}/check-all")
async def check_all_pages(vendor_id: str):
    """Check all active pages for a vendor."""
    async with get_db() as db:
        rows = await db.execute_fetchall(
            "SELECT id FROM watched_pages WHERE vendor_id=? AND status='active'", (vendor_id,)
        )
        page_ids = [r["id"] for r in rows]

    results = []
    for pid in page_ids:
        result = await check_page(pid)
        results.append({"page_id": pid, **result})

    return results


# ── Change Events ─────────────────────────────────────────────────────────────
@app.get("/api/changes")
async def list_changes(verdict: Optional[str] = None):
    """List change events, optionally filtered by verdict."""
    async with get_db() as db:
        if verdict:
            rows = await db.execute_fetchall("""
                SELECT ce.*, wp.url, wp.label, v.name as vendor_name
                FROM change_events ce
                JOIN watched_pages wp ON wp.id = ce.page_id
                JOIN vendors v ON v.id = wp.vendor_id
                WHERE ce.user_verdict = ?
                ORDER BY ce.detected_at DESC
            """, (verdict,))
        else:
            rows = await db.execute_fetchall("""
                SELECT ce.*, wp.url, wp.label, v.name as vendor_name
                FROM change_events ce
                JOIN watched_pages wp ON wp.id = ce.page_id
                JOIN vendors v ON v.id = wp.vendor_id
                ORDER BY ce.detected_at DESC
                LIMIT 100
            """)
        return [dict(r) for r in rows]


@app.get("/api/changes/{event_id}")
async def get_change(event_id: str):
    async with get_db() as db:
        rows = await db.execute_fetchall("""
            SELECT ce.*, wp.url, wp.label, v.name as vendor_name
            FROM change_events ce
            JOIN watched_pages wp ON wp.id = ce.page_id
            JOIN vendors v ON v.id = wp.vendor_id
            WHERE ce.id = ?
        """, (event_id,))
        if not rows:
            raise HTTPException(404)
        return dict(rows[0])


@app.patch("/api/changes/{event_id}/verdict")
async def set_verdict(event_id: str, body: VerdictUpdate):
    if body.verdict not in ("confirmed", "dismissed"):
        raise HTTPException(400, "verdict must be 'confirmed' or 'dismissed'")
    async with get_db() as db:
        await db.execute(
            "UPDATE change_events SET user_verdict=? WHERE id=?",
            (body.verdict, event_id)
        )
        await db.commit()
    return {"ok": True, "verdict": body.verdict}


# ── Snapshot download ─────────────────────────────────────────────────────────
@app.get("/api/changes/{event_id}/download")
async def download_snapshot(event_id: str, version: str = "current"):
    """Download prev or current text snapshot for a change event."""
    async with get_db() as db:
        rows = await db.execute_fetchall(
            "SELECT * FROM change_events WHERE id=?", (event_id,)
        )
        if not rows:
            raise HTTPException(404)
        event = dict(rows[0])

    text = event["curr_text"] if version == "current" else event["prev_text"]
    if not text:
        raise HTTPException(404, "Snapshot text not available")

    return PlainTextResponse(
        content=text,
        headers={"Content-Disposition": f'attachment; filename="snapshot-{event_id}-{version}.txt"'}
    )


# ── Manual baseline (paste) ───────────────────────────────────────────────────
class BaselinePaste(BaseModel):
    text: str
    as_of_date: Optional[str] = None   # ISO date string e.g. "2024-08-01", optional


@app.post("/api/pages/{page_id}/baseline")
async def set_manual_baseline(page_id: str, body: BaselinePaste):
    """Save user-pasted text as the baseline snapshot for a page."""
    if not body.text.strip():
        raise HTTPException(400, "Baseline text cannot be empty")

    import hashlib
    text = body.text.strip()
    content_hash = hashlib.sha256(text.encode()).hexdigest()
    snap_id = str(uuid.uuid4())

    # Parse optional as_of_date, fall back to now
    try:
        from datetime import date
        as_of_ts = int(datetime.fromisoformat(body.as_of_date).timestamp()) \
            if body.as_of_date else int(datetime.now(tz=timezone.utc).timestamp())
    except Exception:
        as_of_ts = int(datetime.now(tz=timezone.utc).timestamp())

    async with get_db() as db:
        row = await db.execute_fetchall("SELECT id FROM watched_pages WHERE id=?", (page_id,))
        if not row:
            raise HTTPException(404, "Page not found")

        # Replace any existing manual or wayback baseline
        await db.execute(
            "DELETE FROM snapshots WHERE page_id=? AND source IN ('manual','wayback')",
            (page_id,)
        )
        await db.execute("""
            INSERT INTO snapshots (id, page_id, content_hash, text_content, source, captured_at)
            VALUES (?,?,?,?,'manual',?)
        """, (snap_id, page_id, content_hash, text, as_of_ts))
        await db.commit()

    return {
        "ok": True,
        "snapshot_id": snap_id,
        "char_count": len(text),
        "as_of_ts": as_of_ts,
    }

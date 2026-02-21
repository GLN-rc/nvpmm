"""
socialEars — FastAPI backend
"""
from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

import database
import storage
from sources import reddit as reddit_src
from sources import hackernews as hn_src
import analyzer

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(name)s  %(message)s")
log = logging.getLogger(__name__)

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")


@asynccontextmanager
async def lifespan(app: FastAPI):
    database.init_db()
    log.info("DB initialised")
    yield


app = FastAPI(title="socialEars", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# ── Models ────────────────────────────────────────────────────────────────────

class RunRequest(BaseModel):
    keywords:    list[str]
    subreddits:  list[str] = []
    sources:     list[str] = ["reddit", "hackernews"]
    time_filter: str       = "month"   # week | month | year | all


# ── Pages ─────────────────────────────────────────────────────────────────────

@app.get("/", response_class=FileResponse)
async def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


# ── API ───────────────────────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/subreddits")
async def get_subreddits():
    return reddit_src.SUBREDDIT_LIST


@app.get("/api/runs")
async def list_runs():
    return storage.list_runs(limit=30)


@app.get("/api/runs/{run_id}")
async def get_run(run_id: str):
    run = storage.get_run(run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    run["keywords"]   = __import__("json").loads(run["keywords"])
    run["subreddits"] = __import__("json").loads(run["subreddits"])
    run["sources"]    = __import__("json").loads(run["sources"])
    return run


@app.get("/api/runs/{run_id}/report")
async def get_report(run_id: str):
    report = storage.get_report(run_id)
    if not report:
        raise HTTPException(404, "Report not ready yet")
    return report


@app.get("/api/runs/{run_id}/posts")
async def get_posts(run_id: str):
    return storage.get_posts(run_id)


@app.post("/api/runs", status_code=202)
async def start_run(req: RunRequest, background_tasks: BackgroundTasks):
    """Start a new collection + analysis run. Returns immediately; work happens in background."""
    keywords = [k.strip() for k in req.keywords if k.strip()]
    if not keywords:
        raise HTTPException(400, "At least one keyword required")

    sources    = [s for s in req.sources if s in ("reddit", "hackernews")]
    subreddits = req.subreddits

    # Default subreddits if none selected but reddit is a source
    if "reddit" in sources and not subreddits:
        subreddits = [s["name"] for s in reddit_src.SUBREDDIT_LIST]

    run_id = storage.create_run(keywords, subreddits, sources, req.time_filter)
    background_tasks.add_task(_run_pipeline, run_id, keywords, subreddits, sources, req.time_filter)

    return {"run_id": run_id, "status": "pending"}


async def _run_pipeline(
    run_id: str,
    keywords: list[str],
    subreddits: list[str],
    sources: list[str],
    time_filter: str,
):
    """Background task: collect → store → analyze → store report."""
    try:
        storage.set_run_status(run_id, "running")
        log.info(f"[{run_id}] Starting collection. keywords={keywords} sources={sources}")

        # ── Collect ──────────────────────────────────────────────────────────
        tasks = []
        if "reddit" in sources:
            tasks.append(reddit_src.collect(keywords, subreddits, time_filter=time_filter))
        if "hackernews" in sources:
            tasks.append(hn_src.collect(keywords, time_filter=time_filter))

        all_posts = []
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if isinstance(r, Exception):
                log.error(f"[{run_id}] Collector error: {r}")
            else:
                all_posts.extend(r)

        log.info(f"[{run_id}] Collected {len(all_posts)} posts total")
        storage.save_posts(run_id, all_posts)
        storage.set_run_status(run_id, "running", post_count=len(all_posts))

        # ── Analyze ──────────────────────────────────────────────────────────
        log.info(f"[{run_id}] Starting LLM analysis")
        analysis = await analyzer.analyze(all_posts, keywords)

        storage.save_report(run_id, analysis)
        storage.set_run_status(run_id, "done", post_count=len(all_posts))
        log.info(f"[{run_id}] Done.")

    except Exception as e:
        log.exception(f"[{run_id}] Pipeline failed: {e}")
        storage.set_run_status(run_id, "error", error_msg=str(e))

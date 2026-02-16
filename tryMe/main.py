"""
tryMe — Interactive Demo Builder
FastAPI app on port 8002
"""
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from typing import Optional
import os

import database as db
import storage
from models import (
    DemoCreate, DemoUpdate, DemoResponse, DemoFull,
    StepResponse, StepUpdate,
    HotspotCreate, HotspotUpdate, HotspotResponse,
    ReorderRequest
)

# ── Static persona list ───────────────────────────────────────────
PERSONAS = [
    "Sales Rep",
    "Sales Engineer / Pre-Sales",
    "IT Admin / IT Manager",
    "Developer / Engineer",
    "Product Manager",
    "End User / Employee",
    "Executive / Decision Maker",
    "Security & Compliance Officer",
    "Marketing / Demand Gen",
    "Customer Success / Support",
]

STATIC_DIR  = os.path.join(os.path.dirname(__file__), "static")
UPLOADS_DIR = os.path.join(os.path.dirname(__file__), "uploads")

app = FastAPI(title="tryMe — Interactive Demo Builder")

# ── Startup ───────────────────────────────────────────────────────
@app.on_event("startup")
def startup():
    db.init_db()
    storage.ensure_uploads_dir()

# ── Static mounts ─────────────────────────────────────────────────
app.mount("/static",  StaticFiles(directory=STATIC_DIR),  name="static")
app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")


# ══════════════════════════════════════════════════════════════════
# HTML page routes
# ══════════════════════════════════════════════════════════════════

@app.get("/", response_class=FileResponse)
def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))

@app.get("/editor", response_class=FileResponse)
def editor_new():
    return FileResponse(os.path.join(STATIC_DIR, "editor.html"))

@app.get("/editor/{demo_id}", response_class=FileResponse)
def editor_existing(demo_id: str):
    return FileResponse(os.path.join(STATIC_DIR, "editor.html"))

@app.get("/demo/{demo_id}", response_class=FileResponse)
def viewer(demo_id: str):
    return FileResponse(os.path.join(STATIC_DIR, "viewer.html"))


# ══════════════════════════════════════════════════════════════════
# API — utility
# ══════════════════════════════════════════════════════════════════

@app.get("/api/health")
def health():
    return {"status": "healthy", "service": "tryMe"}

@app.get("/api/personas")
def get_personas():
    return {"personas": PERSONAS}


# ══════════════════════════════════════════════════════════════════
# API — Demos
# ══════════════════════════════════════════════════════════════════

@app.get("/api/demos")
def list_demos():
    return db.list_demos()

@app.post("/api/demos", status_code=201)
def create_demo(body: DemoCreate):
    return db.create_demo(title=body.title, description=body.description, personas=body.personas)

@app.get("/api/demos/{demo_id}")
def get_demo(demo_id: str):
    demo = db.get_demo_full(demo_id)
    if not demo:
        raise HTTPException(404, "Demo not found")
    return demo

@app.patch("/api/demos/{demo_id}")
def update_demo(demo_id: str, body: DemoUpdate):
    demo = db.update_demo(demo_id, title=body.title, description=body.description, personas=body.personas)
    if not demo:
        raise HTTPException(404, "Demo not found")
    return demo

@app.delete("/api/demos/{demo_id}")
def delete_demo(demo_id: str):
    if not db.delete_demo(demo_id):
        raise HTTPException(404, "Demo not found")
    storage.delete_demo_uploads(demo_id)
    return {"status": "deleted"}

@app.get("/api/demos/{demo_id}/full")
def get_demo_full(demo_id: str):
    demo = db.get_demo_full(demo_id)
    if not demo:
        raise HTTPException(404, "Demo not found")
    return demo


# ══════════════════════════════════════════════════════════════════
# API — Steps
# ══════════════════════════════════════════════════════════════════

@app.post("/api/demos/{demo_id}/steps", status_code=201)
async def create_step(
    demo_id: str,
    title: str = Form(default=""),
    tooltip: str = Form(default=""),
    position: Optional[int] = Form(default=None),
    image: Optional[UploadFile] = File(default=None),
):
    # Verify demo exists
    if not db.get_demo(demo_id):
        raise HTTPException(404, "Demo not found")

    step = db.create_step(demo_id=demo_id, title=title, tooltip=tooltip, position=position)
    step_id = step["id"]

    # Handle optional screenshot upload
    if image and image.filename:
        file_bytes = await image.read()
        image_path = storage.save_screenshot(demo_id, step_id, file_bytes, image.filename)
        step = db.update_step(step_id, image_path=image_path)

    return step


@app.patch("/api/demos/{demo_id}/steps/{step_id}")
async def update_step(
    demo_id: str,
    step_id: str,
    title: Optional[str] = Form(default=None),
    tooltip: Optional[str] = Form(default=None),
    position: Optional[int] = Form(default=None),
    image: Optional[UploadFile] = File(default=None),
):
    step = db.get_step(step_id)
    if not step or step["demo_id"] != demo_id:
        raise HTTPException(404, "Step not found")

    if image and image.filename:
        # Remove old screenshot before saving new one
        storage.delete_step_screenshot(demo_id, step_id)
        file_bytes = await image.read()
        image_path = storage.save_screenshot(demo_id, step_id, file_bytes, image.filename)
    else:
        image_path = None

    return db.update_step(step_id, title=title, tooltip=tooltip, image_path=image_path, position=position)


@app.delete("/api/demos/{demo_id}/steps/{step_id}")
def delete_step(demo_id: str, step_id: str):
    step = db.get_step(step_id)
    if not step or step["demo_id"] != demo_id:
        raise HTTPException(404, "Step not found")
    storage.delete_step_screenshot(demo_id, step_id)
    db.delete_step(step_id)
    return {"status": "deleted"}


@app.post("/api/demos/{demo_id}/steps/reorder")
def reorder_steps(demo_id: str, body: ReorderRequest):
    if not db.get_demo(demo_id):
        raise HTTPException(404, "Demo not found")
    db.reorder_steps(demo_id, body.order)
    return {"status": "ok"}


# ══════════════════════════════════════════════════════════════════
# API — Hotspots
# ══════════════════════════════════════════════════════════════════

@app.post("/api/steps/{step_id}/hotspots", status_code=201)
def create_hotspot(step_id: str, body: HotspotCreate):
    if not db.get_step(step_id):
        raise HTTPException(404, "Step not found")
    return db.create_hotspot(
        step_id=step_id, label=body.label,
        x=body.x, y=body.y, width=body.width, height=body.height,
        action_type=body.action_type, action_target=body.action_target
    )

@app.patch("/api/steps/{step_id}/hotspots/{hotspot_id}")
def update_hotspot(step_id: str, hotspot_id: str, body: HotspotUpdate):
    hs = db.get_hotspot(hotspot_id)
    if not hs or hs["step_id"] != step_id:
        raise HTTPException(404, "Hotspot not found")
    return db.update_hotspot(
        hotspot_id, label=body.label, x=body.x, y=body.y,
        width=body.width, height=body.height,
        action_type=body.action_type, action_target=body.action_target
    )

@app.delete("/api/steps/{step_id}/hotspots/{hotspot_id}")
def delete_hotspot(step_id: str, hotspot_id: str):
    hs = db.get_hotspot(hotspot_id)
    if not hs or hs["step_id"] != step_id:
        raise HTTPException(404, "Hotspot not found")
    db.delete_hotspot(hotspot_id)
    return {"status": "deleted"}

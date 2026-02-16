"""
tryMe — Pydantic request/response models
"""
from pydantic import BaseModel
from typing import Optional, List


# ── Hotspot ──────────────────────────────────────────────────────

class HotspotCreate(BaseModel):
    label: str = ""
    x: float
    y: float
    width: float
    height: float
    action_type: str = "next"          # "next" | "goto" | "end"
    action_target: Optional[str] = None  # step_id if action_type == "goto"


class HotspotUpdate(BaseModel):
    label: Optional[str] = None
    x: Optional[float] = None
    y: Optional[float] = None
    width: Optional[float] = None
    height: Optional[float] = None
    action_type: Optional[str] = None
    action_target: Optional[str] = None


class HotspotResponse(BaseModel):
    id: str
    step_id: str
    label: str
    x: float
    y: float
    width: float
    height: float
    action_type: str
    action_target: Optional[str]
    created_at: float


# ── Step ─────────────────────────────────────────────────────────

class StepCreate(BaseModel):
    title: str = ""
    tooltip: str = ""
    position: Optional[int] = None


class StepUpdate(BaseModel):
    title: Optional[str] = None
    tooltip: Optional[str] = None
    position: Optional[int] = None


class StepResponse(BaseModel):
    id: str
    demo_id: str
    position: int
    title: str
    tooltip: str
    image_path: str
    hotspots: List[HotspotResponse] = []
    created_at: float
    updated_at: float


# ── Demo ─────────────────────────────────────────────────────────

class DemoCreate(BaseModel):
    title: str
    description: str = ""
    personas: List[str] = []


class DemoUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    personas: Optional[List[str]] = None


class DemoResponse(BaseModel):
    id: str
    title: str
    description: str
    personas: List[str]
    created_at: float
    updated_at: float
    step_count: int = 0


class DemoFull(DemoResponse):
    steps: List[StepResponse] = []


# ── Reorder ──────────────────────────────────────────────────────

class ReorderRequest(BaseModel):
    order: List[str]   # list of step_ids in desired order

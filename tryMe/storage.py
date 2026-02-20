"""
tryMe — File storage helpers
Screenshots are saved under uploads/{demo_id}/{step_id}.{ext}
FastAPI mounts /uploads as a StaticFiles directory so they're served directly.
"""
import os
import shutil
from typing import Optional

UPLOADS_DIR = os.path.join(os.path.expanduser("~"), "tryMe-uploads")


def ensure_uploads_dir():
    os.makedirs(UPLOADS_DIR, exist_ok=True)


def demo_dir(demo_id: str) -> str:
    return os.path.join(UPLOADS_DIR, demo_id)


def save_screenshot(demo_id: str, step_id: str, file_bytes: bytes, original_filename: str) -> str:
    """
    Save screenshot bytes to uploads/{demo_id}/{step_id}.{ext}.
    Returns the URL path: /uploads/{demo_id}/{step_id}.{ext}
    """
    ext = _safe_ext(original_filename)
    dir_path = demo_dir(demo_id)
    os.makedirs(dir_path, exist_ok=True)
    file_name = f"{step_id}{ext}"
    file_path = os.path.join(dir_path, file_name)
    with open(file_path, "wb") as f:
        f.write(file_bytes)
    return f"/uploads/{demo_id}/{file_name}"


def delete_step_screenshot(demo_id: str, step_id: str):
    """Delete any screenshot file for a given step (all extensions)."""
    dir_path = demo_dir(demo_id)
    if not os.path.isdir(dir_path):
        return
    for fname in os.listdir(dir_path):
        name_no_ext = os.path.splitext(fname)[0]
        if name_no_ext == step_id:
            try:
                os.remove(os.path.join(dir_path, fname))
            except OSError:
                pass


def copy_demo_uploads(source_demo_id: str, dest_demo_id: str) -> dict:
    """
    Copy all screenshot files from uploads/{source_demo_id}/ to uploads/{dest_demo_id}/.
    Returns a mapping of old filename → new path so the DB can be updated.
    """
    src_dir  = demo_dir(source_demo_id)
    dest_dir = demo_dir(dest_demo_id)
    mapping  = {}   # old /uploads/src/file.ext → new /uploads/dest/file.ext
    if not os.path.isdir(src_dir):
        return mapping
    os.makedirs(dest_dir, exist_ok=True)
    for fname in os.listdir(src_dir):
        src_path  = os.path.join(src_dir, fname)
        dest_path = os.path.join(dest_dir, fname)
        shutil.copy2(src_path, dest_path)
        mapping[f"/uploads/{source_demo_id}/{fname}"] = f"/uploads/{dest_demo_id}/{fname}"
    return mapping


def delete_demo_uploads(demo_id: str):
    """Remove the entire uploads/{demo_id}/ directory."""
    dir_path = demo_dir(demo_id)
    if os.path.isdir(dir_path):
        shutil.rmtree(dir_path, ignore_errors=True)


def _safe_ext(filename: str) -> str:
    """Return a safe lowercase extension like .png or .jpg. Default .png."""
    _, ext = os.path.splitext(filename or "")
    ext = ext.lower()
    if ext in (".png", ".jpg", ".jpeg", ".gif", ".webp"):
        return ext
    return ".png"

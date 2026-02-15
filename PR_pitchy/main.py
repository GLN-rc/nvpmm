"""
PR Pitchy - Main FastAPI Application
Analyzes news content and brand docs to generate personalized PR pitches.
"""

import os
import tempfile
from typing import Optional
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Reuse document processor from web-scanner
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'web-scanner'))
from document_processor import DocumentProcessor, BrandContextBuilder

from pitcher import PRPitcher
from publication_finder import PublicationFinder

app = FastAPI(
    title="PR Pitchy",
    description="AI-powered PR pitch generator for B2B tech",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    return FileResponse("static/index.html")


@app.post("/api/pitch")
async def generate_pitches(
    news_docs: list[UploadFile] = File(default=[]),
    brand_docs: list[UploadFile] = File(default=[]),
    extra_context: Optional[str] = Form(default=""),
    tier_filter: Optional[int] = Form(default=2),
):
    """
    Main endpoint. Accepts:
    - news_docs: the announcement, press release, survey data, research, etc.
    - brand_docs: messaging guide, sales deck, positioning doc, etc.
    - extra_context: any free-text notes about goals, target audience, timing
    - tier_filter: 1 = top-tier only, 2 = all publications
    """
    doc_processor = DocumentProcessor()
    brand_builder = BrandContextBuilder()
    pitcher = PRPitcher()
    pub_finder = PublicationFinder()

    # Process brand docs
    brand_doc_list = []
    for doc in brand_docs:
        if not doc.filename:
            continue
        ext = os.path.splitext(doc.filename)[1]
        content_bytes = await doc.read()
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            tmp.write(content_bytes)
            tmp_path = tmp.name
        try:
            extracted = doc_processor.extract_content(tmp_path, doc.filename)
            brand_doc_list.append({"filename": doc.filename, "content": extracted.get("content", "")})
        finally:
            os.unlink(tmp_path)

    # Process news docs
    news_parts = []
    for doc in news_docs:
        if not doc.filename:
            continue
        ext = os.path.splitext(doc.filename)[1]
        content_bytes = await doc.read()
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            tmp.write(content_bytes)
            tmp_path = tmp.name
        try:
            extracted = doc_processor.extract_content(tmp_path, doc.filename)
            news_parts.append(f"[From: {doc.filename}]\n{extracted.get('content', '')}")
        finally:
            os.unlink(tmp_path)

    # Combine news content
    news_content = "\n\n".join(news_parts)
    if extra_context:
        news_content = f"[Additional context from user]\n{extra_context}\n\n{news_content}"

    if not news_content.strip():
        return {"status": "error", "message": "Please provide news content to pitch."}

    # Build brand context
    brand_context_obj = brand_builder.build_context(brand_doc_list)
    brand_context = brand_context_obj.get("combined_content", "No brand documents uploaded.")

    # Scan publications for recent coverage
    pub_summaries, recent_articles = await pub_finder.scan_publications(
        tier_filter=tier_filter
    )

    # Generate analysis and pitches
    result = await pitcher.analyze_and_pitch(
        brand_context=brand_context,
        news_content=news_content,
        publication_summaries=pub_summaries,
        recent_headlines=recent_articles,
    )

    return {
        "status": "success",
        "news_analysis": result["news_analysis"],
        "targets": result["targets"],
        "publication_count": len(pub_summaries),
        "articles_scanned": len(recent_articles),
    }


@app.get("/api/publications")
async def list_publications():
    """Return the full curated publication list."""
    from publication_finder import PUBLICATIONS
    return {"publications": PUBLICATIONS}


@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "service": "PR Pitchy"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)

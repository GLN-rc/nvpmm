"""
Website Competitor Scanner - Main FastAPI Application
Analyzes your website, competitors, and brand documents to provide
SEO/GEO/LLM discoverability optimization suggestions.
"""

import os
import tempfile
from typing import Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from scraper import WebsiteScraper
from analyzer import OptimizationAnalyzer
from document_processor import DocumentProcessor

app = FastAPI(
    title="Website Competitor Scanner",
    description="Scan your website and competitors to get AI-powered optimization suggestions",
    version="1.0.0"
)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")


class ScanRequest(BaseModel):
    your_website: str
    competitor_urls: list[str]
    focus_areas: Optional[list[str]] = None


class AnalysisResponse(BaseModel):
    status: str
    your_site_analysis: dict
    competitor_analyses: list[dict]
    recommendations: list[dict]
    priority_actions: list[dict]


@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    """Serve the main frontend application."""
    return FileResponse("static/index.html")


@app.post("/api/scan", response_model=AnalysisResponse)
async def scan_websites(
    your_website: str = Form(...),
    competitor_urls: str = Form(...),  # Comma-separated
    focus_areas: Optional[str] = Form(None),
    brand_docs: list[UploadFile] = File(default=[])
):
    """
    Scan your website and competitor websites, analyze uploaded documents,
    and return prioritized optimization suggestions.
    """
    try:
        scraper = WebsiteScraper()
        analyzer = OptimizationAnalyzer()
        doc_processor = DocumentProcessor()

        # Parse competitor URLs
        competitors = [url.strip() for url in competitor_urls.split(",") if url.strip()]

        # Parse focus areas if provided
        areas = []
        if focus_areas:
            areas = [area.strip() for area in focus_areas.split(",") if area.strip()]

        # Scrape your website
        your_site_data = await scraper.analyze_website(your_website)

        # Scrape competitor websites
        competitor_data = []
        for comp_url in competitors[:5]:  # Limit to 5 competitors
            try:
                comp_analysis = await scraper.analyze_website(comp_url)
                competitor_data.append(comp_analysis)
            except Exception as e:
                competitor_data.append({
                    "url": comp_url,
                    "error": str(e),
                    "status": "failed"
                })

        # Process uploaded documents (temporary, no storage)
        brand_context = []
        for doc in brand_docs:
            if doc.filename:
                # Create temp file, process, then delete
                with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(doc.filename)[1]) as tmp:
                    content = await doc.read()
                    tmp.write(content)
                    tmp_path = tmp.name

                try:
                    doc_content = doc_processor.extract_content(tmp_path, doc.filename)
                    brand_context.append({
                        "filename": doc.filename,
                        "content": doc_content
                    })
                finally:
                    # Clean up temp file
                    os.unlink(tmp_path)

        # Generate optimization recommendations
        recommendations = await analyzer.generate_recommendations(
            your_site=your_site_data,
            competitors=competitor_data,
            brand_documents=brand_context,
            focus_areas=areas
        )

        return AnalysisResponse(
            status="success",
            your_site_analysis=your_site_data,
            competitor_analyses=competitor_data,
            recommendations=recommendations["recommendations"],
            priority_actions=recommendations["priority_actions"]
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/quick-scan")
async def quick_scan(request: ScanRequest):
    """Quick scan without file uploads - JSON API."""
    scraper = WebsiteScraper()
    analyzer = OptimizationAnalyzer()

    your_site_data = await scraper.analyze_website(request.your_website)

    competitor_data = []
    for comp_url in request.competitor_urls[:5]:
        try:
            comp_analysis = await scraper.analyze_website(comp_url)
            competitor_data.append(comp_analysis)
        except Exception as e:
            competitor_data.append({
                "url": comp_url,
                "error": str(e),
                "status": "failed"
            })

    recommendations = await analyzer.generate_recommendations(
        your_site=your_site_data,
        competitors=competitor_data,
        brand_documents=[],
        focus_areas=request.focus_areas or []
    )

    return {
        "status": "success",
        "your_site_analysis": your_site_data,
        "competitor_analyses": competitor_data,
        "recommendations": recommendations["recommendations"],
        "priority_actions": recommendations["priority_actions"]
    }


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "Website Competitor Scanner"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

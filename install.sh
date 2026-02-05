#!/bin/bash
# Website Competitor Scanner - One-Click Installer
# Run: curl -sL [url] | bash  OR  bash install.sh

set -e
echo "Creating Website Competitor Scanner..."

mkdir -p ~/website-scanner/static/css ~/website-scanner/static/js
cd ~/website-scanner

# requirements.txt
cat > requirements.txt << 'EOF'
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
python-multipart>=0.0.6
aiohttp>=3.9.0
beautifulsoup4>=4.12.0
lxml>=4.9.0
readability-lxml>=0.8.0
tldextract>=5.0.0
python-dotenv>=1.0.0
pydantic>=2.0.0
EOF

# run.py
cat > run.py << 'EOF'
import os, sys
os.chdir(os.path.dirname(os.path.abspath(__file__)))
if __name__ == "__main__":
    import uvicorn
    print("\n" + "="*50)
    print("  Website Competitor Scanner")
    print("  Open: http://localhost:8000")
    print("="*50 + "\n")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
EOF

# main.py (FastAPI app)
cat > main.py << 'EOF'
from fastapi import FastAPI, Form, File, UploadFile, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import asyncio

app = FastAPI(title="Website Competitor Scanner")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.mount("/static", StaticFiles(directory="static"), name="static")

from scraper import WebsiteScraper
from analyzer import OptimizationAnalyzer

@app.get("/")
async def home():
    return FileResponse("static/index.html")

@app.get("/api/health")
async def health():
    return {"status": "healthy"}

@app.post("/api/scan")
async def scan(
    your_website: str = Form(...),
    competitor_urls: str = Form(""),
    focus_areas: Optional[str] = Form(None),
    brand_docs: list[UploadFile] = File(default=[])
):
    scraper = WebsiteScraper()
    analyzer = OptimizationAnalyzer()

    your_site = await scraper.analyze_website(your_website)
    competitors = [url.strip() for url in competitor_urls.split(",") if url.strip()]

    comp_data = []
    for url in competitors[:5]:
        try:
            comp_data.append(await scraper.analyze_website(url))
        except:
            comp_data.append({"url": url, "status": "failed"})

    areas = [a.strip() for a in (focus_areas or "").split(",") if a.strip()]
    recs = await analyzer.generate_recommendations(your_site, comp_data, [], areas)

    return {
        "status": "success",
        "your_site_analysis": your_site,
        "competitor_analyses": comp_data,
        "recommendations": recs["recommendations"],
        "priority_actions": recs["priority_actions"]
    }
EOF

# scraper.py
cat > scraper.py << 'EOF'
import asyncio, re
from urllib.parse import urlparse
import aiohttp
from bs4 import BeautifulSoup

class WebsiteScraper:
    def __init__(self):
        self.timeout = aiohttp.ClientTimeout(total=30)
        self.headers = {"User-Agent": "Mozilla/5.0 (compatible; WebsiteAnalyzer/1.0)"}

    async def analyze_website(self, url: str) -> dict:
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"

        result = {"url": url, "status": "success", "seo_factors": {}, "technical_factors": {},
                  "llm_discoverability": {}, "geo_factors": {}, "issues": [], "strengths": []}

        try:
            async with aiohttp.ClientSession(timeout=self.timeout, headers=self.headers) as session:
                async with session.get(url, allow_redirects=True, ssl=False) as resp:
                    html = await resp.text()
                    result["http_status"] = resp.status

            soup = BeautifulSoup(html, "lxml")
            result["seo_factors"] = self._analyze_seo(soup)
            result["technical_factors"] = {"https": url.startswith("https")}
            result["llm_discoverability"] = self._analyze_llm(soup)
            result["geo_factors"] = self._analyze_geo(soup)
            result["issues"], result["strengths"] = self._compile_findings(result)
        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)

        return result

    def _analyze_seo(self, soup):
        seo = {"title": None, "title_length": 0, "meta_description": None,
               "meta_description_length": 0, "h1_tags": [], "h2_tags": [],
               "images_without_alt": 0, "images_total": 0, "word_count": 0}

        title = soup.find("title")
        if title:
            seo["title"] = title.get_text(strip=True)
            seo["title_length"] = len(seo["title"])

        meta = soup.find("meta", attrs={"name": "description"})
        if meta and meta.get("content"):
            seo["meta_description"] = meta["content"]
            seo["meta_description_length"] = len(seo["meta_description"])

        for h1 in soup.find_all("h1"):
            seo["h1_tags"].append(h1.get_text(strip=True)[:100])
        for h2 in soup.find_all("h2"):
            seo["h2_tags"].append(h2.get_text(strip=True)[:100])

        for img in soup.find_all("img"):
            seo["images_total"] += 1
            if not img.get("alt"):
                seo["images_without_alt"] += 1

        seo["word_count"] = len(soup.get_text(separator=" ", strip=True).split())
        return seo

    def _analyze_llm(self, soup):
        llm = {"structured_content": False, "faq_schema": False}
        if len(soup.find_all(["h1", "h2", "h3"])) >= 3:
            llm["structured_content"] = True
        for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
            if "faqpage" in script.get_text().lower():
                llm["faq_schema"] = True
        return llm

    def _analyze_geo(self, soup):
        geo = {"statistics_present": False, "lists_and_bullets": 0, "citation_ready": False}
        text = soup.get_text()
        if re.search(r"\d+%|\d+ percent|\d+\s*(million|billion)", text, re.I):
            geo["statistics_present"] = True
        geo["lists_and_bullets"] = len(soup.find_all(["ul", "ol"]))
        geo["citation_ready"] = geo["statistics_present"] and geo["lists_and_bullets"] > 2
        return geo

    def _compile_findings(self, result):
        issues, strengths = [], []
        seo = result.get("seo_factors", {})

        if not seo.get("title"):
            issues.append({"category": "SEO", "severity": "high", "issue": "Missing page title"})
        elif seo.get("title_length", 0) > 60:
            issues.append({"category": "SEO", "severity": "medium", "issue": "Title too long (>60 chars)"})

        if not seo.get("meta_description"):
            issues.append({"category": "SEO", "severity": "high", "issue": "Missing meta description"})

        if len(seo.get("h1_tags", [])) == 0:
            issues.append({"category": "SEO", "severity": "high", "issue": "No H1 tag found"})
        elif len(seo.get("h1_tags", [])) > 1:
            issues.append({"category": "SEO", "severity": "medium", "issue": "Multiple H1 tags found"})

        if seo.get("images_without_alt", 0) > 0:
            issues.append({"category": "SEO", "severity": "medium", "issue": f"{seo['images_without_alt']} images missing alt text"})

        if not result.get("geo_factors", {}).get("statistics_present"):
            issues.append({"category": "GEO", "severity": "medium", "issue": "No statistics found for AI citations"})

        if not result.get("llm_discoverability", {}).get("faq_schema"):
            issues.append({"category": "LLM", "severity": "low", "issue": "No FAQ schema markup"})

        if seo.get("title") and 30 <= seo.get("title_length", 0) <= 60:
            strengths.append({"category": "SEO", "strength": "Good title length"})
        if result.get("technical_factors", {}).get("https"):
            strengths.append({"category": "Technical", "strength": "Using HTTPS"})

        return issues, strengths
EOF

# analyzer.py
cat > analyzer.py << 'EOF'
class OptimizationAnalyzer:
    async def generate_recommendations(self, your_site, competitors, docs, focus_areas):
        recs = []
        rec_id = 1
        issues = your_site.get("issues", [])
        geo = your_site.get("geo_factors", {})
        llm = your_site.get("llm_discoverability", {})

        for issue in issues:
            if issue.get("severity") == "high":
                recs.append({
                    "id": rec_id, "category": issue["category"],
                    "title": f"Fix: {issue['issue']}", "description": f"Critical: {issue['issue']}",
                    "impact": "high", "effort": "low",
                    "specific_actions": [f"Resolve: {issue['issue']}"],
                    "expected_outcome": "Improved visibility"
                })
                rec_id += 1

        if not geo.get("citation_ready"):
            recs.append({
                "id": rec_id, "category": "GEO",
                "title": "Optimize for AI Citations",
                "description": "Add statistics and structured content for AI engines to cite",
                "impact": "high", "effort": "medium",
                "specific_actions": [
                    "Add statistics with specific numbers",
                    "Include expert quotes with attribution",
                    "Use bulleted lists for key points"
                ],
                "expected_outcome": "Higher chance of AI citation"
            })
            rec_id += 1

        if not llm.get("faq_schema"):
            recs.append({
                "id": rec_id, "category": "LLM",
                "title": "Add FAQ Schema",
                "description": "Implement FAQ structured data for AI search",
                "impact": "high", "effort": "low",
                "specific_actions": [
                    "Create FAQ section with common questions",
                    "Add FAQPage JSON-LD markup",
                    "Write questions as users ask them"
                ],
                "expected_outcome": "Better AI search visibility"
            })
            rec_id += 1

        if not llm.get("structured_content"):
            recs.append({
                "id": rec_id, "category": "LLM",
                "title": "Improve Content Structure",
                "description": "Use clear headings for LLM parsing",
                "impact": "high", "effort": "low",
                "specific_actions": [
                    "Use H1 > H2 > H3 hierarchy",
                    "Start sections with summaries",
                    "Add bullet points for features"
                ],
                "expected_outcome": "Better AI content extraction"
            })
            rec_id += 1

        priority = []
        for i, r in enumerate(sorted(recs, key=lambda x: (x["impact"]=="high", x["effort"]=="low"), reverse=True)[:5]):
            priority.append({
                "priority": i+1, "title": r["title"], "category": r["category"],
                "impact": r["impact"], "effort": r["effort"],
                "first_step": r["specific_actions"][0] if r["specific_actions"] else ""
            })

        return {"recommendations": recs, "priority_actions": priority}
EOF

# static/index.html
cat > static/index.html << 'EOF'
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Website Competitor Scanner</title>
    <link rel="stylesheet" href="/static/css/styles.css">
</head>
<body>
    <header><div class="container">
        <h1>Website Competitor Scanner</h1>
        <p>Analyze your website for SEO, GEO & LLM optimization opportunities</p>
    </div></header>
    <main><div class="container">
        <section id="input-section">
            <form id="scan-form">
                <div class="card">
                    <h2>Your Website</h2>
                    <input type="url" id="your-website" placeholder="https://yoursite.com" required>
                </div>
                <div class="card">
                    <h2>Competitors (optional)</h2>
                    <textarea id="competitor-urls" rows="3" placeholder="https://competitor1.com&#10;https://competitor2.com"></textarea>
                </div>
                <button type="submit" class="btn-primary">Analyze Website</button>
            </form>
        </section>
        <section id="loading" style="display:none;text-align:center;padding:40px;">
            <div class="spinner"></div>
            <p>Analyzing websites...</p>
        </section>
        <section id="results" style="display:none;">
            <div class="card">
                <h2>Priority Actions</h2>
                <div id="priority-list"></div>
            </div>
            <div class="card">
                <h2>All Recommendations</h2>
                <div id="recommendations-list"></div>
            </div>
            <div class="card">
                <h2>Site Analysis</h2>
                <div id="site-analysis"></div>
            </div>
            <button onclick="location.reload()" class="btn-secondary">New Scan</button>
        </section>
    </div></main>
    <script src="/static/js/app.js"></script>
</body>
</html>
EOF

# static/css/styles.css
cat > static/css/styles.css << 'EOF'
:root {
    --olive: #708238;
    --olive-dark: #5a6a2c;
    --persimmon: #ec5800;
    --ivory: #faf9f6;
    --grey: #4a4a4a;
    --grey-light: #e5e5e5;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: var(--ivory); color: var(--grey); line-height: 1.6; }
.container { max-width: 900px; margin: 0 auto; padding: 0 20px; }
header { background: linear-gradient(135deg, var(--olive), var(--olive-dark)); color: white; padding: 30px 0; margin-bottom: 30px; }
header h1 { font-size: 1.8rem; margin-bottom: 5px; }
header p { opacity: 0.9; }
.card { background: white; border-radius: 12px; padding: 25px; margin-bottom: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }
.card h2 { color: var(--olive-dark); font-size: 1.2rem; margin-bottom: 15px; }
input, textarea { width: 100%; padding: 12px; border: 2px solid var(--grey-light); border-radius: 8px; font-size: 1rem; margin-bottom: 10px; }
input:focus, textarea:focus { outline: none; border-color: var(--olive); }
.btn-primary { background: var(--persimmon); color: white; border: none; padding: 15px 40px; font-size: 1.1rem; border-radius: 8px; cursor: pointer; width: 100%; font-weight: 600; }
.btn-primary:hover { background: #d14e00; }
.btn-secondary { background: var(--olive); color: white; border: none; padding: 12px 30px; border-radius: 8px; cursor: pointer; margin-top: 20px; }
.spinner { width: 40px; height: 40px; border: 4px solid var(--grey-light); border-top-color: var(--persimmon); border-radius: 50%; animation: spin 1s linear infinite; margin: 0 auto 15px; }
@keyframes spin { to { transform: rotate(360deg); } }
.priority-item { display: flex; gap: 15px; padding: 15px; border: 2px solid var(--grey-light); border-radius: 8px; margin-bottom: 10px; }
.priority-num { background: var(--persimmon); color: white; width: 30px; height: 30px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold; flex-shrink: 0; }
.priority-content h4 { margin-bottom: 5px; }
.priority-content p { font-size: 0.9rem; color: #666; }
.rec { border: 1px solid var(--grey-light); border-radius: 8px; padding: 15px; margin-bottom: 10px; }
.rec h4 { color: var(--olive-dark); margin-bottom: 8px; }
.rec .badges { margin-bottom: 10px; }
.badge { display: inline-block; padding: 3px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 600; margin-right: 5px; }
.badge-cat { background: var(--olive); color: white; }
.badge-high { background: var(--persimmon); color: white; }
.badge-medium { background: #f59e0b; color: white; }
.badge-low { background: #6b7280; color: white; }
.actions { background: #f5f5f5; padding: 10px; border-radius: 6px; margin-top: 10px; }
.actions h5 { font-size: 0.85rem; margin-bottom: 8px; }
.actions li { font-size: 0.85rem; margin-left: 20px; }
.metric { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid var(--grey-light); }
.metric:last-child { border-bottom: none; }
.good { color: var(--olive); font-weight: 600; }
.bad { color: var(--persimmon); font-weight: 600; }
EOF

# static/js/app.js
cat > static/js/app.js << 'EOF'
document.getElementById('scan-form').addEventListener('submit', async (e) => {
    e.preventDefault();

    const url = document.getElementById('your-website').value;
    const competitors = document.getElementById('competitor-urls').value;

    document.getElementById('input-section').style.display = 'none';
    document.getElementById('loading').style.display = 'block';

    const formData = new FormData();
    formData.append('your_website', url);
    formData.append('competitor_urls', competitors.replace(/\n/g, ','));

    try {
        const resp = await fetch('/api/scan', { method: 'POST', body: formData });
        const data = await resp.json();

        document.getElementById('loading').style.display = 'none';
        document.getElementById('results').style.display = 'block';

        // Priority actions
        const priorityHtml = (data.priority_actions || []).map((p, i) => `
            <div class="priority-item">
                <div class="priority-num">${i + 1}</div>
                <div class="priority-content">
                    <h4>${p.title}</h4>
                    <p><span class="badge badge-cat">${p.category}</span> ${p.first_step}</p>
                </div>
            </div>
        `).join('');
        document.getElementById('priority-list').innerHTML = priorityHtml || '<p>No priority actions</p>';

        // Recommendations
        const recsHtml = (data.recommendations || []).map(r => `
            <div class="rec">
                <h4>${r.title}</h4>
                <div class="badges">
                    <span class="badge badge-cat">${r.category}</span>
                    <span class="badge badge-${r.impact}">Impact: ${r.impact}</span>
                </div>
                <p>${r.description}</p>
                ${r.specific_actions ? `<div class="actions"><h5>Actions:</h5><ul>${r.specific_actions.map(a => `<li>${a}</li>`).join('')}</ul></div>` : ''}
            </div>
        `).join('');
        document.getElementById('recommendations-list').innerHTML = recsHtml || '<p>No recommendations</p>';

        // Site analysis
        const seo = data.your_site_analysis?.seo_factors || {};
        const analysisHtml = `
            <div class="metric"><span>Title</span><span>${seo.title || 'Missing'}</span></div>
            <div class="metric"><span>Title Length</span><span class="${seo.title_length >= 30 && seo.title_length <= 60 ? 'good' : 'bad'}">${seo.title_length || 0} chars</span></div>
            <div class="metric"><span>Meta Description</span><span class="${seo.meta_description ? 'good' : 'bad'}">${seo.meta_description ? 'Present' : 'Missing'}</span></div>
            <div class="metric"><span>H1 Tags</span><span class="${seo.h1_tags?.length === 1 ? 'good' : 'bad'}">${seo.h1_tags?.length || 0}</span></div>
            <div class="metric"><span>Word Count</span><span>${seo.word_count || 0}</span></div>
            <div class="metric"><span>Images Missing Alt</span><span class="${seo.images_without_alt === 0 ? 'good' : 'bad'}">${seo.images_without_alt || 0}</span></div>
        `;
        document.getElementById('site-analysis').innerHTML = analysisHtml;

    } catch (err) {
        alert('Error: ' + err.message);
        location.reload();
    }
});
EOF

echo ""
echo "======================================"
echo "  Installation complete!"
echo "======================================"
echo ""
echo "  Now run:"
echo "    cd ~/website-scanner"
echo "    pip3 install -r requirements.txt"
echo "    python3 run.py"
echo ""
echo "  Then open: http://localhost:8000"
echo ""

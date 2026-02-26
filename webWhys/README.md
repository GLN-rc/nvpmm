# webWhys

**webWhys** is an open-source website and competitor analysis tool for marketers, PMs, and founders who want to understand *why* their site isn't showing up in search — or in AI answers.

Enter your URL and up to 5 competitor URLs. webWhys scrapes each page, analyzes SEO, GEO (Generative Engine Optimization), and LLM discoverability signals, and generates prioritized recommendations with AI-powered copy suggestions.

---

## What it analyzes

**Your site**
- Title tag, meta description, heading structure
- Word count, reading time, scannability score
- Images, internal/external link counts
- Structured data (JSON-LD, schema.org)
- Technical: HTTPS, sitemap, robots.txt, security headers
- LLM factors: FAQ schema, How-To schema, content freshness
- GEO factors: statistics, comparison tables, list/bullet use, citation-readiness
- Page messaging: primary headline, value proposition, audience signals, CTA language, tone

**Competitors**
- Same signals as above for each competitor URL
- Side-by-side comparison table with tooltips
- Messaging breakdown cards per site
- Keyword intelligence: what terms each competitor is optimizing for

**AI-powered output**
- Prioritized action list (impact × effort ranked)
- Ready-to-use copy suggestions for titles, H1s, meta descriptions, value props, and FAQs
- All recommendations filterable by category (SEO, AI Discoverability, Messaging, Technical, Competitive)
- Export to Word (.docx) for Google Docs

---

## Setup

**Requirements:** Python 3.9+, an OpenAI API key

```bash
git clone https://github.com/GLN-rc/nvpmm.git
cd nvpmm/webWhys

python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env               # then add your OpenAI key
python run.py
```

Open [http://localhost:8000](http://localhost:8000)

---

## Environment variables

Create a `.env` file:

```
OPENAI_API_KEY=sk-...
LLM_MODEL=gpt-4o-mini            # optional, defaults to gpt-4o-mini
```

You can use any model supported by [litellm](https://docs.litellm.ai) — Claude, Gemini, local Ollama, etc. Just change `LLM_MODEL`.

---

## How to use

1. Enter your website URL
2. Add 1–5 competitor URLs (one per line)
3. Optionally upload brand documents (PDF, DOCX, TXT, MD) — these make copy suggestions brand-accurate
4. Set focus areas if you want to prioritize specific categories (e.g., "LLM discoverability, technical SEO")
5. Click **Analyze Websites**

Results appear in 5 tabs:
- **Priority Actions** — top 5 highest-impact changes to make first
- **Copy Suggestions** — drop-in rewrites for titles, headlines, meta descriptions, FAQs
- **All Recommendations** — full list, filterable and sortable
- **Your Site Analysis** — metrics, issues, strengths
- **Competitor Comparison** — side-by-side table + messaging breakdown + keyword intelligence

---

## Notes

- Analysis runs on the homepage only (no deep crawl)
- Files uploaded for brand context are processed in memory and never stored
- Some competitor sites behind aggressive bot protection (Cloudflare, Vercel WAF) may return limited or no data — the tool will flag these clearly
- Typical scan time: 15–45 seconds depending on site complexity and number of competitors

---

## Stack

- **Backend:** Python, FastAPI, aiohttp, BeautifulSoup, litellm
- **Frontend:** Vanilla JS SPA, no build step required
- **LLM:** OpenAI gpt-4o-mini by default (configurable)
- **Export:** python-docx → .docx

---

## Part of the nvpmm toolkit

webWhys is one tool in a set of open-source PMM utilities at [github.com/GLN-rc/nvpmm](https://github.com/GLN-rc/nvpmm). Each tool is standalone and runs locally.

---

*Built by Nicole Scott / Grey Market Labs*

#!/usr/bin/env python3
"""
weekly_snapshot2.py — LIVE-only generator with strict scope + style, no 'email' asks

- Reads org context from YAML (+ optional notes) to constrain coverage.
- Strong style guide: short TL;DR, precise table, role-based actions (no 'email' tasks).
- UTF-8 output with a LIVE badge.
- Exits 1 if model returns empty/invalid (no canned fallback).
"""

import os, sys, re, json, textwrap
from datetime import date, datetime, timedelta, timezone

# --- Env ---
MODEL         = os.getenv("MODEL", "mistralai/mixtral-8x7b-instruct")
LLM_API_BASE  = os.getenv("LLM_API_BASE")
LLM_API_KEY   = os.getenv("LLM_API_KEY")
MAX_TOKENS    = int(os.getenv("MAX_TOKENS", "1600"))
TEMP          = float(os.getenv("TEMP", "0.19"))
OUTPUT_HTML   = os.getenv("OUTPUT_HTML", "report.html")
CONF_PATH     = os.getenv("SNAPSHOT_CONFIG", "config/company.yaml")
NOTES_PATH    = os.getenv("EXTRA_NOTES", "notes/weekly_signals.md")

# --- Date window ---
end = date.today()
start = end - timedelta(days=6)
WINDOW = f"{start:%b %d}–{end:%b %d, %Y}" if start.year == end.year else f"{start:%b %d, %Y}–{end:%b %d, %Y}"

# --- Helpers ---
def _badge() -> str:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
    return f'<div style="color:#0a0;font-size:12px;margin:10px 20px">Mode: <b>LIVE</b> • Model: {MODEL} • Generated: {ts}</div>'

def _unwrap_fences(s: str) -> str:
    s = s.strip()
    m = re.match(r"^```(?:html|HTML)?\s*(.*?)\s*```$", s, flags=re.DOTALL)
    return m.group(1).strip() if m else s

def _wrap_if_needed(html: str) -> str:
    if "<html" in html.lower() and "</html>" in html.lower():
        return html
    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>ReplicaRivals — Weekly Snapshot ({WINDOW})</title>
<style>
  body{{font-family:Inter,Arial,Helvetica,sans-serif;color:#111;background:#fff}}
  .container{{max-width:920px;margin:0 auto;border:1px solid #e5e7eb;border-radius:10px}}
  .section{{padding:18px 20px}}
  h2{{margin:0 0 6px;font-size:22px}}
  h3{{margin:0 0 8px;font-size:18px}}
  .tl-dr{{margin-top:10px;background:#f6f8fa;border:1px solid #e5e7eb;border-radius:8px;padding:12px}}
  table{{border-collapse:collapse;width:100%;font-size:14px}}
  th,td{{padding:8px;vertical-align:top}}
  thead tr{{background:#111;color:#fff}}
  tbody tr{{border-bottom:1px solid #e5e7eb}}
  .tag{{padding:2px 6px;border-radius:999px;display:inline-block;font-size:12px}}
  .tag-fyi{{background:#fef9c3;color:#854d0e}}
  .tag-watch{{background:#e0f2fe;color:#0369a1}}
  .tag-action{{background:#dcfce7;color:#166534}}
  a{{color:#0e4cf5;text-decoration:none}} a:hover{{text-decoration:underline}}
  .footer{{color:#666;font-size:12px}}
</style></head><body>
<div class="container"><div class="section">{html}</div></div>
</body></html>"""

def _write(html: str) -> None:
    final = html.replace("</body>", f"{_badge()}</body>") if "</body>" in html.lower() else (html + _badge())
    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(final)
    sys.stdout.write(final)

def _load_yaml(path: str) -> dict:
    import yaml
    if not os.path.exists(path): return {}
    with open(path, "r", encoding="utf-8") as f: return yaml.safe_load(f) or {}

def _load_text(path: str) -> str:
    if not os.path.exists(path): return ""
    with open(path, "r", encoding="utf-8", errors="replace") as f: return f.read().strip()

def _j(items): return "; ".join(items) if items else "(none)"

def _render_context(cfg: dict) -> str:
    company      = cfg.get("company_name") or "Replica"
    industry     = cfg.get("industry") or ""
    icps         = cfg.get("icps") or []
    regions      = cfg.get("regions") or []
    pillars      = cfg.get("product_pillars") or []
    anchors      = cfg.get("positioning_anchors") or [
        "Anonymous attack surface","Instant deployment",
        "Cross-team collaboration","Enterprise control with operational privacy"
    ]
    competitors  = cfg.get("competitors") or []
    ignore_comps = cfg.get("ignore_competitors") or []
    focus        = cfg.get("focus_areas") or []
    allowed_src  = cfg.get("allowed_sources") or []

    return "\n".join([
        f"Company: {company}",
        f"Industry: {industry}",
        f"ICPs/personas: {_j(icps)}",
        f"Regions: {_j(regions)}",
        f"Product pillars: {_j(pillars)}",
        f"Positioning anchors: {_j(anchors)}",
        f"Competitors of record (cover only these unless decisively material): {_j(competitors)}",
        f"Ignore/do not cover: {_j(ignore_comps)}",
        f"Priority focus areas: {_j(focus)}",
        f"Preferred source domains (prioritize): {_j(allowed_src)}",
    ])

def _build_prompts(cfg: dict, notes: str) -> tuple[str,str]:
    cx = _render_context(cfg)
    style = f"""
YOU ARE: A skeptical competitive intelligence analyst for Replica Cyber  (replicacyber.com).
GOAL: An exec-grade weekly brief a VP can scan in 60s. No fluff, no speculation. Mimic the Morning Brew stlye of newsletter. We want quick insights, food for thought and a cross-landscape view of changes that our customers will hear about. 

STRICT SCOPE:
- Include ONLY in-scope competitors/themes from COMPANY CONTEXT. Ignore everything else.
- Prefer links from preferred domains. No social screenshots, but links are ok. No blogs-of-blogs, but competitor blogs are resources are ok.

FORMAT (HTML ONLY):
1) Header with coverage window: "{WINDOW}".
2) TL;DR:
   • 3–4 bullets, ≤20 words each, state finding, reason, and impact to market.
3) Key Events (by Competitor):
   • Table columns EXACTLY: Date (ET), Competitor, Theme, What happened, Why it matters , Source
   • 3–8 rows. Tag ∈ {{FYI, Watch, Action}}.
   • Each row MUST include ≥1 direct, credible <a href="...">Source</a>.
4) Deltas vs. Prior Week: 2–4 bullets contrasting this vs last week.
5) Recommended Actions (by Function):
   • Exec, Sales, Marketing, Product. 1-2 bullets each.
   • DO NOT instruct to "email", "reach out via email", or include any email addresses.
   • Use concrete actions (who/what/outcome) when relevant, or just include food for thought based on findings.
6) Footer: concise sources list (domains OK) + positioning anchors.

QUALITY BAR (optimize for 5/5):
• Relevance: strictly in-scope competitors/themes; tie to ICP needs.
• Specificity: facts with dates/names/SKUs/docs; avoid vague claims.
• Impact: why it matters for win/loss, pricing, roadmap, or compliance.
• Brevity: keep TL;DR bullets ≤20 words; avoid repetition.
• Evidence: every table row cites a credible link (prefer: {_j(cfg.get('allowed_sources', []))}).

If a section has no updates, write "No material updates".
"""
    user = textwrap.dedent(f"""
COMPANY CONTEXT
---------------
{cx}

NOTES / SEEDS (optional)
------------------------
{notes if notes else "(none)"}

TASK
----
Generate this week's snapshot covering {WINDOW} for Exec, Sales, Marketing, Product.
Return HTML only (no ``` fences). Keep width under ~900px.
    """).strip()
    return style.strip(), user

def generate_html() -> str:
    if not (LLM_API_BASE and LLM_API_KEY):
        raise RuntimeError("LLM_API_BASE and LLM_API_KEY are required")

    cfg   = _load_yaml(CONF_PATH)
    notes = _load_text(NOTES_PATH)
    system, user = _build_prompts(cfg, notes)

    # Debug: show scope
    dbg = {k: cfg.get(k, []) for k in ("competitors","ignore_competitors","focus_areas")}
    print("[weekly_snapshot2] Context:", json.dumps(dbg), file=sys.stderr)

    from litellm import completion
    resp = completion(
        model=MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        api_base=LLM_API_BASE,
        api_key=LLM_API_KEY,
        custom_llm_provider="openai",
        extra_headers={
            "HTTP-Referer": "https://github.com/OWNER/REPO",
            "X-Title": "ReplicaRivals Weekly Snapshot"
        },
        temperature=TEMP,
        max_tokens=MAX_TOKENS,
    )
    content = (resp["choices"][0]["message"]["content"] or "").strip()
    content = _unwrap_fences(content)
    if not content:
        raise RuntimeError("Model returned empty content")
    html = _wrap_if_needed(content)

    # Hard guard: no emails in actions
    if re.search(r"(?i)\bemail\b", html):
        raise RuntimeError("Actions contain 'email' guidance; forbidden per spec")

    return html

def main() -> int:
    try:
        html = generate_html()
        _write(html)
        return 0
    except Exception as e:
        sys.stderr.write(f"[weekly_snapshot2] LIVE generation failed: {e}\n")
        # Minimal HTML error for artifact visibility; still fail
        try:
            with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
                f.write(f"<!doctype html><meta charset='utf-8'><pre>LIVE generation failed: {e}</pre>")
        except Exception:
            pass
        return 1

if __name__ == "__main__":
    sys.exit(main())

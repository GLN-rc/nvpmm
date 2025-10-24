#!/usr/bin/env python3
"""
weekly_snapshot2.py — LIVE generator w/ strict style guide (no canned fallback)

- Reads org context from YAML + optional notes
- Uses LiteLLM against an OpenAI-compatible endpoint (e.g., OpenRouter)
- Enforces scannable format via style/rubric instructions (no placeholders)
- Produces UTF-8 HTML with a small LIVE footer badge
"""

import os, sys, re, json, textwrap
from datetime import date, datetime, timedelta, timezone

# -------- Runtime config (env) --------
MODEL         = os.getenv("MODEL", "mistralai/mixtral-8x7b-instruct")
LLM_API_BASE  = os.getenv("LLM_API_BASE")
LLM_API_KEY   = os.getenv("LLM_API_KEY")
MAX_TOKENS    = int(os.getenv("MAX_TOKENS", "1500"))
TEMP          = float(os.getenv("TEMP", "0.25"))
OUTPUT_HTML   = os.getenv("OUTPUT_HTML", "report.html")
CONF_PATH     = os.getenv("SNAPSHOT_CONFIG", "config/company.yaml")
NOTES_PATH    = os.getenv("EXTRA_NOTES", "notes/weekly_signals.md")

# -------- Date window --------
end = date.today()
start = end - timedelta(days=6)
WINDOW_STR = f"{start:%b %d}–{end:%b %d, %Y}" if start.year == end.year else f"{start:%b %d, %Y}–{end:%b %d, %Y}"

# -------- Helpers --------
def _badge() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
    return f'<div style="color:#0a0;font-size:12px;margin:10px 20px">Mode: <b>LIVE</b> • Model: {MODEL} • Generated: {stamp}</div>'

def _unwrap_fences(s: str) -> str:
    s = s.strip()
    m = re.match(r"^```(?:html|HTML)?\s*(.*?)\s*```$", s, flags=re.DOTALL)
    return m.group(1).strip() if m else s

def _wrap_if_needed(html: str) -> str:
    if "<html" in html.lower() and "</html>" in html.lower():
        return html
    # Minimal, clean shell – email-safe CSS
    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>ReplicaRivals — Weekly Snapshot ({WINDOW_STR})</title>
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
</style>
</head><body>
<div class="container"><div class="section">{html}</div></div>
</body></html>"""

def _write(html: str) -> None:
    final = html.replace("</body>", f"{_badge()}</body>") if "</body>" in html.lower() else (html + _badge())
    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(final)
    sys.stdout.write(final)

def _load_yaml(path: str) -> dict:
    import yaml
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def _load_text(path: str) -> str:
    if not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read().strip()

def _j(items): 
    return "; ".join(items) if items else "(none)"

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

    lines = [
        f"Company: {company}",
        f"Industry: {industry}",
        f"ICPs/personas: {_j(icps)}",
        f"Regions: {_j(regions)}",
        f"Product pillars: {_j(pillars)}",
        f"Positioning anchors: {_j(anchors)}",
        f"Competitors of record (cover these, and only these unless decisively material): {_j(competitors)}",
        f"Ignore/do not cover: {_j(ignore_comps)}",
        f"Priority focus areas: {_j(focus)}",
        f"Preferred sources for links: {_j(allowed_src)}",
    ]
    return "\n".join(lines)

def _build_prompts(cfg: dict, notes: str) -> tuple[str, str]:
    context_block = _render_context(cfg)

    # ---- Style guide & rubric to force crisp, useful output ----
    style = f"""
YOU ARE: A skeptical competitive intelligence analyst for the company below.
GOAL: Produce an executive-grade weekly brief that a VP can scan in 60 seconds.

ABSOLUTE RULES:
- No placeholders. No speculation. Every claim must be specific and customer-relevant.
- Cover ONLY in-scope competitors and themes (see COMPANY CONTEXT). Ignore noise.
- Keep it tight and scannable; remove fluff and duplicate ideas.

FORMAT (HTML ONLY, NO MARKDOWN FENCES):
1) Header line with coverage window: "{WINDOW_STR}".
2) TL;DR:
   - 3–4 bullets, each ≤ 20 words, focusing on deltas vs prior state, impact, and urgency.
3) Key Events (by Competitor):
   - A table with EXACT columns: Date (ET), Competitor, Theme, What happened, Why it matters, Tag, Source.
   - 3–8 rows max. 'Tag' must be one of: FYI, Watch, Action.
   - 'Source' must include at least one working <a href="...">Name</a> link per row.
4) Deltas vs. Prior Week: 2–4 bullets that contrast this week vs last week.
5) Recommended Actions (by Function):
   - Exec, Sales, Marketing, Product. 2 bullets each.
   - Make actions specific & testable (who/what/expected impact).
6) Footer: cite sources list (domain names allowed) + positioning anchors.

SCORING RUBRIC (optimize your output to score 5/5 on each):
- Relevance (5): Only in-scope competitors/themes, clearly tied to ICP needs.
- Specificity (5): Concrete facts (dates, product names, SKUs, SKUs/tiers, SKUs/pricing, doc pages).
- Impact (5): Why it matters for pipeline, win/loss, pricing, or roadmap.
- Brevity (5): No bullet > 20 words in TL;DR; avoid repetition.
- Evidence (5): Every table row has a credible source link (prefer: {_j(cfg.get('allowed_sources', []))}).

If a section truly has no relevant updates this week, write: "No material updates."
"""
    user = textwrap.dedent(f"""
COMPANY CONTEXT
---------------
{context_block}

NOTES / SEEDS (optional)
------------------------
{notes if notes else "(none)"}

TASK
----
Generate this week's snapshot covering {WINDOW_STR} for Exec, Sales, Marketing, and Product.
Return HTML only (no ``` fences). Keep width under ~900px.
    """).strip()

    return style.strip(), user

def generate_html() -> str:
    if not (LLM_API_BASE and LLM_API_KEY):
        raise RuntimeError("LLM_API_BASE and LLM_API_KEY are required")

    cfg   = _load_yaml(CONF_PATH)
    notes = _load_text(NOTES_PATH)
    system, user = _build_prompts(cfg, notes)

    # Log the loaded scope for debugging
    dbg = {
        "competitors": cfg.get("competitors", []),
        "ignore_competitors": cfg.get("ignore_competitors", []),
        "focus_areas": cfg.get("focus_areas", []),
    }
    print("[weekly_snapshot2] Context:", json.dumps(dbg), file=sys.stderr)

    from litellm import completion
    resp = completion(
        model=MODEL,
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": user}],
        api_base=LLM_API_BASE,
        api_key=LLM_API_KEY,
        custom_llm_provider="openai",  # OpenAI-compatible endpoint (e.g., OpenRouter)
        extra_headers={
            "HTTP-Referer": "https://github.com/OWNER/REPO",
            "X-Title": "ReplicaRivals Weekly Snapshot"
        },
        temperature=TEMP,
        max_tokens=MAX_TOKENS,
    )
    content = resp["choices"][0]["message"]["content"] or ""
    content = _unwrap_fences(content).strip()
    if not content:
        raise RuntimeError("Model returned empty content")

    # Ensure we send valid HTML
    html = _wrap_if_needed(content)
    return html

def main() -> int:
    try:
        html = generate_html()
        _write(html)
        return 0
    except Exception as e:
        sys.stderr.write(f"[weekly_snapshot2] LIVE generation failed: {e}\n")
        # Emit minimal HTML error then fail
        try:
            with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
                f.write(f"<!doctype html><meta charset='utf-8'><pre>LIVE generation failed: {e}</pre>")
        except Exception:
            pass
        return 1

if __name__ == "__main__":
    sys.exit(main())

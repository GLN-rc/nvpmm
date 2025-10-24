#!/usr/bin/env python3
"""
weekly_snapshot2.py — LIVE generator with company config (no canned fallback)

- Loads org context from YAML (competitors, ICPs, pillars, allowed/ignored topics)
- Calls an OpenAI-compatible endpoint (e.g., OpenRouter) via LiteLLM
- Adds a small LIVE badge with model + timestamp
- Exits 1 on empty/invalid output (so CI catches issues)

Env (required):
  LLM_API_BASE (e.g., https://openrouter.ai/api/v1)
  LLM_API_KEY

Env (optional):
  MODEL            (default: mistralai/mixtral-8x7b-instruct)
  MAX_TOKENS       (default: 1500)
  TEMP             (default: 0.25)
  OUTPUT_HTML      (default: report.html)
  SNAPSHOT_CONFIG  (default: config/company.yaml)
  EXTRA_NOTES      (default: notes/weekly_signals.md)

Files (optional but recommended):
  config/company.yaml
  notes/weekly_signals.md
"""

import os, sys, re, textwrap, json
from datetime import date, datetime, timedelta, timezone

# ---------- Env ----------
MODEL = os.getenv("MODEL", "mistralai/mixtral-8x7b-instruct")
LLM_API_BASE = os.getenv("LLM_API_BASE")
LLM_API_KEY  = os.getenv("LLM_API_KEY")
MAX_TOKENS   = int(os.getenv("MAX_TOKENS", "1500"))
TEMP         = float(os.getenv("TEMP", "0.25"))
OUTPUT_HTML  = os.getenv("OUTPUT_HTML", "report.html")
CONF_PATH    = os.getenv("SNAPSHOT_CONFIG", "config/company.yaml")
NOTES_PATH   = os.getenv("EXTRA_NOTES", "notes/weekly_signals.md")

# ---------- Date window ----------
end = date.today()
start = end - timedelta(days=6)
window_str = f"{start:%b %d}–{end:%b %d, %Y}" if start.year == end.year else f"{start:%b %d, %Y}–{end:%b %d, %Y}"

# ---------- Utils ----------
def _badge(model: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
    return f'<div style="color:#0a0;font-size:12px;margin:10px 20px">Mode: <b>LIVE</b> • Model: {model} • Generated: {stamp}</div>'

def _unwrap_fences(s: str) -> str:
    s = s.strip()
    m = re.match(r"^```(?:html|HTML)?\s*(.*?)\s*```$", s, flags=re.DOTALL)
    return m.group(1).strip() if m else s

def _wrap_if_needed(html: str) -> str:
    if "<html" in html.lower() and "</html>" in html.lower():
        return html
    # Minimal shell around fragment (LIVE content)
    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>ReplicaRivals — Weekly Snapshot ({window_str})</title>
<style>
  body{{font-family:Inter,Arial,Helvetica,sans-serif;color:#111;background:#fff}}
  .container{{max-width:920px;margin:0 auto;border:1px solid #e5e7eb;border-radius:10px}}
  .section{{padding:18px 20px}}
  table{{border-collapse:collapse;width:100%}}
  th,td{{padding:8px;vertical-align:top;border-bottom:1px solid #e5e7eb}}
  .tl-dr{{background:#f6f8fa;border:1px solid #e5e7eb;border-radius:8px;padding:12px}}
  a{{color:#0e4cf5;text-decoration:none}} a:hover{{text-decoration:underline}}
</style>
</head><body><div class="container"><div class="section">
{html}
</div></div></body></html>"""

def _write(html: str) -> None:
    final = html.replace("</body>", f"{_badge(MODEL)}</body>") if "</body>" in html.lower() else (html + _badge(MODEL))
    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(final)
    sys.stdout.write(final)

def _load_yaml(path: str) -> dict:
    try:
        import yaml  # PyYAML
    except Exception as e:
        raise RuntimeError("PyYAML not installed; add pyyaml to your workflow") from e
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def _load_text(path: str) -> str:
    if not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read().strip()

def _render_context(cfg: dict) -> str:
    # Make compact bullet strings the model can follow
    company     = cfg.get("company_name") or "Replica (assumed)"
    industry    = cfg.get("industry") or ""
    icps        = cfg.get("icps") or []
    regions     = cfg.get("regions") or []
    pillars     = cfg.get("product_pillars") or []
    competitors = cfg.get("competitors") or []
    ignore_comps= cfg.get("ignore_competitors") or []
    focus       = cfg.get("focus_areas") or []
    banned      = cfg.get("out_of_scope") or []
    sources     = cfg.get("allowed_sources") or []
    # brand anchors (from your internal doc)
    anchors     = cfg.get("positioning_anchors") or [
        "Anonymous attack surface","Instant deployment",
        "Cross-team collaboration","Enterprise control with operational privacy"
    ]

    def j(items): return "; ".join(items) if items else "(none)"
    lines = [
        f"Company: {company}",
        f"Industry: {industry}",
        f"ICPs/personas: {j(icps)}",
        f"Regions: {j(regions)}",
        f"Product pillars: {j(pillars)}",
        f"Positioning anchors: {j(anchors)}",
        f"Competitors of record (cover these): {j(competitors)}",
        f"Ignore/do not cover: {j(ignore_comps)}",
        f"Priority focus areas: {j(focus)}",
        f"Out-of-scope (skip unless truly material): {j(banned)}",
        f"Allowed/priority sources (prefer these for links): {j(sources)}",
    ]
    return "\n".join(lines)

def _prompt(cfg: dict, notes: str) -> tuple[str,str]:
    context_block = _render_context(cfg)
    system = (
        "You are a competitive intelligence analyst for the company below.\n"
        "STRICTLY follow the provided competitor list and scope; do not include unrelated companies.\n"
        "Return EMAIL-READY HTML only (no markdown fences), with inline styles or simple tags.\n"
        "Must include sections:\n"
        " • TL;DR (bulleted)\n"
        " • Key Events table (Date, Competitor, Theme, What happened, Why it matters, Tag, Source link)\n"
        " • Deltas vs prior week\n"
        " • Recommended actions (Exec, Sales, Marketing, Product)\n"
        "Be concise, links must be direct and plausible; avoid placeholders, avoid speculation.\n"
        "If a required section has no material items this week, explicitly say 'No material updates'."
    )
    user = textwrap.dedent(f"""
        COMPANY CONTEXT
        ----------------
        {context_block}

        NOTES / SEEDS (optional)
        ------------------------
        {notes if notes else "(none)"}

        TASK
        ----
        Generate this week's snapshot covering {window_str}.
        Only include competitors/themes within scope. Keep width under ~900px.
        Return HTML only (no ``` fences).
    """).strip()
    return system, user

def generate_html() -> str:
    if not (LLM_API_BASE and LLM_API_KEY):
        raise RuntimeError("LLM_API_BASE and LLM_API_KEY are required")

    cfg   = _load_yaml(CONF_PATH)
    notes = _load_text(NOTES_PATH)
    system, user = _prompt(cfg, notes)

    # Log the loaded competitor list for debugging
    loaded = {
        "competitors": cfg.get("competitors", []),
        "ignore_competitors": cfg.get("ignore_competitors", []),
        "focus_areas": cfg.get("focus_areas", []),
    }
    print("[weekly_snapshot2] Loaded context:", json.dumps(loaded), file=sys.stderr)

    from litellm import completion
    resp = completion(
        model=MODEL,
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": user}],
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
    content = resp["choices"][0]["message"]["content"] or ""
    content = _unwrap_fences(content).strip()
    if not content:
        raise RuntimeError("Model returned empty content")
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

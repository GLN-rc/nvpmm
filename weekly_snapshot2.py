#!/usr/bin/env python3
"""
weekly_snapshot2.py — LIVE-only generator (no canned fallback)

- OpenRouter via LiteLLM (OpenAI-compatible /chat/completions)
- Saves raw model output to llm_raw.txt for debugging
- If model returns HTML fragment or fenced markdown, normalize to full HTML
- Adds a small LIVE badge with model + timestamp
- Exits 1 only if the model returns empty

Env:
  LLM_API_BASE  (e.g., https://openrouter.ai/api/v1)
  LLM_API_KEY
  MODEL         (default: mistralai/mixtral-8x7b-instruct)
  MAX_TOKENS    (default: 1500)
  TEMP          (default: 0.2)
  OUTPUT_HTML   (default: report.html)
"""

import os, sys, re, textwrap
from datetime import date, datetime, timedelta, timezone

MODEL = os.getenv("MODEL", "mistralai/mixtral-8x7b-instruct")
LLM_API_BASE = os.getenv("LLM_API_BASE")
LLM_API_KEY = os.getenv("LLM_API_KEY")
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "1500"))
TEMP = float(os.getenv("TEMP", "0.2"))
OUTPUT_HTML = os.getenv("OUTPUT_HTML", "report.html")

# Compute 7-day window
end = date.today()
start = end - timedelta(days=6)
window_str = f"{start:%b %d}–{end:%b %d, %Y}" if start.year == end.year else f"{start:%b %d, %Y}–{end:%b %d, %Y}"

def _badge() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
    return f'<div style="color:#0a0;font-size:12px;margin:10px 20px">Mode: <b>LIVE</b> • Model: {MODEL} • Generated: {stamp}</div>'

def _unwrap_fences(s: str) -> str:
    # Strip common markdown code fences like ```html ... ``` or ``` ... ```
    s = s.strip()
    fence = re.compile(r"^```(?:html|HTML)?\s*(.*?)\s*```$", re.DOTALL)
    m = fence.match(s)
    return m.group(1).strip() if m else s

def _wrap_if_needed(html: str) -> str:
    if "<html" in html.lower() and "</html>" in html.lower():
        return html
    # Minimal shell around a fragment (still LIVE content, not a canned template)
    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
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
</head><body>
<div class="container">
<div class="section">
{html}
</div>
</div>
</body></html>"""

def _write(html: str) -> None:
    badge = _badge()
    final = html.replace("</body>", f"{badge}</body>") if "</body>" in html.lower() else (html + badge)
    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(final)
    sys.stdout.write(final)

def _save_raw(raw: str) -> None:
    try:
        with open("llm_raw.txt", "w", encoding="utf-8") as f:
            f.write(raw)
    except Exception:
        pass

def generate_html() -> str:
    if not (LLM_API_BASE and LLM_API_KEY):
        raise RuntimeError("LLM_API_BASE and LLM_API_KEY are required")

    # Prompt tuned to force sections but allow the model to layout HTML freely
    system = (
        "You are a competitive intelligence analyst for ReplicaRivals. "
        "Return EMAIL-READY HTML only (no markdown fences), inline styles OK. "
        "Must include: a TL;DR list, a Key Events table (columns: Date, Competitor, Theme, "
        "What happened, Why it matters, Tag, Source), a short 'Deltas vs prior week', and "
        "role-based actions (Exec, Sales, Marketing, Product). Use concise bullets and direct links."
    )
    user = textwrap.dedent(f"""
        Generate the weekly snapshot covering {window_str}.
        Emphasize deltas vs prior week and include direct source links.
        IMPORTANT: Return HTML only (no ``` fences). Keep under ~900px width.
    """).strip()

    from litellm import completion
    resp = completion(
        model=MODEL,
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": user}],
        api_base=LLM_API_BASE,
        api_key=LLM_API_KEY,
        custom_llm_provider="openai",      # tell LiteLLM to use OpenAI-style endpoint
        extra_headers={
            "HTTP-Referer": "https://github.com/OWNER/REPO",
            "X-Title": "ReplicaRivals Weekly Snapshot"
        },
        temperature=TEMP,
        max_tokens=MAX_TOKENS,
    )
    content = resp["choices"][0]["message"]["content"] or ""
    _save_raw(content)
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
        # Emit a tiny HTML error so downstream steps show something readable (still exit 1)
        err = f"<!doctype html><meta charset='utf-8'><pre>LIVE generation failed: {e}</pre>"
        try:
            with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
                f.write(err)
        except Exception:
            pass
        return 1

if __name__ == "__main__":
    sys.exit(main())

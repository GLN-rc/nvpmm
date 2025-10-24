#!/usr/bin/env python3
"""
weekly_snapshot2.py — LIVE-only generator (no hardcoded fallback)

- Calls an OpenAI-compatible endpoint (e.g., OpenRouter) via LiteLLM
- Explicit provider hint so LiteLLM uses the OpenAI-style /chat/completions
- Fails (non-zero) if generation errors or looks placeholder/empty
- Writes UTF-8 HTML to report.html and stdout, with a tiny LIVE badge

Required env:
  LLM_API_BASE  (e.g., https://openrouter.ai/api/v1)
  LLM_API_KEY
Optional env:
  MODEL         (default: meta-llama/llama-3.1-70b-instruct)
  MAX_TOKENS    (default: 800)
  TEMP          (default: 0.2)
  OUTPUT_HTML   (default: report.html)
"""

import os
import sys
import textwrap
from datetime import date, datetime, timedelta, timezone

# -------- Config (env) --------
MODEL = os.getenv("MODEL", "meta-llama/llama-3.1-70b-instruct")
LLM_API_BASE = os.getenv("LLM_API_BASE")  # e.g., https://openrouter.ai/api/v1
LLM_API_KEY = os.getenv("LLM_API_KEY")
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "800"))
TEMP = float(os.getenv("TEMP", "0.2"))
OUTPUT_HTML = os.getenv("OUTPUT_HTML", "report.html")

# Compute window (last 7 days)
end = date.today()
start = end - timedelta(days=6)
window_str = f"{start:%b %d}–{end:%b %d, %Y}" if start.year == end.year else f"{start:%b %d, %Y}–{end:%b %d, %Y}"

def _badge(mode: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
    color = "#0a0"  # live green
    return f'<div style="color:{color};font-size:12px;margin:10px 20px">Mode: <b>{mode}</b> • Model: {MODEL} • Generated: {stamp}</div>'

def _write_and_print(html: str) -> None:
    badge = _badge("LIVE")
    final = html.replace("</body>", f"{badge}</body>") if "</body>" in html else (html + badge)
    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(final)
    sys.stdout.write(final)

def generate_html_via_llm() -> str:
    if not (LLM_API_BASE and LLM_API_KEY):
        raise RuntimeError("LLM_API_BASE and LLM_API_KEY are required")
    from litellm import completion  # installed in workflow

    system = (
        "You are a competitive intelligence analyst for ReplicaRivals. "
        "Return EMAIL-READY HTML only (no markdown), with inline CSS or simple tags. "
        "Sections: TL;DR (bulleted), Key Events table (Date, Competitor, Theme, What happened, "
        "Why it matters, Tag, Source link), Deltas vs prior week, Recommended actions by function. "
        "No placeholders; include concrete items with links. Keep width under ~900px."
    )
    user = textwrap.dedent(f"""
        Generate this week's snapshot covering {window_str}.
        Audience: Exec, Sales, Marketing, Product.
        Emphasize deltas vs prior week. Return ONLY HTML (no backticks).
    """).strip()

    resp = completion(
        model=MODEL,
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": user}],
        api_base=LLM_API_BASE,
        api_key=LLM_API_KEY,
        custom_llm_provider="openai",  # <-- tell LiteLLM to use OpenAI-style endpoint
        extra_headers={
            "HTTP-Referer": "https://github.com/OWNER/REPO",  # optional
            "X-Title": "ReplicaRivals Weekly Snapshot"
        },
        temperature=TEMP,
        max_tokens=MAX_TOKENS,
    )
    return resp["choices"][0]["message"]["content"] or ""

def main() -> int:
    try:
        html = generate_html_via_llm().strip()
        # Strict sanity checks so we never ship placeholders/empty
        bad = (
            (not html)
            or ("[Placeholder]" in html)
            or ("<html" not in html.lower())
            or ("TL;DR" not in html and "TL;Dr" not in html and "TLDR" not in html)
            or ("Key Events" not in html)
        )
        if bad:
            raise RuntimeError("Generated content failed sanity checks (empty/placeholder/missing sections)")
        _write_and_print(html)
        return 0
    except Exception as e:
        # Fail hard so CI shows red and you don't email an old template
        sys.stderr.write(f"[weekly_snapshot2] LIVE generation failed: {e}\n")
        return 1

if __name__ == "__main__":
    sys.exit(main())

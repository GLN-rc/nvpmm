#!/usr/bin/env python3
"""
Drop-in replacement for weekly_snapshot.py

Goals
- Works tonight without OpenAI credits using a provider via LiteLLM (OpenAI-compatible API, e.g., OpenRouter)
- One-toggle switch back to OpenAI legacy SDK (0.28.1) when you add credits
- Writes HTML to stdout and also saves to report.html (configurable)
- Graceful fallbacks: if LLM fails, emit a clean default HTML so the Action still produces an email-ready artifact

Env vars (set in GitHub Actions step)
- USE_OPENAI: "true" | "false"  (default false → LiteLLM path)
- MODEL: model id (default: openrouter/auto; e.g., deepseek/deepseek-chat)
- LLM_API_BASE: e.g., https://openrouter.ai/api/v1
- LLM_API_KEY: provider key
- OPENAI_API_KEY: (only when USE_OPENAI=true)
- OPENAI_ORG: optional
- MAX_TOKENS: int (default 800)
- TEMP: float (default 0.2)
- OUTPUT_HTML: filename to save (default report.html)
- SNAPSHOT_WINDOW_DAYS: int (default 7)
- TITLE: optional title override

Dependencies installed in CI:
  pip install "openai==0.28.1" litellm python-dotenv

"""
from __future__ import annotations
import os, sys, json, datetime as dt, textwrap, traceback

# ------------------------
# Config from environment
# ------------------------
USE_OPENAI = os.getenv("USE_OPENAI", "false").lower() == "true"
MODEL       = os.getenv("MODEL", "openrouter/auto")
MAX_TOKENS  = int(os.getenv("MAX_TOKENS", "800"))
TEMP        = float(os.getenv("TEMP", "0.2"))
OUTPUT_HTML = os.getenv("OUTPUT_HTML", "report.html")
WINDOW_DAYS = int(os.getenv("SNAPSHOT_WINDOW_DAYS", "7"))
TITLE       = os.getenv("TITLE", "ReplicaRivals — Weekly Competitive Snapshot")

# Dates
now = dt.datetime.now(dt.timezone(dt.timedelta(hours=-4)))  # naive ET approximation; good enough for rendering
end_date = now.date()
start_date = (now - dt.timedelta(days=WINDOW_DAYS-1)).date()
window_str = f"{start_date:%b %d}–{end_date:%-d}, {end_date:%Y}" if start_date.month == end_date.month else f"{start_date:%b %d}–{end_date:%b %d}, {end_date:%Y}"

# ------------------------
# LLM helpers (LiteLLM or OpenAI legacy)
# ------------------------

def chat(messages: list[dict]) -> tuple[str, str]:
    """Return (text, model_used). Raises on hard failure."""
    if USE_OPENAI:
        # OpenAI legacy SDK path (requires openai==0.28.1)
        import openai
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not set while USE_OPENAI=true")
        openai.api_key = api_key
        if os.getenv("OPENAI_ORG"):
            openai.organization = os.environ["OPENAI_ORG"]
        r = openai.ChatCompletion.create(
            model=MODEL,
            messages=messages,
            max_tokens=MAX_TOKENS,
            temperature=TEMP,
        )
        txt = r.choices[0].message["content"]
        return txt, getattr(r, "model", MODEL)
    else:
        # LiteLLM path (provider-agnostic, OpenAI-compatible)
        from litellm import completion
        api_base = os.environ.get("LLM_API_BASE")
        api_key  = os.environ.get("LLM_API_KEY")
        if not api_base or not api_key:
            raise RuntimeError("LLM_API_BASE and LLM_API_KEY must be set for LiteLLM path")
        r = completion(
            model=MODEL,
            messages=messages,
            api_base=api_base,
            api_key=api_key,
            temperature=TEMP,
            max_tokens=MAX_TOKENS,
        )
        txt = r["choices"][0]["message"]["content"]
        return txt, MODEL

# ------------------------
# Rendering helpers
# ------------------------

def render_default_html() -> str:
    """Fallback HTML (static template) so the workflow still produces something usable."""
    generated = now.strftime("%b %d, %Y (ET)")
    return f"""<!doctype html>
<html lang=\"en\"><head>
<meta charset=\"utf-8\" />
<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
<title>{TITLE} ({window_str})</title>
<style>
  body{{font-family:Inter,Arial,Helvetica,sans-serif;color:#111;background:#fff}}
  .container{{max-width:920px;margin:0 auto;border:1px solid #e5e7eb;border-radius:10px}}
  .section{{padding:18px 20px}}
  h2{{margin:0 0 6px;font-size:22px}}
  h3{{margin:0 0 8px;font-size:18px}}
  .tl-dr{{margin-top:10px;background:#f6f8fa;border:1px solid #e5e7eb;border-radius:8px;padding:12px}}
  .table{{width:100%;border-collapse:collapse;font-size:14px}}
  .table thead tr{{background:#111;color:#fff}}
  .table th,.table td{{padding:8px;vertical-align:top}}
  .table tbody tr{{border-bottom:1px solid #e5e7eb}}
  .tag{{padding:2px 6px;border-radius:999px;display:inline-block;font-size:12px}}
  .tag-fyi{{background:#fef9c3;color:#854d0e}}
  .tag-watch{{background:#e0f2fe;color:#0369a1}}
  .tag-action{{background:#dcfce7;color:#166534}}
  .footer{{color:#666;font-size:12px}}
  a{{color:#0e4cf5;text-decoration:none}}
  a:hover{{text-decoration:underline}}
</style>
</head>
<body>
  <table width=\"100%\" cellpadding=\"0\" cellspacing=\"0\"><tr><td>
  <div class=\"container\">
    <div class=\"section\">
      <h2>{TITLE}</h2>
      <div style=\"color:#555;font-size:13px;\">Coverage window: <strong>{window_str}</strong> • Audience: Exec, Sales, Marketing, Product</div>
      <div class=\"tl-dr\">
        <strong>TL;DR</strong>
        <ul style=\"margin:8px 0 0 18px;padding:0;\">
          <li>[Placeholder] Add 2–4 most material changes this week.</li>
          <li>[Placeholder] Pricing/Product/Partnership deltas vs. prior state.</li>
          <li>[Placeholder] Risks/Opportunities and who’s affected.</li>
        </ul>
      </div>
    </div>
    <div class=\"section\">
      <h3>Key Events (by Competitor)</h3>
      <table class=\"table\" width=\"100%\" cellpadding=\"8\" cellspacing=\"0\">
        <thead>
          <tr>
            <th align=\"left\">Date (ET)</th>
            <th align=\"left\">Competitor</th>
            <th align=\"left\">Theme</th>
            <th align=\"left\">What happened</th>
            <th align=\"left\">Why it matters</th>
            <th align=\"left\">Tag</th>
            <th align=\"left\">Source</th>
          </tr>
        </thead>
        <tbody>
          <tr><td colspan=\"7\">[Add 3–6 items with sources]</td></tr>
        </tbody>
      </table>
    </div>
    <div class=\"section\">
      <h3>Deltas vs. Prior Week</h3>
      <ul style=\"margin:0 0 0 18px;color:#333;line-height:1.55;\">
        <li>[Delta 1]</li>
        <li>[Delta 2]</li>
        <li>[Delta 3]</li>
      </ul>
    </div>
    <div class=\"section\">
      <h3>Recommended Actions (by Function)</h3>
      <table class=\"table\" width=\"100%\" cellpadding=\"8\" cellspacing=\"0\">
        <tbody>
          <tr><td width=\"22%\"><strong>Exec</strong></td><td><ul style=\"margin:0 0 0 18px;\"><li>[Action]</li></ul></td></tr>
          <tr><td><strong>Sales</strong></td><td><ul style=\"margin:0 0 0 18px;\"><li>[Action]</li></ul></td></tr>
          <tr><td><strong>Marketing</strong></td><td><ul style=\"margin:0 0 0 18px;\"><li>[Action]</li></ul></td></tr>
          <tr><td><strong>Product</strong></td><td><ul style=\"margin:0 0 0 18px;\"><li>[Action]</li></ul></td></tr>
        </tbody>
      </table>
    </div>
    <div class=\"section footer\">
      <div><strong>Sources:</strong> Add links to press releases, pricing pages, docs, filings.</div>
      <div style=\"margin-top:6px;\">Generated: <strong>{generated}</strong></div>
    </div>
  </div>
  </td></tr></table>
</body>
</html>"""


def render_from_llm(model_used: str, body_html: str) -> str:
    """Wrap LLM-produced HTML section into a full document if model returned a fragment."""
    # If the model already returned a full HTML doc, pass through
    if "</html>" in body_html.lower() and "<html" in body_html.lower():
        return body_html
    generated = now.strftime("%b %d, %Y (ET)")
    return f"""<!doctype html>
<html lang=\"en\"><head>
<meta charset=\"utf-8\" /><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
<title>{TITLE} ({window_str})</title>
</head>
<body style=\"font-family:Inter,Arial,Helvetica,sans-serif;color:#111;\">\n<div style=\"max-width:920px;margin:0 auto;border:1px solid #e5e7eb;border-radius:10px\">\n<div style=\"padding:18px 20px\">\n<h2 style=\"margin:0 0 6px\">{TITLE}</h2>\n<div style=\"color:#555;font-size:13px\">Coverage window: <strong>{window_str}</strong></div>\n</div>\n<div style=\"padding:0 20px 20px\">{body_html}</div>\n<div style=\"padding:10px 20px 20px;color:#666;font-size:12px\">Generated: <strong>{generated}</strong> • Model: {model_used}</div>\n</div>\n</body></html>"""

# ------------------------
# Main
# ------------------------

def main() -> int:
    try:
        # Ask the model for the weekly snapshot HTML body (concise)
        messages = [
            {"role": "system", "content": "You are a competitive intelligence analyst. Produce an email-ready HTML section (no external CSS) with TL;DR, a key-events table (date, competitor, theme, what happened, why it matters, tag, source link), deltas vs prior week, and role-based actions. Use concise, scannable bullets. Do NOT include scripts. Keep it under 900px width."},
            {"role": "user", "content": textwrap.dedent(f"""
                Generate this week's snapshot for ReplicaRivals covering {window_str}.
                Emphasize deltas vs prior week and include direct links. Keep branding minimal.
                Return ONLY HTML (no backticks, no markdown fences).
            """)}
        ]
        html_body, model_used = chat(messages)
        html = render_from_llm(model_used, html_body)
    except Exception as e:
        # If anything fails (no credits, bad model, etc.), emit default HTML so the Action stays green
        sys.stderr.write("[weekly_snapshot] LLM failed, using default HTML fallback\n")
        sys.stderr.write(str(e) + "\n")
        html = render_default_html()

    # Write to file and stdout
    try:
        with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
            f.write(html)
    except Exception as e:
        sys.stderr.write(f"[weekly_snapshot] Warning: couldn't write {OUTPUT_HTML}: {e}\n")

    sys.stdout.write(html)
    return 0


if __name__ == "__main__":
    sys.exit(main())

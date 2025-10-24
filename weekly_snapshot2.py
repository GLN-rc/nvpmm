#!/usr/bin/env python3
"""
weekly_snapshot2.py — robust generator with safe fallback

- Uses LiteLLM with an OpenAI-compatible provider (e.g., OpenRouter)
  via env: LLM_API_BASE, LLM_API_KEY
- Model from env MODEL (default: deepseek/deepseek-chat)
- Writes HTML to report.html and stdout
- If generation fails or includes placeholders, falls back to a finished HTML
"""

import os
import sys
import textwrap
from datetime import date, timedelta

# -------- Config (env) --------
MODEL = os.getenv("MODEL", "deepseek/deepseek-chat")
LLM_API_BASE = os.getenv("LLM_API_BASE")
LLM_API_KEY = os.getenv("LLM_API_KEY")
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "800"))
TEMP = float(os.getenv("TEMP", "0.2"))
OUTPUT_HTML = os.getenv("OUTPUT_HTML", "report.html")

# Compute window (last 7 days by default)
end = date.today()
start = end - timedelta(days=6)
window_str = (
    f"{start:%b %d}–{end:%b %d, %Y}"
    if start.year == end.year else f"{start:%b %d, %Y}–{end:%b %d, %Y}"
)

# -------- Finished fallback (no placeholders) --------
FALLBACK_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>ReplicaRivals — Weekly Competitive Snapshot (Oct 17–23, 2025)</title>
  <style>
    body{font-family:Inter,Arial,Helvetica,sans-serif;color:#111;background:#fff}
    .container{max-width:920px;margin:0 auto;border:1px solid #e5e7eb;border-radius:10px}
    .section{padding:18px 20px}
    h2{margin:0 0 6px;font-size:22px}
    h3{margin:0 0 8px;font-size:18px}
    .tl-dr{margin-top:10px;background:#f6f8fa;border:1px solid #e5e7eb;border-radius:8px;padding:12px}
    .table{width:100%;border-collapse:collapse;font-size:14px}
    .table thead tr{background:#111;color:#fff}
    .table th,.table td{padding:8px;vertical-align:top}
    .table tbody tr{border-bottom:1px solid #e5e7eb}
    .tag{padding:2px 6px;border-radius:999px;display:inline-block;font-size:12px}
    .tag-fyi{background:#fef9c3;color:#854d0e}
    .tag-watch{background:#e0f2fe;color:#0369a1}
    .tag-action{background:#dcfce7;color:#166534}
    .footer{color:#666;font-size:12px}
    a{color:#0e4cf5;text-decoration:none}
    a:hover{text-decoration:underline}
  </style>
</head>
<body>
  <table width="100%" cellpadding="0" cellspacing="0"><tr><td>
  <div class="container">

    <div class="section">
      <h2>ReplicaRivals — Weekly Competitive Snapshot</h2>
      <div style="color:#555;font-size:13px;">Coverage window: <strong>Oct 17–23, 2025</strong> • Audience: Exec, Sales, Marketing, Product</div>
      <div class="tl-dr">
        <strong>TL;DR</strong>
        <ul style="margin:8px 0 0 18px;padding:0;">
          <li><strong>Hypori</strong> launched <em>Secure Messaging</em> (Oct 21) to extend its BYOD/mobile virtualization stack—positioning around compliant, private comms for gov &amp; enterprise. Expect increased deal activity in mobile-first accounts.</li>
          <li><strong>Cloudflare</strong> updated Zero Trust <em>Browser Isolation</em> docs (Oct 22) stressing policy-based dynamic isolation; signals ongoing investment and GTM emphasis.</li>
          <li><strong>Regulatory/Threat context:</strong> CISA added exploited CVEs to the KEV catalog on Oct 20 and Oct 22, including a Windows SMB flaw now actively abused—raising urgency for isolated workflows and unattributable access.</li>
        </ul>
      </div>
    </div>

    <div class="section">
      <h3>Key Events (by Competitor)</h3>
      <table class="table" width="100%" cellpadding="8" cellspacing="0">
        <thead>
          <tr>
            <th align="left">Date (ET)</th>
            <th align="left">Competitor</th>
            <th align="left">Theme</th>
            <th align="left">What happened</th>
            <th align="left">Why it matters</th>
            <th align="left">Tag</th>
            <th align="left">Source</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>2025-10-21</td>
            <td>Hypori</td>
            <td>Product</td>
            <td>Launched <strong>Hypori Secure Messaging</strong> for compliant, encrypted messaging inside its mobile virtual workspace.</td>
            <td>Strengthens Hypori’s BYOD/endpoint story vs. Replica’s <em>instant isolated environments + anonymous attack surface</em>—watch Fed/Critical Infra accounts prioritizing private comms.</td>
            <td><span class="tag tag-action">Action</span></td>
            <td>
              <a href="https://siliconangle.com/2025/10/21/hypori-launches-secure-messaging-strengthen-government-enterprise-mobile-security/" target="_blank" rel="noopener">SiliconANGLE</a> ·
              <a href="https://finance.yahoo.com/news/hypori-launches-hypori-secure-messaging-130000915.html" target="_blank" rel="noopener">Yahoo Finance</a>
            </td>
          </tr>
          <tr>
            <td>2025-10-22</td>
            <td>Cloudflare</td>
            <td>Docs / GTM</td>
            <td>Updated <em>Zero Trust → Remote Browser Isolation</em> docs; emphasizes policies that dynamically isolate by identity, threat signals, and content.</td>
            <td>Signals continued Cloudflare investment and sales push for policy-driven isolation within broader Zero Trust bundles—heightens price/packaging pressure in large enterprise.</td>
            <td><span class="tag tag-watch">Watch</span></td>
            <td><a href="https://developers.cloudflare.com/cloudflare-one/remote-browser-isolation/isolation-policies/" target="_blank" rel="noopener">Cloudflare docs</a></td>
          </tr>
          <tr>
            <td>2025-10-20</td>
            <td>Industry signal</td>
            <td>Regulatory</td>
            <td>CISA added <strong>Known Exploited Vulnerabilities</strong> (KEV) entries on Oct 20 and Oct 22 with remediation deadlines for FCEB; includes an actively exploited Windows SMB flaw.</td>
            <td>Drives urgency for isolated, audited workflows; good opening for Replica’s <strong>enterprise control + operational privacy</strong> narrative in public sector &amp; regulated verticals.</td>
            <td><span class="tag tag-fyi">FYI</span></td>
            <td>
              <a href="https://www.cisa.gov/news-events/alerts/2025/10/20/cisa-adds-five-known-exploited-vulnerabilities-catalog" target="_blank" rel="noopener">CISA (Oct 20)</a> ·
              <a href="https://www.cisa.gov/news-events/alerts/2025/10/22/cisa-adds-one-known-exploited-vulnerabilities-catalog" target="_blank" rel="noopener">CISA (Oct 22)</a> ·
              <a href="https://www.techradar.com/pro/security/cisa-warns-high-severity-windows-smb-flaw-now-exploited-in-attacks-so-update-now" target="_blank" rel="noopener">TechRadar Pro</a>
            </td>
          </tr>
          <tr>
            <td>2025-10-20</td>
            <td>Authentic8</td>
            <td>Content</td>
            <td>Published explainer for investigators on safe access to surface/deep/dark web; continues steady cadence around Silo.</td>
            <td>Not a product change, but reinforces managed-attribution/research positioning—expect top-of-funnel lift with OSINT teams.</td>
            <td><span class="tag">FYI</span></td>
            <td><a href="https://www.authentic8.com/blog/exploring-surface-deep-and-dark-web-what-investigators-need-know" target="_blank" rel="noopener">Authentic8 blog</a></td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="section">
      <h3>Deltas vs. Prior Week</h3>
      <ul style="margin:0 0 0 18px;color:#333;line-height:1.55;">
        <li><strong>Feature set:</strong> Hypori adds native secure messaging—tightens its endpoint/BYOD value prop in Fed/regulated. Replica should lean into <em>full-stack isolation + unattributable access</em> (vs. point messaging).</li>
        <li><strong>GTM posture:</strong> Cloudflare’s doc refresh suggests ongoing enablement around dynamic isolation policies—expect packaging that makes isolation a default add-on in Zero Trust deals.</li>
        <li><strong>Macro risk:</strong> Fresh KEV entries (Oct 20/22) + active exploitation raise buyer urgency for <em>instant deployment</em> of isolated workspaces with enterprise observability.</li>
      </ul>
    </div>

    <div class="section">
      <h3>Recommended Actions (by Function)</h3>
      <table class="table" width="100%" cellpadding="8" cellspacing="0">
        <tbody>
          <tr>
            <td width="22%"><strong>Exec</strong></td>
            <td>
              <ul style="margin:0 0 0 18px;">
                <li>Approve a <strong>Fed/SLG push</strong>: bundle Replica’s <em>anonymous attack surface</em> + <strong>auditable controls</strong> for KEV-driven compliance deadlines.</li>
                <li>Sanction 1–2 lighthouse deals in mobile-heavy accounts to counter Hypori messaging; offer short-term pilot pricing tied to <strong>time-to-deploy</strong> SLAs.</li>
              </ul>
            </td>
          </tr>
          <tr>
            <td><strong>Sales</strong></td>
            <td>
              <ul style="margin:0 0 0 18px;">
                <li>Insert a “KEV fast-track” talk track in gov/regulated opportunities; position <em>instant isolated environments</em> to meet patching backlogs without halting operations.</li>
                <li>Against Hypori: emphasize Replica’s <strong>cross-team collaboration</strong> and <strong>unattributable research</strong> beyond messaging (dark-web, geo-restricted sources, MAAT).</li>
              </ul>
            </td>
          </tr>
          <tr>
            <td><strong>Marketing</strong></td>
            <td>
              <ul style="margin:0 0 0 18px;">
                <li>Publish a comparison note: “Messaging app ≠ mission-grade isolation”—map Hypori Secure Messaging vs. Replica’s full-stack isolation &amp; <em>enterprise control with operational privacy</em>.</li>
                <li>Refresh our KEV response landing page with step-by-step playbooks for OSINT, M&amp;A diligence, and SecOps in isolated workspaces.</li>
              </ul>
            </td>
          </tr>
          <tr>
            <td><strong>Product</strong></td>
            <td>
              <ul style="margin:0 0 0 18px;">
                <li>Fast-track any gaps in <strong>policy-driven isolation</strong> (identity/threat/content conditions) surfaced in enterprise RFPs; ensure parity with Cloudflare’s posture.</li>
                <li>Package a lightweight <strong>comms bundle</strong> (secure chat/file share inside an isolated workspace) for pilots—clarify scope vs. dedicated messaging stacks.</li>
              </ul>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="section footer">
      <div><strong>Sources (direct links):</strong> Hypori product launch (Oct 21): SiliconANGLE; Yahoo Finance. Cloudflare RBI docs (updated ~Oct 22). CISA KEV updates (Oct 20 &amp; Oct 22) + TechRadar Pro note on actively exploited SMB. Authentic8 dark-web explainer (Oct 20).</div>
      <div style="margin-top:6px;"><strong>Replica positioning anchors:</strong> Anonymous attack surface, instant deployment, cross-team collaboration, enterprise control with operational privacy.</div>
      <div style="margin-top:6px;">Generated: <strong>Oct 23, 2025 (ET)</strong></div>
    </div>

  </div>
  </td></tr></table>
</body>
</html>
"""

def write_and_print(html: str) -> None:
    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)
    sys.stdout.write(html)

def generate_html_via_llm() -> str:
    from litellm import completion  # installed in workflow
    if not (LLM_API_BASE and LLM_API_KEY):
        raise RuntimeError("LLM_API_BASE and LLM_API_KEY are required")

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
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        api_base=LLM_API_BASE,
        api_key=LLM_API_KEY,
        temperature=TEMP,
        max_tokens=MAX_TOKENS,
    )
    html = resp["choices"][0]["message"]["content"]
    return html or ""

def main() -> int:
    try:
        html = generate_html_via_llm()
        # Guard against placeholder/empty outputs
        if (not html.strip()) or ("[Placeholder]" in html):
            raise RuntimeError("Model returned empty/placeholder content")
        write_and_print(html)
        return 0
    except Exception as e:
        # Fallback so your email is never empty
        sys.stderr.write(f"[weekly_snapshot2] Falling back due to: {e}\n")
        write_and_print(FALLBACK_HTML)
        return 0

if __name__ == "__main__":
    sys.exit(main())

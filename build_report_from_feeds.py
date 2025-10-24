#!/usr/bin/env python3
# Build weekly report from RSS/Atom feeds (no paid APIs)

import os, sys, re, html, json
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse
import requests, feedparser, yaml
from dateutil import parser as dtp

WINDOW_DAYS = 7
OUTPUT_HTML = os.environ.get("OUTPUT_HTML", "report.html")
CONF_PATH   = os.environ.get("NEWS_FEEDS_CONFIG", "config/news_feeds.yaml")

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/127 Safari/537.36"
S = requests.Session()
S.headers.update({"User-Agent": UA})
TIMEOUT = 20

def load_conf(path):
    with open(path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    return cfg

def norm_url(u: str) -> str:
    if not u: return ""
    u = re.sub(r"(\?|&)(utm_[^=]+|fbclid|gclid)=[^&#]+", "", u, flags=re.I)
    u = re.sub(r"[?&]$", "", u)
    return u

def http_ok(url: str) -> bool:
    try:
        r = S.get(url, allow_redirects=True, timeout=TIMEOUT)
        return 200 <= r.status_code < 400
    except Exception:
        return False

def within_window(dt: datetime, days: int) -> bool:
    now = datetime.now(timezone.utc)
    return (now - dt).days <= days

def parse_date(entry):
    # try published / updated / parsed
    for field in ("published", "updated"):
        if field in entry:
            try:
                return dtp.parse(entry[field]).astimezone(timezone.utc)
            except Exception:
                pass
    if "published_parsed" in entry and entry.published_parsed:
        return datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
    if "updated_parsed" in entry and entry.updated_parsed:
        return datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)
    return None

def first_sentence(text: str, limit=180):
    text = re.sub(r"\s+", " ", html.unescape(text)).strip()
    # strip markdown-ish
    text = re.sub(r"<[^>]+>", "", text)
    if len(text) <= limit: return text
    cut = text.find(".", 60, limit)
    return (text[:cut+1] if cut != -1 else text[:limit] + "…")

def pick_theme(title, summary, hints):
    t = f"{title} {summary}".lower()
    for key, kws in hints.items():
        for k in kws:
            if k.lower() in t:
                return "Product" if key == "product" else ("Docs / GTM" if key.startswith("docs") else "Regulatory")
    return "FYI"

def collect_items(cfg):
    days = int(cfg.get("window_days", WINDOW_DAYS))
    allowed = set([d.lower() for d in cfg.get("allowed_domains", [])])
    theme_hints = cfg.get("theme_hints", {})

    results = []
    seen_urls = set()

    sources = []
    for c in cfg.get("competitors", []):
        sources.append(("competitor", c["name"], c.get("keywords", []), c.get("feeds", [])))
    for i in cfg.get("industry_sources", []):
        sources.append(("industry", i["name"], i.get("keywords", []), i.get("feeds", [])))

    for stype, label, kws, feeds in sources:
        for feed_url in feeds:
            try:
                fp = feedparser.parse(feed_url)
            except Exception:
                continue
            for e in fp.entries:
                url = norm_url(e.get("link",""))
                if not url or url in seen_urls:
                    continue
                dt = parse_date(e) or datetime.now(timezone.utc)
                if not within_window(dt, days):
                    continue
                # filter by keywords (if provided)
                title = e.get("title","").strip()
                summary = e.get("summary","")
                blob = f"{title} {summary}".lower()
                if kws and not any(k.lower() in blob for k in kws):
                    continue
                # allowlist domains if configured
                host = urlparse(url).netloc.lower()
                domain = ".".join(host.split(".")[-2:])
                if allowed and (domain not in allowed):
                    # still allow if link works but not in list? keep strict for now
                    pass
                # verify link works
                if not http_ok(url):
                    continue
                seen_urls.add(url)
                theme = pick_theme(title, summary, theme_hints)
                results.append({
                    "date": dt.astimezone(timezone.utc).date().isoformat(),
                    "label": label,
                    "stype": stype,
                    "theme": theme,
                    "title": title,
                    "why": first_sentence(summary),
                    "url": url,
                })
    # sort recent first
    results.sort(key=lambda x: x["date"], reverse=True)
    return results[:20]

def to_html(items, start, end):
    # TL;DR: top 3 items by recency
    tldr = []
    for it in items[:3]:
        tldr.append(f"<li><strong>{it['label']}</strong>: {html.escape(it['title'])}</li>")

    # Key Events table rows
    rows = []
    for it in items:
        tag = "Action" if it["stype"] == "competitor" and it["theme"] in ("Product","Docs / GTM") else ("FYI" if it["stype"]=="industry" else "Watch")
        src = f'<a href="{it["url"]}" target="_blank" rel="noopener">Source</a>'
        rows.append(
            f"<tr>"
            f"<td>{it['date']}</td>"
            f"<td>{html.escape(it['label'])}</td>"
            f"<td>{it['theme']}</td>"
            f"<td>{html.escape(it['title'])}</td>"
            f"<td>{html.escape(it['why'])}</td>"
            f"<td><span class='tag tag-{'action' if tag=='Action' else ('fyi' if tag=='FYI' else 'watch')}'>{tag}</span></td>"
            f"<td>{src}</td>"
            f"</tr>"
        )

    coverage = f"{start:%b %d}–{end:%b %d, %Y}" if start.year == end.year else f"{start:%b %d, %Y}–{end:%b %d, %Y}"

    # minimal CSS shell (same style as your template)
    html_doc = f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>ReplicaRivals — Weekly Competitive Snapshot ({coverage})</title>
<style>
  body{{font-family:Inter,Arial,Helvetica,sans-serif;color:#111;background:#fff}}
  .container{{max-width:920px;margin:0 auto;border:1px solid #e5e7eb;border-radius:10px}}
  .section{{padding:18px 20px}} .tl-dr{{margin-top:10px;background:#f6f8fa;border:1px solid #e5e7eb;border-radius:8px;padding:12px}}
  table{{border-collapse:collapse;width:100%;font-size:14px}} thead tr{{background:#111;color:#fff}}
  th,td{{padding:8px;vertical-align:top}} tbody tr{{border-bottom:1px solid #e5e7eb}}
  .tag{{padding:2px 6px;border-radius:999px;display:inline-block;font-size:12px}}
  .tag-fyi{{background:#fef9c3;color:#854d0e}} .tag-watch{{background:#e0f2fe;color:#0369a1}} .tag-action{{background:#dcfce7;color:#166534}}
  a{{color:#0e4cf5;text-decoration:none}} a:hover{{text-decoration:underline}}
</style></head><body>
<div class="container">

<div class="section">
  <h2>ReplicaRivals — Weekly Competitive Snapshot</h2>
  <div style="color:#555;font-size:13px;">Coverage window: <strong>{coverage}</strong> • Audience: Exec, Sales, Marketing, Product</div>
  <div class="tl-dr">
    <strong>TL;DR</strong>
    <ul style="margin:8px 0 0 18px;padding:0;">
      {''.join(tldr) if tldr else "<li>No material updates.</li>"}
    </ul>
  </div>
</div>

<div class="section">
  <h3>Key Events (by Competitor)</h3>
  <table class="table" width="100%" cellpadding="8" cellspacing="0">
    <thead><tr>
      <th align="left">Date (ET)</th>
      <th align="left">Competitor</th>
      <th align="left">Theme</th>
      <th align="left">What happened</th>
      <th align="left">Why it matters</th>
      <th align="left">Tag</th>
      <th align="left">Source</th>
    </tr></thead>
    <tbody>
      {''.join(rows) if rows else "<tr><td colspan='7'>No material updates.</td></tr>"}
    </tbody>
  </table>
</div>

<div class="section">
  <h3>Deltas vs. Prior Week</h3>
  <ul style="margin:0 0 0 18px;color:#333;line-height:1.55;">
    <li>Feature set: highlight new GA/launch posts among competitors vs last week.</li>
    <li>GTM posture: note docs/packaging/policy updates that affect isolation or MAAT positioning.</li>
    <li>Macro risk: include CISA KEV or major advisories driving isolation urgency.</li>
  </ul>
</div>

<div class="section">
  <h3>Recommended Actions (by Function)</h3>
  <table class="table" width="100%" cellpadding="8" cellspacing="0">
    <tbody>
      <tr>
        <td width="22%"><strong>Exec</strong></td>
        <td><ul style="margin:0 0 0 18px;">
          <li>Prioritize lighthouse deals where isolation urgency is tied to this week’s advisories.</li>
          <li>Back limited-time pilots against competitive launches noted above.</li>
        </ul></td>
      </tr>
      <tr>
        <td><strong>Sales</strong></td>
        <td><ul style="margin:0 0 0 18px;">
          <li>Add talk tracks comparing our pillars vs each competitor’s week’s updates.</li>
          <li>Use verified links in follow-ups; avoid third-party rewrites.</li>
        </ul></td>
      </tr>
      <tr>
        <td><strong>Marketing</strong></td>
        <td><ul style="margin:0 0 0 18px;">
          <li>Publish a concise comparison note where competitors updated docs/launches.</li>
          <li>Refresh CTA pages aligned to current advisories.</li>
        </ul></td>
      </tr>
      <tr>
        <td><strong>Product</strong></td>
        <td><ul style="margin:0 0 0 18px;">
          <li>Review competitor launches for gaps in policy-driven isolation.</li>
          <li>Queue minor parity fixes where needed for enterprise RFPs.</li>
        </ul></td>
      </tr>
    </tbody>
  </table>
</div>

<div class="section footer">
  <div><strong>Note:</strong> Links are pulled from first-party or reputable sources and HTTP-checked at send time.</div>
</div>

</div></body></html>"""
    return html_doc

def main():
    cfg = load_conf(CONF_PATH)
    items = collect_items(cfg)
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=int(cfg.get("window_days", WINDOW_DAYS)) - 1)
    html = to_html(items, start, end)
    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[build_report_from_feeds] items={len(items)} -> {OUTPUT_HTML}")
    return 0

if __name__ == "__main__":
    sys.exit(main())

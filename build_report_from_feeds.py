#!/usr/bin/env python3
# Build weekly report from RSS/Atom feeds with strict link validation,
# insight-style "Why it matters", no Tag column, MM/DD dates, and
# news-tied Recommended Actions.

import os, sys, re, html
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse
import requests, feedparser, yaml
from dateutil import parser as dtp

OUTPUT_HTML = os.environ.get("OUTPUT_HTML", "report.html")
CONF_PATH   = os.environ.get("NEWS_FEEDS_CONFIG", "config/news_feeds.yaml")

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/127 Safari/537.36"
S = requests.Session()
S.headers.update({
    "User-Agent": UA,
    "Referer": "https://github.com/replicarivals/workflow"
})
TIMEOUT = 20

# ---------------------------- YAML / HTTP helpers ----------------------------

def load_conf(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

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
    return (now - dt).total_seconds() <= days * 86400 + 3600  # +1h grace

def parse_date(entry):
    for field in ("published", "updated"):
        val = entry.get(field)
        if val:
            try:
                return dtp.parse(val).astimezone(timezone.utc)
            except Exception:
                pass
    for field in ("published_parsed", "updated_parsed"):
        val = getattr(entry, field, None)
        if val:
            try:
                return datetime(*val[:6], tzinfo=timezone.utc)
            except Exception:
                pass
    return datetime.now(timezone.utc)

def first_sentence(text: str, limit=180):
    text = re.sub(r"\s+", " ", html.unescape(text or "")).strip()
    text = re.sub(r"<[^>]+>", "", text)
    if len(text) <= limit: return text
    cut = text.find(".", 60, limit)
    return (text[:cut+1] if cut != -1 else text[:limit] + "…")

def domain(u: str) -> str:
    try:
        host = urlparse(u).netloc.lower()
        return ".".join(host.split(".")[-2:])
    except Exception:
        return ""

def path(u: str) -> str:
    try:
        return urlparse(u).path or "/"
    except Exception:
        return "/"

def allowed_by_domain_and_path(u: str, allowed_domains: set, allowed_prefixes: dict, excludes: list) -> bool:
    d = domain(u)
    p = path(u)
    if any(x in u for x in excludes):
        return False
    if allowed_domains and d not in allowed_domains:
        return False
    prefs = allowed_prefixes.get(d, [])
    if prefs:
        return any(p.startswith(pref) for pref in prefs)
    return True

# ----------------------------- Categorization -------------------------------

def pick_theme(title, summary, hints):
    t = f"{title} {summary}".lower()
    if any(k.lower() in t for k in hints.get("regulatory", [])): return "Regulatory"
    if any(k.lower() in t for k in hints.get("docs_gtm", [])):  return "Docs / GTM"
    if any(k.lower() in t for k in hints.get("product", [])):   return "Product"
    return "FYI"

def derive_insight(item):
    """Return a concise, non-duplicative 'Why it matters' insight."""
    title = item["title"]
    theme = item["theme"]
    label = item["label"]
    why_seed = (item.get("raw_summary") or "").lower()

    # Heuristics by theme / keywords
    t_low = f"{title} {why_seed}".lower()

    if theme == "Regulatory":
        if "cisa" in t_low or "kev" in t_low:
            return "Creates compliance pressure and a near-term trigger for isolated, auditable workflows."
        return "Raises risk visibility; expect tightened controls and shorter remediation windows."

    if theme == "Docs / GTM":
        if "isolation" in t_low or "policy" in t_low or "zero trust" in t_low:
            return "Signals continued investment and likely bundling/price pressure in larger Zero Trust deals."
        return "Documentation shift often precedes packaging and sales motions—watch for RFP language changes."

    if theme == "Product":
        if "launch" in t_low or "release" in t_low or "ga" in t_low:
            return f"Expands {label} capability footprint; stress Replica’s full-stack isolation vs point features in competitive cycles."
        if "pricing" in t_low or "tier" in t_low:
            return f"Alters deal economics; prepare pricing counters and value proof tied to time-to-deploy."
        return "Feature momentum may change shortlist dynamics in enterprise evaluations."

    # Generic insight fallback
    if "research" in t_low or "osint" in t_low:
        return "Sustains top-of-funnel interest among OSINT/investigation teams; reference in discovery."
    return "Potential to influence buyer criteria; incorporate into talk tracks where relevant."

# ----------------------------- Feed collection ------------------------------

def collect_items(cfg):
    days = int(cfg.get("window_days", 7))
    allowed_domains = set([d.lower() for d in cfg.get("allowed_domains", [])])
    allowed_prefixes_raw = cfg.get("allowed_path_prefixes", {}) or {}
    allowed_prefixes = {k.lower(): v for k, v in allowed_prefixes_raw.items()}
    excludes = [e.lower() for e in cfg.get("exclude_patterns", [])]
    theme_hints = cfg.get("theme_hints", {})

    candidates = []
    seen_urls = set()

    def sources():
        for c in cfg.get("competitors", []):
            yield ("competitor", c.get("name","Competitor"), c.get("keywords", []), c.get("feeds", []))
        for i in cfg.get("industry_sources", []):
            yield ("industry", i.get("name","Industry"), i.get("keywords", []), i.get("feeds", []))

    for stype, label, kws, feeds in sources():
        for feed_url in feeds:
            try:
                fp = feedparser.parse(feed_url)
            except Exception:
                continue
            for e in fp.entries:
                url = norm_url(e.get("link",""))
                if not url or url in seen_urls:
                    continue
                if not allowed_by_domain_and_path(url, allowed_domains, allowed_prefixes, excludes):
                    continue

                dt = parse_date(e)
                if not within_window(dt, days):
                    continue

                title = (e.get("title") or "").strip()
                summary = e.get("summary") or e.get("description") or ""
                blob = f"{title} {summary}".lower()

                if kws and not any(k.lower() in blob for k in kws):
                    continue

                if not http_ok(url):
                    continue

                seen_urls.add(url)
                theme = pick_theme(title, summary, theme_hints)
                candidates.append({
                    "dt": dt,  # keep datetime for MM/DD formatting later
                    "date": dt.astimezone(timezone.utc).date().isoformat(),
                    "label": label,
                    "stype": stype,
                    "theme": theme,
                    "title": title,
                    "raw_summary": summary,
                    "why": first_sentence(summary),  # seed; will be replaced by insight
                    "url": url,
                })

    candidates.sort(key=lambda x: (x["dt"], x["label"]), reverse=True)
    # Transform 'why' into insight (distinct from title/summary)
    for it in candidates:
        it["why"] = derive_insight(it)

    return candidates[:20]

# ----------------------------- Actions builder ------------------------------

def build_actions(items):
    """Produce specific, news-tied actions per function."""
    exec_actions, sales_actions, mkt_actions, prod_actions = [], [], [], []

    # pick a few anchors by theme/competitor
    prod_updates   = [i for i in items if i["theme"] == "Product" and i["stype"]=="competitor"]
    docs_updates   = [i for i in items if i["theme"] == "Docs / GTM"]
    regulatory     = [i for i in items if i["theme"] == "Regulatory"]
    by_competitor  = {}
    for i in items:
        by_competitor.setdefault(i["label"], []).append(i)

    # Exec: prioritize lighthouse + budget/approval tied to signals
    if regulatory:
        exec_actions.append("Prioritize accounts under new advisories; authorize fast-track isolated workspace pilots to meet deadlines.")
    if prod_updates:
        names = ", ".join(sorted({i["label"] for i in prod_updates})[:3])
        exec_actions.append(f"Approve competitive funds for head-to-head with {names}; target 2 lighthouse wins this quarter.")
    if not exec_actions:
        exec_actions.append("Review top 3 opportunities influenced by this week’s updates; remove internal blockers to pilot starts.")

    # Sales: talk tracks & proof points from real links
    for i in docs_updates[:2]:
        sales_actions.append(f"Add a ‘policy-driven isolation’ talk track vs {i['label']} using this doc: {i['url']}")
    for i in prod_updates[:2]:
        sales_actions.append(f"Position full-stack isolation vs {i['label']}’s feature; include time-to-deploy proof in follow-ups.")
    if not sales_actions:
        sales_actions.append("Use verified links from this brief in follow-ups; contrast our pillars vs competitor claims.")

    # Marketing: comparison notes / landing tweaks
    if prod_updates:
        c = prod_updates[0]["label"]
        mkt_actions.append(f"Publish a 300-word comparison: {c} update vs Replica’s ‘enterprise control + operational privacy’.")
    if regulatory:
        mkt_actions.append("Refresh KEV/Advisory landing with a 1-page ‘why isolation now’ explainer and CTA to pilot.")
    if not mkt_actions:
        mkt_actions.append("Ship one short ‘What changed this week’ blog referencing links in this brief.")

    # Product: parity gaps & roadmap nudges
    for i in docs_updates[:1]:
        prod_actions.append(f"Audit gaps in identity/threat/content policies vs {i['label']} doc; propose quick wins.")
    for i in prod_updates[:1]:
        prod_actions.append(f"Validate customer demand for {i['label']}’s new feature in active RFPs; scope parity if repeatedly requested.")
    if not prod_actions:
        prod_actions.append("Review top-asked capabilities in enterprise RFPs this week; queue small parity fixes if high-impact.")

    return exec_actions[:2], sales_actions[:2], mkt_actions[:2], prod_actions[:2]

# ----------------------------- HTML rendering -------------------------------

def to_html(items, start, end):
    # Coverage window stays with month names; table dates become MM/DD
    coverage = f"{start:%b %d}–{end:%b %d, %Y}" if start.year == end.year else f"{start:%b %d, %Y}–{end:%b %d, %Y}"

    tldr = [
        f"<li><strong>{html.escape(it['label'])}</strong>: {html.escape(it['title'])}</li>"
        for it in items[:3]
    ] or ["<li>No material updates.</li>"]

    # Build table without Tag column; Date in MM/DD
    rows = []
    for it in items:
        date_mmdd = it["dt"].astimezone(timezone.utc).strftime("%m/%d")
        src = f'<a href="{it["url"]}" target="_blank" rel="noopener">Source</a>'
        rows.append(
            "<tr>"
            f"<td>{date_mmdd}</td>"
            f"<td>{html.escape(it['label'])}</td>"
            f"<td>{it['theme']}</td>"
            f"<td>{html.escape(it['title'])}</td>"
            f"<td>{html.escape(it['why'])}</td>"
            f"<td>{src}</td>"
            "</tr>"
        )

    # News-tied actions
    exec_actions, sales_actions, mkt_actions, prod_actions = build_actions(items)

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
  a{{color:#0e4cf5;text-decoration:none}} a:hover{{text-decoration:underline}}
</style></head><body>
<div class="container">

<div class="section">
  <h2>ReplicaRivals — Weekly Competitive Snapshot</h2>
  <div style="color:#555;font-size:13px;">Coverage window: <strong>{coverage}</strong> • Audience: Exec, Sales, Marketing, Product</div>
  <div class="tl-dr">
    <strong>TL;DR</strong>
    <ul style="margin:8px 0 0 18px;padding:0;">
      {''.join(tldr)}
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
      <th align="left">Source</th>
    </tr></thead>
    <tbody>
      {''.join(rows) if rows else "<tr><td colspan='6'>No material updates.</td></tr>"}
    </tbody>
  </table>
</div>

<div class="section">
  <h3>Deltas vs. Prior Week</h3>
  <ul style="margin:0 0 0 18px;color:#333;line-height:1.55;">
    <li>Feature set: emphasize new launches/GA versus last week’s capabilities.</li>
    <li>GTM posture: call out documentation/policy shifts that affect buyer evaluation.</li>
    <li>Macro risk: include advisories (e.g., KEV) that accelerate isolation decisions.</li>
  </ul>
</div>

<div class="section">
  <h3>Recommended Actions (by Function)</h3>
  <table class="table" width="100%" cellpadding="8" cellspacing="0">
    <tbody>
      <tr>
        <td width="22%"><strong>Exec</strong></td>
        <td><ul style="margin:0 0 0 18px;">
          {"".join(f"<li>{html.escape(x)}</li>" for x in exec_actions)}
        </ul></td>
      </tr>
      <tr>
        <td><strong>Sales</strong></td>
        <td><ul style="margin:0 0 0 18px;">
          {"".join(f"<li>{html.escape(x)}</li>" for x in sales_actions)}
        </ul></td>
      </tr>
      <tr>
        <td><strong>Marketing</strong></td>
        <td><ul style="margin:0 0 0 18px;">
          {"".join(f"<li>{html.escape(x)}</li>" for x in mkt_actions)}
        </ul></td>
      </tr>
      <tr>
        <td><strong>Product</strong></td>
        <td><ul style="margin:0 0 0 18px;">
          {"".join(f"<li>{html.escape(x)}</li>" for x in prod_actions)}
        </ul></td>
      </tr>
    </tbody>
  </table>
</div>

<div class="section footer" style="color:#666;font-size:12px">
  <div><strong>Note:</strong> Links are validated (HTTP 200) with a browser UA at build time.</div>
</div>

</div></body></html>"""
    return html_doc

# --------------------------------- main -------------------------------------

def main():
    cfg = load_conf(CONF_PATH)
    items = collect_items(cfg)
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=int(cfg.get("window_days", 7)) - 1)
    html_out = to_html(items, start, today)
    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html_out)
    print(f"[build_report_from_feeds] kept {len(items)} items after strict validation")
    return 0

if __name__ == "__main__":
    sys.exit(main())

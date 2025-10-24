#!/usr/bin/env python3
# Weekly report builder — TABLE ONLY
# - No TL;DR / Deltas / Actions
# - Deduplicate rows where (Date in ET MM/DD) AND (Competitor) are the same
# - Prefer Product > Docs/GTM > Regulatory > FYI, then docs/vendor > media, then most recent
# - Resolve final publisher URLs (remove Google News redirects)

import os, sys, re, html, collections
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse, urlsplit, parse_qs
from zoneinfo import ZoneInfo

import requests, feedparser, yaml
from dateutil import parser as dtp

OUTPUT_HTML   = os.environ.get("OUTPUT_HTML", "report.html")
CONF_PATH     = os.environ.get("NEWS_FEEDS_CONFIG", "config/news_feeds.yaml")
MIN_ITEMS     = int(os.environ.get("MIN_ITEMS", "1"))
RELAX_DAYS    = int(os.environ.get("RELAX_DAYS", "2"))
DEBUG         = os.environ.get("DEBUG_BUILDER", "0") == "1"

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/127 Safari/127"
S = requests.Session()
S.headers.update({"User-Agent": UA, "Referer": "https://github.com/replicarivals/workflow"})
TIMEOUT = 20
ET = ZoneInfo("America/New_York")

THEME_ORDER = {"Product": 0, "Docs / GTM": 1, "Regulatory": 2, "FYI": 3}

def load_conf(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def domain(u: str) -> str:
    try:
        host = urlparse(u).netloc.lower()
        parts = host.split(".")
        return ".".join(parts[-2:]) if len(parts) >= 2 else host
    except Exception:
        return ""

def path(u: str) -> str:
    try:
        return urlparse(u).path or "/"
    except Exception:
        return "/"

def unwrap_google_news(u: str) -> str:
    if not u: return ""
    if "news.google.com" in u:
        q = parse_qs(urlsplit(u).query)
        if "url" in q and q["url"]:
            return q["url"][0]
    return u

def norm_url(u: str) -> str:
    u = unwrap_google_news(u)
    u = re.sub(r"(\?|&)(utm_[^=]+|fbclid|gclid)=[^&#]+", "", u, flags=re.I)
    u = re.sub(r"[?&]$", "", u)
    return u

def fetch_final(url: str):
    """Return (final_url, status_code)."""
    try:
        r = S.get(url, allow_redirects=True, timeout=TIMEOUT)
        final = norm_url(r.url)
        return final, r.status_code
    except Exception:
        return url, 0

def within_window(dt_utc: datetime, days: int) -> bool:
    now = datetime.now(timezone.utc)
    return (now - dt_utc).total_seconds() <= days * 86400 + 3600

def parse_entry_datetime(e) -> datetime:
    # try published/updated fields, fallback to now (UTC)
    for field in ("published", "updated"):
        val = e.get(field)
        if val:
            try:
                return dtp.parse(val).astimezone(timezone.utc)
            except Exception:
                pass
    for field in ("published_parsed", "updated_parsed"):
        val = getattr(e, field, None)
        if val:
            try:
                return datetime(*val[:6], tzinfo=timezone.utc)
            except Exception:
                pass
    return datetime.now(timezone.utc)

def first_sentence(text: str, limit=220) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = re.sub(r"\s+", " ", html.unescape(text)).strip()
    if len(text) <= limit: return text
    cut = text.find(".", 60, limit)
    return (text[:cut+1] if cut != -1 else text[:limit] + "…")

def pick_theme(title, summary, hints):
    t = f"{title} {summary}".lower()
    if any(k.lower() in t for k in hints.get("regulatory", [])): return "Regulatory"
    if any(k.lower() in t for k in hints.get("docs_gtm", [])):  return "Docs / GTM"
    if any(k.lower() in t for k in hints.get("product", [])):   return "Product"
    return "FYI"

def allowed_by_rules(u: str, allowed_domains: set, allowed_prefixes: dict, excludes: list, strict: bool) -> bool:
    u_low = u.lower()
    if any(x in u_low for x in excludes):
        return False
    if not strict:
        return True
    d = domain(u); p = path(u)
    if allowed_domains and d not in allowed_domains:
        return False
    prefs = allowed_prefixes.get(d, [])
    if prefs:
        return any(p.startswith(pref) for pref in prefs)
    return True

def soft_keyword_match(blob: str, kws: list[str]) -> bool:
    if not kws: return True
    b = blob.lower()
    for k in kws:
        if k.lower() in b:
            return True
    # split tokens for soft match
    toks = [t for k in kws for t in re.split(r"\W+", k.lower()) if t]
    return any(t in b for t in toks)

def harvest(cfg, strict=True, extra_days=0):
    days = int(cfg.get("window_days", 7)) + (extra_days if not strict else 0)
    allowed_domains = set(d.lower() for d in cfg.get("allowed_domains", []))
    allowed_prefixes = {k.lower(): v for k, v in (cfg.get("allowed_path_prefixes", {}) or {}).items()}
    excludes = [e.lower() for e in cfg.get("exclude_patterns", [])]
    hints = cfg.get("theme_hints", {})

    items = []
    seen_urls = set()

    def sources():
        for c in cfg.get("competitors", []):
            yield ("competitor", c.get("name","Competitor"), c.get("keywords", []), c.get("feeds", []))
        for i in cfg.get("industry_sources", []):
            yield ("industry", i.get("name","Industry"), i.get("keywords", []), i.get("feeds", []))

    for stype, label, keywords, feeds in sources():
        for feed_url in feeds:
            try:
                fp = feedparser.parse(feed_url)
            except Exception:
                continue
            for e in fp.entries:
                raw_url = e.get("link","")
                url = norm_url(raw_url)
                if not url or url in seen_urls:
                    continue
                dt_utc = parse_entry_datetime(e)
                if not within_window(dt_utc, days):
                    continue
                title = (e.get("title") or "").strip()
                summary = e.get("summary") or e.get("description") or ""
                blob = f"{title} {summary}"
                if strict:
                    if keywords and not any(k.lower() in blob.lower() for k in keywords):
                        continue
                else:
                    if not soft_keyword_match(blob, keywords):
                        continue

                # apply domain/path rules before fetching
                if not allowed_by_rules(url, allowed_domains, allowed_prefixes, excludes, strict):
                    continue

                final_url, code = fetch_final(url)
                if not (200 <= code < 400):
                    continue

                seen_urls.add(url)
                seen_urls.add(final_url)

                theme = pick_theme(title, summary, hints)
                items.append({
                    "dt_utc": dt_utc,
                    "label": label,
                    "stype": stype,
                    "theme": theme,
                    "title": title,
                    "why": first_sentence(summary, 200),
                    "url": final_url
                })
    # sort newest first
    items.sort(key=lambda x: (x["dt_utc"], x["label"]), reverse=True)
    return items

def choose_best(a, b):
    """Compare two items for same competitor+date; return the better one."""
    # 1) theme priority
    ta = THEME_ORDER.get(a["theme"], 9)
    tb = THEME_ORDER.get(b["theme"], 9)
    if ta != tb:
        return a if ta < tb else b
    # 2) source preference
    def pref(u):
        d = domain(u)
        if "developers." in d or "docs" in u: return 0
        if d.startswith("blog.") or d.endswith(".gov"): return 1
        return 2
    pa, pb = pref(a["url"]), pref(b["url"])
    if pa != pb:
        return a if pa < pb else b
    # 3) most recent
    return a if a["dt_utc"] >= b["dt_utc"] else b

def dedupe_by_date_competitor(items):
    """Group by (MM/DD in ET, competitor label) and keep the best row per group."""
    buckets = {}
    for it in items:
        dt_et = it["dt_utc"].astimezone(ET)
        mmdd = dt_et.strftime("%m/%d")
        key = (mmdd, it["label"])
        it_copy = dict(it)
        it_copy["date_mmdd"] = mmdd
        if key not in buckets:
            buckets[key] = it_copy
        else:
            buckets[key] = choose_best(buckets[key], it_copy)
    # return as list sorted by datetime desc then label
    out = list(buckets.values())
    out.sort(key=lambda x: (x["dt_utc"], x["label"]), reverse=True)
    return out

def render_html(items):
    # coverage window (ET)
    if items:
        newest = max(it["dt_utc"] for it in items).astimezone(ET).date()
        oldest = min(it["dt_utc"] for it in items).astimezone(ET).date()
    else:
        today_et = datetime.now(ET).date()
        newest = oldest = today_et
    def cov(d): return d.strftime("%b %d")
    coverage = f"{cov(oldest)}–{cov(newest)}, {newest.year}" if oldest.year == newest.year else f"{cov(oldest)}, {oldest.year}–{cov(newest)}, {newest.year}"

    # table rows
    rows = []
    for it in items:
        src = f'<a href="{it["url"]}" target="_blank" rel="noopener">Source</a>'
        rows.append(
            "<tr>"
            f"<td>{it['date_mmdd']}</td>"
            f"<td>{html.escape(it['label'])}</td>"
            f"<td>{it['theme']}</td>"
            f"<td>{html.escape(it['title'])}</td>"
            f"<td>{html.escape(it['why'])}</td>"
            f"<td>{src}</td>"
            "</tr>"
        )

    html_doc = f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>ReplicaRivals — Weekly Competitive Snapshot ({coverage})</title>
<style>
  body{{font-family:Inter,Arial,Helvetica,sans-serif;color:#111;background:#fff}}
  .container{{max-width:920px;margin:0 auto;border:1px solid #e5e7eb;border-radius:10px}}
  .section{{padding:18px 20px}}
  h2{{margin:0 0 6px;font-size:22px}}
  h3{{margin:0 0 8px;font-size:18px}}
  table{{border-collapse:collapse;width:100%;font-size:14px}}
  thead tr{{background:#111;color:#fff}}
  th,td{{padding:8px;vertical-align:top}}
  tbody tr{{border-bottom:1px solid #e5e7eb}}
  a{{color:#0e4cf5;text-decoration:none}}
  a:hover{{text-decoration:underline}}
</style></head><body>
<table width="100%" cellpadding="0" cellspacing="0"><tr><td>
<div class="container">

  <div class="section">
    <h2>ReplicaRivals — Weekly Competitive Snapshot</h2>
    <div style="color:#555;font-size:13px;">Coverage window: <strong>{coverage}</strong> • Audience: Exec, Sales, Marketing, Product</div>
  </div>

  <div class="section">
    <h3>Key Events (by Competitor)</h3>
    <table width="100%" cellpadding="8" cellspacing="0">
      <thead>
        <tr>
          <th align="left">Date (ET)</th>
          <th align="left">Competitor</th>
          <th align="left">Theme</th>
          <th align="left">What happened</th>
          <th align="left">Why it matters</th>
          <th align="left">Source</th>
        </tr>
      </thead>
      <tbody>
        {''.join(rows) if rows else "<tr><td colspan='6'>No material updates.</td></tr>"}
      </tbody>
    </table>
  </div>

</div>
</td></tr></table>
</body></html>"""
    return html_doc

def main():
    cfg = load_conf(CONF_PATH)

    # strict pass
    items = harvest(cfg, strict=True, extra_days=0)
    # relaxed if too few
    if len(items) < MIN_ITEMS:
        items = harvest(cfg, strict=False, extra_days=RELAX_DAYS)

    # dedupe by (date_mmdd in ET, competitor)
    items = dedupe_by_date_competitor(items)

    html_out = render_html(items)
    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html_out)
    print(f"[build_report_from_feeds] rows={len(items)} (dedup by date+competitor)")
    return 0

if __name__ == "__main__":
    sys.exit(main())

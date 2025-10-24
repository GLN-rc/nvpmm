#!/usr/bin/env python3
# Weekly report builder - ZERO API INSIGHTS
# - strict pass + relaxed fallback if too few items
# - fetch & extract article text (readability)
# - keyphrase extraction (YAKE) -> insight sentences (no boilerplate)
# - TL;DR & Deltas computed from items (no LLM)
# - de-duplication, HTTP 200 checks, MM/DD dates, no Tag column

import os, sys, re, html, json, collections
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse
import requests, feedparser, yaml
from dateutil import parser as dtp
from readability import Document
from bs4 import BeautifulSoup
import yake

OUTPUT_HTML   = os.environ.get("OUTPUT_HTML", "report.html")
CONF_PATH     = os.environ.get("NEWS_FEEDS_CONFIG", "config/news_feeds.yaml")
MIN_ITEMS     = int(os.environ.get("MIN_ITEMS", "4"))
RELAX_DAYS    = int(os.environ.get("RELAX_DAYS", "3"))
DEBUG_BUILDER = os.environ.get("DEBUG_BUILDER", "0") == "1"
CACHE_PATH    = os.environ.get("DELTA_CACHE", "data/last_items.json")

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/127 Safari/127"
S = requests.Session()
S.headers.update({"User-Agent": UA, "Referer": "https://github.com/replicarivals/workflow"})
TIMEOUT = 25

# ---------------- YAML / HTTP helpers ----------------

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

# ---------------- Theming / categorization ----------------

def pick_theme(title, summary, hints):
    t = f"{title} {summary}".lower()
    if any(k.lower() in t for k in hints.get("regulatory", [])): return "Regulatory"
    if any(k.lower() in t for k in hints.get("docs_gtm", [])):  return "Docs / GTM"
    if any(k.lower() in t for k in hints.get("product", [])):   return "Product"
    return "FYI"

# ---------------- Harvest (strict -> relaxed) ----------------

def allowed_by_rules(u: str, allowed_domains: set, allowed_prefixes: dict, excludes: list, strict: bool) -> bool:
    if any(x in u for x in excludes):
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
        if k.lower() in b: return True
    tokens = [t for k in kws for t in re.split(r"\W+", k.lower()) if t]
    return any(t and t in b for t in tokens)

def collect_items(cfg, strict=True, extra_days=0):
    days = int(cfg.get("window_days", 7)) + (extra_days if not strict else 0)
    allowed_domains = set(d.lower() for d in cfg.get("allowed_domains", []))
    allowed_prefixes = {k.lower(): v for k, v in (cfg.get("allowed_path_prefixes", {}) or {}).items()}
    excludes = [e.lower() for e in cfg.get("exclude_patterns", [])]
    theme_hints = cfg.get("theme_hints", {})

    raw, seen_urls = [], set()

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
                if not allowed_by_rules(url, allowed_domains, allowed_prefixes, excludes, strict):
                    continue
                dt = parse_date(e)
                if not within_window(dt, days):
                    continue

                title = (e.get("title") or "").strip()
                summary = e.get("summary") or e.get("description") or ""
                blob = f"{title} {summary}"

                if strict:
                    if kws and not any(k.lower() in blob.lower() for k in kws):
                        continue
                else:
                    if not soft_keyword_match(blob, kws):
                        continue

                if not http_ok(url):
                    continue

                seen_urls.add(url)
                theme = pick_theme(title, summary, theme_hints)
                raw.append({
                    "dt": dt,
                    "date": dt.astimezone(timezone.utc).date().isoformat(),
                    "label": label,
                    "stype": stype,
                    "theme": theme,
                    "title": title,
                    "raw_summary": summary,
                    "url": url,
                })

    # De-dup across feeds/pubs — prefer first-party docs, then vendor blog/.gov, then media; keep most recent
    def norm_title(t: str) -> str:
        t = t.lower()
        t = re.sub(r"[^a-z0-9 ]+", " ", t)
        t = re.sub(r"\b(pr|press|announces|launches|introduces|releases|updated?)\b", "", t)
        t = re.sub(r"\s+", " ", t).strip()
        return t

    best_by_key = {}
    for it in raw:
        key = (it["label"].lower(), it["theme"], norm_title(it["title"]))
        d = domain(it["url"])
        pr = 2
        if "developers." in d or "docs" in it["url"]: pr = 0
        elif d.startswith("blog.") or d.endswith(".gov"): pr = 1
        score = (pr, -int(it["dt"].timestamp()))
        if key not in best_by_key or score < best_by_key[key]["_score"]:
            v = it.copy(); v["_score"] = score
            best_by_key[key] = v

    items = list(best_by_key.values())
    items.sort(key=lambda x: (x["dt"], x["label"]), reverse=True)
    return items

# ---------------- Content extraction & insights (NO LLM) ----------------

def fetch_main_text(url: str) -> str:
    """Extract main article text using readability + bs4; fall back to text/html stripping."""
    try:
        r = S.get(url, timeout=TIMEOUT)
        r.raise_for_status()
        doc = Document(r.text)
        html_body = doc.summary()
        soup = BeautifulSoup(html_body, "html.parser")
        # remove nav/code/figcaptions
        for tag in soup(["script","style","nav","code","pre","aside","figure","figcaption"]):
            tag.decompose()
        text = soup.get_text(" ", strip=True)
        # limit length to keep YAKE fast
        text = re.sub(r"\s+", " ", text).strip()
        return text[:8000]
    except Exception:
        return ""

_yake = yake.KeywordExtractor(lan="en", n=1, top=12)

def key_phrases(text: str):
    try:
        kws = [w for (w,score) in _yake.extract_keywords(text)]
        # de-dup while preserving order
        seen=set(); out=[]
        for k in kws:
            k = k.strip().lower()
            if k and k not in seen:
                out.append(k); seen.add(k)
        return out[:10]
    except Exception:
        return []

def insight_from_phrases(item, phrases):
    """Compose a short insight sentence using signals from phrases + theme. 16–26 words."""
    label = item["label"]; theme = item["theme"]
    # light weighting
    words = set(phrases[:6])
    def has(*ks): return any(k in words for k in ks)
    # theme-driven templates, but filled from content keywords (no title repeat)
    if theme == "Product":
        if has("pricing","tier","license","bundle"):
            return f"Alters {label} deal economics; sharpen value proof and counters tied to time-to-deploy and operational privacy."
        if has("policy","identity","threat","content"):
            return f"Expands {label} policy depth; expect RFP asks for conditional isolation—position cross-team control and quick rollout."
        if has("messaging","chat","mobile","byod"):
            return f"Pushes {label} toward comms/mobile; reframe scope around unattributable access and full-stack isolation rather than chat features."
        return f"Signals capability momentum for {label}; test impact on shortlists and address parity questions early in cycles."
    if theme == "Docs / GTM":
        if has("policy","zero trust","isolation","sse","bundle","packaging"):
            return f"Indicates packaging/enablement moves; anticipate isolation bundled into Zero Trust SKUs, raising pricing pressure in enterprise deals."
        return f"Documentation shift likely precedes GTM changes; watch for updated RFP language and buyer evaluation criteria."
    if theme == "Regulatory":
        if has("cisa","kev","exploit","smb","deadline","directive"):
            return "Creates compliance pressure and near-term triggers for isolated, auditable workflows in public sector and regulated accounts."
        return "Raises risk visibility; expect tighter controls and shorter remediation windows across security-sensitive segments."
    # catch-all using top phrases
    top = ", ".join(list(words)[:2]) if words else "buyer criteria"
    return f"Likely to influence {top}; integrate into talk tracks and discovery this week."

# ---------------- TL;DR & Deltas (NO LLM) ----------------

def build_tldr(items, texts_by_idx, max_bullets=4):
    if not items: return ["No material updates."]
    # score items by theme priority + recency + content richness
    pri = {"Product":0,"Docs / GTM":1,"Regulatory":2,"FYI":3}
    scored = []
    for i,it in enumerate(items):
        text = texts_by_idx.get(i,"")
        richness = min(len(text)//300, 3)  # 0..3
        scored.append((pri.get(it["theme"],9), -int(it["dt"].timestamp()), -richness, i))
    scored.sort()
    bullets=[]
    for _,__,___,i in scored[:max_bullets]:
        it = items[i]
        why = texts_by_idx.get(i,"")
        # compress to 18–22 words using phrases
        phrases = key_phrases(why)[:4]
        gist = ", ".join(phrases) if phrases else "policy, packaging, and buyer urgency"
        if it["theme"]=="Product":
            bullets.append(f"{it['label']}: product change shaping evaluations — {gist}.")
        elif it["theme"]=="Docs / GTM":
            bullets.append(f"{it['label']}: GTM/docs signal packaging shifts — {gist}.")
        elif it["theme"]=="Regulatory":
            bullets.append(f"Regulatory: accelerates decisions — {gist}.")
        else:
            bullets.append(f"{it['label']}: notable signal — {gist}.")
    return bullets

def load_prev_cache(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"items":[]}

def save_cache(path, items):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    data = [{"label":i["label"], "theme":i["theme"], "title":i["title"], "url":i["url"]} for i in items[:60]]
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"saved_at": datetime.now(timezone.utc).isoformat(), "items": data}, f, indent=2)

def build_deltas(curr, prev):
    def k(i): return (i["label"].lower(), i["theme"], re.sub(r"\W+","", i["title"].lower()))
    prev_set = {k(i) for i in prev}
    curr_set = {k(i) for i in curr}
    added = curr_set - prev_set
    removed = prev_set - curr_set
    add_theme = collections.Counter([a[1] for a in added])
    rem_theme = collections.Counter([r[1] for r in removed])
    out=[]
    if add_theme:
        out.append("New this week — " + ", ".join(f"{t}: +{n}" for t,n in add_theme.most_common()))
    if rem_theme:
        out.append("Quiet this week — " + ", ".join(f"{t}: −{n}" for t,n in rem_theme.most_common()))
    # competitor momentum
    add_comp = collections.Counter([a[0] for a in added])
    if add_comp:
        comps = ", ".join(c for c,_ in add_comp.most_common(3))
        out.append(f"Increased activity: {comps}")
    if not out:
        out.append("No major shifts vs. last week.")
    return out[:4]

# ---------------- HTML rendering ----------------

def to_html(items, start, end, tldr, deltas, whys, texts_by_idx):
    coverage = f"{start:%b %d}–{end:%b %d, %Y}" if start.year == end.year else f"{start:%b %d, %Y}–{end:%b %d, %Y}"

    rows=[]
    for idx,it in enumerate(items):
        date_mmdd = it["dt"].astimezone(timezone.utc).strftime("%m/%d")
        src = f'<a href="{it["url"]}" target="_blank" rel="noopener">Source</a>'
        why = whys.get(idx) or "Potential to influence buyer criteria; integrate into talk tracks."
        rows.append(
            "<tr>"
            f"<td>{date_mmdd}</td>"
            f"<td>{html.escape(it['label'])}</td>"
            f"<td>{it['theme']}</td>"
            f"<td>{html.escape(it['title'])}</td>"
            f"<td>{html.escape(why)}</td>"
            f"<td>{src}</td>"
            "</tr>"
        )

    def bullets(lst): 
        return "".join(f"<li>{html.escape(x)}</li>" for x in lst) if lst else "<li>No material updates.</li>"

    # Build role actions from items + phrases (still zero-LLM)
    exec_actions, sales_actions, mkt_actions, prod_actions = derive_actions(items, texts_by_idx)

    def role_block(role, lst):
        if not lst: return ""
        return ("<tr>"
                f"<td width='22%'><strong>{role}</strong></td>"
                f"<td><ul style='margin:0 0 0 18px;'>{bullets(lst)}</ul></td>"
                "</tr>")

    actions_rows = "".join([
        role_block("Exec", exec_actions),
        role_block("Sales", sales_actions),
        role_block("Marketing", mkt_actions),
        role_block("Product", prod_actions),
    ]) or "<tr><td colspan='2'>No role-specific actions this week.</td></tr>"

    return f"""<!doctype html>
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
      {bullets(tldr)}
    </ul>
  </div>
</div>

<div class="section">
  <h3>Key Events (by Competitor)</h3>
  <table class="table" width="100%" cellpadding="8" cellspacing="0">
    <thead><tr>
      <th align="left">Date</th>
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
    {bullets(deltas)}
  </ul>
</div>

<div class="section">
  <h3>Recommended Actions (by Function)</h3>
  <table class="table" width="100%" cellpadding="8" cellspacing="0">
    <tbody>
      {actions_rows}
    </tbody>
  </table>
</div>

<div class="section footer" style="color:#666;font-size:12px">
  <div><strong>Note:</strong> Source links are validated (HTTP 200) at build time. Insights are locally generated from page text and keywords (no external AI).</div>
</div>

</div></body></html>"""

# ---------------- Derive actions from items (no LLM) ----------------

def derive_actions(items, texts_by_idx):
    exec_actions, sales_actions, mkt_actions, prod_actions = [], [], [], []
    # score items for actionability
    pri = {"Product":0,"Docs / GTM":1,"Regulatory":2,"FYI":3}
    sorted_idx = sorted(range(len(items)), key=lambda i: (pri.get(items[i]["theme"],9), -int(items[i]["dt"].timestamp())))
    top = sorted_idx[:6]

    def short(url): return url

    for i in top:
        it = items[i]
        text = texts_by_idx.get(i,"")
        kws = key_phrases(text)
        label, theme, u = it["label"], it["theme"], it["url"]

        if theme == "Regulatory" and ("cisa" in u or "kev" in u or "gov" in domain(u)):
            exec_actions.append(f"Prioritize opportunities under advisory; approve isolated workspace pilots tied to deadlines — {short(u)}")
            mkt_actions.append(f"Update advisory landing with ‘why isolation now’; link source — {short(u)}")
        elif theme == "Docs / GTM":
            if any(k in kws for k in ["policy","isolation","zero trust","bundle","packaging"]):
                sales_actions.append(f"Add policy-driven isolation talk track vs {label}; cite doc — {short(u)}")
                prod_actions.append(f"Audit identity/threat/content policy gaps vs {label} doc; propose quick wins — {short(u)}")
        elif theme == "Product":
            if any(k in kws for k in ["pricing","tier","bundle","license"]):
                exec_actions.append(f"Fund 1–2 lighthouse head-to-heads vs {label}; prepare pricing counters — {short(u)}")
            else:
                sales_actions.append(f"Position full-stack isolation vs {label} feature; include time-to-deploy proof — {short(u)}")
                mkt_actions.append(f"Publish 300-word comparison: {label} update vs Replica’s ‘enterprise control + operational privacy’ — {short(u)}")

    # dedupe / cap
    def dedupe_cap(seq, n=2):
        seen=set(); out=[]
        for s in seq:
            if s not in seen:
                out.append(s); seen.add(s)
        return out[:n]

    return (dedupe_cap(exec_actions), dedupe_cap(sales_actions),
            dedupe_cap(mkt_actions), dedupe_cap(prod_actions))

# --------------------------------- main -------------------------------------

def main():
    cfg = load_conf(CONF_PATH)

    items = collect_items(cfg, strict=True, extra_days=0)
    if len(items) < MIN_ITEMS:
        items = collect_items(cfg, strict=False, extra_days=RELAX_DAYS)

    # Extract article text and generate insights
    texts_by_idx = {}
    for idx, it in enumerate(items):
        texts_by_idx[idx] = fetch_main_text(it["url"])

    whys = {}
    for idx, it in enumerate(items):
        phrases = key_phrases(texts_by_idx.get(idx,""))
        whys[idx] = insight_from_phrases(it, phrases)

    # TL;DR and Deltas
    tldr = build_tldr(items, texts_by_idx, max_bullets=4)
    prev = load_prev_cache(CACHE_PATH).get("items", [])
    deltas = build_deltas(items, prev)
    try:
        save_cache(CACHE_PATH, items)
    except Exception:
        pass

    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=int(cfg.get("window_days", 7)) - 1)
    html_out = to_html(items, start, today, tldr, deltas, whys, texts_by_idx)
    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html_out)
    print(f"[build_report_from_feeds] items={len(items)} (min={MIN_ITEMS}) zero-api insights=on")
    return 0

if __name__ == "__main__":
    sys.exit(main())

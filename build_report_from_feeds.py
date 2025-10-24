#!/usr/bin/env python3
# Weekly report builder (no paid LLM)
# - Follows redirects to final URLs (drops Google News links)
# - Strong de-dupe by title + content similarity
# - Insights/TL;DR/Actions from extracted page text (readability + YAKE)
# - Dates MM/DD, no Tag column

import os, sys, re, html, json, difflib, hashlib, collections
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse, urlsplit, parse_qs
import requests, feedparser, yaml
from dateutil import parser as dtp
from readability import Document
from bs4 import BeautifulSoup
import yake

# ---- config/env
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

# ---- helpers
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

def norm_url(u: str) -> str:
    if not u: return ""
    # unwrap Google News redirect if present
    if "news.google.com" in u:
        q = parse_qs(urlsplit(u).query)
        if "url" in q and q["url"]:
            u = q["url"][0]
    # strip UTMs etc.
    u = re.sub(r"(\?|&)(utm_[^=]+|fbclid|gclid)=[^&#]+", "", u, flags=re.I)
    u = re.sub(r"[?&]$", "", u)
    return u

def fetch_final(url: str):
    """Return (final_url, status_code, text) after redirects (or (url, code, '') on failure)."""
    try:
        r = S.get(url, allow_redirects=True, timeout=TIMEOUT)
        final = r.url
        # unwrap Google News even if redirected through it
        final = norm_url(final)
        return final, r.status_code, r.text if 200 <= r.status_code < 400 else ""
    except Exception:
        return url, 0, ""

def http_ok(url: str) -> bool:
    _, code, _ = fetch_final(url)
    return 200 <= code < 400

def within_window(dt: datetime, days: int) -> bool:
    now = datetime.now(timezone.utc)
    return (now - dt).total_seconds() <= days * 86400 + 3600

def parse_date(entry):
    for field in ("published", "updated"):
        val = entry.get(field)
        if val:
            try: return dtp.parse(val).astimezone(timezone.utc)
            except Exception: pass
    for field in ("published_parsed", "updated_parsed"):
        val = getattr(entry, field, None)
        if val:
            try: return datetime(*val[:6], tzinfo=timezone.utc)
            except Exception: pass
    return datetime.now(timezone.utc)

def clean_text(html_text: str) -> str:
    if not html_text: return ""
    doc = Document(html_text)
    html_body = doc.summary()
    soup = BeautifulSoup(html_body, "html.parser")
    for tag in soup(["script","style","nav","code","pre","aside","figure","figcaption"]):
        tag.decompose()
    text = soup.get_text(" ", strip=True)
    return re.sub(r"\s+", " ", text).strip()

def short_hash(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8", "ignore")).hexdigest()[:10]

_yake = yake.KeywordExtractor(lan="en", n=1, top=12)
def key_phrases(text: str):
    try:
        kws = [w for (w,score) in _yake.extract_keywords(text)]
        seen=set(); out=[]
        for k in kws:
            k = k.strip().lower()
            if k and k not in seen:
                out.append(k); seen.add(k)
        return out[:10]
    except Exception:
        return []

# ---- categorize
def pick_theme(title, summary, hints):
    t = f"{title} {summary}".lower()
    if any(k.lower() in t for k in hints.get("regulatory", [])): return "Regulatory"
    if any(k.lower() in t for k in hints.get("docs_gtm", [])):  return "Docs / GTM"
    if any(k.lower() in t for k in hints.get("product", [])):   return "Product"
    return "FYI"

# ---- rule filters
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
        if k.lower() in b: return True
    tokens = [t for k in kws for t in re.split(r"\W+", k.lower()) if t]
    return any(t and t in b for t in tokens)

# ---- harvest (strict -> relaxed)
def collect_items(cfg, strict=True, extra_days=0):
    days = int(cfg.get("window_days", 7)) + (extra_days if not strict else 0)
    allowed_domains = set(d.lower() for d in cfg.get("allowed_domains", []))
    allowed_prefixes = {k.lower(): v for k, v in (cfg.get("allowed_path_prefixes", {}) or {}).items()}
    excludes = [e.lower() for e in cfg.get("exclude_patterns", [])]
    theme_hints = cfg.get("theme_hints", {})

    raw, seen = [], set()

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
                if not url or url in seen:
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
                    if kws and not any(k.lower() in blob.lower() for k in kws): continue
                else:
                    if not soft_keyword_match(blob, kws): continue

                # Validate and resolve to final URL
                final_url, code, html_text = fetch_final(url)
                if not (200 <= code < 400): continue

                seen.add(url)
                seen.add(final_url)

                theme = pick_theme(title, summary, theme_hints)
                raw.append({
                    "dt": dt,
                    "date": dt.astimezone(timezone.utc).date().isoformat(),
                    "label": label,
                    "stype": stype,
                    "theme": theme,
                    "title": title,
                    "raw_summary": summary,
                    "url": final_url,
                    "_html": html_text
                })

    # ---- strong de-dup: title normalization + content similarity
    def norm_title(t: str) -> str:
        t = t.lower()
        t = re.sub(r"[^a-z0-9 ]+", " ", t)
        t = re.sub(r"\b(pr|press|announces?|launch(es|ed)?|introduc(es|ed)?|releases?|updated?)\b", "", t)
        t = re.sub(r"\s+", " ", t).strip()
        return t

    # prepare content text + small hash for fast equality
    for it in raw:
        text = clean_text(it["_html"])
        it["_text"] = text
        it["_hash"] = short_hash(text[:1000]) if text else ""

    # cluster within (competitor,label) by title key; then merge by content similarity
    clusters = {}
    for it in raw:
        key = (it["label"].lower(), it["theme"], norm_title(it["title"]))
        clusters.setdefault(key, []).append(it)

    deduped = []
    for key, items in clusters.items():
        # sort by (first-party/docs) then recency
        def pref_score(u):
            d = domain(u)
            if "developers." in d or "docs" in u: return 0
            if d.startswith("blog.") or d.endswith(".gov"): return 1
            return 2
        items.sort(key=lambda x: (pref_score(x["url"]), -int(x["dt"].timestamp())))
        kept = []
        for cand in items:
            dup = False
            for k in kept:
                # if content hashes match OR high similarity on text/title -> drop as duplicate
                if cand["_hash"] and cand["_hash"] == k["_hash"]:
                    dup = True; break
                if cand["_text"] and k["_text"]:
                    if difflib.SequenceMatcher(None, cand["_text"][:1500], k["_text"][:1500]).ratio() > 0.90:
                        dup = True; break
                if difflib.SequenceMatcher(None, norm_title(cand["title"]), norm_title(k["title"])).ratio() > 0.92:
                    dup = True; break
            if not dup:
                kept.append(cand)
        # keep the best one
        if kept:
            best = kept[0]
            deduped.append(best)

    # final sort recent first
    deduped.sort(key=lambda x: (x["dt"], x["label"]), reverse=True)
    return deduped

# ---- insights from content (no LLM)
def compose_why(item, phrases):
    label = item["label"]; theme = item["theme"]
    words = set(phrases[:6])
    def has(*ks): return any(k in words for k in ks)
    if theme == "Product":
        if has("pricing","tier","bundle","license"):
            return f"Changes {label} deal economics; arm reps with counters and time-to-deploy proof."
        if has("policy","identity","threat","content"):
            return f"Signals richer policy controls; expect RFP asks for conditional isolation and fine-grained audit."
        if has("messaging","chat","mobile","byod"):
            return f"Pivots toward comms/mobile; reframe against Replica’s full-stack isolation and unattributable access."
        return f"Shifts evaluation criteria; test shortlist impact and address parity early."
    if theme == "Docs / GTM":
        if has("isolation","policy","zero trust","bundle","packaging","sse"):
            return "Hints at bundling isolation inside Zero Trust SKUs; expect pricing/packaging pressure in enterprise deals."
        return "Doc posture change usually precedes GTM moves; watch RFP language and buyer expectations."
    if theme == "Regulatory":
        if has("cisa","kev","exploit","deadline","directive"):
            return "Creates compliance pressure and near-term triggers for isolated, auditable workflows."
        return "Raises perceived risk; accelerates control adoption timelines."
    # fallback
    top = ", ".join(list(words)[:2]) if words else "buyer criteria"
    return f"Likely to influence {top}; fold into talk tracks this week."

def build_tldr(items):
    if not items: return ["No material updates."]
    # group by competitor, prefer Product/Docs in summary
    pri = {"Product":0,"Docs / GTM":1,"Regulatory":2,"FYI":3}
    by_comp = collections.defaultdict(list)
    for it in items:
        by_comp[it["label"]].append(it)
    bullets=[]
    for comp, arr in sorted(by_comp.items(), key=lambda kv: min(pri.get(i["theme"],9) for i in kv[1])):
        # roll up phrases across this competitor
        phrases = []
        for it in arr:
            text = it.get("_text","")
            phrases += key_phrases(text)
        top = [p for p,_ in collections.Counter(phrases).most_common(4)]
        gist = ", ".join(top) if top else "policy, packaging, buyer urgency"
        theme = sorted(arr, key=lambda i: (pri.get(i["theme"],9), -int(i["dt"].timestamp())))[0]["theme"]
        if theme=="Product":
            bullets.append(f"{comp}: product/feature shift shaping evaluations — {gist}.")
        elif theme=="Docs / GTM":
            bullets.append(f"{comp}: docs/GTM signal packaging changes — {gist}.")
        elif theme=="Regulatory":
            bullets.append(f"Regulatory: accelerates decision timelines — {gist}.")
        else:
            bullets.append(f"{comp}: notable movement — {gist}.")
        if len(bullets) >= 4: break
    return bullets

# ---- deltas vs last week
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
        out.append("Quieter vs last week — " + ", ".join(f"{t}: −{n}" for t,n in rem_theme.most_common()))
    add_comp = collections.Counter([a[0] for a in added])
    if add_comp:
        comps = ", ".join(c for c,_ in add_comp.most_common(3))
        out.append(f"Momentum: {comps}")
    if not out:
        out.append("No major shifts vs last week.")
    return out[:4]

# ---- actions from items (no boilerplate, no Google News links)
def best_link(items):
    def pref(u):
        d = domain(u)
        if "developers." in d or "docs" in u: return 0
        if d.startswith("blog.") or d.endswith(".gov"): return 1
        return 2
    return sorted(items, key=lambda it: (pref(it["url"]), -int(it["dt"].timestamp())))[0]["url"]

def build_actions(items):
    exec_actions, sales_actions, mkt_actions, prod_actions = [], [], [], []
    if not items: return exec_actions, sales_actions, mkt_actions, prod_actions

    by_theme = collections.defaultdict(list)
    for it in items:
        by_theme[it["theme"]].append(it)

    # Exec: regulatory triggers or sizable product moves
    if by_theme.get("Regulatory"):
        u = best_link(by_theme["Regulatory"])
        exec_actions.append(f"Prioritize advisory-affected accounts; approve isolated workspace pilots to hit deadlines — {u}")
    prod_moves = [it for it in items if it["theme"]=="Product" and it["stype"]=="competitor"]
    if prod_moves:
        # pick top competitor and concrete link
        u = best_link(prod_moves)
        comps = ", ".join(sorted({i['label'] for i in prod_moves})[:3])
        exec_actions.append(f"Fund 1–2 lighthouse head-to-heads vs {comps}; tie offers to time-to-deploy proof — {u}")

    # Sales: doc talk-tracks + product counters
    docs = by_theme.get("Docs / GTM", [])[:2]
    for it in docs:
        sales_actions.append(f"Add policy-driven isolation talk track vs {it['label']}; cite doc — {best_link([it])}")
    for it in prod_moves[:2]:
        sales_actions.append(f"Position full-stack isolation vs {it['label']} feature; include time-to-deploy proof — {best_link([it])}")

    # Marketing: a single comparison + advisory landing, grounded in real links
    if prod_moves:
        it = prod_moves[0]
        mkt_actions.append(f"Publish 300-word comparison: {it['label']} update vs Replica’s enterprise control + operational privacy — {best_link([it])}")
    if by_theme.get("Regulatory"):
        it = by_theme["Regulatory"][0]
        mkt_actions.append(f"Refresh advisory landing with ‘why isolation now’; link source — {best_link([it])}")

    # Product: gaps from docs + validate demand from launches
    if docs:
        it = docs[0]
        prod_actions.append(f"Audit identity/threat/content policy gaps vs {it['label']} doc; propose quick wins — {best_link([it])}")
    if prod_moves:
        it = prod_moves[0]
        prod_actions.append(f"Validate demand for {it['label']} feature in current RFPs; scope parity if repeated — {best_link([it])}")

    # dedupe & cap
    def dedupe_cap(seq, n=2):
        seen=set(); out=[]
        for s in seq:
            if s not in seen:
                out.append(s); seen.add(s)
        return out[:n]
    return (dedupe_cap(exec_actions), dedupe_cap(sales_actions),
            dedupe_cap(mkt_actions), dedupe_cap(prod_actions))

# ---- HTML
def to_html(items, start, end):
    coverage = f"{start:%b %d}–{end:%b %d, %Y}" if start.year == end.year else f"{start:%b %d, %Y}–{end:%b %d, %Y}"

    # Prepare per-row insights
    whys = {}
    for idx, it in enumerate(items):
        phrases = key_phrases(it.get("_text",""))
        whys[idx] = compose_why(it, phrases)

    # TL;DR
    tldr = build_tldr(items)

    # Table rows (MM/DD, no Tag)
    rows=[]
    for idx,it in enumerate(items):
        date_mmdd = it["dt"].astimezone(timezone.utc).strftime("%m/%d")
        src = f'<a href="{it["url"]}" target="_blank" rel="noopener">Source</a>'
        rows.append(
            "<tr>"
            f"<td>{date_mmdd}</td>"
            f"<td>{html.escape(it['label'])}</td>"
            f"<td>{it['theme']}</td>"
            f"<td>{html.escape(it['title'])}</td>"
            f"<td>{html.escape(whys[idx])}</td>"
            f"<td>{src}</td>"
            "</tr>"
        )

    # Deltas
    prev = load_prev_cache(CACHE_PATH).get("items", [])
    deltas = build_deltas(items, prev)
    try: save_cache(CACHE_PATH, items)
    except Exception: pass

    # Actions
    exec_actions, sales_actions, mkt_actions, prod_actions = build_actions(items)
    def role_block(role, lst):
        if not lst: return ""
        return ("<tr>"
                f"<td width='22%'><strong>{role}</strong></td>"
                f"<td><ul style='margin:0 0 0 18px;'>"
                + "".join(f"<li>{html.escape(x)}</li>" for x in lst)
                + "</ul></td></tr>")
    actions_rows = "".join([
        role_block("Exec", exec_actions),
        role_block("Sales", sales_actions),
        role_block("Marketing", mkt_actions),
        role_block("Product", prod_actions),
    ]) or "<tr><td colspan='2'>No role-specific actions this week.</td></tr>"

    # HTML skeleton
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
      {''.join(f"<li>{html.escape(x)}</li>" for x in tldr) if tldr else "<li>No material updates.</li>"}
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
    {''.join(f"<li>{html.escape(x)}</li>" for x in deltas) if deltas else "<li>No major shifts vs last week.</li>"}
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

<div class="section" style="color:#666;font-size:12px">
  <div><strong>Note:</strong> Links are the publisher’s final URLs (no Google News). Duplicates are clustered by title + content similarity.</div>
</div>

</div></body></html>"""

# ---- main
def main():
    cfg = load_conf(CONF_PATH)
    items = collect_items(cfg, strict=True, extra_days=0)
    if len(items) < MIN_ITEMS:
        items = collect_items(cfg, strict=False, extra_days=RELAX_DAYS)

    # if still empty, emit minimal doc
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=int(cfg.get("window_days", 7)) - 1)

    html_out = to_html(items, start, today)
    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html_out)
    print(f"[build_report_from_feeds] items={len(items)} (min={MIN_ITEMS}) dedup=on final_urls=on")
    return 0

if __name__ == "__main__":
    sys.exit(main())

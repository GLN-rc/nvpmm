#!/usr/bin/env python3
# Weekly report from RSS/Atom feeds with:
# - strict pass + relaxed fallback (if too few items)
# - robust de-duplication across feeds/domains
# - TL;DR summarization (no title copy)
# - Deltas vs prior week (data/last_items.json cache)
# - Actions derived from items (no canned bullets)
# - MM/DD dates, no Tag column, link 200-checks

import os, sys, re, html, json, collections
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse
import requests, feedparser, yaml
from dateutil import parser as dtp

OUTPUT_HTML   = os.environ.get("OUTPUT_HTML", "report.html")
CONF_PATH     = os.environ.get("NEWS_FEEDS_CONFIG", "config/news_feeds.yaml")
MIN_ITEMS     = int(os.environ.get("MIN_ITEMS", "4"))
RELAX_DAYS    = int(os.environ.get("RELAX_DAYS", "3"))
DEBUG_BUILDER = os.environ.get("DEBUG_BUILDER", "0") == "1"
CACHE_PATH    = os.environ.get("DELTA_CACHE", "data/last_items.json")

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/127 Safari/537.36"
S = requests.Session()
S.headers.update({"User-Agent": UA, "Referer": "https://github.com/replicarivals/workflow"})
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

# ----------------------------- Categorization -------------------------------

def pick_theme(title, summary, hints):
    t = f"{title} {summary}".lower()
    if any(k.lower() in t for k in hints.get("regulatory", [])): return "Regulatory"
    if any(k.lower() in t for k in hints.get("docs_gtm", [])):  return "Docs / GTM"
    if any(k.lower() in t for k in hints.get("product", [])):   return "Product"
    return "FYI"

def derive_insight(item):
    """Concise, non-duplicative 'Why it matters'."""
    title = item["title"]
    theme = item["theme"]
    label = item["label"]
    why_seed = (item.get("raw_summary") or "").lower()
    t_low = f"{title} {why_seed}".lower()

    if theme == "Regulatory":
        if "cisa" in t_low or "kev" in t_low:
            return "Creates compliance pressure and near-term triggers for isolated, auditable workflows."
        return "Raises risk visibility; expect tighter controls and shorter remediation windows."
    if theme == "Docs / GTM":
        if any(k in t_low for k in ["isolation", "policy", "zero trust"]):
            return "Signals bundling/price pressure as isolation is positioned inside larger Zero Trust deals."
        return "Doc changes often precede packaging/sales motions—watch RFP language."
    if theme == "Product":
        if any(k in t_low for k in ["launch", "release", "ga"]):
            return f"Expands {label} footprint; stress Replica’s full-stack isolation vs point features."
        if any(k in t_low for k in ["pricing", "tier", "license"]):
            return "Changes deal economics; prepare counters and time-to-deploy proof."
        if any(k in t_low for k in ["messaging","secure messaging","chat"]):
            return "Emphasizes comms over isolation; reframe to unattributable access and policy depth."
        return "May shift shortlists; validate impact in current evaluations."
    if any(k in t_low for k in ["research","osint","investigator"]):
        return "Lifts TOFU with OSINT/investigation teams; reference in discovery."
    return "Likely to influence buyer criteria; integrate into talk tracks."

# -------------------------- Filtering & collection --------------------------

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
    allowed_domains = set([d.lower() for d in cfg.get("allowed_domains", [])])
    allowed_prefixes = {k.lower(): v for k, v in (cfg.get("allowed_path_prefixes", {}) or {}).items()}
    excludes = [e.lower() for e in cfg.get("exclude_patterns", [])]
    theme_hints = cfg.get("theme_hints", {})

    raw, seen_urls = [], set()
    reasons = collections.Counter()
    per_feed_counts = collections.Counter()

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
                reasons["feed_parse_error"] += 1; continue
            kept_this_feed = 0
            for e in fp.entries:
                url = norm_url(e.get("link",""))
                if not url: reasons["no_url"] += 1; continue
                if url in seen_urls: reasons["duplicate_url"] += 1; continue
                if not allowed_by_rules(url, allowed_domains, allowed_prefixes, excludes, strict):
                    reasons["domain_or_path_filtered"] += 1; continue

                dt = parse_date(e)
                if not within_window(dt, days):
                    reasons["outside_window"] += 1; continue

                title = (e.get("title") or "").strip()
                summary = e.get("summary") or e.get("description") or ""
                blob = f"{title} {summary}"

                if strict:
                    if kws and not any(k.lower() in blob.lower() for k in kws):
                        reasons["keyword_filtered_strict"] += 1; continue
                else:
                    if not soft_keyword_match(blob, kws):
                        reasons["keyword_filtered_relaxed"] += 1; continue

                if not http_ok(url):
                    reasons["http_non_200"] += 1; continue

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
                kept_this_feed += 1
            per_feed_counts[feed_url] += kept_this_feed

    # --- robust de-duplication across feeds/publishers ---
    def norm_title(t: str) -> str:
        t = t.lower()
        t = re.sub(r"[^a-z0-9 ]+", " ", t)
        t = re.sub(r"\b(pr|press|announces|launches|introduces|releases|update|updated)\b", "", t)
        t = re.sub(r"\s+", " ", t).strip()
        return t

    best_by_key = {}
    for it in raw:
        key = (it["label"].lower(), it["theme"], norm_title(it["title"]))
        # prefer first-party/docs and more recent
        d = domain(it["url"])
        priority = 2
        if "developers." in d or "docs" in it["url"]: priority = 0
        elif d.endswith(".gov") or d.startswith("blog."): priority = 1
        score = (priority, -int(it["dt"].timestamp()))
        if key not in best_by_key or score < best_by_key[key]["_score"]:
            best = it.copy(); best["_score"] = score
            best_by_key[key] = best

    items = list(best_by_key.values())
    items.sort(key=lambda x: (x["dt"], x["label"]), reverse=True)

    # derive insights
    for it in items:
        it["why"] = derive_insight(it)

    if DEBUG_BUILDER:
        mode = "STRICT" if strict else f"RELAXED(+{extra_days}d)"
        print(f"[builder] {mode}: raw={len(raw)} kept(after dedupe)={len(items)}", file=sys.stderr)
        print("[builder] drop reasons:", dict(reasons), file=sys.stderr)
        print("[builder] per-feed kept:", dict(per_feed_counts), file=sys.stderr)

    return items

# ----------------------------- TL;DR builder --------------------------------

def build_tldr(items, max_bullets=4):
    # cluster by competitor, prefer Product/Docs items, then Regulatory
    if not items: return ["No material updates."]
    by_label = collections.defaultdict(list)
    for it in items:
        by_label[it["label"]].append(it)

    bullets = []
    # priority ordering: Product -> Docs -> Regulatory -> FYI
    order = {"Product":0, "Docs / GTM":1, "Regulatory":2, "FYI":3}
    for label, arr in sorted(by_label.items(), key=lambda kv: min(order.get(i["theme"],9) for i in kv[1])):
        # pick the best representative
        best = sorted(arr, key=lambda i: (order.get(i["theme"],9), -int(i["dt"].timestamp())))[0]
        if best["theme"] == "Product":
            text = f"{label}: new/updated capability shifts evaluations — {best['why']}"
        elif best["theme"] == "Docs / GTM":
            text = f"{label}: docs/packaging posture evolving — {best['why']}"
        elif best["theme"] == "Regulatory":
            text = f"Regulatory: {best['why']}"
        else:
            text = f"{label}: {best['why']}"
        bullets.append(f"<li>{html.escape(text)}</li>")
        if len(bullets) >= max_bullets: break
    return bullets

# ----------------------------- Deltas vs prior -------------------------------

def load_prev_cache(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"items":[]}

def save_cache(path, items):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    data = [{"label":i["label"], "theme":i["theme"], "title":i["title"], "url":i["url"]} for i in items[:40]]
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"saved_at": datetime.now(timezone.utc).isoformat(), "items": data}, f, indent=2)

def build_deltas(curr, prev):
    # compare on (label, theme, norm_title)
    def k(i): return (i["label"].lower(), i["theme"], re.sub(r"\W+","", i["title"].lower()))
    prev_set = {tuple(k(i)) for i in prev}
    curr_set = {tuple(k(i)) for i in curr}
    added = curr_set - prev_set
    removed = prev_set - curr_set

    # summarize by theme
    add_theme = collections.Counter([a[1] for a in added])
    rem_theme = collections.Counter([r[1] for r in removed])

    bullets = []
    if add_theme:
        top = ", ".join(f"{t}: +{n}" for t,n in add_theme.most_common())
        bullets.append(f"New signals this week — {html.escape(top)}.")
    if rem_theme:
        top = ", ".join(f"{t}: −{n}" for t,n in rem_theme.most_common())
        bullets.append(f"Quiet vs. last week — {html.escape(top)}.")
    # competitor focus shifts
    add_comp = collections.Counter([a[0] for a in added])
    if add_comp:
        comps = ", ".join(c for c,_ in add_comp.most_common(3))
        bullets.append(f"Increased activity: {html.escape(comps)}.")
    if not bullets:
        bullets.append("No major shifts vs. last week.")
    return [f"<li>{b}</li>" for b in bullets[:4]]

# ----------------------------- Actions from items ----------------------------

def summarize_competitor_focus(items):
    by_comp = collections.defaultdict(lambda: {"Product": [], "Docs / GTM": [], "Regulatory": [], "FYI": []})
    for it in items:
        by_comp[it["label"]][it["theme"]].append(it)
    return by_comp

def choose_url(it):
    d = domain(it["url"]); pr = 3
    if "developers." in d or "docs" in it["url"]: pr = 0
    elif "blog." in d or d.endswith(".gov"): pr = 1
    return (pr, it["url"])

def build_actions_from_items(items):
    exec_actions, sales_actions, mkt_actions, prod_actions = [], [], [], []
    if not items: return exec_actions, sales_actions, mkt_actions, prod_actions

    by_comp = summarize_competitor_focus(items)
    recent = items[:8]

    regs = [it for it in recent if it["theme"] == "Regulatory"]
    prods = [it for it in recent if it["theme"] == "Product" and it["stype"]=="competitor"]
    docs  = [it for it in recent if it["theme"] == "Docs / GTM"]

    if regs:
        it = sorted(regs, key=choose_url)[0]
        exec_actions.append(f"Prioritize opportunities under the advisory; authorize isolated workspace pilots — {it['url']}")
    if prods:
        comps = ", ".join(sorted({i['label'] for i in prods})[:3])
        it = sorted(prods, key=choose_url)[0]
        exec_actions.append(f"Fund 1–2 lighthouse head-to-heads vs {comps}; tie offers to time-to-deploy proof — {it['url']}")

    for it in docs[:2]:
        sales_actions.append(f"Add ‘policy-driven isolation’ talk track vs {it['label']} — {it['url']}")
    for it in prods[:2]:
        sales_actions.append(f"Position full-stack isolation vs {it['label']} feature; include time-to-deploy proof — {it['url']}")

    if prods:
        it = sorted(prods, key=choose_url)[0]
        mkt_actions.append(f"Publish 300-word comparison: {it['label']} update vs Replica’s ‘enterprise control + operational privacy’ — {it['url']}")
    if regs:
        it = sorted(regs, key=choose_url)[0]
        mkt_actions.append(f"Refresh advisory landing with ‘why isolation now’; link to source — {it['url']}")

    if docs:
        it = sorted(docs, key=choose_url)[0]
        prod_actions.append(f"Audit identity/threat/content policy gaps vs {it['label']} doc — {it['url']}")
    if prods:
        it = sorted(prods, key=choose_url)[0]
        prod_actions.append(f"Validate demand for {it['label']} feature in active RFPs; scope parity if repeat asks — {it['url']}")

    def dedupe(seq):
        seen=set(); out=[]
        for s in seq:
            if s not in seen: out.append(s); seen.add(s)
        return out[:2]

    return dedupe(exec_actions), dedupe(sales_actions), dedupe(mkt_actions), dedupe(prod_actions)

# ----------------------------- HTML rendering -------------------------------

def to_html(items, start, end, deltas_html, tldr_html):
    coverage = f"{start:%b %d}–{end:%b %d, %Y}" if start.year == end.year else f"{start:%b %d, %Y}–{end:%b %d, %Y}"

    # table rows (Date in MM/DD)
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

    exec_actions, sales_actions, mkt_actions, prod_actions = build_actions_from_items(items)

    def role_block(role, bullets):
        if not bullets: return ""
        return ("<tr>"
                f"<td width='22%'><strong>{role}</strong></td>"
                f"<td><ul style='margin:0 0 0 18px;'>"
                + "".join(f"<li>{html.escape(b)}</li>" for b in bullets)
                + "</ul></td></tr>")

    actions_rows = "".join([
        role_block("Exec", exec_actions),
        role_block("Sales", sales_actions),
        role_block("Marketing", mkt_actions),
        role_block("Product", prod_actions),
    ]) or "<tr><td colspan='2'>No role-specific actions this week.</td></tr>"

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
      {''.join(tldr_html)}
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
    {''.join(deltas_html)}
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
  <div><strong>Note:</strong> Links are validated (HTTP 200) with a browser UA at build time. Filters relax automatically if too few items are found.</div>
</div>

</div></body></html>"""
    return html_doc

# --------------------------------- main -------------------------------------

def main():
    cfg = load_conf(CONF_PATH)

    # strict pass
    items = collect_items(cfg, strict=True, extra_days=0)
    # relaxed if needed
    if len(items) < MIN_ITEMS:
        if DEBUG_BUILDER:
            print(f"[builder] Strict pass yielded {len(items)} (< {MIN_ITEMS}); running relaxed pass…", file=sys.stderr)
        items = collect_items(cfg, strict=False, extra_days=RELAX_DAYS)

    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=int(cfg.get("window_days", 7)) - 1)

    # TL;DR that summarizes impact (no titles)
    tldr_html = build_tldr(items, max_bullets=4)

    # Deltas vs prior week using cache
    prev = load_prev_cache(CACHE_PATH).get("items", [])
    deltas_html = build_deltas(items, prev)
    # Save current snapshot for next run
    try:
        save_cache(CACHE_PATH, items)
    except Exception as e:
        if DEBUG_BUILDER:
            print(f"[builder] cache save failed: {e}", file=sys.stderr)

    html_out = to_html(items, start, today, deltas_html, tldr_html)
    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html_out)
    print(f"[build_report_from_feeds] kept {len(items)} items (min={MIN_ITEMS})")
    return 0

if __name__ == "__main__":
    sys.exit(main())

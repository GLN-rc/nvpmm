#!/usr/bin/env python3
"""
verify_report.py — fail the run if report.html has bad links or mailto: links.
- Extracts all <a href="..."> from report.html
- Skips anchors/mailto; follows redirects; HEAD then GET as fallback
- Fails if any link is 4xx/5xx or times out
- Also fails if any 'mailto:' is present anywhere
"""
import re, sys, html, requests
from urllib.parse import urlparse

HTML_PATH = "report.html"
TIMEOUT = 15

def extract_hrefs(text: str):
    # naive but effective for our simple HTML
    return re.findall(r'<a\s+[^>]*href=["\']([^"\']+)["\']', text, re.I)

def ok_status(code: int) -> bool:
    return 200 <= code < 400

def main():
    try:
        raw = open(HTML_PATH, "r", encoding="utf-8", errors="replace").read()
    except FileNotFoundError:
        print("report.html not found"); return 1

    if "mailto:" in raw.lower():
        print("❌ Found mailto: link(s) — not allowed in report"); return 1

    hrefs = extract_hrefs(raw)
    hrefs = [h for h in hrefs if h and not h.startswith("#") and not h.startswith("mailto:")]
    if not hrefs:
        print("ℹ️ No external links found"); return 0

    bad = []
    s = requests.Session()
    for url in hrefs:
        try:
            # sanity URL
            pr = urlparse(url)
            if not pr.scheme.startswith("http"):
                bad.append((url, "invalid_scheme"))
                continue
            # HEAD first
            r = s.head(url, allow_redirects=True, timeout=TIMEOUT)
            if not ok_status(r.status_code):
                # try GET
                r = s.get(url, allow_redirects=True, timeout=TIMEOUT)
            if not ok_status(r.status_code):
                bad.append((url, f"status_{r.status_code}"))
        except Exception as e:
            bad.append((url, f"error_{type(e).__name__}"))

    if bad:
        print("❌ Broken/invalid links:")
        for u, why in bad:
            print(f" - {u}  ({why})")
        return 1

    print(f"✅ All {len(hrefs)} links OK")
    return 0

if __name__ == "__main__":
    sys.exit(main())

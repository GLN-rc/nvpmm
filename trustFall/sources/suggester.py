"""
trustFall — URL suggester.
Given a vendor name and website, suggests likely trust/legal/AI policy URLs.
Strategy:
  1. Try known path patterns
  2. Check sitemap.xml for legal/trust/privacy/ai pages
  3. Ask LLM as a fallback for known vendors
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Optional
from urllib.parse import urljoin, urlparse

import aiohttp

log = logging.getLogger(__name__)

# Common path patterns for trust/legal/AI pages
KNOWN_PATTERNS = [
    ("/privacy",                  "Privacy Policy"),
    ("/privacy-policy",           "Privacy Policy"),
    ("/legal/privacy",            "Privacy Policy"),
    ("/terms",                    "Terms of Service"),
    ("/terms-of-service",         "Terms of Service"),
    ("/legal/terms",              "Terms of Service"),
    ("/trust",                    "Trust Center"),
    ("/trust-center",             "Trust Center"),
    ("/security",                 "Security"),
    ("/legal/ai-policy",          "AI Policy"),
    ("/ai-policy",                "AI Policy"),
    ("/legal/acceptable-use",     "Acceptable Use"),
    ("/acceptable-use-policy",    "Acceptable Use"),
    ("/data-processing",          "Data Processing"),
    ("/legal/dpa",                "Data Processing Agreement"),
    ("/legal",                    "Legal Hub"),
    ("/responsible-ai",           "Responsible AI"),
    ("/ai",                       "AI Information"),
]

SITEMAP_KEYWORDS = [
    "privacy", "trust", "legal", "terms", "security",
    "ai", "data", "policy", "compliance", "dpa"
]


def _normalize_base(website: str) -> str:
    """Ensure website has a scheme."""
    if not website.startswith("http"):
        website = "https://" + website
    parsed = urlparse(website)
    return f"{parsed.scheme}://{parsed.netloc}"


async def _check_url(session: aiohttp.ClientSession, url: str) -> bool:
    """Return True if URL responds with 200."""
    try:
        async with session.head(url, allow_redirects=True, timeout=aiohttp.ClientTimeout(total=8)) as r:
            return r.status == 200
    except Exception:
        return False


async def _parse_sitemap(session: aiohttp.ClientSession, base: str) -> list[tuple[str, str]]:
    """
    Fetch /sitemap.xml and return URLs that look like trust/legal pages.
    Returns list of (url, guessed_label).
    """
    sitemap_url = f"{base}/sitemap.xml"
    try:
        async with session.get(sitemap_url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status != 200:
                return []
            text = await resp.text()

        import re
        urls = re.findall(r'<loc>(.*?)</loc>', text)
        results = []
        for u in urls:
            low = u.lower()
            if any(kw in low for kw in SITEMAP_KEYWORDS):
                # Guess a label from the URL path
                path = urlparse(u).path.strip("/").replace("-", " ").replace("/", " › ")
                label = path.title() if path else "Legal Page"
                results.append((u, label))
        return results[:10]  # cap at 10 from sitemap
    except Exception as e:
        log.debug("Sitemap fetch failed for %s: %s", base, e)
        return []


async def _llm_suggest(vendor_name: str, website: str) -> list[tuple[str, str]]:
    """
    Ask the LLM to suggest likely trust/AI policy URLs for a known vendor.
    Used as a last resort when patterns and sitemap don't find anything.
    """
    try:
        import litellm
        prompt = f"""You are a researcher finding vendor trust and AI data usage pages.

Vendor: {vendor_name}
Website: {website}

List up to 6 specific URLs on this vendor's website that would contain:
- Their privacy policy
- AI or LLM data usage policy
- Trust center
- Terms of service
- Data processing agreement

Return ONLY a JSON array of objects with "url" and "label" keys.
Example: [{{"url": "https://example.com/privacy", "label": "Privacy Policy"}}]
Only include URLs you are confident exist for this specific vendor."""

        response = await litellm.acompletion(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=500,
        )
        import json, re
        content = response.choices[0].message.content
        match = re.search(r'\[.*?\]', content, re.DOTALL)
        if match:
            items = json.loads(match.group())
            return [(i["url"], i["label"]) for i in items if "url" in i and "label" in i]
    except Exception as e:
        log.warning("LLM URL suggestion failed: %s", e)
    return []


async def suggest_urls(
    vendor_name: str,
    website: str,
    known_url: Optional[str] = None,
) -> list[dict]:
    """
    Main entry point. Returns a list of suggested URLs with labels and confidence.
    Each result: {"url": str, "label": str, "source": str, "reachable": bool}
    """
    base = _normalize_base(website)
    suggestions = []
    seen_urls = set()

    if known_url:
        seen_urls.add(known_url.rstrip("/"))

    async with aiohttp.ClientSession(
        headers={"User-Agent": "trustFall/1.0 (vendor trust page monitor)"}
    ) as session:

        # 1. Try known patterns
        pattern_tasks = []
        for path, label in KNOWN_PATTERNS:
            url = base + path
            if url.rstrip("/") not in seen_urls:
                pattern_tasks.append((url, label, _check_url(session, url)))

        pattern_results = await asyncio.gather(*[t[2] for t in pattern_tasks])
        for (url, label, _), reachable in zip(pattern_tasks, pattern_results):
            if reachable:
                suggestions.append({"url": url, "label": label, "source": "pattern", "reachable": True})
                seen_urls.add(url.rstrip("/"))

        # 2. Sitemap
        sitemap_hits = await _parse_sitemap(session, base)
        for url, label in sitemap_hits:
            if url.rstrip("/") not in seen_urls:
                reachable = await _check_url(session, url)
                if reachable:
                    suggestions.append({"url": url, "label": label, "source": "sitemap", "reachable": True})
                    seen_urls.add(url.rstrip("/"))

    # 3. LLM fallback if we found very little
    if len(suggestions) < 2:
        llm_hits = await _llm_suggest(vendor_name, website)
        for url, label in llm_hits:
            if url.rstrip("/") not in seen_urls:
                suggestions.append({"url": url, "label": label, "source": "llm", "reachable": None})
                seen_urls.add(url.rstrip("/"))

    return suggestions

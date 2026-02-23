"""
trustFall — Wayback Machine baseline lookup.
Uses the CDX API (lightweight, no scraping) to find historical snapshots.
Throttled carefully — one request per URL, with delays between calls.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

import aiohttp

log = logging.getLogger(__name__)

CDX_API     = "https://web.archive.org/cdx/search/cdx"
WAYBACK_URL = "https://web.archive.org/web"

# Be a good citizen — wait between requests
REQUEST_DELAY_SECONDS = 3


@dataclass
class WaybackSnapshot:
    url: str
    timestamp: str          # yyyymmddhhmmss
    captured_at: datetime
    wayback_url: str
    status_code: str


async def find_snapshots(
    url: str,
    months_back: int = 6,
    max_results: int = 5,
) -> list[WaybackSnapshot]:
    """
    Query the CDX API for snapshots of a URL within the past N months.
    Returns up to max_results snapshots, oldest first.
    Throttled with a delay to be respectful.
    """
    since = datetime.now(tz=timezone.utc) - timedelta(days=months_back * 30)
    from_str = since.strftime("%Y%m%d")

    params = {
        "url":      url,
        "output":   "json",
        "fl":       "timestamp,statuscode",
        "from":     from_str,
        "filter":   "statuscode:200",
        "collapse": "timestamp:8",   # one per day max
        "limit":    max_results,
    }

    await asyncio.sleep(REQUEST_DELAY_SECONDS)

    try:
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=20),
            headers={"User-Agent": "trustFall/1.0 (vendor trust page monitor; contact: user)"},
        ) as session:
            async with session.get(CDX_API, params=params) as resp:
                if resp.status != 200:
                    log.warning("CDX API returned %s for %s", resp.status, url)
                    return []
                data = await resp.json(content_type=None)

        if not data or len(data) < 2:
            return []

        # First row is headers
        rows = data[1:]
        results = []
        for row in rows:
            ts, status = row[0], row[1]
            try:
                captured = datetime.strptime(ts, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
            except ValueError:
                continue
            results.append(WaybackSnapshot(
                url=url,
                timestamp=ts,
                captured_at=captured,
                wayback_url=f"{WAYBACK_URL}/{ts}/{url}",
                status_code=status,
            ))

        log.info("Found %d Wayback snapshots for %s", len(results), url)
        return results

    except Exception as e:
        log.error("Wayback CDX lookup failed for %s: %s", url, e)
        return []


async def fetch_wayback_text(snapshot: WaybackSnapshot) -> Optional[str]:
    """
    Fetch the actual text content of a Wayback snapshot.
    Tries lightweight aiohttp first, then falls back to Playwright.
    """
    import re
    await asyncio.sleep(REQUEST_DELAY_SECONDS)

    # Try 1: plain HTTP fetch — fast, works for most archived static pages
    try:
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={"User-Agent": "Mozilla/5.0 (compatible; trustFall/1.0)"},
        ) as session:
            async with session.get(snapshot.wayback_url, allow_redirects=True) as resp:
                if resp.status == 200:
                    html = await resp.text(errors="replace")
                    text = re.sub(r'<[^>]+>', ' ', html)
                    text = re.sub(r'\s{2,}', ' ', text).strip()
                    if len(text) > 200:
                        log.info("Wayback fetch succeeded (aiohttp) for %s", snapshot.wayback_url)
                        return text
    except Exception as e:
        log.warning("Wayback aiohttp fetch failed, trying Playwright: %s", e)

    # Try 2: Playwright for JS-heavy Wayback pages
    await asyncio.sleep(REQUEST_DELAY_SECONDS)
    from sources.fetcher import fetch_page
    result = await fetch_page(snapshot.wayback_url)
    if result.success:
        return result.text

    log.warning("Could not fetch Wayback snapshot %s: %s", snapshot.wayback_url, result.error)
    return None

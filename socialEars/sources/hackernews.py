"""
Hacker News collector — uses the free Algolia search API.
No auth required. Returns posts compatible with the Post schema.
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone, timedelta

import aiohttp

log = logging.getLogger(__name__)

ALGOLIA_URL = "https://hn.algolia.com/api/v1/search_by_date"


def _map_time_filter(time_filter: str) -> int:
    """Convert time_filter string to Unix timestamp (oldest allowed)."""
    now = time.time()
    mapping = {
        "week":  now - 7  * 86400,
        "month": now - 30 * 86400,
        "year":  now - 365 * 86400,
        "all":   0,
    }
    return int(mapping.get(time_filter, mapping["month"]))


def _item_to_dict(hit: dict) -> dict:
    """Convert an Algolia HN hit to our standard post dict."""
    # Stories have title + url; Ask HN / Show HN have story_text
    title = hit.get("title") or hit.get("story_title") or ""
    text  = hit.get("story_text") or hit.get("comment_text") or ""
    combined = f"{title}\n\n{text}".strip() if text else title

    created_raw = hit.get("created_at") or hit.get("created_at_i")
    if isinstance(created_raw, int):
        created_iso = datetime.fromtimestamp(created_raw, tz=timezone.utc).isoformat()
    else:
        created_iso = created_raw or ""

    return {
        "source":       "hackernews",
        "source_id":    str(hit.get("objectID", "")),
        "subreddit":    None,
        "title":        title,
        "text":         combined,
        "url":          hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}",
        "score":        hit.get("points") or 0,
        "num_comments": hit.get("num_comments") or 0,
        "created_at":   created_iso,
        "author":       hit.get("author") or "",
        "post_type":    "post",
        "parent_id":    None,
    }


async def collect(
    keywords: list[str],
    time_filter: str = "month",
    max_per_keyword: int = 30,
) -> list[dict]:
    """Search HN via Algolia for each keyword. Returns combined post list."""
    since = _map_time_filter(time_filter)
    results = []
    seen_ids = set()

    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=20)
    ) as session:
        for keyword in keywords:
            try:
                params = {
                    "query":          keyword,
                    "tags":           "story",
                    "hitsPerPage":    max_per_keyword,
                    "numericFilters": f"created_at_i>{since}",
                }
                async with session.get(ALGOLIA_URL, params=params) as resp:
                    if resp.status != 200:
                        log.warning(f"HN Algolia returned {resp.status} for '{keyword}'")
                        continue
                    data = await resp.json()
                    for hit in data.get("hits", []):
                        obj_id = str(hit.get("objectID", ""))
                        if obj_id and obj_id not in seen_ids:
                            seen_ids.add(obj_id)
                            item = _item_to_dict(hit)
                            if item["text"]:
                                results.append(item)
            except Exception as e:
                log.warning(f"HN collect failed for '{keyword}': {e}")

    return results

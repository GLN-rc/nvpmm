"""
LLM Analyzer — sends collected posts to GPT and extracts structured GTM intelligence:
  1. Pain point themes (with supporting quotes)
  2. Language worth mirroring in messaging
  3. Competitive signals (tools/vendors mentioned with sentiment)
"""
from __future__ import annotations

import os
import json
import logging
import textwrap
from typing import Optional

import litellm

log = logging.getLogger(__name__)

MODEL = os.getenv("LLM_MODEL", "gpt-4o")

# Max characters of post text to send per batch (avoid token overload)
BATCH_CHAR_LIMIT = 60_000


def _build_post_corpus(posts: list[dict]) -> str:
    """Format posts as a numbered corpus for the LLM."""
    lines = []
    for i, p in enumerate(posts, 1):
        source = p.get("source", "")
        sub    = f" r/{p['subreddit']}" if p.get("subreddit") else ""
        score  = p.get("score", 0)
        date   = (p.get("created_at") or "")[:10]
        text   = (p.get("text") or "").strip()[:800]  # cap per post
        lines.append(
            f"[{i}] [{source}{sub}] [score:{score}] [{date}]\n{text}"
        )
    return "\n\n---\n\n".join(lines)


def _chunk_posts(posts: list[dict]) -> list[list[dict]]:
    """Split posts into batches that fit within BATCH_CHAR_LIMIT."""
    batches, current, current_size = [], [], 0
    for p in posts:
        size = len(p.get("text") or "")
        if current and current_size + size > BATCH_CHAR_LIMIT:
            batches.append(current)
            current, current_size = [], 0
        current.append(p)
        current_size += size
    if current:
        batches.append(current)
    return batches


ANALYSIS_PROMPT = textwrap.dedent("""
You are a senior GTM analyst for Replica Cyber, a cybersecurity company that helps
security teams conduct safe, efficient high-trust investigations — including isolated
browsing, malware analysis, OSINT research, fraud investigations, and dark web monitoring.

Our key buyer personas are:
- Security Operations (SecOps): SOC managers, incident responders, security directors
- Fraud Investigations: fraud analysts, AML leads, financial crime investigators
- Threat Intelligence (CTI): threat intel analysts, dark web researchers

Below are {n} posts/comments collected from cybersecurity communities on Reddit and
Hacker News. Your job is to extract actionable GTM intelligence.

Respond ONLY with valid JSON in exactly this structure (no markdown, no explanation):

{{
  "pain_points": [
    {{
      "theme": "short theme label (3-8 words)",
      "description": "1-2 sentence explanation of the pain",
      "frequency": "high|medium|low",
      "personas": ["SecOps", "Fraud", "ThreatIntel"],
      "quotes": ["verbatim quote from a post", "another quote"],
      "post_indices": [1, 4, 7]
    }}
  ],
  "language": [
    {{
      "phrase": "exact phrase or term from the posts",
      "context": "what situation/emotion it signals",
      "use_in": "where Replica could use this language (headline, email, objection handling, etc.)"
    }}
  ],
  "competitive_signals": [
    {{
      "vendor": "tool or vendor name",
      "sentiment": "positive|negative|mixed|neutral",
      "what_they_say": "brief summary of how it's discussed",
      "opportunity": "what this means for Replica's positioning"
    }}
  ],
  "summary": "3-4 sentence overall synthesis of what these communities are worried about right now",
  "post_count": {n},
  "top_topics": ["topic1", "topic2", "topic3", "topic4", "topic5"]
}}

POSTS:
{corpus}
""").strip()


async def analyze(posts: list[dict], keywords: list[str]) -> dict:
    """
    Run LLM analysis on collected posts. If there are many posts, batch them
    and merge results.
    """
    if not posts:
        return _empty_report(keywords)

    batches = _chunk_posts(posts)
    log.info(f"Analyzing {len(posts)} posts in {len(batches)} batch(es)")

    batch_results = []
    for i, batch in enumerate(batches):
        log.info(f"  Batch {i+1}/{len(batches)}: {len(batch)} posts")
        result = await _analyze_batch(batch)
        if result:
            batch_results.append(result)

    if not batch_results:
        return _empty_report(keywords)

    if len(batch_results) == 1:
        return batch_results[0]

    return _merge_results(batch_results, len(posts))


async def _analyze_batch(posts: list[dict]) -> Optional[dict]:
    """Send one batch to the LLM and parse the JSON response."""
    corpus = _build_post_corpus(posts)
    prompt = ANALYSIS_PROMPT.format(n=len(posts), corpus=corpus)

    try:
        response = await litellm.acompletion(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=4000,
        )
        raw = response.choices[0].message.content.strip()

        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        return json.loads(raw)

    except json.JSONDecodeError as e:
        log.error(f"JSON parse error from LLM: {e}")
        return None
    except Exception as e:
        log.error(f"LLM analysis failed: {e}")
        return None


def _merge_results(results: list[dict], total_posts: int) -> dict:
    """Merge multiple batch results into a single report."""
    merged = {
        "pain_points":          [],
        "language":             [],
        "competitive_signals":  [],
        "summary":              "",
        "post_count":           total_posts,
        "top_topics":           [],
    }

    seen_themes    = set()
    seen_phrases   = set()
    seen_vendors   = set()
    all_summaries  = []
    all_topics     = []

    for r in results:
        for pp in r.get("pain_points", []):
            key = pp.get("theme", "").lower()
            if key and key not in seen_themes:
                seen_themes.add(key)
                merged["pain_points"].append(pp)

        for lang in r.get("language", []):
            key = lang.get("phrase", "").lower()
            if key and key not in seen_phrases:
                seen_phrases.add(key)
                merged["language"].append(lang)

        for cs in r.get("competitive_signals", []):
            key = cs.get("vendor", "").lower()
            if key and key not in seen_vendors:
                seen_vendors.add(key)
                merged["competitive_signals"].append(cs)

        if r.get("summary"):
            all_summaries.append(r["summary"])

        all_topics.extend(r.get("top_topics", []))

    merged["summary"]    = " ".join(all_summaries)
    merged["top_topics"] = list(dict.fromkeys(all_topics))[:8]  # dedupe, cap at 8

    return merged


def _empty_report(keywords: list[str]) -> dict:
    return {
        "pain_points":         [],
        "language":            [],
        "competitive_signals": [],
        "summary":             "No posts were collected for the given keywords and sources.",
        "post_count":          0,
        "top_topics":          keywords[:5],
    }

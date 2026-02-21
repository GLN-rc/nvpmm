"""
Reddit collector — uses PRAW to search subreddits for posts + top comments.
Returns a list of dicts compatible with the Post schema in database.py.
"""
from __future__ import annotations

import os
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

log = logging.getLogger(__name__)

# Subreddits seeded from Replica's buyer persona research brief,
# mapped to which persona(s) they serve.
SUBREDDIT_CATALOG = [
    # name, display label, personas
    ("cybersecurity",     "r/cybersecurity",    ["SecOps", "Fraud", "ThreatIntel"]),
    ("netsec",            "r/netsec",           ["SecOps", "ThreatIntel"]),
    ("AskNetsec",         "r/AskNetsec",        ["SecOps", "ThreatIntel"]),
    ("blueteamsec",       "r/blueteamsec",      ["SecOps", "ThreatIntel"]),
    ("OSINT",             "r/OSINT",            ["Fraud", "ThreatIntel"]),
    ("malware",           "r/malware",          ["SecOps", "ThreatIntel"]),
    ("threatintel",       "r/threatintel",      ["ThreatIntel"]),
    ("FraudPrevention",   "r/FraudPrevention",  ["Fraud"]),
    ("Scams",             "r/Scams",            ["Fraud", "ThreatIntel"]),
    ("sysadmin",          "r/sysadmin",         ["SecOps"]),
]

# Expose as simple list for the UI
SUBREDDIT_LIST = [
    {"name": s[0], "label": s[1], "personas": s[2]}
    for s in SUBREDDIT_CATALOG
]


def _get_reddit_client():
    """Build a read-only PRAW Reddit instance from env vars."""
    import praw
    client_id     = os.getenv("REDDIT_CLIENT_ID", "")
    client_secret = os.getenv("REDDIT_CLIENT_SECRET", "")
    user_agent    = os.getenv("REDDIT_USER_AGENT", "socialEars/1.0")

    if not client_id or not client_secret:
        raise RuntimeError(
            "REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET must be set in .env. "
            "Create an app at https://www.reddit.com/prefs/apps (type: script)."
        )

    return praw.Reddit(
        client_id=client_id,
        client_secret=client_secret,
        user_agent=user_agent,
        # Read-only — no username/password needed
    )


def _post_to_dict(submission, subreddit_name: str) -> dict:
    """Convert a PRAW Submission to our standard post dict."""
    text = (submission.selftext or "").strip()
    title = (submission.title or "").strip()
    combined = f"{title}\n\n{text}".strip() if text else title

    return {
        "source":       "reddit",
        "source_id":    submission.id,
        "subreddit":    subreddit_name,
        "title":        title,
        "text":         combined,
        "url":          f"https://reddit.com{submission.permalink}",
        "score":        submission.score,
        "num_comments": submission.num_comments,
        "created_at":   datetime.fromtimestamp(submission.created_utc, tz=timezone.utc).isoformat(),
        "author":       str(submission.author) if submission.author else "[deleted]",
        "post_type":    "post",
        "parent_id":    None,
    }


def _comment_to_dict(comment, subreddit_name: str, parent_post_id: str) -> Optional[dict]:
    """Convert a PRAW Comment to our standard post dict. Returns None if not useful."""
    try:
        text = (comment.body or "").strip()
    except Exception:
        return None

    if not text or text in ("[deleted]", "[removed]") or len(text) < 30:
        return None

    return {
        "source":       "reddit",
        "source_id":    comment.id,
        "subreddit":    subreddit_name,
        "title":        None,
        "text":         text,
        "url":          f"https://reddit.com{comment.permalink}",
        "score":        comment.score,
        "num_comments": 0,
        "created_at":   datetime.fromtimestamp(comment.created_utc, tz=timezone.utc).isoformat(),
        "author":       str(comment.author) if comment.author else "[deleted]",
        "post_type":    "comment",
        "parent_id":    parent_post_id,
    }


async def collect(
    keywords: list[str],
    subreddits: list[str],
    time_filter: str = "month",
    max_posts_per_sub: int = 25,
    max_comments_per_post: int = 5,
) -> list[dict]:
    """
    Search each subreddit for each keyword, collect posts + top comments.
    Runs PRAW synchronously in a thread pool to avoid blocking the event loop.
    """
    def _sync_collect():
        reddit = _get_reddit_client()
        results = []
        seen_ids = set()

        for sub_name in subreddits:
            try:
                subreddit = reddit.subreddit(sub_name)
                for keyword in keywords:
                    try:
                        posts = subreddit.search(
                            keyword,
                            time_filter=time_filter,
                            limit=max_posts_per_sub,
                            sort="relevance",
                        )
                        for submission in posts:
                            if submission.id in seen_ids:
                                continue
                            seen_ids.add(submission.id)

                            post_dict = _post_to_dict(submission, sub_name)
                            results.append(post_dict)

                            # Pull top comments
                            try:
                                submission.comments.replace_more(limit=0)
                                top_comments = sorted(
                                    submission.comments.list(),
                                    key=lambda c: getattr(c, "score", 0),
                                    reverse=True,
                                )[:max_comments_per_post]

                                for comment in top_comments:
                                    c_dict = _comment_to_dict(comment, sub_name, submission.id)
                                    if c_dict and c_dict["source_id"] not in seen_ids:
                                        seen_ids.add(c_dict["source_id"])
                                        results.append(c_dict)
                            except Exception as e:
                                log.warning(f"Comment fetch failed for {submission.id}: {e}")

                    except Exception as e:
                        log.warning(f"Search failed in r/{sub_name} for '{keyword}': {e}")

            except Exception as e:
                log.warning(f"Could not access r/{sub_name}: {e}")

        return results

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _sync_collect)

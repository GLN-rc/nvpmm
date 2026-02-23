"""
trustFall — page fetcher using Playwright.
Handles JS-rendered pages, detects Cloudflare blocks, extracts clean text.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import re
from dataclasses import dataclass
from typing import Optional

log = logging.getLogger(__name__)

# Phrases that indicate we hit a bot/Cloudflare block rather than real content
BLOCK_SIGNALS = [
    "just a moment",
    "enable javascript",
    "cf-browser-verification",
    "checking your browser",
    "ddos protection",
    "please wait while we check your browser",
]


@dataclass
class FetchResult:
    url: str
    success: bool
    text: str
    content_hash: str
    blocked: bool = False
    page_moved: bool = False
    error: Optional[str] = None


def _clean_text(raw: str) -> str:
    """Strip excess whitespace and normalize text from a page."""
    # Remove runs of whitespace/newlines
    text = re.sub(r'\n{3,}', '\n\n', raw)
    text = re.sub(r'[ \t]{2,}', ' ', text)
    return text.strip()


def _is_blocked(text: str) -> bool:
    low = text.lower()
    return any(signal in low for signal in BLOCK_SIGNALS)


def _check_fingerprints(text: str, fingerprints: list[str]) -> bool:
    """Return True if all fingerprint phrases are found in the text."""
    if not fingerprints:
        return True
    low = text.lower()
    return all(fp.lower() in low for fp in fingerprints)


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


async def fetch_page(
    url: str,
    fingerprint_phrases: Optional[list[str]] = None,
    timeout_ms: int = 30000,
) -> FetchResult:
    """
    Fetch a page using Playwright (Chromium, headless).
    Returns cleaned text content and a content hash.
    """
    try:
        from playwright.async_api import async_playwright, TimeoutError as PWTimeout
    except ImportError:
        return FetchResult(
            url=url, success=False, text="", content_hash="",
            error="Playwright not installed. Run: pip install playwright && playwright install chromium"
        )

    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 800},
            )
            page = await context.new_page()

            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                # Give JS a moment to render
                await page.wait_for_timeout(2000)
                text = await page.inner_text("body")
            except PWTimeout:
                await browser.close()
                return FetchResult(
                    url=url, success=False, text="", content_hash="",
                    error=f"Timeout fetching {url}"
                )
            finally:
                await browser.close()

        text = _clean_text(text)

        if _is_blocked(text):
            return FetchResult(
                url=url, success=False, text=text, content_hash=_hash(text),
                blocked=True, error="Page returned a bot-detection block"
            )

        page_moved = False
        if fingerprint_phrases and not _check_fingerprints(text, fingerprint_phrases):
            page_moved = True
            log.warning("Fingerprint phrases not found in %s — page may have moved", url)

        return FetchResult(
            url=url,
            success=True,
            text=text,
            content_hash=_hash(text),
            page_moved=page_moved,
        )

    except Exception as e:
        log.error("fetch_page failed for %s: %s", url, e)
        return FetchResult(
            url=url, success=False, text="", content_hash="",
            error=str(e)
        )

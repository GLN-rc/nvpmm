"""
Article Scraper Module
Attempts to fetch full article body text from URLs for deeper pitch personalization.
Gracefully degrades when content is paywalled, JS-rendered, or unavailable.
"""

import asyncio
import re
import aiohttp
from bs4 import BeautifulSoup


# Tags/classes that are noise — strip before extracting body text
NOISE_SELECTORS = [
    "nav", "header", "footer", "aside", ".sidebar", ".related", ".recommended",
    ".advertisement", ".ad", ".ads", ".promo", ".newsletter", ".cookie-banner",
    ".social-share", ".share-buttons", ".comments", ".comment-section",
    "script", "style", "noscript", "[class*='subscribe']", "[class*='paywall']",
    "[class*='popup']", "[class*='modal']", "[id*='cookie']",
]

# Ordered list of CSS selectors to try for article body
BODY_SELECTORS = [
    "article",
    "[itemprop='articleBody']",
    ".article-body",
    ".article-content",
    ".post-content",
    ".entry-content",
    ".story-body",
    ".story-content",
    ".article__body",
    ".content-body",
    "main",
    "[role='main']",
]

# Paywall/registration signal phrases
PAYWALL_SIGNALS = [
    "subscribe to continue", "create a free account", "sign in to read",
    "register to read", "this content is for subscribers", "become a member",
    "unlock this article", "premium content", "access denied",
]


class ArticleScraper:
    """Async article scraper with graceful degradation."""

    def __init__(self):
        self.timeout = aiohttp.ClientTimeout(total=8)
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }

    async def scrape_article(self, url: str, rss_title: str = "", rss_summary: str = "") -> dict:
        """
        Attempt to fetch and extract article body from a URL.
        Returns a dict with body_text and scrape_quality flag.
        scrape_quality: "full" | "partial" | "title_only" | "failed"
        """
        if not url:
            return self._fallback(rss_title, rss_summary, "failed", "No URL available")

        try:
            async with aiohttp.ClientSession(
                timeout=self.timeout, headers=self.headers
            ) as session:
                async with session.get(url, allow_redirects=True) as response:
                    if response.status != 200:
                        return self._fallback(
                            rss_title, rss_summary, "failed",
                            f"HTTP {response.status}"
                        )
                    content_type = response.headers.get("content-type", "")
                    if "html" not in content_type:
                        return self._fallback(
                            rss_title, rss_summary, "failed",
                            f"Non-HTML content type: {content_type}"
                        )
                    html = await response.text(errors="replace")

        except asyncio.TimeoutError:
            return self._fallback(rss_title, rss_summary, "failed", "Request timed out")
        except Exception as e:
            return self._fallback(rss_title, rss_summary, "failed", str(e)[:80])

        return self._extract_body(html, url, rss_title, rss_summary)

    def _extract_body(self, html: str, url: str, rss_title: str, rss_summary: str) -> dict:
        """Parse HTML, extract article body, classify quality."""
        try:
            soup = BeautifulSoup(html, "html.parser")
        except Exception:
            return self._fallback(rss_title, rss_summary, "failed", "HTML parse error")

        # Extract title from page
        page_title = ""
        title_tag = soup.find("title")
        if title_tag:
            page_title = title_tag.get_text(strip=True)
        # Prefer h1 if available
        h1 = soup.find("h1")
        if h1:
            page_title = h1.get_text(strip=True)

        # Extract author if available
        author = ""
        for selector in [
            "[rel='author']", "[class*='author']", "[itemprop='author']",
            ".byline", ".by-line", "[class*='byline']"
        ]:
            author_el = soup.select_one(selector)
            if author_el:
                candidate = author_el.get_text(strip=True)
                # Clean up "By Jane Smith" → "Jane Smith"
                candidate = re.sub(r'^[Bb]y\s+', '', candidate).strip()
                if 3 < len(candidate) < 60:
                    author = candidate
                    break

        # Remove noise elements
        for selector in NOISE_SELECTORS:
            for el in soup.select(selector):
                el.decompose()

        # Try body selectors in order
        body_text = ""
        for selector in BODY_SELECTORS:
            el = soup.select_one(selector)
            if el:
                body_text = el.get_text(separator=" ", strip=True)
                # Normalize whitespace
                body_text = re.sub(r'\s{2,}', ' ', body_text)
                if len(body_text) > 200:
                    break

        # Check for paywall signals
        page_lower = html.lower()
        is_paywalled = any(signal in page_lower for signal in PAYWALL_SIGNALS)

        # Classify quality
        if len(body_text) >= 800:
            quality = "full"
            note = f"Scraped {len(body_text)} chars"
        elif len(body_text) >= 200:
            quality = "partial"
            note = f"Partial content ({len(body_text)} chars)"
            if is_paywalled:
                note += " — possible paywall"
        else:
            # Fall back to RSS summary
            body_text = rss_summary or ""
            if is_paywalled:
                quality = "title_only"
                note = "Paywall detected — using RSS summary only"
            elif len(body_text) > 0:
                quality = "title_only"
                note = "Minimal content extracted — using RSS summary"
            else:
                quality = "title_only"
                note = "No body content extracted"

        return {
            "url": url,
            "title": page_title or rss_title,
            "author": author,
            "body_text": body_text[:3000],  # cap at 3000 chars per article
            "scrape_quality": quality,
            "scrape_note": note,
        }

    def _fallback(self, rss_title: str, rss_summary: str, quality: str, note: str) -> dict:
        """Return a graceful fallback result."""
        return {
            "url": "",
            "title": rss_title,
            "author": "",
            "body_text": rss_summary or "",
            "scrape_quality": quality,
            "scrape_note": note,
        }

    async def scrape_articles_for_targets(
        self,
        selected_pub_names: list[str],
        articles_by_pub: dict,  # pub_name → list of {title, url, summary, author, ...}
        articles_per_pub: int = 3,
    ) -> dict:
        """
        Scrape full article bodies for all selected publications in parallel.
        Returns dict keyed by pub_name → list of scraped article dicts.
        """
        # Build list of (pub_name, article) pairs to scrape
        scrape_tasks = []
        task_meta = []

        for pub_name in selected_pub_names:
            articles = articles_by_pub.get(pub_name, [])[:articles_per_pub]
            for article in articles:
                task = self.scrape_article(
                    url=article.get("url", ""),
                    rss_title=article.get("title", ""),
                    rss_summary=article.get("summary", ""),
                )
                scrape_tasks.append(task)
                task_meta.append(pub_name)

        if not scrape_tasks:
            return {pub: [] for pub in selected_pub_names}

        results = await asyncio.gather(*scrape_tasks, return_exceptions=True)

        # Group results by pub_name
        scraped_by_pub = {pub: [] for pub in selected_pub_names}
        for pub_name, result in zip(task_meta, results):
            if isinstance(result, Exception):
                scraped_by_pub[pub_name].append({
                    "url": "", "title": "", "author": "",
                    "body_text": "", "scrape_quality": "failed",
                    "scrape_note": str(result)[:80]
                })
            else:
                scraped_by_pub[pub_name].append(result)

        return scraped_by_pub

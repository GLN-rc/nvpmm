"""
Blog Scraper
Fetches a blog URL and extracts clean readable text content.
Prefers <article> / <main> content, strips nav/footer/ads.
Also attempts to collect inline images for potential PDF use.
"""

import re
import asyncio
from urllib.parse import urlparse, urljoin
from typing import Optional
import aiohttp
from bs4 import BeautifulSoup


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# Tags to strip from content
STRIP_TAGS = [
    "script", "style", "nav", "footer", "header", "aside",
    "form", "button", "noscript", "iframe", "figure.ad",
    ".advertisement", ".sidebar", ".cookie-notice", ".popup"
]


async def fetch_blog(url: str) -> dict:
    """
    Fetch a blog URL and return structured content.
    Returns: { title, text, og_image, inline_images[], url, status }
    """
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"

    timeout = aiohttp.ClientTimeout(total=30)

    try:
        async with aiohttp.ClientSession(timeout=timeout, headers=HEADERS) as session:
            async with session.get(url, allow_redirects=True, ssl=False) as resp:
                if resp.status >= 400:
                    return {
                        "status": "error",
                        "error": f"HTTP {resp.status}",
                        "url": url
                    }
                html = await resp.text(errors="replace")
                final_url = str(resp.url)

        soup = BeautifulSoup(html, "lxml")

        # Extract title
        title = ""
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            title = og_title["content"].strip()
        elif soup.find("h1"):
            title = soup.find("h1").get_text(strip=True)
        elif soup.find("title"):
            title = soup.find("title").get_text(strip=True)

        # Extract OG image
        og_image = None
        og_img_tag = soup.find("meta", property="og:image")
        if og_img_tag and og_img_tag.get("content"):
            og_image = og_img_tag["content"].strip()

        # Extract main content
        text = _extract_main_text(soup)

        # Collect inline images (src + alt) from content area
        inline_images = _extract_images(soup, final_url)

        # Extract CTA link from blog (demo/contact/request links)
        cta = _extract_cta_link(soup, final_url)

        return {
            "status": "success",
            "url": final_url,
            "title": title,
            "text": text,
            "og_image": og_image,
            "inline_images": inline_images[:5],  # cap at 5
            "word_count": len(text.split()),
            "cta_text": cta.get("text", ""),
            "cta_url": cta.get("url", ""),
        }

    except asyncio.TimeoutError:
        return {"status": "error", "error": "Request timed out", "url": url}
    except Exception as e:
        return {"status": "error", "error": str(e), "url": url}


def _extract_main_text(soup: BeautifulSoup) -> str:
    """Extract clean body text from the page, preferring article/main content."""
    # Remove noise elements
    for tag in soup.find_all(["script", "style", "nav", "footer", "aside",
                               "form", "button", "noscript", "iframe"]):
        tag.decompose()
    for tag in soup.find_all(class_=re.compile(
        r"(sidebar|advertisement|cookie|popup|banner|promo|social-share|related)", re.I
    )):
        tag.decompose()

    # Try content containers in priority order
    content = None
    for selector in ["article", "main", '[role="main"]', ".post-content",
                      ".entry-content", ".article-body", ".blog-content", "#content"]:
        content = soup.select_one(selector)
        if content and len(content.get_text(strip=True)) > 200:
            break

    if not content:
        content = soup.find("body") or soup

    # Get text preserving paragraph breaks.
    # First pass: collect from semantic block tags (most reliable for body text).
    seen_texts = set()
    paragraphs = []

    def _add(text):
        t = text.strip()
        if t and len(t) >= 3 and t not in seen_texts:
            seen_texts.add(t)
            paragraphs.append(t)

    for el in content.find_all(["p", "h1", "h2", "h3", "h4", "h5", "li", "blockquote",
                                  "dt", "dd"]):
        _add(el.get_text(separator=" ", strip=True))

    # Second pass: pick up FAQ-style content in divs/sections that wasn't covered above.
    # Only grab leaf-ish divs (no nested block children) to avoid duplicating body text.
    for el in content.find_all(["div", "section"]):
        # Skip if it contains any of the block tags we already processed
        if el.find(["p", "h1", "h2", "h3", "h4", "h5", "li", "blockquote", "dt", "dd"]):
            continue
        _add(el.get_text(separator=" ", strip=True))

    return "\n\n".join(paragraphs)


def _extract_cta_link(soup: BeautifulSoup, base_url: str) -> dict:
    """
    Find the most prominent CTA link on the page (demo, contact, request, etc.).
    Returns { text, url } or empty dict if nothing found.
    """
    # Keywords that signal a CTA anchor
    CTA_KEYWORDS = re.compile(
        r"\b(request\s+a\s+demo|book\s+a\s+demo|schedule\s+a\s+demo|"
        r"get\s+a\s+demo|watch\s+(?:the\s+)?demo|see\s+(?:the\s+)?demo|"
        r"try\s+(?:it\s+)?free|get\s+started|contact\s+us|talk\s+to\s+(?:us|sales)|"
        r"request\s+access|sign\s+up|book\s+a\s+call|schedule\s+a\s+call)\b",
        re.IGNORECASE
    )

    best = None
    best_score = 0

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith("#") or href.startswith("javascript"):
            continue

        text = a.get_text(separator=" ", strip=True)
        if not text:
            continue

        score = 0

        # High score: text matches CTA keywords
        if CTA_KEYWORDS.search(text):
            score += 10

        # Medium score: href contains CTA keywords
        if re.search(r"(demo|contact|request|schedule|book|get-started|trial)", href, re.I):
            score += 5

        # Boost for button-like roles or classes
        role = a.get("role", "")
        cls  = " ".join(a.get("class", []))
        if re.search(r"(btn|button|cta|primary)", cls + role, re.I):
            score += 3

        if score > best_score:
            best_score = score
            abs_url = urljoin(base_url, href)
            best = {"text": text[:80], "url": abs_url}

    return best or {}


def _extract_images(soup: BeautifulSoup, base_url: str) -> list:
    """Extract meaningful inline images (skip icons/avatars/tiny images)."""
    images = []
    seen = set()

    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src") or img.get("data-lazy-src")
        if not src:
            continue

        # Make absolute URL
        src = urljoin(base_url, src)

        if src in seen:
            continue
        seen.add(src)

        # Skip likely icons/avatars (small, or path contains icon/avatar/logo)
        if re.search(r"(icon|avatar|logo|emoji|spinner|pixel|tracking)", src, re.I):
            continue

        # Skip data URIs
        if src.startswith("data:"):
            continue

        alt = img.get("alt", "").strip()
        images.append({"src": src, "alt": alt})

    return images

"""
Website Scraper Module
Extracts and analyzes website content for SEO/GEO/LLM discoverability assessment.
"""

import asyncio
import re
from urllib.parse import urlparse, urljoin
from typing import Optional
import aiohttp
from bs4 import BeautifulSoup
from readability import Document
import tldextract


class WebsiteScraper:
    """Scrapes and analyzes websites for optimization opportunities."""

    def __init__(self, timeout: int = 30):
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.headers = {
            "User-Agent": "Mozilla/5.0 (compatible; WebsiteAnalyzer/1.0; +https://example.com/bot)"
        }

    async def analyze_website(self, url: str) -> dict:
        """
        Comprehensive website analysis for SEO/GEO/LLM discoverability.
        """
        # Normalize URL
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"

        result = {
            "url": url,
            "domain": self._extract_domain(url),
            "status": "success",
            "seo_factors": {},
            "content_analysis": {},
            "technical_factors": {},
            "llm_discoverability": {},
            "geo_factors": {},
            "issues": [],
            "strengths": []
        }

        try:
            async with aiohttp.ClientSession(timeout=self.timeout, headers=self.headers) as session:
                # Fetch main page
                async with session.get(url, allow_redirects=True) as response:
                    result["http_status"] = response.status
                    result["final_url"] = str(response.url)
                    html = await response.text()

                soup = BeautifulSoup(html, "lxml")
                doc = Document(html)

                # Analyze all aspects
                result["seo_factors"] = self._analyze_seo(soup, url)
                result["content_analysis"] = self._analyze_content(soup, doc)
                result["technical_factors"] = await self._analyze_technical(session, url, soup, response)
                result["llm_discoverability"] = self._analyze_llm_factors(soup, html)
                result["geo_factors"] = self._analyze_geo_factors(soup)

                # Compile issues and strengths
                result["issues"], result["strengths"] = self._compile_findings(result)

        except asyncio.TimeoutError:
            result["status"] = "timeout"
            result["error"] = "Request timed out"
        except aiohttp.ClientError as e:
            result["status"] = "error"
            result["error"] = f"Connection error: {str(e)}"
        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)

        return result

    def _extract_domain(self, url: str) -> str:
        """Extract the domain from a URL."""
        extracted = tldextract.extract(url)
        return f"{extracted.domain}.{extracted.suffix}"

    def _analyze_seo(self, soup: BeautifulSoup, url: str) -> dict:
        """Analyze on-page SEO factors."""
        seo = {
            "title": None,
            "title_length": 0,
            "meta_description": None,
            "meta_description_length": 0,
            "h1_tags": [],
            "h2_tags": [],
            "h3_tags": [],
            "canonical_url": None,
            "og_tags": {},
            "twitter_cards": {},
            "internal_links": 0,
            "external_links": 0,
            "images_without_alt": 0,
            "images_total": 0,
            "keywords_in_url": [],
            "word_count": 0
        }

        # Title
        title_tag = soup.find("title")
        if title_tag:
            seo["title"] = title_tag.get_text(strip=True)
            seo["title_length"] = len(seo["title"])

        # Meta description
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc and meta_desc.get("content"):
            seo["meta_description"] = meta_desc["content"]
            seo["meta_description_length"] = len(seo["meta_description"])

        # Headings
        for h1 in soup.find_all("h1"):
            seo["h1_tags"].append(h1.get_text(strip=True)[:100])
        for h2 in soup.find_all("h2"):
            seo["h2_tags"].append(h2.get_text(strip=True)[:100])
        for h3 in soup.find_all("h3"):
            seo["h3_tags"].append(h3.get_text(strip=True)[:100])

        # Canonical
        canonical = soup.find("link", attrs={"rel": "canonical"})
        if canonical:
            seo["canonical_url"] = canonical.get("href")

        # Open Graph tags
        for og in soup.find_all("meta", attrs={"property": re.compile(r"^og:")}):
            prop = og.get("property", "").replace("og:", "")
            seo["og_tags"][prop] = og.get("content", "")[:200]

        # Twitter cards
        for tw in soup.find_all("meta", attrs={"name": re.compile(r"^twitter:")}):
            name = tw.get("name", "").replace("twitter:", "")
            seo["twitter_cards"][name] = tw.get("content", "")[:200]

        # Links analysis
        parsed_url = urlparse(url)
        base_domain = self._extract_domain(url)
        for link in soup.find_all("a", href=True):
            href = link["href"]
            if href.startswith(("http://", "https://")):
                link_domain = self._extract_domain(href)
                if link_domain == base_domain:
                    seo["internal_links"] += 1
                else:
                    seo["external_links"] += 1
            elif href.startswith("/"):
                seo["internal_links"] += 1

        # Images
        for img in soup.find_all("img"):
            seo["images_total"] += 1
            if not img.get("alt"):
                seo["images_without_alt"] += 1

        # Word count
        text = soup.get_text(separator=" ", strip=True)
        seo["word_count"] = len(text.split())

        return seo

    def _analyze_content(self, soup: BeautifulSoup, doc: Document) -> dict:
        """Analyze content quality and structure."""
        content = {
            "main_content": "",
            "content_length": 0,
            "readability_score": 0,
            "has_structured_data": False,
            "structured_data_types": [],
            "content_sections": [],
            "key_phrases": [],
            "cta_elements": []
        }

        # Extract main content
        try:
            content["main_content"] = doc.summary()[:2000]
            clean_text = BeautifulSoup(content["main_content"], "lxml").get_text(strip=True)
            content["content_length"] = len(clean_text)
        except Exception:
            pass

        # Structured data (JSON-LD, microdata)
        json_ld = soup.find_all("script", attrs={"type": "application/ld+json"})
        if json_ld:
            content["has_structured_data"] = True
            content["structured_data_types"].append("JSON-LD")

        # Check for schema.org microdata
        if soup.find(attrs={"itemtype": True}):
            content["has_structured_data"] = True
            content["structured_data_types"].append("Microdata")

        # CTAs
        cta_patterns = ["sign up", "get started", "try", "demo", "contact", "learn more", "download", "subscribe"]
        for link in soup.find_all(["a", "button"]):
            text = link.get_text(strip=True).lower()
            for pattern in cta_patterns:
                if pattern in text:
                    content["cta_elements"].append({
                        "text": link.get_text(strip=True)[:50],
                        "type": pattern
                    })
                    break

        return content

    async def _analyze_technical(self, session: aiohttp.ClientSession, url: str, soup: BeautifulSoup, response) -> dict:
        """Analyze technical SEO factors."""
        technical = {
            "https": url.startswith("https"),
            "response_time_ms": 0,
            "has_robots_txt": False,
            "has_sitemap": False,
            "mobile_friendly_hints": [],
            "page_speed_hints": [],
            "security_headers": {}
        }

        # Check security headers
        important_headers = ["strict-transport-security", "content-security-policy", "x-frame-options", "x-content-type-options"]
        for header in important_headers:
            if header in response.headers:
                technical["security_headers"][header] = True

        # Mobile hints
        viewport = soup.find("meta", attrs={"name": "viewport"})
        if viewport:
            technical["mobile_friendly_hints"].append("Has viewport meta tag")

        # Check robots.txt
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        try:
            async with session.get(robots_url) as robots_resp:
                if robots_resp.status == 200:
                    technical["has_robots_txt"] = True
        except Exception:
            pass

        # Check sitemap
        sitemap_url = f"{parsed.scheme}://{parsed.netloc}/sitemap.xml"
        try:
            async with session.get(sitemap_url) as sitemap_resp:
                if sitemap_resp.status == 200:
                    technical["has_sitemap"] = True
        except Exception:
            pass

        return technical

    def _analyze_llm_factors(self, soup: BeautifulSoup, html: str) -> dict:
        """
        Analyze factors that affect LLM discoverability and AI search results.
        """
        llm = {
            "clear_value_proposition": False,
            "structured_content": False,
            "entity_mentions": [],
            "faq_schema": False,
            "how_to_schema": False,
            "clear_product_descriptions": False,
            "authoritative_content_signals": [],
            "citations_and_sources": 0,
            "content_freshness_signals": [],
            "unique_insights": []
        }

        # Check for FAQ structured data
        faq_indicators = ["faq", "frequently asked", "questions"]
        for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
            content = script.get_text().lower()
            if "faqpage" in content:
                llm["faq_schema"] = True
            if "howto" in content:
                llm["how_to_schema"] = True

        # Check for clear sections
        headers = soup.find_all(["h1", "h2", "h3"])
        if len(headers) >= 3:
            llm["structured_content"] = True

        # Look for value proposition patterns
        hero_patterns = ["hero", "banner", "jumbotron", "headline"]
        for pattern in hero_patterns:
            if soup.find(class_=re.compile(pattern, re.I)):
                llm["clear_value_proposition"] = True
                break

        # Check for authoritative signals
        if soup.find(text=re.compile(r"(research|study|data|according to|source)", re.I)):
            llm["authoritative_content_signals"].append("References research/data")

        # Citations (links to external authoritative sources)
        external_links = soup.find_all("a", href=re.compile(r"^https?://"))
        llm["citations_and_sources"] = len(external_links)

        # Freshness signals
        date_patterns = soup.find_all(attrs={"datetime": True})
        if date_patterns:
            llm["content_freshness_signals"].append("Has datetime attributes")

        time_tags = soup.find_all("time")
        if time_tags:
            llm["content_freshness_signals"].append("Uses time elements")

        return llm

    def _analyze_geo_factors(self, soup: BeautifulSoup) -> dict:
        """Analyze Generative Engine Optimization (GEO) factors."""
        geo = {
            "citation_ready": False,
            "quotable_statements": [],
            "statistics_present": False,
            "expert_attribution": False,
            "source_links": [],
            "definition_blocks": [],
            "comparison_tables": False,
            "lists_and_bullets": 0
        }

        # Check for statistics
        text = soup.get_text()
        if re.search(r"\d+%|\d+ percent|\d+\s*(million|billion|thousand)", text, re.I):
            geo["statistics_present"] = True

        # Check for lists
        lists = soup.find_all(["ul", "ol"])
        geo["lists_and_bullets"] = len(lists)

        # Check for tables (comparison/feature tables)
        tables = soup.find_all("table")
        if tables:
            geo["comparison_tables"] = True

        # Check for blockquotes (expert citations)
        blockquotes = soup.find_all("blockquote")
        if blockquotes:
            geo["expert_attribution"] = True
            for bq in blockquotes[:3]:
                geo["quotable_statements"].append(bq.get_text(strip=True)[:150])

        # Definition-like content
        dl_tags = soup.find_all("dl")
        if dl_tags:
            geo["definition_blocks"] = [dl.get_text(strip=True)[:100] for dl in dl_tags[:3]]

        # Citation readiness
        if geo["statistics_present"] and (geo["expert_attribution"] or geo["lists_and_bullets"] > 2):
            geo["citation_ready"] = True

        return geo

    def _compile_findings(self, result: dict) -> tuple[list, list]:
        """Compile issues and strengths from analysis."""
        issues = []
        strengths = []

        seo = result.get("seo_factors", {})
        tech = result.get("technical_factors", {})
        content = result.get("content_analysis", {})
        llm = result.get("llm_discoverability", {})
        geo = result.get("geo_factors", {})

        # SEO Issues
        if not seo.get("title"):
            issues.append({"category": "SEO", "severity": "high", "issue": "Missing page title"})
        elif seo.get("title_length", 0) > 60:
            issues.append({"category": "SEO", "severity": "medium", "issue": "Title too long (>60 chars)"})
        elif seo.get("title_length", 0) < 30:
            issues.append({"category": "SEO", "severity": "low", "issue": "Title may be too short (<30 chars)"})

        if not seo.get("meta_description"):
            issues.append({"category": "SEO", "severity": "high", "issue": "Missing meta description"})
        elif seo.get("meta_description_length", 0) > 160:
            issues.append({"category": "SEO", "severity": "medium", "issue": "Meta description too long (>160 chars)"})

        if len(seo.get("h1_tags", [])) == 0:
            issues.append({"category": "SEO", "severity": "high", "issue": "No H1 tag found"})
        elif len(seo.get("h1_tags", [])) > 1:
            issues.append({"category": "SEO", "severity": "medium", "issue": "Multiple H1 tags found"})

        if seo.get("images_without_alt", 0) > 0:
            issues.append({
                "category": "SEO",
                "severity": "medium",
                "issue": f"{seo['images_without_alt']} images missing alt text"
            })

        if not seo.get("og_tags"):
            issues.append({"category": "SEO", "severity": "medium", "issue": "Missing Open Graph tags"})

        # Technical Issues
        if not tech.get("https"):
            issues.append({"category": "Technical", "severity": "high", "issue": "Not using HTTPS"})

        if not tech.get("has_robots_txt"):
            issues.append({"category": "Technical", "severity": "medium", "issue": "No robots.txt found"})

        if not tech.get("has_sitemap"):
            issues.append({"category": "Technical", "severity": "medium", "issue": "No sitemap.xml found"})

        if not tech.get("mobile_friendly_hints"):
            issues.append({"category": "Technical", "severity": "high", "issue": "No viewport meta tag (mobile issues)"})

        # LLM Discoverability Issues
        if not llm.get("structured_content"):
            issues.append({"category": "LLM", "severity": "medium", "issue": "Content lacks clear structure (few headers)"})

        if not llm.get("faq_schema"):
            issues.append({"category": "LLM", "severity": "low", "issue": "No FAQ schema markup"})

        # GEO Issues
        if not geo.get("statistics_present"):
            issues.append({"category": "GEO", "severity": "medium", "issue": "No statistics or data points found"})

        if geo.get("lists_and_bullets", 0) < 2:
            issues.append({"category": "GEO", "severity": "low", "issue": "Limited use of lists for scannable content"})

        if not geo.get("citation_ready"):
            issues.append({"category": "GEO", "severity": "medium", "issue": "Content not optimized for AI citations"})

        # Strengths
        if seo.get("title") and 30 <= seo.get("title_length", 0) <= 60:
            strengths.append({"category": "SEO", "strength": "Well-optimized title length"})

        if seo.get("meta_description") and 120 <= seo.get("meta_description_length", 0) <= 160:
            strengths.append({"category": "SEO", "strength": "Good meta description length"})

        if content.get("has_structured_data"):
            strengths.append({"category": "SEO", "strength": f"Has structured data: {', '.join(content.get('structured_data_types', []))}"})

        if tech.get("https"):
            strengths.append({"category": "Technical", "strength": "Using HTTPS"})

        if tech.get("has_sitemap"):
            strengths.append({"category": "Technical", "strength": "Has sitemap.xml"})

        if llm.get("faq_schema"):
            strengths.append({"category": "LLM", "strength": "Has FAQ schema for AI search"})

        if geo.get("statistics_present"):
            strengths.append({"category": "GEO", "strength": "Contains statistics/data points"})

        if geo.get("comparison_tables"):
            strengths.append({"category": "GEO", "strength": "Has comparison tables"})

        return issues, strengths

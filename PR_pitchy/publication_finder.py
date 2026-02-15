"""
Publication Finder Module
Fetches recent articles from known tech/B2B publications to reverse-engineer
journalist coverage patterns for beat matching and pitch personalization.
"""

import asyncio
import re
from typing import Optional
import aiohttp
from bs4 import BeautifulSoup


# Curated publication list with RSS feeds and metadata
# Tiered by audience and relevance to B2B tech / cybersecurity
PUBLICATIONS = [
    # Tier 1 — B2B Cybersecurity Trade Press
    {
        "name": "Dark Reading",
        "domain": "darkreading.com",
        "tier": 1,
        "beat": "cybersecurity",
        "audience": "Security professionals, CISOs, SOC teams",
        "rss": "https://www.darkreading.com/rss.xml",
        "description": "Leading cybersecurity news — threats, vulnerabilities, tools, industry trends"
    },
    {
        "name": "SecurityWeek",
        "domain": "securityweek.com",
        "tier": 1,
        "beat": "cybersecurity",
        "audience": "Security professionals, enterprise IT",
        "rss": "https://feeds.feedburner.com/securityweek",
        "description": "Breaking cybersecurity news, malware, privacy, policy, AI security"
    },
    {
        "name": "SC Magazine",
        "domain": "scmagazine.com",
        "tier": 1,
        "beat": "cybersecurity",
        "audience": "Security practitioners, IT managers",
        "rss": "https://www.scmagazine.com/feed",
        "description": "Cybersecurity news, threat intelligence, data protection, compliance"
    },
    {
        "name": "Help Net Security",
        "domain": "helpnetsecurity.com",
        "tier": 1,
        "beat": "cybersecurity",
        "audience": "IT security professionals",
        "rss": "https://www.helpnetsecurity.com/feed/",
        "description": "Threat intelligence, incident response, cybersecurity best practices"
    },
    {
        "name": "The Hacker News",
        "domain": "thehackernews.com",
        "tier": 1,
        "beat": "cybersecurity",
        "audience": "Hackers, security researchers, IT pros",
        "rss": "https://feeds.feedburner.com/TheHackersNews",
        "description": "Hacking news, cybersecurity incidents, critical vulnerabilities, data breaches"
    },
    {
        "name": "Infosecurity Magazine",
        "domain": "infosecurity-magazine.com",
        "tier": 1,
        "beat": "cybersecurity",
        "audience": "CISOs, security managers, compliance officers",
        "rss": "https://www.infosecurity-magazine.com/rss/news/",
        "description": "Risk management, threat intelligence, compliance, enterprise security"
    },
    # Tier 1 — Broad B2B Tech Press
    {
        "name": "TechCrunch",
        "domain": "techcrunch.com",
        "tier": 1,
        "beat": "startups, enterprise tech, funding",
        "audience": "Founders, investors, tech industry",
        "rss": "https://techcrunch.com/feed/",
        "description": "Startups, funding rounds, enterprise tech, product launches"
    },
    {
        "name": "VentureBeat",
        "domain": "venturebeat.com",
        "tier": 1,
        "beat": "enterprise tech, AI, security",
        "audience": "Enterprise decision makers, tech leaders",
        "rss": "https://venturebeat.com/feed/",
        "description": "Enterprise AI, cloud, security, digital transformation"
    },
    {
        "name": "Wired",
        "domain": "wired.com",
        "tier": 1,
        "beat": "technology, security, culture",
        "audience": "Tech-savvy general audience, decision makers",
        "rss": "https://www.wired.com/feed/rss",
        "description": "Technology, cybersecurity, culture, policy, innovation"
    },
    # Tier 2 — Enterprise / Business Tech
    {
        "name": "CSO Online",
        "domain": "csoonline.com",
        "tier": 2,
        "beat": "security leadership, risk",
        "audience": "CSOs, CISOs, security executives",
        "rss": "https://www.csoonline.com/index.rss",
        "description": "Security leadership, risk management, compliance, CISO strategy"
    },
    {
        "name": "TechRepublic",
        "domain": "techrepublic.com",
        "tier": 2,
        "beat": "enterprise IT, security, productivity",
        "audience": "IT professionals, managers, decision makers",
        "rss": "https://www.techrepublic.com/rssfeeds/articles/",
        "description": "Enterprise IT advice, security, compliance, AI tools"
    },
    {
        "name": "ZDNet",
        "domain": "zdnet.com",
        "tier": 2,
        "beat": "enterprise tech, cloud, security",
        "audience": "IT professionals, business leaders",
        "rss": "https://www.zdnet.com/news/rss.xml",
        "description": "Enterprise technology news, cloud, security, digital business"
    },
    {
        "name": "Forbes Tech",
        "domain": "forbes.com",
        "tier": 2,
        "beat": "business technology, startups, leadership",
        "audience": "Business executives, investors, general business",
        "rss": "https://www.forbes.com/innovation/feed2",
        "description": "Business technology, startup profiles, executive thought leadership"
    },
    # Tier 2 — Niche / Specialist
    {
        "name": "CRN",
        "domain": "crn.com",
        "tier": 2,
        "beat": "channel, resellers, MSPs",
        "audience": "VARs, MSPs, channel partners",
        "rss": "https://www.crn.com/rss/news.xml",
        "description": "Channel technology news — resellers, MSPs, vendor partnerships"
    },
    {
        "name": "BetaNews",
        "domain": "betanews.com",
        "tier": 2,
        "beat": "enterprise software, security, open source",
        "audience": "IT professionals, developers",
        "rss": "https://betanews.com/feed/",
        "description": "Enterprise software, security tools, open source, productivity"
    },
    {
        "name": "SiliconANGLE",
        "domain": "siliconangle.com",
        "tier": 2,
        "beat": "cloud, AI, enterprise tech",
        "audience": "Enterprise tech buyers, IT leaders",
        "rss": "https://siliconangle.com/feed/",
        "description": "Cloud, AI, enterprise software, startup coverage"
    },
]


class PublicationFinder:
    """Fetch recent articles from publications to reverse-engineer coverage patterns."""

    def __init__(self):
        self.timeout = aiohttp.ClientTimeout(total=10)
        self.headers = {
            "User-Agent": "Mozilla/5.0 (compatible; PRPitchy/1.0; research bot)"
        }

    async def fetch_recent_articles(self, publication: dict, max_articles: int = 5) -> list[dict]:
        """Fetch recent articles from a publication's RSS feed."""
        articles = []
        try:
            async with aiohttp.ClientSession(timeout=self.timeout, headers=self.headers) as session:
                async with session.get(publication["rss"]) as response:
                    if response.status != 200:
                        return []
                    content = await response.text()

            # Parse RSS with BeautifulSoup
            soup = BeautifulSoup(content, "xml")
            items = soup.find_all("item")[:max_articles]
            if not items:
                # Try Atom format
                items = soup.find_all("entry")[:max_articles]

            for item in items:
                title = item.find("title")
                link = item.find("link")
                description = item.find("description") or item.find("summary")
                pub_date = item.find("pubDate") or item.find("published")

                title_text = title.get_text(strip=True) if title else ""
                # RSS link can be text or attribute
                link_text = ""
                if link:
                    link_text = link.get_text(strip=True) or link.get("href", "")

                desc_text = ""
                if description:
                    # Strip HTML from description
                    desc_soup = BeautifulSoup(description.get_text(strip=True), "html.parser")
                    desc_text = desc_soup.get_text(strip=True)[:300]

                # Extract author/byline — try multiple RSS formats
                author = None
                # Standard RSS <author>
                author_tag = item.find("author")
                if author_tag:
                    author = author_tag.get_text(strip=True)
                # Dublin Core <dc:creator> — most common in WordPress/Drupal feeds
                if not author:
                    dc_creator = item.find("dc:creator") or item.find("creator")
                    if dc_creator:
                        author = dc_creator.get_text(strip=True)
                # Media RSS <media:credit>
                if not author:
                    media_credit = item.find("media:credit") or item.find("credit")
                    if media_credit:
                        author = media_credit.get_text(strip=True)
                # Sanitize email+name format: "foo@bar.com (Jane Smith)" → "Jane Smith"
                if author and "(" in author and "@" in author:
                    match = re.search(r'\(([^)]+)\)', author)
                    author = match.group(1) if match else author.split("(")[-1].rstrip(")")
                # Strip bare email addresses (no name value)
                if author and "@" in author and "(" not in author:
                    author = None

                if title_text:
                    articles.append({
                        "title": title_text,
                        "url": link_text,
                        "summary": desc_text,
                        "date": pub_date.get_text(strip=True) if pub_date else "",
                        "author": author or "",
                        "publication": publication["name"],
                        "domain": publication["domain"],
                        "beat": publication["beat"],
                        "audience": publication["audience"],
                    })

        except Exception:
            pass

        return articles

    async def scan_publications(
        self,
        beat_filter: Optional[str] = None,
        tier_filter: Optional[int] = None,
        max_per_pub: int = 5
    ) -> list[dict]:
        """
        Scan multiple publications in parallel, return recent articles.
        Optionally filter by beat or tier.
        """
        pubs_to_scan = PUBLICATIONS
        if tier_filter:
            pubs_to_scan = [p for p in pubs_to_scan if p["tier"] <= tier_filter]
        if beat_filter:
            pubs_to_scan = [
                p for p in pubs_to_scan
                if beat_filter.lower() in p["beat"].lower()
                or beat_filter.lower() in p["description"].lower()
            ]

        tasks = [self.fetch_recent_articles(pub, max_per_pub) for pub in pubs_to_scan]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_articles = []
        pub_summaries = []

        for pub, result in zip(pubs_to_scan, results):
            if isinstance(result, Exception) or not result:
                articles = []
            else:
                articles = result
                all_articles.extend(articles)

            pub_summaries.append({
                "name": pub["name"],
                "domain": pub["domain"],
                "tier": pub["tier"],
                "beat": pub["beat"],
                "audience": pub["audience"],
                "description": pub["description"],
                "recent_headlines": [a["title"] for a in articles],
                "known_authors": list(set(a["author"] for a in articles if a.get("author"))),
                "article_count": len(articles),
            })

        return pub_summaries, all_articles

    def get_publication_context(self) -> str:
        """Return a text summary of all publications for use in LLM prompts."""
        lines = []
        for pub in PUBLICATIONS:
            lines.append(
                f"- {pub['name']} (Tier {pub['tier']}, {pub['domain']}): "
                f"Beat: {pub['beat']}. Audience: {pub['audience']}. "
                f"{pub['description']}"
            )
        return "\n".join(lines)

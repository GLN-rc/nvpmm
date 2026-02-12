"""
SEO/GEO/LLM Optimization Best Practices
Comprehensive guidelines for optimizing content for traditional search,
AI search engines, and LLM responses.

Based on industry research and established optimization frameworks including:
- 4 Pillars of LLM Retrieval Systems
- Generative Engine Optimization (GEO) principles
- Answer Engine Optimization (AEO)
- Traditional SEO best practices adapted for AI
"""


# ============================================================================
# GEO (Generative Engine Optimization) Best Practices
# ============================================================================

GEO_BEST_PRACTICES = {
    "citation_optimization": {
        "title": "Optimize for AI Citations",
        "description": "Structure content to be easily quoted and cited by AI systems",
        "actions": [
            "Include statistics with specific numbers (e.g., '73% of users prefer...')",
            "Add quotable expert statements with clear attribution",
            "Use definitive statements that can stand alone as citations",
            "Include unique data points or research findings",
            "Format key insights as standalone sentences"
        ],
        "impact": "high",
        "effort": "medium"
    },
    "fluency_optimization": {
        "title": "Improve Content Fluency",
        "description": "Write clear, well-structured content that AI can easily process",
        "actions": [
            "Use clear, concise language avoiding jargon where possible",
            "Write in active voice for better clarity",
            "Structure sentences with subject-verb-object pattern",
            "Avoid ambiguous pronouns and references",
            "Use transition words to connect ideas logically"
        ],
        "impact": "medium",
        "effort": "low"
    },
    "unique_words": {
        "title": "Include Unique Terminology",
        "description": "Use distinctive, memorable terms that AI systems will associate with your brand",
        "actions": [
            "Develop and consistently use branded terminology",
            "Define technical terms clearly on first use",
            "Create memorable names for your methodologies or frameworks",
            "Use specific, descriptive language rather than generic terms"
        ],
        "impact": "medium",
        "effort": "medium"
    },
    "technical_terms": {
        "title": "Proper Technical Term Usage",
        "description": "Use accurate technical terminology that establishes expertise",
        "actions": [
            "Use industry-standard terminology correctly",
            "Include technical specifications where relevant",
            "Reference standards, protocols, or frameworks by proper name",
            "Balance technical depth with accessibility"
        ],
        "impact": "medium",
        "effort": "low"
    },
    "authoritative_content": {
        "title": "Build Authoritative Content",
        "description": "Establish credibility through authoritative sources and expertise",
        "actions": [
            "Cite reputable sources with links",
            "Include author credentials and expertise",
            "Reference industry studies and research",
            "Update content regularly to maintain accuracy",
            "Include 'last updated' timestamps"
        ],
        "impact": "high",
        "effort": "medium"
    },
    "statistics_data": {
        "title": "Include Statistics and Data",
        "description": "Add quantifiable data points that AI systems can cite",
        "actions": [
            "Include relevant statistics with sources",
            "Use specific numbers rather than vague terms",
            "Present data in easily extractable formats",
            "Update statistics regularly",
            "Attribute all data to sources"
        ],
        "impact": "high",
        "effort": "medium"
    }
}


# ============================================================================
# LLM Discoverability Best Practices
# ============================================================================

LLM_BEST_PRACTICES = {
    "structured_content": {
        "title": "Structure Content for LLM Parsing",
        "description": "Organize content in ways that LLMs can easily understand and retrieve",
        "actions": [
            "Use clear heading hierarchy (H1 > H2 > H3)",
            "Start sections with summary statements",
            "Use bullet points for lists of features/benefits",
            "Include table of contents for long content",
            "Keep paragraphs focused on single topics"
        ],
        "impact": "high",
        "effort": "low"
    },
    "faq_schema": {
        "title": "Implement FAQ Schema",
        "description": "Add FAQ structured data to appear in AI-powered search",
        "actions": [
            "Create dedicated FAQ section addressing common questions",
            "Implement FAQPage schema markup (JSON-LD)",
            "Write questions as users would ask them",
            "Provide complete, self-contained answers",
            "Group related questions together"
        ],
        "impact": "high",
        "effort": "low"
    },
    "howto_schema": {
        "title": "Add How-To Schema",
        "description": "Implement HowTo structured data for instructional content",
        "actions": [
            "Break processes into clear, numbered steps",
            "Include estimated time and required tools",
            "Add images for each step where helpful",
            "Implement HowTo schema markup",
            "Test with Google's Rich Results Test"
        ],
        "impact": "medium",
        "effort": "medium"
    },
    "entity_definitions": {
        "title": "Define Entities Clearly",
        "description": "Help LLMs understand what your brand/products are",
        "actions": [
            "Include clear 'what is X' definitions",
            "Define your company/product in the first paragraph",
            "Use Organization and Product schema markup",
            "Maintain consistent naming across all content",
            "Create a glossary for technical terms"
        ],
        "impact": "high",
        "effort": "medium"
    },
    "question_answering": {
        "title": "Optimize for Q&A Retrieval",
        "description": "Structure content to directly answer user questions",
        "actions": [
            "Use questions as H2/H3 headings",
            "Provide direct answers in the first sentence",
            "Follow with supporting details",
            "Address 'who, what, when, where, why, how'",
            "Include comparisons with alternatives"
        ],
        "impact": "high",
        "effort": "low"
    },
    "knowledge_graph": {
        "title": "Build Knowledge Graph Presence",
        "description": "Establish entity presence in knowledge graphs used by LLMs",
        "actions": [
            "Claim and optimize Google Business Profile",
            "Maintain Wikipedia/Wikidata presence if eligible",
            "Use consistent NAP (Name, Address, Phone) everywhere",
            "Implement comprehensive schema markup",
            "Get listed in industry directories"
        ],
        "impact": "high",
        "effort": "high"
    }
}


# ============================================================================
# Traditional SEO Best Practices (Still Relevant)
# ============================================================================

SEO_BEST_PRACTICES = {
    "title_optimization": {
        "title": "Optimize Page Titles",
        "description": "Create compelling, keyword-rich titles",
        "actions": [
            "Keep titles between 50-60 characters",
            "Include primary keyword near the beginning",
            "Make each page title unique",
            "Include brand name at the end",
            "Write for humans, not just search engines"
        ],
        "impact": "high",
        "effort": "low"
    },
    "meta_description": {
        "title": "Write Effective Meta Descriptions",
        "description": "Create compelling descriptions that drive clicks",
        "actions": [
            "Keep between 150-160 characters",
            "Include primary keyword naturally",
            "Include a clear call-to-action",
            "Make each meta description unique",
            "Accurately summarize page content"
        ],
        "impact": "medium",
        "effort": "low"
    },
    "heading_structure": {
        "title": "Use Proper Heading Structure",
        "description": "Create logical content hierarchy with headings",
        "actions": [
            "Use only one H1 per page",
            "Follow hierarchical order (H1 > H2 > H3)",
            "Include keywords in headings naturally",
            "Keep headings descriptive and concise",
            "Don't skip heading levels"
        ],
        "impact": "medium",
        "effort": "low"
    },
    "image_optimization": {
        "title": "Optimize Images",
        "description": "Ensure all images are properly optimized",
        "actions": [
            "Add descriptive alt text to all images",
            "Use descriptive file names",
            "Compress images for fast loading",
            "Use modern formats (WebP, AVIF)",
            "Implement lazy loading"
        ],
        "impact": "medium",
        "effort": "medium"
    },
    "internal_linking": {
        "title": "Build Strong Internal Links",
        "description": "Create effective internal link structure",
        "actions": [
            "Link to related content naturally",
            "Use descriptive anchor text",
            "Create hub/spoke content structures",
            "Ensure important pages aren't orphaned",
            "Fix broken internal links"
        ],
        "impact": "medium",
        "effort": "medium"
    },
    "mobile_first": {
        "title": "Ensure Mobile Optimization",
        "description": "Optimize for mobile-first indexing",
        "actions": [
            "Use responsive design",
            "Ensure text is readable without zooming",
            "Make touch targets adequately sized",
            "Avoid horizontal scrolling",
            "Test with Mobile-Friendly Test"
        ],
        "impact": "high",
        "effort": "medium"
    },
    "page_speed": {
        "title": "Improve Page Speed",
        "description": "Optimize loading performance",
        "actions": [
            "Minimize render-blocking resources",
            "Implement browser caching",
            "Use CDN for static assets",
            "Optimize Core Web Vitals",
            "Monitor with PageSpeed Insights"
        ],
        "impact": "high",
        "effort": "high"
    }
}


# ============================================================================
# AEO (Answer Engine Optimization) Best Practices
# ============================================================================

AEO_BEST_PRACTICES = {
    "featured_snippets": {
        "title": "Optimize for Featured Snippets",
        "description": "Structure content to win position zero",
        "actions": [
            "Answer questions directly in 40-50 words",
            "Use definition format: 'X is...'",
            "Create numbered/bulleted lists",
            "Include comparison tables",
            "Use 'What is', 'How to', 'Why' formats"
        ],
        "impact": "high",
        "effort": "medium"
    },
    "voice_search": {
        "title": "Optimize for Voice Search",
        "description": "Prepare content for voice assistant queries",
        "actions": [
            "Target conversational, long-tail keywords",
            "Answer 'who, what, where, when, why, how'",
            "Write in natural, conversational tone",
            "Target question-based queries",
            "Focus on local search for applicable businesses"
        ],
        "impact": "medium",
        "effort": "low"
    },
    "people_also_ask": {
        "title": "Target 'People Also Ask'",
        "description": "Answer related questions to expand visibility",
        "actions": [
            "Research PAA questions for your topics",
            "Create content sections answering each",
            "Use FAQ schema for these answers",
            "Keep answers concise but complete",
            "Update with new questions regularly"
        ],
        "impact": "medium",
        "effort": "medium"
    }
}


# ============================================================================
# Priority Matrix
# ============================================================================

def get_priority_matrix():
    """
    Returns a prioritized list of all optimizations sorted by
    impact/effort ratio.
    """
    all_practices = []

    impact_scores = {"high": 3, "medium": 2, "low": 1}
    effort_scores = {"low": 3, "medium": 2, "high": 1}

    for category, practices in [
        ("GEO", GEO_BEST_PRACTICES),
        ("LLM", LLM_BEST_PRACTICES),
        ("SEO", SEO_BEST_PRACTICES),
        ("AEO", AEO_BEST_PRACTICES)
    ]:
        for key, practice in practices.items():
            priority_score = (
                impact_scores.get(practice["impact"], 1) *
                effort_scores.get(practice["effort"], 1)
            )
            all_practices.append({
                "category": category,
                "key": key,
                "priority_score": priority_score,
                **practice
            })

    # Sort by priority score (highest first)
    return sorted(all_practices, key=lambda x: x["priority_score"], reverse=True)


def get_recommendations_for_issues(issues: list) -> list:
    """
    Given a list of detected issues, return relevant best practice recommendations.
    """
    recommendations = []
    priority_matrix = get_priority_matrix()

    # Map issue types to relevant practices
    issue_practice_map = {
        "Missing page title": ["title_optimization"],
        "Title too long": ["title_optimization"],
        "Title may be too short": ["title_optimization"],
        "Missing meta description": ["meta_description"],
        "Meta description too long": ["meta_description"],
        "No H1 tag found": ["heading_structure"],
        "Multiple H1 tags": ["heading_structure"],
        "images missing alt text": ["image_optimization"],
        "Missing Open Graph tags": ["structured_content"],
        "Not using HTTPS": ["page_speed"],
        "No robots.txt": ["page_speed"],
        "No sitemap.xml": ["page_speed"],
        "No viewport meta tag": ["mobile_first"],
        "Content lacks clear structure": ["structured_content", "heading_structure"],
        "No FAQ schema": ["faq_schema"],
        "No statistics or data": ["statistics_data"],
        "Limited use of lists": ["fluency_optimization", "featured_snippets"],
        "Content not optimized for AI citations": ["citation_optimization", "statistics_data"]
    }

    matched_practices = set()

    for issue in issues:
        issue_text = issue.get("issue", "")
        for issue_key, practice_keys in issue_practice_map.items():
            if issue_key.lower() in issue_text.lower():
                matched_practices.update(practice_keys)

    for practice in priority_matrix:
        if practice["key"] in matched_practices:
            recommendations.append(practice)

    return recommendations[:10]  # Return top 10 relevant recommendations


# ============================================================================
# Checklist Generator
# ============================================================================

def generate_optimization_checklist(site_analysis: dict) -> dict:
    """
    Generate a customized optimization checklist based on site analysis.
    """
    checklist = {
        "immediate": [],  # Quick wins (high impact, low effort)
        "short_term": [],  # Medium priority
        "long_term": [],  # Strategic improvements
        "monitoring": []  # Ongoing tasks
    }

    seo = site_analysis.get("seo_factors", {})
    tech = site_analysis.get("technical_factors", {})
    llm = site_analysis.get("llm_discoverability", {})
    geo = site_analysis.get("geo_factors", {})

    # Immediate (Quick Wins)
    if not seo.get("title") or seo.get("title_length", 0) > 60:
        checklist["immediate"].append({
            "task": "Optimize page title",
            "detail": "Create a compelling 50-60 character title with primary keyword"
        })

    if not seo.get("meta_description"):
        checklist["immediate"].append({
            "task": "Add meta description",
            "detail": "Write 150-160 character description with call-to-action"
        })

    if seo.get("images_without_alt", 0) > 0:
        checklist["immediate"].append({
            "task": "Add alt text to images",
            "detail": f"Add descriptive alt text to {seo['images_without_alt']} images"
        })

    if len(seo.get("h1_tags", [])) != 1:
        checklist["immediate"].append({
            "task": "Fix H1 tag structure",
            "detail": "Ensure exactly one H1 tag per page"
        })

    # Short-term
    if not llm.get("faq_schema"):
        checklist["short_term"].append({
            "task": "Implement FAQ schema",
            "detail": "Add FAQ section with JSON-LD structured data"
        })

    if not geo.get("statistics_present"):
        checklist["short_term"].append({
            "task": "Add statistics and data",
            "detail": "Include relevant statistics with sources for AI citations"
        })

    if not tech.get("has_sitemap"):
        checklist["short_term"].append({
            "task": "Create XML sitemap",
            "detail": "Generate and submit sitemap to search engines"
        })

    if geo.get("lists_and_bullets", 0) < 3:
        checklist["short_term"].append({
            "task": "Improve content structure",
            "detail": "Add bullet points and numbered lists for key information"
        })

    # Long-term
    if not llm.get("structured_content"):
        checklist["long_term"].append({
            "task": "Restructure content hierarchy",
            "detail": "Create clear heading structure with H2/H3 sections"
        })

    if not geo.get("comparison_tables"):
        checklist["long_term"].append({
            "task": "Create comparison content",
            "detail": "Add comparison tables for features, pricing, or alternatives"
        })

    checklist["long_term"].append({
        "task": "Build authoritative backlinks",
        "detail": "Develop content strategy for earning quality backlinks"
    })

    # Monitoring
    checklist["monitoring"].append({
        "task": "Track Core Web Vitals",
        "detail": "Monitor LCP, FID, CLS regularly"
    })

    checklist["monitoring"].append({
        "task": "Monitor AI search visibility",
        "detail": "Track brand mentions in AI tools like ChatGPT, Perplexity"
    })

    checklist["monitoring"].append({
        "task": "Update content regularly",
        "detail": "Refresh statistics, dates, and outdated information"
    })

    return checklist

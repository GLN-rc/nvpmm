"""
Metric Explanations Module
Provides context and meaning for website analysis metrics.
Helps users understand what metrics mean and why they matter.
"""

METRIC_EXPLANATIONS = {
    # SEO Metrics
    "word_count": {
        "name": "Word Count",
        "what": "Total words on your page",
        "why": "Longer content (1,500-2,500+ words) typically ranks better for competitive keywords. It signals depth and expertise to search engines and AI systems.",
        "benchmark": "Homepage: 500-1000 words. Key landing pages: 1,500-2,500 words. Blog posts: 2,000+ words for competitive topics.",
        "competitor_context": "If competitors have significantly more words, they may be providing more comprehensive coverage of topics, which search engines and AI favor."
    },
    "title_length": {
        "name": "Title Length",
        "what": "Characters in your page title tag",
        "why": "Titles are the #1 on-page SEO factor. They appear in search results and browser tabs. Too short = missed keyword opportunity. Too long = gets cut off in search results.",
        "benchmark": "Optimal: 50-60 characters. Include primary keyword near the beginning.",
        "competitor_context": "Compare title clarity and keyword usage, not just length."
    },
    "meta_description_length": {
        "name": "Meta Description Length",
        "what": "Characters in your meta description",
        "why": "While not a direct ranking factor, meta descriptions are your 'ad copy' in search results. A compelling description increases click-through rate.",
        "benchmark": "Optimal: 150-160 characters. Include a call-to-action and primary keyword.",
        "competitor_context": "Review competitor descriptions for messaging angles you might be missing."
    },
    "h1_tags": {
        "name": "H1 Headings",
        "what": "Number of H1 (main heading) tags on page",
        "why": "H1 tells search engines and AI what your page is primarily about. Best practice: exactly one H1 per page containing your primary topic/keyword.",
        "benchmark": "Exactly 1 H1 per page. Should match/reinforce the page title.",
        "competitor_context": "Multiple H1s or missing H1 indicates poor page structure."
    },
    "images_without_alt": {
        "name": "Images Missing Alt Text",
        "what": "Images without descriptive alt attributes",
        "why": "Alt text helps search engines understand images, improves accessibility, and provides another opportunity to include relevant keywords.",
        "benchmark": "0 images without alt text. Every image should have descriptive alt text.",
        "competitor_context": "This is a quick win - easy to fix and improves SEO."
    },

    # Technical Metrics
    "https": {
        "name": "HTTPS Security",
        "what": "Whether your site uses secure HTTPS protocol",
        "why": "HTTPS is a confirmed Google ranking factor. Users and AI systems trust secure sites more. Chrome marks HTTP sites as 'Not Secure'.",
        "benchmark": "100% of pages should be HTTPS.",
        "competitor_context": "If you're not on HTTPS and competitors are, you're at a disadvantage."
    },
    "has_sitemap": {
        "name": "XML Sitemap",
        "what": "Whether you have a sitemap.xml file",
        "why": "Sitemaps help search engines discover and index your pages faster. Essential for larger sites or sites with poor internal linking.",
        "benchmark": "Every site should have an XML sitemap submitted to Google Search Console.",
        "competitor_context": "Not having a sitemap puts you at an indexing disadvantage."
    },

    # LLM Discoverability Metrics
    "structured_content": {
        "name": "Structured Content",
        "what": "Whether your content uses clear heading hierarchy",
        "why": "AI systems parse content by headings. Clear H1→H2→H3 structure helps AI understand and accurately represent your content.",
        "benchmark": "Use heading hierarchy to create clear content sections. Each H2 should cover a distinct subtopic.",
        "competitor_context": "Better structured content = better AI understanding = better AI recommendations."
    },
    "faq_schema": {
        "name": "FAQ Schema Markup",
        "what": "Whether you have FAQ structured data",
        "why": "FAQ schema can trigger rich results in Google and helps AI systems identify Q&A content for voice search and AI assistants.",
        "benchmark": "Add FAQ schema to pages with Q&A content. Use FAQPage JSON-LD format.",
        "competitor_context": "Competitors with FAQ schema may appear in 'People Also Ask' and AI responses more often."
    },
    "citations_and_sources": {
        "name": "External Citations",
        "what": "Number of links to authoritative external sources",
        "why": "Citing sources builds credibility with both users and AI systems. It signals that your content is well-researched and trustworthy.",
        "benchmark": "Include 2-5 relevant citations per major content page to authoritative sources.",
        "competitor_context": "More citations = more authoritative appearance to AI systems."
    },

    # GEO (Generative Engine Optimization) Metrics
    "statistics_present": {
        "name": "Statistics & Data",
        "what": "Whether your content includes specific numbers and statistics",
        "why": "AI systems love citing specific statistics. Content with data points is more likely to be quoted in AI-generated responses.",
        "benchmark": "Include 3-5 relevant statistics per key page. Always cite sources.",
        "competitor_context": "If competitors include statistics and you don't, AI will prefer citing them."
    },
    "citation_ready": {
        "name": "AI Citation Ready",
        "what": "Whether your content is optimized for AI systems to quote/cite",
        "why": "AI search (ChatGPT, Perplexity, etc.) needs quotable, factual content. Being 'citation ready' means AI can easily extract and attribute info to you.",
        "benchmark": "Combine: statistics + expert quotes + clear statements + proper attribution.",
        "competitor_context": "This is the new competitive battleground - who gets cited by AI."
    },
    "lists_and_bullets": {
        "name": "Lists & Bullet Points",
        "what": "Number of bulleted/numbered lists on page",
        "why": "Lists are easily scannable by humans AND easily extractable by AI. They often become featured snippets and AI response content.",
        "benchmark": "Use lists for features, benefits, steps, and comparisons. Aim for 3+ lists per major content page.",
        "competitor_context": "More lists = higher chance of featured snippet and AI inclusion."
    },
    "comparison_tables": {
        "name": "Comparison Tables",
        "what": "Whether you have HTML tables comparing features/options",
        "why": "Tables are highly extractable by AI for comparison queries. They often win featured snippets for 'X vs Y' searches.",
        "benchmark": "Include comparison tables on product pages and competitive content.",
        "competitor_context": "Competitors with comparison tables will win 'vs' and 'best' queries."
    }
}


def get_metric_explanation(metric_key: str) -> dict:
    """Get explanation for a specific metric."""
    return METRIC_EXPLANATIONS.get(metric_key, {
        "name": metric_key.replace("_", " ").title(),
        "what": "No explanation available",
        "why": "No explanation available",
        "benchmark": "N/A",
        "competitor_context": "N/A"
    })


def get_all_explanations() -> dict:
    """Get all metric explanations."""
    return METRIC_EXPLANATIONS


def generate_metric_insights(your_site: dict, competitors: list[dict]) -> list[dict]:
    """
    Generate insights comparing your metrics to competitors with explanations.
    """
    insights = []

    your_seo = your_site.get("seo_factors", {})
    your_geo = your_site.get("geo_factors", {})
    your_llm = your_site.get("llm_discoverability", {})

    # Calculate competitor averages
    comp_word_counts = []
    comp_with_stats = 0
    comp_with_faq = 0
    total_comps = 0

    for comp in competitors:
        if comp.get("status") == "success":
            total_comps += 1
            comp_seo = comp.get("seo_factors", {})
            comp_geo = comp.get("geo_factors", {})
            comp_llm = comp.get("llm_discoverability", {})

            if comp_seo.get("word_count"):
                comp_word_counts.append(comp_seo["word_count"])
            if comp_geo.get("statistics_present"):
                comp_with_stats += 1
            if comp_llm.get("faq_schema"):
                comp_with_faq += 1

    # Word count insight
    your_words = your_seo.get("word_count", 0)
    if comp_word_counts:
        avg_comp_words = sum(comp_word_counts) / len(comp_word_counts)
        exp = METRIC_EXPLANATIONS["word_count"]

        if your_words < avg_comp_words * 0.7:
            insights.append({
                "metric": "word_count",
                "status": "behind",
                "your_value": your_words,
                "competitor_avg": int(avg_comp_words),
                "explanation": exp["why"],
                "recommendation": f"Your content is {int(avg_comp_words - your_words)} words shorter than competitor average. Consider expanding key sections with more depth.",
                "benchmark": exp["benchmark"]
            })
        elif your_words > avg_comp_words * 1.3:
            insights.append({
                "metric": "word_count",
                "status": "ahead",
                "your_value": your_words,
                "competitor_avg": int(avg_comp_words),
                "explanation": exp["why"],
                "recommendation": "Great content depth! Ensure quality matches quantity.",
                "benchmark": exp["benchmark"]
            })

    # Statistics insight
    if total_comps > 0:
        stats_pct = (comp_with_stats / total_comps) * 100
        exp = METRIC_EXPLANATIONS["statistics_present"]

        if not your_geo.get("statistics_present") and stats_pct >= 50:
            insights.append({
                "metric": "statistics_present",
                "status": "behind",
                "your_value": "No",
                "competitor_avg": f"{int(stats_pct)}% have statistics",
                "explanation": exp["why"],
                "recommendation": "Add specific statistics and data points to improve AI citation potential.",
                "benchmark": exp["benchmark"]
            })

    # FAQ schema insight
    if total_comps > 0:
        faq_pct = (comp_with_faq / total_comps) * 100
        exp = METRIC_EXPLANATIONS["faq_schema"]

        if not your_llm.get("faq_schema") and faq_pct >= 30:
            insights.append({
                "metric": "faq_schema",
                "status": "behind",
                "your_value": "No",
                "competitor_avg": f"{int(faq_pct)}% have FAQ schema",
                "explanation": exp["why"],
                "recommendation": "Add FAQ schema to improve visibility in AI and voice search.",
                "benchmark": exp["benchmark"]
            })

    return insights

"""
Optimization Analyzer Module
Uses LLM to generate specific, prioritized optimization suggestions
based on website analysis and brand context.
"""

import os
import json
from typing import Optional
import litellm
from document_processor import BrandContextBuilder
from best_practices import (
    GEO_BEST_PRACTICES,
    LLM_BEST_PRACTICES,
    SEO_BEST_PRACTICES,
    AEO_BEST_PRACTICES,
    get_recommendations_for_issues,
    generate_optimization_checklist
)


class OptimizationAnalyzer:
    """Generate AI-powered optimization recommendations."""

    def __init__(self):
        self.model = os.getenv("LLM_MODEL", "gpt-4o-mini")
        self.brand_builder = BrandContextBuilder()

    async def generate_recommendations(
        self,
        your_site: dict,
        competitors: list[dict],
        brand_documents: list[dict],
        focus_areas: list[str]
    ) -> dict:
        """
        Generate prioritized optimization recommendations based on:
        - Your website analysis
        - Competitor website analyses
        - Brand/positioning documents
        - Focus areas specified by user
        """

        # Build brand context from documents
        brand_context = self.brand_builder.build_context(brand_documents)

        # Prepare competitor comparison summary
        competitor_summary = self._summarize_competitors(competitors)

        # Identify gaps between you and competitors
        gaps = self._identify_gaps(your_site, competitors)

        # Generate recommendations using LLM
        recommendations = await self._generate_llm_recommendations(
            your_site=your_site,
            competitor_summary=competitor_summary,
            gaps=gaps,
            brand_context=brand_context,
            focus_areas=focus_areas
        )

        # Generate priority actions
        priority_actions = self._prioritize_actions(
            recommendations,
            your_site.get("issues", []),
            gaps
        )

        return {
            "recommendations": recommendations,
            "priority_actions": priority_actions,
            "competitive_gaps": gaps
        }

    def _summarize_competitors(self, competitors: list[dict]) -> dict:
        """Create a summary of competitor strengths and patterns."""
        summary = {
            "total_analyzed": len(competitors),
            "successful_scans": 0,
            "common_strengths": [],
            "seo_patterns": {},
            "content_patterns": {},
            "technical_patterns": {}
        }

        seo_features = {
            "has_og_tags": 0,
            "has_twitter_cards": 0,
            "has_structured_data": 0,
            "has_sitemap": 0,
            "avg_word_count": 0
        }

        for comp in competitors:
            if comp.get("status") == "success":
                summary["successful_scans"] += 1

                seo = comp.get("seo_factors", {})
                tech = comp.get("technical_factors", {})
                content = comp.get("content_analysis", {})

                if seo.get("og_tags"):
                    seo_features["has_og_tags"] += 1
                if seo.get("twitter_cards"):
                    seo_features["has_twitter_cards"] += 1
                if content.get("has_structured_data"):
                    seo_features["has_structured_data"] += 1
                if tech.get("has_sitemap"):
                    seo_features["has_sitemap"] += 1
                seo_features["avg_word_count"] += seo.get("word_count", 0)

                # Track strengths
                for strength in comp.get("strengths", []):
                    summary["common_strengths"].append(strength.get("strength", ""))

        if summary["successful_scans"] > 0:
            seo_features["avg_word_count"] //= summary["successful_scans"]

        summary["seo_patterns"] = seo_features
        return summary

    def _identify_gaps(self, your_site: dict, competitors: list[dict]) -> list[dict]:
        """Identify gaps where competitors are doing better."""
        gaps = []

        your_seo = your_site.get("seo_factors", {})
        your_tech = your_site.get("technical_factors", {})
        your_content = your_site.get("content_analysis", {})
        your_geo = your_site.get("geo_factors", {})

        for comp in competitors:
            if comp.get("status") != "success":
                continue

            comp_seo = comp.get("seo_factors", {})
            comp_tech = comp.get("technical_factors", {})
            comp_content = comp.get("content_analysis", {})
            comp_geo = comp.get("geo_factors", {})

            # Word count comparison
            if comp_seo.get("word_count", 0) > your_seo.get("word_count", 0) * 1.5:
                gaps.append({
                    "type": "content_depth",
                    "competitor": comp.get("domain", comp.get("url")),
                    "detail": f"Competitor has {comp_seo.get('word_count')} words vs your {your_seo.get('word_count')}",
                    "impact": "high"
                })

            # Structured data
            if comp_content.get("has_structured_data") and not your_content.get("has_structured_data"):
                gaps.append({
                    "type": "structured_data",
                    "competitor": comp.get("domain", comp.get("url")),
                    "detail": f"Competitor uses {', '.join(comp_content.get('structured_data_types', []))} structured data",
                    "impact": "medium"
                })

            # GEO factors
            if comp_geo.get("statistics_present") and not your_geo.get("statistics_present"):
                gaps.append({
                    "type": "geo_statistics",
                    "competitor": comp.get("domain", comp.get("url")),
                    "detail": "Competitor includes statistics and data points for AI citation",
                    "impact": "medium"
                })

            if comp_geo.get("comparison_tables") and not your_geo.get("comparison_tables"):
                gaps.append({
                    "type": "comparison_content",
                    "competitor": comp.get("domain", comp.get("url")),
                    "detail": "Competitor has comparison tables for easy AI extraction",
                    "impact": "medium"
                })

        # Deduplicate by type
        seen_types = set()
        unique_gaps = []
        for gap in gaps:
            if gap["type"] not in seen_types:
                seen_types.add(gap["type"])
                unique_gaps.append(gap)

        return unique_gaps

    async def _generate_llm_recommendations(
        self,
        your_site: dict,
        competitor_summary: dict,
        gaps: list[dict],
        brand_context: dict,
        focus_areas: list[str]
    ) -> list[dict]:
        """Use LLM to generate specific, actionable recommendations."""

        # Build the analysis prompt
        prompt = self._build_analysis_prompt(
            your_site, competitor_summary, gaps, brand_context, focus_areas
        )

        try:
            response = await litellm.acompletion(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": """You are an expert in SEO, GEO (Generative Engine Optimization),
                        and LLM discoverability. You help companies optimize their websites and content
                        to rank better in traditional search, AI search results, and LLM responses.

                        Provide specific, actionable recommendations with clear implementation steps.
                        Focus on high-impact changes that align with the brand's positioning."""
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                response_format={"type": "json_object"},
                temperature=0.7,
                max_tokens=4000
            )

            result = json.loads(response.choices[0].message.content)
            return result.get("recommendations", [])

        except Exception as e:
            # Fallback to rule-based recommendations if LLM fails
            return self._generate_fallback_recommendations(your_site, gaps, focus_areas)

    def _build_analysis_prompt(
        self,
        your_site: dict,
        competitor_summary: dict,
        gaps: list[dict],
        brand_context: dict,
        focus_areas: list[str]
    ) -> str:
        """Build the analysis prompt for the LLM."""

        prompt = f"""Analyze this website and provide optimization recommendations.

## Your Website Analysis
URL: {your_site.get('url')}
Domain: {your_site.get('domain')}

### SEO Factors
- Title: {your_site.get('seo_factors', {}).get('title', 'Not found')}
- Title Length: {your_site.get('seo_factors', {}).get('title_length', 0)} chars
- Meta Description: {your_site.get('seo_factors', {}).get('meta_description', 'Not found')[:100]}...
- H1 Tags: {your_site.get('seo_factors', {}).get('h1_tags', [])}
- Word Count: {your_site.get('seo_factors', {}).get('word_count', 0)}
- Images without alt: {your_site.get('seo_factors', {}).get('images_without_alt', 0)}

### Technical Factors
- HTTPS: {your_site.get('technical_factors', {}).get('https', False)}
- Has Sitemap: {your_site.get('technical_factors', {}).get('has_sitemap', False)}
- Has Robots.txt: {your_site.get('technical_factors', {}).get('has_robots_txt', False)}

### LLM Discoverability
- Structured Content: {your_site.get('llm_discoverability', {}).get('structured_content', False)}
- FAQ Schema: {your_site.get('llm_discoverability', {}).get('faq_schema', False)}
- Citations/Sources: {your_site.get('llm_discoverability', {}).get('citations_and_sources', 0)}

### GEO Factors
- Statistics Present: {your_site.get('geo_factors', {}).get('statistics_present', False)}
- Lists/Bullets: {your_site.get('geo_factors', {}).get('lists_and_bullets', 0)}
- Comparison Tables: {your_site.get('geo_factors', {}).get('comparison_tables', False)}
- Citation Ready: {your_site.get('geo_factors', {}).get('citation_ready', False)}

### Current Issues
{json.dumps(your_site.get('issues', []), indent=2)}

### Current Strengths
{json.dumps(your_site.get('strengths', []), indent=2)}

## Competitor Summary
- Competitors Analyzed: {competitor_summary.get('successful_scans', 0)}
- Competitors with Structured Data: {competitor_summary.get('seo_patterns', {}).get('has_structured_data', 0)}
- Average Word Count: {competitor_summary.get('seo_patterns', {}).get('avg_word_count', 0)}

## Competitive Gaps Identified
{json.dumps(gaps, indent=2)}

## Brand Context
{brand_context.get('all_brand_elements', {})}

## Focus Areas
{focus_areas if focus_areas else 'General optimization'}

---

Based on this analysis, provide 8-12 specific, prioritized recommendations in this JSON format:
{{
  "recommendations": [
    {{
      "id": 1,
      "category": "SEO|GEO|LLM|Technical|Content|Brand",
      "title": "Brief title of recommendation",
      "description": "Detailed description of what to do and why",
      "impact": "high|medium|low",
      "effort": "low|medium|high",
      "specific_actions": ["Action 1", "Action 2"],
      "expected_outcome": "What improvement to expect"
    }}
  ]
}}

Prioritize recommendations that:
1. Address high-severity issues first
2. Close competitive gaps
3. Improve LLM/AI search discoverability
4. Align with the brand positioning
5. Have high impact with reasonable effort"""

        return prompt

    def _generate_fallback_recommendations(
        self,
        your_site: dict,
        gaps: list[dict],
        focus_areas: list[str]
    ) -> list[dict]:
        """Generate comprehensive rule-based recommendations using best practices."""
        recommendations = []
        rec_id = 1

        issues = your_site.get("issues", [])
        seo = your_site.get("seo_factors", {})
        tech = your_site.get("technical_factors", {})
        llm = your_site.get("llm_discoverability", {})
        geo = your_site.get("geo_factors", {})

        # Get recommendations based on detected issues
        issue_recs = get_recommendations_for_issues(issues)
        for practice in issue_recs[:5]:
            recommendations.append({
                "id": rec_id,
                "category": practice["category"],
                "title": practice["title"],
                "description": practice["description"],
                "impact": practice["impact"],
                "effort": practice["effort"],
                "specific_actions": practice["actions"],
                "expected_outcome": f"Improved {practice['category'].lower()} performance"
            })
            rec_id += 1

        # Address high severity issues not covered by best practices
        for issue in issues:
            if issue.get("severity") == "high" and rec_id <= 12:
                recommendations.append({
                    "id": rec_id,
                    "category": issue.get("category", "SEO"),
                    "title": f"Fix: {issue.get('issue')}",
                    "description": f"Address this critical issue: {issue.get('issue')}",
                    "impact": "high",
                    "effort": "low",
                    "specific_actions": [f"Resolve: {issue.get('issue')}"],
                    "expected_outcome": "Improved search visibility and user experience"
                })
                rec_id += 1

        # Add GEO-specific recommendations
        if not geo.get("citation_ready") and rec_id <= 12:
            geo_practice = GEO_BEST_PRACTICES.get("citation_optimization", {})
            recommendations.append({
                "id": rec_id,
                "category": "GEO",
                "title": geo_practice.get("title", "Optimize for AI citations"),
                "description": geo_practice.get("description", "Structure content for AI citation"),
                "impact": "high",
                "effort": "medium",
                "specific_actions": geo_practice.get("actions", [
                    "Add relevant statistics and data points",
                    "Include expert quotes with attribution",
                    "Use bulleted lists for key points"
                ]),
                "expected_outcome": "Higher likelihood of being cited in AI search results"
            })
            rec_id += 1

        if not geo.get("statistics_present") and rec_id <= 12:
            geo_practice = GEO_BEST_PRACTICES.get("statistics_data", {})
            recommendations.append({
                "id": rec_id,
                "category": "GEO",
                "title": geo_practice.get("title", "Include Statistics and Data"),
                "description": geo_practice.get("description", "Add quantifiable data points"),
                "impact": "high",
                "effort": "medium",
                "specific_actions": geo_practice.get("actions", [
                    "Include relevant statistics with sources",
                    "Use specific numbers rather than vague terms",
                    "Update statistics regularly"
                ]),
                "expected_outcome": "Enhanced credibility and AI citation potential"
            })
            rec_id += 1

        # Add LLM-specific recommendations
        if not llm.get("faq_schema") and rec_id <= 12:
            llm_practice = LLM_BEST_PRACTICES.get("faq_schema", {})
            recommendations.append({
                "id": rec_id,
                "category": "LLM",
                "title": llm_practice.get("title", "Implement FAQ Schema"),
                "description": llm_practice.get("description", "Add FAQ structured data"),
                "impact": "high",
                "effort": "low",
                "specific_actions": llm_practice.get("actions", [
                    "Create dedicated FAQ section",
                    "Implement FAQPage schema markup",
                    "Write questions as users would ask them"
                ]),
                "expected_outcome": "Enhanced visibility in AI search and voice assistants"
            })
            rec_id += 1

        if not llm.get("structured_content") and rec_id <= 12:
            llm_practice = LLM_BEST_PRACTICES.get("structured_content", {})
            recommendations.append({
                "id": rec_id,
                "category": "LLM",
                "title": llm_practice.get("title", "Structure Content for LLM Parsing"),
                "description": llm_practice.get("description", "Organize content for AI understanding"),
                "impact": "high",
                "effort": "low",
                "specific_actions": llm_practice.get("actions", [
                    "Use clear heading hierarchy",
                    "Start sections with summary statements",
                    "Use bullet points for features/benefits"
                ]),
                "expected_outcome": "Better content extraction by AI systems"
            })
            rec_id += 1

        # Add AEO recommendations
        if rec_id <= 12:
            aeo_practice = AEO_BEST_PRACTICES.get("featured_snippets", {})
            recommendations.append({
                "id": rec_id,
                "category": "AEO",
                "title": aeo_practice.get("title", "Optimize for Featured Snippets"),
                "description": aeo_practice.get("description", "Win position zero in search results"),
                "impact": "high",
                "effort": "medium",
                "specific_actions": aeo_practice.get("actions", [
                    "Answer questions directly in 40-50 words",
                    "Create numbered/bulleted lists",
                    "Include comparison tables"
                ]),
                "expected_outcome": "Increased visibility in search features"
            })
            rec_id += 1

        # Address competitive gaps
        for gap in gaps[:3]:
            if rec_id <= 12:
                recommendations.append({
                    "id": rec_id,
                    "category": "Competitive",
                    "title": f"Close gap: {gap.get('type', '').replace('_', ' ').title()}",
                    "description": gap.get("detail", ""),
                    "impact": gap.get("impact", "medium"),
                    "effort": "medium",
                    "specific_actions": [f"Implement {gap.get('type', '')} improvements"],
                    "expected_outcome": "Match or exceed competitor capabilities"
                })
                rec_id += 1

        return recommendations

    def _prioritize_actions(
        self,
        recommendations: list[dict],
        issues: list[dict],
        gaps: list[dict]
    ) -> list[dict]:
        """Create a prioritized action list from recommendations."""
        priority_actions = []

        # Score and sort recommendations
        scored = []
        for rec in recommendations:
            score = 0
            # Impact scoring
            if rec.get("impact") == "high":
                score += 30
            elif rec.get("impact") == "medium":
                score += 20
            else:
                score += 10

            # Effort scoring (lower effort = higher priority)
            if rec.get("effort") == "low":
                score += 20
            elif rec.get("effort") == "medium":
                score += 10
            else:
                score += 5

            # Category bonuses
            if rec.get("category") in ["GEO", "LLM"]:
                score += 10  # Prioritize AI-related optimizations

            scored.append((score, rec))

        # Sort by score descending
        scored.sort(key=lambda x: x[0], reverse=True)

        # Take top 5 as priority actions
        for i, (score, rec) in enumerate(scored[:5]):
            priority_actions.append({
                "priority": i + 1,
                "title": rec.get("title"),
                "category": rec.get("category"),
                "impact": rec.get("impact"),
                "effort": rec.get("effort"),
                "first_step": rec.get("specific_actions", [""])[0] if rec.get("specific_actions") else ""
            })

        return priority_actions

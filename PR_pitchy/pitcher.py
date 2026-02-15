"""
PR Pitcher Module
Uses LLM to analyze news content, assess newsworthiness,
identify best-fit publications and angles, and draft pitch emails.
"""

import os
import json
import litellm


class PRPitcher:
    """AI-powered PR pitch generator."""

    def __init__(self):
        self.model = os.getenv("LLM_MODEL", "gpt-4o")

    async def analyze_and_pitch(
        self,
        brand_context: str,
        news_content: str,
        publication_summaries: list[dict],
        recent_headlines: list[dict],
    ) -> dict:
        """
        Full pipeline:
        1. Analyze the news — what is it, who cares, why now
        2. Score each publication for fit
        3. For top fits: define angle, companion content, draft pitch
        """

        # Step 1: Analyze the news itself
        news_analysis = await self._analyze_news(brand_context, news_content)

        # Step 2: Match and score publications
        targets = await self._match_publications(
            brand_context, news_analysis, publication_summaries, recent_headlines
        )

        # Step 3: Draft pitches for top targets
        targets_with_pitches = await self._draft_pitches(
            brand_context, news_analysis, targets[:6]
        )

        return {
            "news_analysis": news_analysis,
            "targets": targets_with_pitches,
        }

    async def _analyze_news(self, brand_context: str, news_content: str) -> dict:
        """Analyze the submitted news — classify it, assess newsworthiness, identify angles."""

        prompt = f"""You are a senior PR strategist with deep experience in B2B tech and cybersecurity media relations.

Analyze the following news/announcement and brand context. Return a structured assessment.

## Brand Context
{brand_context[:6000]}

## News / Announcement Content
{news_content[:4000]}

---

Return JSON with this exact structure:
{{
  "headline": "A crisp 1-sentence summary of the news (as a journalist would write it)",
  "news_type": "One of: Product Launch | Partnership | Research/Data | Funding | Executive Hire | Thought Leadership | Industry Commentary | Customer Win",
  "newsworthiness_score": <1-10 integer>,
  "newsworthiness_reasoning": "2-3 sentences explaining why this is or isn't newsworthy to journalists",
  "why_now": "What current trend, event, or market moment makes this timely? If nothing, say so honestly.",
  "who_cares": ["Audience segment 1", "Audience segment 2", "Audience segment 3"],
  "core_story": "The single most compelling story here in 1-2 sentences — the version a journalist would want to tell",
  "data_assets": ["Any stats, numbers, or research findings in the content worth highlighting", "..."],
  "angles": [
    {{
      "angle_name": "Short name for this angle",
      "framing": "How to frame this story for this angle — 2 sentences",
      "best_for": "Which type of publication or journalist beat this angle suits"
    }}
  ],
  "weaknesses": ["What's missing that would make this more pitchable", "..."],
  "companion_content_needed": {{
    "press_release": true/false,
    "data_exclusive": true/false,
    "byline_opportunity": true/false,
    "embargoed_briefing": true/false,
    "reasoning": "Why these companion content types would help"
  }}
}}

Be honest about newsworthiness. A score of 4 or below means this needs more work before pitching.
Angles should be genuinely distinct — different framings that would appeal to different journalist beats.
"""

        try:
            response = await litellm.acompletion(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.5,
                max_tokens=2000
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            return {
                "headline": "Analysis failed",
                "news_type": "Unknown",
                "newsworthiness_score": 0,
                "newsworthiness_reasoning": f"Error: {str(e)}",
                "why_now": "",
                "who_cares": [],
                "core_story": "",
                "data_assets": [],
                "angles": [],
                "weaknesses": ["LLM analysis failed — check API key and try again"],
                "companion_content_needed": {}
            }

    async def _match_publications(
        self,
        brand_context: str,
        news_analysis: dict,
        publication_summaries: list[dict],
        recent_headlines: list[dict],
    ) -> list[dict]:
        """Score each publication for fit and return ranked targets."""

        # Build a summary of recent headlines per publication
        headlines_by_pub = {}
        for article in recent_headlines:
            pub = article["publication"]
            if pub not in headlines_by_pub:
                headlines_by_pub[pub] = []
            headlines_by_pub[pub].append(article["title"])

        pub_context = []
        for pub in publication_summaries:
            headlines = headlines_by_pub.get(pub["name"], [])
            pub_context.append(
                f"- {pub['name']} (Tier {pub['tier']}): Beat: {pub['beat']}. "
                f"Audience: {pub['audience']}. "
                f"Recent headlines: {'; '.join(headlines[:4]) if headlines else 'Not available'}"
            )

        prompt = f"""You are a PR strategist matching a story to the right publications and journalists.

## The Story
Type: {news_analysis.get('news_type')}
Core story: {news_analysis.get('core_story')}
Why now: {news_analysis.get('why_now')}
Who cares: {', '.join(news_analysis.get('who_cares', []))}
Newsworthiness: {news_analysis.get('newsworthiness_score')}/10

## Available Publications (with recent coverage examples)
{chr(10).join(pub_context)}

---

Score each publication for fit with this specific story. Return JSON:
{{
  "targets": [
    {{
      "publication": "Publication name exactly as listed",
      "fit_score": <1-10>,
      "fit_reasoning": "1-2 sentences: why this publication is or isn't a fit based on their beat AND recent coverage",
      "best_angle": "Which angle from the story analysis fits this outlet best, and why",
      "suggested_journalist_type": "Describe the type of journalist/beat writer to target at this outlet (e.g. 'security reporter covering enterprise tools', 'startup reporter focused on funding and product launches')",
      "pitch_hook": "A single sentence — the opening hook for a pitch to this outlet specifically"
    }}
  ]
}}

Include ALL publications in the response, sorted by fit_score descending.
Be realistic — most publications won't be a great fit for any given story.
A fit_score of 7+ means this is a real target worth pitching.
"""

        try:
            response = await litellm.acompletion(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.4,
                max_tokens=3000
            )
            result = json.loads(response.choices[0].message.content)
            targets = result.get("targets", [])
            # Sort by fit score, add publication metadata
            pub_meta = {p["name"]: p for p in publication_summaries}
            for t in targets:
                meta = pub_meta.get(t["publication"], {})
                t["tier"] = meta.get("tier", 2)
                t["domain"] = meta.get("domain", "")
                t["beat"] = meta.get("beat", "")
                t["audience"] = meta.get("audience", "")
                t["recent_headlines"] = headlines_by_pub.get(t["publication"], [])
            targets.sort(key=lambda x: x.get("fit_score", 0), reverse=True)
            return targets
        except Exception as e:
            return []

    async def _draft_pitches(
        self,
        brand_context: str,
        news_analysis: dict,
        targets: list[dict],
    ) -> list[dict]:
        """Draft a personalized pitch email for each top target."""

        enriched = []
        for target in targets:
            pitch = await self._draft_single_pitch(brand_context, news_analysis, target)
            target["pitch"] = pitch
            enriched.append(target)

        return enriched

    async def _draft_single_pitch(
        self,
        brand_context: str,
        news_analysis: dict,
        target: dict,
    ) -> dict:
        """Draft one pitch email for one target publication."""

        recent = "\n".join(f"  - {h}" for h in target.get("recent_headlines", [])[:4])
        companion = news_analysis.get("companion_content_needed", {})

        prompt = f"""You are a PR professional writing a cold pitch email to a journalist.

## About the journalist's outlet
Publication: {target['publication']}
Beat: {target['beat']}
Audience: {target['audience']}
Target journalist type: {target.get('suggested_journalist_type', '')}
Recent headlines from this outlet:
{recent if recent else '  (No recent headlines available)'}

## The story
{news_analysis.get('core_story', '')}
Type: {news_analysis.get('news_type', '')}
Why now: {news_analysis.get('why_now', '')}
Best angle for this outlet: {target.get('best_angle', '')}
Opening hook: {target.get('pitch_hook', '')}

## Brand context (use exact brand name, do not invent claims)
{brand_context[:3000]}

## Companion content available
- Press release: {companion.get('press_release', False)}
- Data exclusive: {companion.get('data_exclusive', False)}
- Byline opportunity: {companion.get('byline_opportunity', False)}
- Embargoed briefing: {companion.get('embargoed_briefing', False)}

---

Write a cold pitch email. Rules:
1. UNDER 150 WORDS total for the body — journalists delete long pitches
2. Subject line: specific, no fluff, ideally references something they recently covered
3. First sentence: reference their recent coverage or beat — show you read their work
4. Second paragraph: the news, the angle for THEIR audience, the "why now"
5. Third paragraph (1-2 sentences): what you're offering (interview, data, byline, exclusive)
6. Sign off simply — no "I look forward to hearing from you" clichés
7. DO NOT use the brand's exact document language verbatim — write naturally
8. DO NOT invent statistics or capabilities not in the brand context

Return JSON:
{{
  "subject_line": "The email subject line",
  "body": "The full email body (plain text, use \\n for line breaks)",
  "word_count": <integer>,
  "personalization_notes": "What specific thing about this outlet/journalist made you write it this way",
  "companion_content_recommended": "What companion content to attach or offer in this specific pitch"
}}
"""

        try:
            response = await litellm.acompletion(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.7,
                max_tokens=1000
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            return {
                "subject_line": "Error generating pitch",
                "body": f"Pitch generation failed: {str(e)}",
                "word_count": 0,
                "personalization_notes": "",
                "companion_content_recommended": ""
            }

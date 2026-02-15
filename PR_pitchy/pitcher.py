"""
PR Pitcher Module
Uses LLM to analyze news content, assess newsworthiness,
identify best-fit publications and angles, draft a structured
multi-wave PR campaign with contingency guidance.
"""

import asyncio
import os
import json
import litellm


class PRPitcher:
    """AI-powered PR pitch generator with campaign wave structure."""

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
        1. Analyze the news — what is it, who cares, why now, exclusive viability
        2. Score each publication for fit + wave suitability + known authors
        3. Plan campaign waves — assign outlets to Wave 1/2/3 with contingencies
        4. Draft personalized pitches per wave, parallelized
        """

        # Step 1: Analyze the news
        news_analysis = await self._analyze_news(brand_context, news_content)

        # Step 2: Match and score publications
        targets = await self._match_publications(
            brand_context, news_analysis, publication_summaries, recent_headlines
        )

        # Step 3: Plan campaign wave structure
        campaign_plan = await self._plan_campaign(news_analysis, targets)

        # Build lookup dict for fast target retrieval by pub name
        targets_lookup = {t["publication"]: t for t in targets}

        # Step 4: Draft pitches per wave (Wave 2 + 3 in parallel)
        waves = await self._draft_pitches_by_wave(
            brand_context, news_analysis, campaign_plan, targets_lookup
        )

        return {
            "news_analysis": news_analysis,
            "campaign_plan": campaign_plan,
            "waves": waves,
            "all_targets": targets,
        }

    # ─────────────────────────────────────────────
    # STEP 1: Analyze the news
    # ─────────────────────────────────────────────

    async def _analyze_news(self, brand_context: str, news_content: str) -> dict:
        """Analyze submitted news/announcement — classify, assess, identify angles and exclusive viability."""

        prompt = f"""You are a senior PR strategist with deep experience in B2B tech and cybersecurity media relations.

Analyze the following news/announcement and brand context. Read the ENTIRE content carefully — recommendations, data findings, and conclusions at the end are just as important as the opening.

## Brand Context
{brand_context}

## News / Announcement Content
{news_content}

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
  "data_assets": ["Any specific stats, numbers, percentages, or research findings worth highlighting in pitches — quote them exactly", "..."],
  "angles": [
    {{
      "angle_name": "Short name for this angle",
      "framing": "How to frame this story for this angle — 2 sentences",
      "best_for": "Which type of publication or journalist beat this angle suits"
    }}
  ],
  "weaknesses": ["What's missing that would make this more pitchable", "..."],
  "exclusive_viability": {{
    "can_offer_exclusive": true,
    "what_to_offer": "Specific thing you can offer one outlet that others won't get — e.g. 'full raw dataset before public release', 'CEO interview 48 hours before launch', 'embargoed draft report with analyst commentary'. Be specific. null if nothing credible to offer.",
    "embargo_window_suggested": "e.g. '48 hours before launch' or '72 hours' or null if no embargo recommended"
  }},
  "campaign_timing_notes": "Any notes about timing that should influence wave structure — e.g. 'tied to an industry event', 'data is evergreen', 'announcement is time-sensitive due to upcoming regulation enforcement date'",
  "companion_content_needed": {{
    "press_release": true,
    "data_exclusive": true,
    "byline_opportunity": true,
    "embargoed_briefing": true,
    "reasoning": "Why these companion content types would help"
  }}
}}

Be honest about newsworthiness. A score of 4 or below means this needs more work before pitching.
Angles should be genuinely distinct — different framings that would appeal to different journalist beats.
data_assets should include the actual numbers/stats verbatim so they can be dropped directly into pitches.
"""

        try:
            response = await litellm.acompletion(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.5,
                max_tokens=3000
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
                "exclusive_viability": {"can_offer_exclusive": False, "what_to_offer": None, "embargo_window_suggested": None},
                "campaign_timing_notes": "",
                "companion_content_needed": {}
            }

    # ─────────────────────────────────────────────
    # STEP 2: Match publications
    # ─────────────────────────────────────────────

    async def _match_publications(
        self,
        brand_context: str,
        news_analysis: dict,
        publication_summaries: list[dict],
        recent_headlines: list[dict],
    ) -> list[dict]:
        """Score each publication for fit, wave suitability, and surface known authors."""

        # Build headlines and authors per publication
        headlines_by_pub = {}
        authors_by_pub = {}
        for article in recent_headlines:
            pub = article["publication"]
            if pub not in headlines_by_pub:
                headlines_by_pub[pub] = []
                authors_by_pub[pub] = []
            headlines_by_pub[pub].append(article["title"])
            if article.get("author"):
                authors_by_pub[pub].append(article["author"])

        pub_context = []
        for pub in publication_summaries:
            headlines = headlines_by_pub.get(pub["name"], [])
            authors = list(set(authors_by_pub.get(pub["name"], [])))
            pub_context.append(
                f"- {pub['name']} (Tier {pub['tier']}): Beat: {pub['beat']}. "
                f"Audience: {pub['audience']}. "
                f"Recent headlines: {'; '.join(headlines[:4]) if headlines else 'Not available'}. "
                f"Known authors/contributors: {', '.join(authors[:4]) if authors else 'Not available'}"
            )

        prompt = f"""You are a PR strategist matching a story to the right publications and journalists.

## The Story
Type: {news_analysis.get('news_type')}
Core story: {news_analysis.get('core_story')}
Why now: {news_analysis.get('why_now')}
Who cares: {', '.join(news_analysis.get('who_cares', []))}
Newsworthiness: {news_analysis.get('newsworthiness_score')}/10
Key data points: {', '.join(news_analysis.get('data_assets', [])) or 'None identified'}

## Available Publications (with recent coverage and known authors)
{chr(10).join(pub_context)}

---

Score each publication for fit with this specific story. Consider their recent coverage patterns and known authors.

Return JSON:
{{
  "targets": [
    {{
      "publication": "Publication name exactly as listed",
      "fit_score": <1-10>,
      "fit_reasoning": "1-2 sentences: why this pub is or isn't a fit based on their beat AND recent coverage patterns",
      "best_angle": "Which angle from the story analysis fits this outlet best, and why in 1 sentence",
      "known_authors": ["Author name (what they appear to cover based on headlines)", "..."],
      "suggested_journalist_type": "Describe the specific beat writer to target — e.g. 'enterprise security reporter covering IAM tools', 'startup reporter focused on funded B2B security companies'",
      "pitch_hook": "A single sentence — the opening hook for a pitch to this outlet, written as if you're referencing something they recently covered",
      "wave_suitability": {{
        "good_for_exclusive": true,
        "good_for_launch_day": true,
        "good_for_followon": false,
        "suitability_reasoning": "1 sentence explaining the wave fit"
      }}
    }}
  ]
}}

Include ALL publications in the response, sorted by fit_score descending.
Be realistic — most publications won't be a great fit for any given story.
A fit_score of 7+ means this is a real target worth pitching.
If known_authors are available, list them — don't leave the array empty if the data is there.
"""

        try:
            response = await litellm.acompletion(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.4,
                max_tokens=4000
            )
            result = json.loads(response.choices[0].message.content)
            targets = result.get("targets", [])
            # Attach publication metadata
            pub_meta = {p["name"]: p for p in publication_summaries}
            for t in targets:
                meta = pub_meta.get(t["publication"], {})
                t["tier"] = meta.get("tier", 2)
                t["domain"] = meta.get("domain", "")
                t["beat"] = meta.get("beat", "")
                t["audience"] = meta.get("audience", "")
                t["recent_headlines"] = headlines_by_pub.get(t["publication"], [])
                # Merge known authors from RSS fetch + LLM inference
                rss_authors = list(set(authors_by_pub.get(t["publication"], [])))
                llm_authors = t.get("known_authors", [])
                t["known_authors"] = rss_authors if rss_authors else llm_authors
            targets.sort(key=lambda x: x.get("fit_score", 0), reverse=True)
            return targets
        except Exception as e:
            return []

    # ─────────────────────────────────────────────
    # STEP 3: Plan campaign waves
    # ─────────────────────────────────────────────

    async def _plan_campaign(self, news_analysis: dict, targets: list[dict]) -> dict:
        """Assign publications to campaign waves with timing and contingency logic."""

        exclusive_viability = news_analysis.get("exclusive_viability", {})
        qualifying_targets = [t for t in targets if t.get("fit_score", 0) >= 5]

        targets_summary = json.dumps([{
            "publication": t["publication"],
            "tier": t["tier"],
            "fit_score": t["fit_score"],
            "beat": t["beat"],
            "wave_suitability": t.get("wave_suitability", {}),
            "pitch_hook": t.get("pitch_hook", ""),
            "known_authors": t.get("known_authors", [])
        } for t in qualifying_targets], indent=2)

        companion = news_analysis.get("companion_content_needed", {})

        prompt = f"""You are a senior PR strategist planning the launch campaign sequence for a news announcement.

## Story Summary
Type: {news_analysis.get('news_type')}
Newsworthiness: {news_analysis.get('newsworthiness_score')}/10
Core story: {news_analysis.get('core_story')}
Why now: {news_analysis.get('why_now')}
Key data: {', '.join(news_analysis.get('data_assets', [])) or 'None identified'}
Timing notes: {news_analysis.get('campaign_timing_notes', 'None')}

## Exclusive Viability
Can offer exclusive: {exclusive_viability.get('can_offer_exclusive', False)}
What to offer: {exclusive_viability.get('what_to_offer', 'N/A')}
Suggested embargo window: {exclusive_viability.get('embargo_window_suggested', 'N/A')}

## Companion Content Available
Press release: {companion.get('press_release', False)}
Data exclusive: {companion.get('data_exclusive', False)}
Byline opportunity: {companion.get('byline_opportunity', False)}
Embargoed briefing: {companion.get('embargoed_briefing', False)}

## Qualifying Publication Targets (fit score 5+)
{targets_summary}

---

Plan the PR campaign wave structure. Assign each qualifying publication to the appropriate wave.

RULES:
1. Wave 1 (Exclusive/Embargo): EXACTLY ONE outlet. ONLY assign if can_offer_exclusive is true AND that outlet has fit_score >= 8 AND good_for_exclusive is true. If no outlet meets all criteria, set wave_1.publication to null.
2. Wave 2 (Launch Day): 3-5 outlets. Pitched simultaneously when wire release goes live. Each outlet gets a DIFFERENT angle — not the same email.
3. Wave 3 (Follow-on): Remaining outlets with fit_score >= 5. Pitched 1-2 weeks post-launch. Primarily bylines, deep-dives, niche verticals, podcasts. Use Wave 2 coverage as social proof.
4. Do NOT put the same outlet in multiple waves.
5. If the Wave 1 exclusive outlet is moved to Wave 2 (rejected/no response), Wave 2 should have a note about this.
6. If newsworthiness_score <= 4: only populate Wave 2 with the best 3 fits, leave Wave 3 empty, and note the story needs strengthening.

Return JSON:
{{
  "campaign_summary": "2-3 sentence plain English description of the overall campaign strategy — what the arc is, why this wave structure makes sense for this story",
  "wave_1": {{
    "publication": "Exact publication name or null",
    "timing_label": "e.g. '48 hours before launch' or '72 hours before launch' or null",
    "rationale": "Why this outlet for the exclusive — what makes them the right first call",
    "exclusive_offer": "The exact specific offer to make: what they get, when they get it, what no one else gets. Be concrete.",
    "contingency": {{
      "if_rejected": "Specific action: which outlet to move to Wave 2, whether to offer a second exclusive and to whom, exact next step",
      "if_no_response_48h": "Specific action: follow-up once, then move where? Be prescriptive.",
      "second_choice_exclusive": "Publication name or null — if rejected, offer exclusive to this outlet instead before going to Wave 2 full batch"
    }}
  }},
  "wave_2": {{
    "timing_label": "Launch Day",
    "publications": [
      {{
        "publication": "Publication name",
        "angle_note": "1-2 sentences: the specific angle for THIS outlet — how it differs from others in this wave"
      }}
    ],
    "wave_2_note": "Important coordination note — e.g. 'pitch all simultaneously, do not stagger' or 'if Wave 1 exclusive was accepted, wait for embargo lift before sending'"
  }},
  "wave_3": {{
    "timing_label": "1-2 weeks post-launch",
    "publications": [
      {{
        "publication": "Publication name",
        "angle_note": "What angle your readers haven't seen yet — the follow-on hook",
        "format_suggestion": "e.g. 'contributed byline', 'podcast pitch', 'data-led feature request', 'analyst briefing'"
      }}
    ],
    "wave_3_strategy": "How to use Wave 2 coverage as social proof — exactly what to reference and how to frame it"
  }},
  "contingency_if_wave2_thin": "If Wave 2 generates fewer than 2 placements, specific guidance on how to adapt Wave 3 — what to emphasize, how to reframe, which outlets to prioritize"
}}
"""

        try:
            response = await litellm.acompletion(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.4,
                max_tokens=2500
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            return {
                "campaign_summary": f"Campaign planning failed: {str(e)}",
                "wave_1": {"publication": None},
                "wave_2": {"timing_label": "Launch Day", "publications": [], "wave_2_note": ""},
                "wave_3": {"timing_label": "1-2 weeks post-launch", "publications": [], "wave_3_strategy": ""},
                "contingency_if_wave2_thin": ""
            }

    # ─────────────────────────────────────────────
    # STEP 4: Draft pitches by wave
    # ─────────────────────────────────────────────

    async def _draft_pitches_by_wave(
        self,
        brand_context: str,
        news_analysis: dict,
        campaign_plan: dict,
        targets_lookup: dict,
    ) -> dict:
        """Draft personalized pitch emails for each wave. Wave 2 + 3 drafted in parallel."""
        waves = {}

        # ── Wave 1 — single exclusive pitch ──
        wave1_plan = campaign_plan.get("wave_1", {})
        wave1_pub = wave1_plan.get("publication") if wave1_plan else None
        if wave1_pub and wave1_pub in targets_lookup:
            target = targets_lookup[wave1_pub]
            pitch = await self._draft_single_pitch(
                brand_context=brand_context,
                news_analysis=news_analysis,
                target=target,
                wave=1,
                wave_label="Exclusive / Embargo",
                wave_timing=wave1_plan.get("timing_label", "48 hours before launch"),
                is_exclusive=True,
                exclusive_offer=wave1_plan.get("exclusive_offer", ""),
                angle_note=wave1_plan.get("rationale", ""),
            )
            waves["wave_1"] = {
                **wave1_plan,
                "target_data": {**target, "pitch": pitch}
            }
        else:
            waves["wave_1"] = None

        # ── Wave 2 — parallel launch day pitches ──
        wave2_entries = campaign_plan.get("wave_2", {}).get("publications", [])
        wave2_coroutines = []
        wave2_meta = []
        for entry in wave2_entries:
            pub_name = entry["publication"]
            target = targets_lookup.get(pub_name, {"publication": pub_name, "beat": "", "audience": "", "recent_headlines": [], "known_authors": []})
            wave2_coroutines.append(
                self._draft_single_pitch(
                    brand_context=brand_context,
                    news_analysis=news_analysis,
                    target=target,
                    wave=2,
                    wave_label="Launch Day",
                    wave_timing="Launch Day",
                    is_exclusive=False,
                    angle_note=entry.get("angle_note", ""),
                )
            )
            wave2_meta.append((entry, target))

        wave2_pitches = await asyncio.gather(*wave2_coroutines, return_exceptions=True)
        waves["wave_2"] = []
        for (entry, target), pitch in zip(wave2_meta, wave2_pitches):
            if isinstance(pitch, Exception):
                pitch = {"subject_line": "Error", "body": str(pitch), "word_count": 0, "personalization_notes": "", "companion_content_recommended": ""}
            waves["wave_2"].append({
                "angle_note": entry.get("angle_note", ""),
                "target_data": {**target, "pitch": pitch}
            })

        # ── Wave 3 — parallel follow-on pitches ──
        wave3_entries = campaign_plan.get("wave_3", {}).get("publications", [])
        wave3_strategy = campaign_plan.get("wave_3", {}).get("wave_3_strategy", "")
        wave3_coroutines = []
        wave3_meta = []
        for entry in wave3_entries:
            pub_name = entry["publication"]
            target = targets_lookup.get(pub_name, {"publication": pub_name, "beat": "", "audience": "", "recent_headlines": [], "known_authors": []})
            wave3_coroutines.append(
                self._draft_single_pitch(
                    brand_context=brand_context,
                    news_analysis=news_analysis,
                    target=target,
                    wave=3,
                    wave_label="Follow-on",
                    wave_timing="1-2 weeks post-launch",
                    is_exclusive=False,
                    angle_note=entry.get("angle_note", ""),
                    format_suggestion=entry.get("format_suggestion", ""),
                    wave_3_strategy=wave3_strategy,
                )
            )
            wave3_meta.append((entry, target))

        wave3_pitches = await asyncio.gather(*wave3_coroutines, return_exceptions=True)
        waves["wave_3"] = []
        for (entry, target), pitch in zip(wave3_meta, wave3_pitches):
            if isinstance(pitch, Exception):
                pitch = {"subject_line": "Error", "body": str(pitch), "word_count": 0, "personalization_notes": "", "companion_content_recommended": ""}
            waves["wave_3"].append({
                "angle_note": entry.get("angle_note", ""),
                "format_suggestion": entry.get("format_suggestion", ""),
                "target_data": {**target, "pitch": pitch}
            })

        return waves

    async def _draft_single_pitch(
        self,
        brand_context: str,
        news_analysis: dict,
        target: dict,
        wave: int,
        wave_label: str,
        wave_timing: str,
        is_exclusive: bool,
        exclusive_offer: str = "",
        angle_note: str = "",
        format_suggestion: str = "",
        wave_3_strategy: str = "",
    ) -> dict:
        """Draft one highly personalized pitch email for one target publication."""

        recent_headlines = target.get("recent_headlines", [])[:5]
        known_authors = target.get("known_authors", [])
        data_assets = news_analysis.get("data_assets", [])
        companion = news_analysis.get("companion_content_needed", {})

        # Format recent headlines with context
        if recent_headlines:
            headlines_block = "\n".join(f"  - {h}" for h in recent_headlines)
        else:
            headlines_block = "  (No recent headlines available — write pitch based on known beat)"

        if known_authors:
            authors_block = ", ".join(known_authors[:4])
        else:
            authors_block = "Unknown — address to the security/tech beat writer"

        if data_assets:
            data_block = "\n".join(f"  - {d}" for d in data_assets)
        else:
            data_block = "  (No specific data points identified)"

        # Wave-specific instructions
        if wave == 1:
            wave_instructions = f"""WAVE 1 — EXCLUSIVE PITCH RULES:
- This is an exclusive offer. ONE outlet only gets this.
- You MUST include the specific exclusive offer in the pitch: {exclusive_offer}
- Mention the embargo window explicitly: {wave_timing}
- Keep the pitch body under 120 words — exclusives work because they are rare and concise
- The subject line should signal exclusivity without using the word "exclusive" clumsily — e.g. "Embargo: [story] — first look for [Publication]"
- Opening must reference something they specifically recently covered (use a headline above)"""
        elif wave == 2:
            wave_instructions = f"""WAVE 2 — LAUNCH DAY PITCH RULES:
- The press release is now live on the wire. You can reference this.
- Angle for this outlet specifically: {angle_note}
- This outlet's angle MUST differ from any exclusive pitch sent earlier
- Reference a specific recent headline from this outlet to show you read their work
- Keep under 150 words
- Offer: interview, data, or quote — make the ask specific"""
        else:
            wave_instructions = f"""WAVE 3 — FOLLOW-ON PITCH RULES:
- Timing: 1-2 weeks after launch. Wave 2 coverage may already be published.
- Use Wave 2 coverage as social proof: {wave_3_strategy}
- Angle for this outlet: {angle_note}
- Format suggested: {format_suggestion if format_suggestion else 'contributed byline or feature pitch'}
- Position this as "here's the angle your readers haven't seen yet"
- Reference the existing coverage briefly, then pivot to the fresh angle
- Keep under 150 words"""

        prompt = f"""You are a PR professional writing a cold pitch email to a journalist. This must be genuinely personalized — not a template with a name swapped in.

## Target Publication
Publication: {target.get('publication', 'Unknown')}
Beat: {target.get('beat', 'Unknown')}
Audience: {target.get('audience', 'Unknown')}
Known contributors/authors at this outlet: {authors_block}
Target journalist type: {target.get('suggested_journalist_type', 'Beat reporter covering this topic')}

## Their Recent Coverage (REFERENCE THESE — pick 1-2 to show you actually read them)
{headlines_block}

## The Story
{news_analysis.get('core_story', '')}
Type: {news_analysis.get('news_type', '')}
Why now: {news_analysis.get('why_now', '')}
Best angle for this outlet: {target.get('best_angle', angle_note)}
Opening hook idea: {target.get('pitch_hook', '')}

## Specific Data Points to Work In (use actual numbers — don't be vague)
{data_block}

## Brand Context (use exact brand name, do not invent claims)
{brand_context}

## Companion Content Available
- Press release: {companion.get('press_release', False)}
- Data exclusive: {companion.get('data_exclusive', False)}
- Byline opportunity: {companion.get('byline_opportunity', False)}
- Embargoed briefing: {companion.get('embargoed_briefing', False)}

## Campaign Wave Context
Wave: {wave_label} — {wave_timing}

{wave_instructions}

---

PITCH WRITING RULES (apply to all waves):
1. First sentence MUST reference something specific they recently covered — a headline, a topic, a beat they own
2. If known authors are listed, write as if addressing that type of journalist specifically
3. Include at least one specific data point or stat from the data assets above — not vague claims
4. DO NOT use filler phrases: "I hope this finds you well", "I wanted to reach out", "I look forward to hearing from you"
5. DO NOT use the brand's document language verbatim — write naturally, like a PR pro who deeply knows the story
6. DO NOT invent statistics or capabilities not in the brand context
7. Sign off simply — first name, title optional

Return JSON:
{{
  "subject_line": "The email subject line — specific, no fluff",
  "body": "The full email body (plain text, use \\n for line breaks, no HTML)",
  "word_count": <integer>,
  "personalization_notes": "What specific thing about this outlet/journalist drove the personalization choices — be specific about which headline you referenced and why",
  "companion_content_recommended": "What to attach or offer alongside this specific pitch",
  "exclusive_offer_line": {"the exact 1-sentence offer if Wave 1, null otherwise"},
  "follow_on_hook": {"the exact coverage-reference line if Wave 3, null otherwise"}
}}
"""

        try:
            response = await litellm.acompletion(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.7,
                max_tokens=1200
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            return {
                "subject_line": "Error generating pitch",
                "body": f"Pitch generation failed: {str(e)}",
                "word_count": 0,
                "personalization_notes": "",
                "companion_content_recommended": "",
                "exclusive_offer_line": None,
                "follow_on_hook": None,
            }

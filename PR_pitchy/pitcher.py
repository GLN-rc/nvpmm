"""
PR Pitcher Module
Two-step pipeline:
  Step 1 (analyze_and_plan): analyze news + match publications + plan waves → return for user selection
  Step 2 (draft_campaign): accept user selections + scraped articles → draft personalized pitches
"""

import asyncio
import os
import json
from typing import Optional
import litellm


class PRPitcher:
    """AI-powered PR pitch generator with two-step campaign builder."""

    def __init__(self):
        self.model = os.getenv("LLM_MODEL", "gpt-4o")

    # ═══════════════════════════════════════════════════
    # STEP 1: Analyze news + match pubs + plan waves
    # Called by /api/analyze — returns targets for user selection
    # ═══════════════════════════════════════════════════

    async def analyze_and_plan(
        self,
        brand_context: str,
        news_content: str,
        user_constraints: str,
        publication_summaries: list[dict],
        recent_headlines: list[dict],
    ) -> dict:
        """
        Steps 1-3 only. Does NOT draft pitches.
        Returns news_analysis, ranked targets with audience_hook, and campaign wave suggestions.
        """
        news_analysis = await self._analyze_news(brand_context, news_content, user_constraints)

        targets = await self._match_publications(
            brand_context, news_analysis, user_constraints, publication_summaries, recent_headlines
        )

        campaign_suggestion = await self._suggest_waves(news_analysis, targets, user_constraints)

        return {
            "news_analysis": news_analysis,
            "targets": targets,
            "campaign_suggestion": campaign_suggestion,
        }

    # ═══════════════════════════════════════════════════
    # STEP 2: Draft campaign from user selections
    # Called by /api/campaign — drafts pitches with scraped article context
    # ═══════════════════════════════════════════════════

    async def draft_campaign(
        self,
        brand_context: str,
        news_content: str,
        user_constraints: str,
        news_analysis: dict,
        targets: list[dict],
        wave_1_pub: Optional[str],
        wave_2_pubs: list[str],
        wave_3_pubs: list[str],
        scraped_by_pub: dict,     # pub_name → list of scraped article dicts
        launch_date: str = "",    # e.g. "2025-04-15", optional
    ) -> dict:
        """
        Draft personalized pitches for user-selected publications.
        Enriches each target with scraped article content before drafting.
        Runs press release drafting in parallel with pitch drafting.
        """
        targets_lookup = {t["publication"]: t for t in targets}

        # Build campaign_plan structure compatible with _draft_pitches_by_wave
        campaign_plan = await self._plan_campaign_from_selections(
            news_analysis, targets_lookup, wave_1_pub, wave_2_pubs, wave_3_pubs,
            user_constraints, launch_date
        )

        # Enrich targets with scraped article content
        for pub_name, target in targets_lookup.items():
            target["scraped_articles"] = scraped_by_pub.get(pub_name, [])

        # Run pitch drafting + press release drafting in parallel
        waves, press_release = await asyncio.gather(
            self._draft_pitches_by_wave(
                brand_context, news_analysis, user_constraints, campaign_plan, targets_lookup
            ),
            self._draft_press_release(
                brand_context, news_content, user_constraints, news_analysis, campaign_plan, launch_date
            ),
        )

        return {
            "news_analysis": news_analysis,
            "campaign_plan": campaign_plan,
            "waves": waves,
            "all_targets": targets,
            "press_release": press_release,
        }

    # ─────────────────────────────────────────────
    # STEP 1a: Analyze the news
    # ─────────────────────────────────────────────

    async def _analyze_news(
        self, brand_context: str, news_content: str, user_constraints: str
    ) -> dict:
        """Analyze news — classify, assess newsworthiness, identify angles and exclusive viability."""

        constraints_block = f"""
## User Constraints (HARD RULES — these override all LLM defaults)
{user_constraints}
""" if user_constraints.strip() else ""

        prompt = f"""You are a senior PR strategist with deep experience in B2B tech and cybersecurity media relations.

Analyze the following news/announcement and brand context. Read the ENTIRE content carefully — recommendations, data findings, and conclusions at the end are just as important as the opening.
{constraints_block}
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
  "data_assets": ["Specific stats, numbers, percentages verbatim — quote them exactly as they appear in the content", "..."],
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
    "what_to_offer": "Specific thing you can offer one outlet that others won't get. Be concrete. null if nothing credible.",
    "embargo_window_suggested": "e.g. '48 hours before launch' or null"
  }},
  "campaign_timing_notes": "Any timing considerations that should influence campaign structure",
  "companion_content_needed": {{
    "press_release": true,
    "data_exclusive": true,
    "byline_opportunity": true,
    "embargoed_briefing": true,
    "reasoning": "Why these companion content types would help"
  }}
}}

Be honest about newsworthiness. Score of 4 or below means story needs more work.
data_assets should include actual verbatim numbers/stats so they can be dropped directly into pitches.
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
                "headline": "Analysis failed", "news_type": "Unknown",
                "newsworthiness_score": 0,
                "newsworthiness_reasoning": f"Error: {str(e)}",
                "why_now": "", "who_cares": [], "core_story": "",
                "data_assets": [], "angles": [],
                "weaknesses": ["LLM analysis failed — check API key"],
                "exclusive_viability": {"can_offer_exclusive": False, "what_to_offer": None, "embargo_window_suggested": None},
                "campaign_timing_notes": "", "companion_content_needed": {}
            }

    # ─────────────────────────────────────────────
    # STEP 1b: Match and score publications
    # ─────────────────────────────────────────────

    async def _match_publications(
        self,
        brand_context: str,
        news_analysis: dict,
        user_constraints: str,
        publication_summaries: list[dict],
        recent_headlines: list[dict],
    ) -> list[dict]:
        """Score each publication for fit. Generate audience_hook per outlet."""

        headlines_by_pub = {}
        authors_by_pub = {}
        articles_by_pub = {}  # full article objects for later scraping
        for article in recent_headlines:
            pub = article["publication"]
            if pub not in headlines_by_pub:
                headlines_by_pub[pub] = []
                authors_by_pub[pub] = []
                articles_by_pub[pub] = []
            headlines_by_pub[pub].append(article["title"])
            if article.get("author"):
                authors_by_pub[pub].append(article["author"])
            articles_by_pub[pub].append(article)

        pub_context = []
        for pub in publication_summaries:
            headlines = headlines_by_pub.get(pub["name"], [])
            authors = list(set(authors_by_pub.get(pub["name"], [])))
            pub_context.append(
                f"- {pub['name']} (Tier {pub['tier']}): Beat: {pub['beat']}. "
                f"Audience: {pub['audience']}. "
                f"Recent headlines: {'; '.join(headlines[:5]) if headlines else 'Not available'}. "
                f"Known authors: {', '.join(authors[:4]) if authors else 'Not available'}"
            )

        constraints_block = f"""
## User Constraints (HARD RULES — must be respected in scoring and hook generation)
{user_constraints}
""" if user_constraints.strip() else ""

        prompt = f"""You are a PR strategist who deeply understands what makes stories perform well for different audiences.
{constraints_block}
## The Story
Type: {news_analysis.get('news_type')}
Core story: {news_analysis.get('core_story')}
Why now: {news_analysis.get('why_now')}
Who cares: {', '.join(news_analysis.get('who_cares', []))}
Newsworthiness: {news_analysis.get('newsworthiness_score')}/10
Key data points: {', '.join(news_analysis.get('data_assets', [])) or 'None identified'}

## Available Publications
{chr(10).join(pub_context)}

---

For each publication, score fit AND generate an audience_hook.

The audience_hook is NOT about topic matching. It answers:
"Given what makes stories PERFORM WELL for this outlet's specific audience — what framing of this research would get the most clicks, shares, and engagement from their readers? What would make a [CISO/practitioner/exec] stop scrolling? What angle feels genuinely new and useful to them — not more of the same they've already seen?"

Think about audience psychology, not keyword overlap. A CISO reading Dark Reading wants to feel like they have inside knowledge their peers don't. A VentureBeat reader wants to understand business implications. Frame accordingly.

Return JSON:
{{
  "targets": [
    {{
      "publication": "Publication name exactly as listed",
      "fit_score": <1-10>,
      "fit_reasoning": "1-2 sentences on why this pub is or isn't a fit",
      "best_angle": "Which angle from the story fits this outlet, and why",
      "audience_hook": "The specific framing that would perform best for THIS outlet's readers — what makes them click. Must respect user constraints.",
      "known_authors": ["Author name if available", "..."],
      "suggested_journalist_type": "The specific beat writer to target at this outlet",
      "wave_suitability": {{
        "good_for_exclusive": true,
        "good_for_launch_day": true,
        "good_for_followon": false,
        "suitability_reasoning": "1 sentence"
      }}
    }}
  ]
}}

Include ALL publications sorted by fit_score descending.
audience_hook must be a concrete, compelling sentence — not vague ("your readers will find this interesting").
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
            pub_meta = {p["name"]: p for p in publication_summaries}
            for t in targets:
                meta = pub_meta.get(t["publication"], {})
                t["tier"] = meta.get("tier", 2)
                t["domain"] = meta.get("domain", "")
                t["beat"] = meta.get("beat", "")
                t["audience"] = meta.get("audience", "")
                t["recent_headlines"] = headlines_by_pub.get(t["publication"], [])
                t["articles"] = articles_by_pub.get(t["publication"], [])  # for scraping later
                rss_authors = list(set(authors_by_pub.get(t["publication"], [])))
                llm_authors = t.get("known_authors", [])
                t["known_authors"] = rss_authors if rss_authors else llm_authors
            targets.sort(key=lambda x: x.get("fit_score", 0), reverse=True)
            return targets
        except Exception:
            return []

    # ─────────────────────────────────────────────
    # STEP 1c: Suggest wave assignments (for pre-selection in UI)
    # ─────────────────────────────────────────────

    async def _suggest_waves(
        self, news_analysis: dict, targets: list[dict], user_constraints: str
    ) -> dict:
        """Suggest which outlets belong in each wave. User can override."""

        qualifying = [t for t in targets if t.get("fit_score", 0) >= 5]
        excl = news_analysis.get("exclusive_viability", {})

        constraints_block = f"""
## User Constraints
{user_constraints}
""" if user_constraints.strip() else ""

        targets_summary = json.dumps([{
            "publication": t["publication"],
            "tier": t["tier"],
            "fit_score": t["fit_score"],
            "audience_hook": t.get("audience_hook", ""),
            "wave_suitability": t.get("wave_suitability", {})
        } for t in qualifying], indent=2)

        prompt = f"""You are a PR strategist recommending a campaign wave structure.
{constraints_block}
## Story
Newsworthiness: {news_analysis.get('newsworthiness_score')}/10
Type: {news_analysis.get('news_type')}
Can offer exclusive: {excl.get('can_offer_exclusive', False)}
What to offer: {excl.get('what_to_offer', 'N/A')}

## Qualifying Targets
{targets_summary}

Suggest wave assignments. These are SUGGESTIONS — the user will confirm or change them.

Rules:
- Wave 1 (exclusive): ONE outlet only, fit_score >= 8, good_for_exclusive = true, only if can_offer_exclusive is true. Null otherwise.
- Wave 2 (launch day): 3-5 outlets, pitched simultaneously. Best fit for news coverage.
- Wave 3 (follow-on): Remaining outlets fit_score >= 5. Better for bylines, deep-dives, niche verticals.
- Do NOT put the same outlet in multiple waves.

Return JSON:
{{
  "wave_1_suggestion": "Publication name or null",
  "wave_2_suggestions": ["pub1", "pub2", "pub3"],
  "wave_3_suggestions": ["pub4", "pub5"],
  "suggestion_rationale": "2-3 sentences explaining the overall strategy and why you assigned outlets this way"
}}
"""

        try:
            response = await litellm.acompletion(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.3,
                max_tokens=800
            )
            return json.loads(response.choices[0].message.content)
        except Exception:
            # Fallback: auto-assign by fit_score
            sorted_q = sorted(qualifying, key=lambda x: x.get("fit_score", 0), reverse=True)
            return {
                "wave_1_suggestion": None,
                "wave_2_suggestions": [t["publication"] for t in sorted_q[:4]],
                "wave_3_suggestions": [t["publication"] for t in sorted_q[4:7]],
                "suggestion_rationale": "Auto-assigned by fit score (wave suggestion LLM call failed)."
            }

    # ─────────────────────────────────────────────
    # STEP 2a: Build campaign plan from user selections
    # ─────────────────────────────────────────────

    async def _plan_campaign_from_selections(
        self,
        news_analysis: dict,
        targets_lookup: dict,
        wave_1_pub: Optional[str],
        wave_2_pubs: list[str],
        wave_3_pubs: list[str],
        user_constraints: str,
        launch_date: str = "",
    ) -> dict:
        """Build full campaign plan (with contingencies + timing) based on user's selections."""

        excl = news_analysis.get("exclusive_viability", {})
        constraints_block = f"""
## User Constraints
{user_constraints}
""" if user_constraints.strip() else ""

        launch_date_block = f"""
## Launch Date
{launch_date}
Use this to calculate EXACT calendar dates for each wave and each follow-up.
Format dates as human-readable short strings like "Tue Apr 15" — NOT ISO format.
""" if launch_date.strip() else ""

        # Build context about selected targets
        selected_context = []
        all_selected = []
        if wave_1_pub:
            all_selected.append(wave_1_pub)
        all_selected.extend(wave_2_pubs)
        all_selected.extend(wave_3_pubs)

        for pub_name in all_selected:
            t = targets_lookup.get(pub_name, {})
            selected_context.append({
                "publication": pub_name,
                "wave": "1" if pub_name == wave_1_pub else ("2" if pub_name in wave_2_pubs else "3"),
                "fit_score": t.get("fit_score", 0),
                "audience_hook": t.get("audience_hook", ""),
                "wave_suitability": t.get("wave_suitability", {})
            })

        prompt = f"""You are a senior PR strategist building a campaign execution plan.
{constraints_block}{launch_date_block}
## Story
Core story: {news_analysis.get('core_story')}
Newsworthiness: {news_analysis.get('newsworthiness_score')}/10
Can offer exclusive: {excl.get('can_offer_exclusive', False)}
Exclusive offer: {excl.get('what_to_offer', 'N/A')}

## User's Selected Targets (already assigned to waves by user)
{json.dumps(selected_context, indent=2)}

Build the campaign execution plan for these exact selections. Do NOT reassign outlets — respect the user's wave choices.

## Timing Best-Practice Rules (always apply these regardless of launch_date)
- Best send days: Tuesday, Wednesday, or Thursday only
- Best send time: 7–9am recipient's local time (before their morning standup/inbox flood)
- Wave 1 exclusive: send at minimum 48h before launch; allow journalist 24h to confirm before wire release goes out
- Wave 2 (launch day): send simultaneously with the wire release, or 30 minutes before it goes live
- Wave 3 follow-on: 7–10 business days after launch, NOT before (let Wave 2 coverage accumulate)
- Follow-up cadence: if no response, follow up once at +3 business days, then one final at +5 business days, then move on
- Do NOT follow up on launch day — too much noise, journalists are already flooded
- If launch date falls on Mon or Fri, move Wave 2 pitches to the next Tuesday

Return JSON:
{{
  "campaign_summary": "2-3 sentence overview of the campaign strategy",
  "wave_1": {{
    "publication": "{wave_1_pub or 'null'}",
    "timing_label": "e.g. '48 hours before launch'",
    "send_date": "Calculated date if launch_date provided, else 'TBD — enter launch date for exact dates'",
    "send_time_guidance": "e.g. 'Send Tuesday 7–9am EST — gives journalist 48h to confirm before your wire drops'",
    "follow_up_window": "e.g. 'Follow up Thu Apr 17 if no response — one follow-up only on exclusives'",
    "rationale": "Why this outlet for the exclusive",
    "exclusive_offer": "Exact concrete offer — what they get, when, what no one else gets",
    "contingency": {{
      "if_rejected": "Specific next step if this outlet declines",
      "if_no_response_48h": "Specific next step if no reply in 48 hours",
      "second_choice_exclusive": "Which Wave 2 outlet to approach for exclusive instead, or null"
    }}
  }},
  "wave_2": {{
    "timing_label": "Launch Day",
    "send_date": "Calculated date if launch_date provided, else 'TBD'",
    "send_time_guidance": "e.g. 'Send 30 min before wire release goes live — typically 8am–9am EST'",
    "follow_up_window": "e.g. 'Follow up Fri Apr 22 (+3 business days), final follow-up Wed Apr 27 (+5 biz days)'",
    "publications": [
      {{"publication": "name", "angle_note": "The specific angle for THIS outlet's audience — must be distinct from others"}}
    ],
    "wave_2_note": "Coordination note — pitch simultaneously, wait for embargo lift, etc."
  }},
  "wave_3": {{
    "timing_label": "7–10 business days post-launch",
    "send_date": "Calculated date if launch_date provided, else 'TBD'",
    "send_time_guidance": "e.g. 'Send Tuesday 7–9am — reference 2-3 specific pieces of coverage already received'",
    "follow_up_window": "e.g. 'One follow-up at +3 business days if no response'",
    "publications": [
      {{"publication": "name", "angle_note": "The follow-on angle your readers haven't seen yet", "format_suggestion": "e.g. contributed byline, podcast pitch, data feature"}}
    ],
    "wave_3_strategy": "How to use Wave 2 coverage as social proof in Wave 3 pitches"
  }},
  "contingency_if_wave2_thin": "If Wave 2 gets fewer than 2 placements, specific guidance on Wave 3 adaptation"
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
            # Build minimal plan from selections
            return {
                "campaign_summary": f"Campaign plan generation failed: {str(e)}",
                "wave_1": {"publication": wave_1_pub, "timing_label": "48h before launch", "rationale": "", "exclusive_offer": excl.get("what_to_offer", ""), "contingency": {}},
                "wave_2": {"timing_label": "Launch Day", "publications": [{"publication": p, "angle_note": ""} for p in wave_2_pubs], "wave_2_note": ""},
                "wave_3": {"timing_label": "1-2 weeks post-launch", "publications": [{"publication": p, "angle_note": "", "format_suggestion": ""} for p in wave_3_pubs], "wave_3_strategy": ""},
                "contingency_if_wave2_thin": ""
            }

    # ─────────────────────────────────────────────
    # STEP 2b: Draft pitches by wave
    # ─────────────────────────────────────────────

    async def _draft_pitches_by_wave(
        self,
        brand_context: str,
        news_analysis: dict,
        user_constraints: str,
        campaign_plan: dict,
        targets_lookup: dict,
    ) -> dict:
        """Draft personalized pitch emails for each wave. Wave 2 + 3 in parallel."""
        waves = {}

        # ── Wave 1 — exclusive ──
        wave1_plan = campaign_plan.get("wave_1", {})
        wave1_pub = wave1_plan.get("publication") if wave1_plan else None
        if wave1_pub and wave1_pub in targets_lookup:
            target = targets_lookup[wave1_pub]
            pitch = await self._draft_single_pitch(
                brand_context=brand_context,
                news_analysis=news_analysis,
                user_constraints=user_constraints,
                target=target,
                wave=1,
                wave_label="Exclusive / Embargo",
                wave_timing=wave1_plan.get("timing_label", "48 hours before launch"),
                is_exclusive=True,
                exclusive_offer=wave1_plan.get("exclusive_offer", ""),
                angle_note=wave1_plan.get("rationale", ""),
            )
            waves["wave_1"] = {**wave1_plan, "target_data": {**target, "pitch": pitch}}
        else:
            waves["wave_1"] = None

        # ── Wave 2 — parallel ──
        wave2_entries = campaign_plan.get("wave_2", {}).get("publications", [])
        wave2_coros = []
        wave2_meta = []
        for entry in wave2_entries:
            pub_name = entry["publication"]
            target = targets_lookup.get(pub_name, {"publication": pub_name, "beat": "", "audience": "", "recent_headlines": [], "known_authors": [], "scraped_articles": []})
            wave2_coros.append(self._draft_single_pitch(
                brand_context=brand_context, news_analysis=news_analysis,
                user_constraints=user_constraints, target=target,
                wave=2, wave_label="Launch Day", wave_timing="Launch Day",
                is_exclusive=False, angle_note=entry.get("angle_note", ""),
            ))
            wave2_meta.append((entry, target))

        wave2_pitches = await asyncio.gather(*wave2_coros, return_exceptions=True)
        waves["wave_2"] = []
        for (entry, target), pitch in zip(wave2_meta, wave2_pitches):
            if isinstance(pitch, Exception):
                pitch = {"subject_line": "Error", "body": str(pitch), "word_count": 0, "personalization_notes": "", "companion_content_recommended": ""}
            waves["wave_2"].append({"angle_note": entry.get("angle_note", ""), "target_data": {**target, "pitch": pitch}})

        # ── Wave 3 — parallel ──
        wave3_entries = campaign_plan.get("wave_3", {}).get("publications", [])
        wave3_strategy = campaign_plan.get("wave_3", {}).get("wave_3_strategy", "")
        wave3_coros = []
        wave3_meta = []
        for entry in wave3_entries:
            pub_name = entry["publication"]
            target = targets_lookup.get(pub_name, {"publication": pub_name, "beat": "", "audience": "", "recent_headlines": [], "known_authors": [], "scraped_articles": []})
            wave3_coros.append(self._draft_single_pitch(
                brand_context=brand_context, news_analysis=news_analysis,
                user_constraints=user_constraints, target=target,
                wave=3, wave_label="Follow-on", wave_timing="1-2 weeks post-launch",
                is_exclusive=False, angle_note=entry.get("angle_note", ""),
                format_suggestion=entry.get("format_suggestion", ""),
                wave_3_strategy=wave3_strategy,
            ))
            wave3_meta.append((entry, target))

        wave3_pitches = await asyncio.gather(*wave3_coros, return_exceptions=True)
        waves["wave_3"] = []
        for (entry, target), pitch in zip(wave3_meta, wave3_pitches):
            if isinstance(pitch, Exception):
                pitch = {"subject_line": "Error", "body": str(pitch), "word_count": 0, "personalization_notes": "", "companion_content_recommended": ""}
            waves["wave_3"].append({"angle_note": entry.get("angle_note", ""), "format_suggestion": entry.get("format_suggestion", ""), "target_data": {**target, "pitch": pitch}})

        return waves

    # ─────────────────────────────────────────────
    # STEP 2c: Draft one pitch
    # ─────────────────────────────────────────────

    async def _draft_single_pitch(
        self,
        brand_context: str,
        news_analysis: dict,
        user_constraints: str,
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
        """Draft one personalized pitch email with scraped article context."""

        known_authors = target.get("known_authors", [])
        data_assets = news_analysis.get("data_assets", [])
        companion = news_analysis.get("companion_content_needed", {})
        audience_hook = target.get("audience_hook", angle_note)
        scraped_articles = target.get("scraped_articles", [])

        # Build scraped article context block
        if scraped_articles:
            article_blocks = []
            for art in scraped_articles[:3]:
                quality = art.get("scrape_quality", "failed")
                title = art.get("title", "")
                author = art.get("author", "")
                body = art.get("body_text", "")
                note = art.get("scrape_note", "")
                block = f"Title: {title}"
                if author:
                    block += f"\nAuthor: {author}"
                block += f"\nContent quality: {quality} ({note})"
                if body and quality != "failed":
                    block += f"\nContent excerpt:\n{body[:800]}"
                article_blocks.append(block)
            articles_context = "\n\n---\n\n".join(article_blocks)
            articles_intro = "Use the article content below to understand HOW this outlet frames stories — their argument structure, their angle choices, what they emphasize for their audience. Do NOT just reference the topic; understand the framing."
        else:
            articles_context = "(No article content available — work from publication description and beat)"
            articles_intro = "No scraped article content available for this outlet."

        authors_block = ", ".join(known_authors[:4]) if known_authors else "Unknown — address to the beat writer"
        data_block = "\n".join(f"  - {d}" for d in data_assets) if data_assets else "  (No specific data points identified)"

        constraints_block = f"""
## User Constraints (HARD RULES — these override all other instructions)
{user_constraints}
""" if user_constraints.strip() else ""

        # Wave-specific rules
        if wave == 1:
            wave_rules = f"""WAVE 1 — EXCLUSIVE PITCH:
- ONE outlet only. This pitch is a pre-launch exclusive offer.
- MUST include the exclusive offer: {exclusive_offer}
- MUST mention the embargo window: {wave_timing}
- Under 120 words in the body — exclusives work because they are rare and concise
- Subject line should signal first access without being clunky — e.g. "Embargo: [story] — [Publication] first look"
- Open by showing you understand their audience and what performs well for them (use audience_hook)
- The exclusive offer is the closer, not the opener"""
        elif wave == 2:
            wave_rules = f"""WAVE 2 — LAUNCH DAY PITCH:
- Press release is now live on the wire. You may reference this.
- Angle for this outlet specifically: {angle_note}
- Under 150 words
- Lead with the audience_hook — what will make THEIR readers click
- Offer: interview, data access, or quote — make the ask specific"""
        else:
            wave_rules = f"""WAVE 3 — FOLLOW-ON PITCH:
- Timing: 1-2 weeks after launch
- Social proof strategy: {wave_3_strategy}
- Angle: {angle_note}
- Format: {format_suggestion or 'contributed byline or feature pitch'}
- Brief reference to existing coverage, then pivot to the angle your readers haven't seen yet
- Under 150 words"""

        prompt = f"""You are a PR professional writing a pitch email. This must be genuinely personalized — not a template.
{constraints_block}
## Target Publication
Publication: {target.get('publication', 'Unknown')}
Beat: {target.get('beat', 'Unknown')}
Audience: {target.get('audience', 'Unknown')}
Known contributors: {authors_block}
Journalist type to target: {target.get('suggested_journalist_type', 'Beat reporter')}

## Audience Hook (the framing that performs best for this outlet's readers)
{audience_hook}

## What this outlet has been writing about
{articles_intro}

{articles_context}

## The Story
{news_analysis.get('core_story', '')}
Type: {news_analysis.get('news_type', '')}
Why now: {news_analysis.get('why_now', '')}

## Specific Data Points (use actual numbers — not vague claims)
{data_block}

## Brand Context
{brand_context}

## Companion Content Available
- Press release: {companion.get('press_release', False)}
- Data exclusive: {companion.get('data_exclusive', False)}
- Byline opportunity: {companion.get('byline_opportunity', False)}
- Embargoed briefing: {companion.get('embargoed_briefing', False)}

## Wave: {wave_label} — {wave_timing}

{wave_rules}

---

PITCH RULES:
1. Lead with the audience_hook — what makes THEIR readers engage. Not a topic match, a genuine hook.
2. Include at least one specific data point verbatim from the data assets
3. If scraped article content is available, reference the ARGUMENT or FRAMING the journalist used — not just the headline topic
4. DO NOT: "I hope this finds you well", "I wanted to reach out", "I look forward to hearing from you"
5. DO NOT use brand document language verbatim — write naturally
6. DO NOT invent statistics or claims not in the brand context
7. Respect all user constraints — they override your defaults
8. Sign off simply

Return JSON:
{{
  "subject_line": "Specific, no fluff — ideally references their audience's current concern",
  "body": "Full email body (plain text, \\n for line breaks)",
  "word_count": <integer>,
  "personalization_notes": "What specific thing from the scraped content or audience analysis drove your choices — be precise",
  "companion_content_recommended": "What to attach or offer with this pitch",
  "scrape_quality_used": "What quality level of article content you had to work with",
  "exclusive_offer_line": "The exact 1-sentence offer if Wave 1, null otherwise",
  "follow_on_hook": "The coverage-reference line if Wave 3, null otherwise"
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
                "scrape_quality_used": "failed",
                "exclusive_offer_line": None,
                "follow_on_hook": None,
            }

    # ─────────────────────────────────────────────
    # STEP 2d: Draft press release + PR firm coordination memo
    # ─────────────────────────────────────────────

    async def _draft_press_release(
        self,
        brand_context: str,
        news_content: str,
        user_constraints: str,
        news_analysis: dict,
        campaign_plan: dict,
        launch_date: str = "",
    ) -> dict:
        """
        Draft a wire-ready press release + coordination guidance for PR firms.
        Runs in parallel with pitch drafting — no extra latency.
        """

        constraints_block = f"""
## User Constraints (HARD RULES)
{user_constraints}
""" if user_constraints.strip() else ""

        launch_date_line = f"Launch / wire date: {launch_date}" if launch_date.strip() else "Launch date: TBD"
        wave_1_pub = campaign_plan.get("wave_1", {}).get("publication", "None")
        wave_1_send = campaign_plan.get("wave_1", {}).get("send_date", "TBD")
        wire_timing = campaign_plan.get("wave_2", {}).get("send_date", "Launch day")
        exclusive_offer = campaign_plan.get("wave_1", {}).get("exclusive_offer", "")

        prompt = f"""You are a senior PR professional. Write a wire-ready press release AND create a practical coordination memo for working with a PR firm.
{constraints_block}
## Story Details
{news_analysis.get('core_story', '')}
Type: {news_analysis.get('news_type', '')}
Key data points: {', '.join(news_analysis.get('data_assets', [])) or 'See content below'}

## Brand Context
{brand_context}

## Source Content
{news_content[:3000]}

## Campaign Context
{launch_date_line}
Wave 1 exclusive target: {wave_1_pub} (send date: {wave_1_send})
Wire release goes live: {wire_timing}
Exclusive offer being made: {exclusive_offer or 'None'}

---

Return JSON with exactly these fields:

{{
  "press_release": "Full formatted press release FOR THE WIRE. Format:\\nFOR IMMEDIATE RELEASE\\n\\n[HEADLINE IN CAPS]\\n\\n[Subheadline — 1 sentence]\\n\\n[City, Date] — [Lead paragraph — who, what, where, when, why in 2-3 sentences. Inverted pyramid. Strongest news first.]\\n\\n[Body paragraph 2 — supporting detail, data points]\\n\\n[Quote from company spokesperson — specific, not generic platitude]\\n\\n[Body paragraph 3 — product/service detail or broader context]\\n\\n[Second quote if appropriate — customer, partner, or analyst]\\n\\n[Forward-looking paragraph — what this means for the market]\\n\\n### About [Company]\\n[Boilerplate — 3-4 sentences]\\n\\nMedia Contact:\\n[Name]\\n[Title]\\n[Email]\\n[Phone]",

  "pr_firm_brief": "Short internal memo written AS IF you are the client briefing your PR firm. Start with: 'Here is what to tell your PR firm:'. Cover: (1) the campaign structure and timing, (2) which outlet has the exclusive and what the offer is, (3) exactly when the wire release should go out and NOT before, (4) what they should NOT share until the embargo lifts, (5) what assets you will provide them (quote approval, exec availability for interviews, data sheet, etc.)",

  "embargo_protocol": "Step-by-step ordered list of the embargo management sequence — who gets contacted first, what they receive, when each embargo lifts, what triggers the wire release, how to handle a journalist who breaks embargo. Write as numbered steps, practical and specific.",

  "wire_timing_note": "1-2 sentence practical note on exactly when to send to the wire relative to the campaign waves — e.g. 'Send to PR Newswire/Business Wire to embargo lift at [time] on [date], 30 minutes before Wave 2 pitches go out.'"
}}

Rules:
- Press release must be ready to copy-paste to a wire service — proper structure, real headline, real quote (use [SPOKESPERSON NAME] as placeholder if unknown)
- No vague language in the PR firm brief — be concrete about dates, outlets, what to hold back
- Embargo protocol should be specific enough that a junior PR coordinator could execute it
- Respect all user constraints
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
                "press_release": f"Press release generation failed: {str(e)}",
                "pr_firm_brief": "",
                "embargo_protocol": "",
                "wire_timing_note": "",
            }

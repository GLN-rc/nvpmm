"""
Blog Extractor
Uses an LLM to transform raw blog text + brand doc into structured brief content.
Returns validated JSON ready for pdf_generator.py.
"""

import json
import os
import re
from typing import Optional


async def extract_brief(
    blog_text: str,
    blog_title: str,
    brand_doc_text: str,
    page_preference: int = 2,
    inline_images: Optional[list] = None
) -> dict:
    """
    Call LLM to extract structured brief content from blog text.
    Returns dict with: title, subtitle, exec_summary, takeaways[], sections[],
    elevator_pitch_header, elevator_pitch_body, cta_text, cta_url,
    needs_extra_page, image_suggestions[], faqs[]
    """
    try:
        import litellm
    except ImportError:
        raise RuntimeError("litellm not installed. Run: pip install litellm")

    model = os.getenv("LLM_MODEL", "gpt-4o-mini")
    images_context = ""
    if inline_images:
        imgs = [f"- {img.get('alt', 'image')} ({img['src'][:80]})" for img in inline_images[:3]]
        images_context = "\n\nImages found in blog:\n" + "\n".join(imgs)

    # 3 sections keeps sections full + leaves room for FAQ
    section_count = 3

    prompt = f"""You are a B2B marketing content specialist. Transform this blog post into structured content for a polished executive brief PDF. The PDF needs to fill the page - write rich, substantive content.

## Blog Title
{blog_title}

## Blog Content
{blog_text[:12000]}
{images_context}

## Brand Document (extract elevator pitch and CTA from this)
{brand_doc_text[:3000] if brand_doc_text else "[No brand document provided - use empty strings for elevator pitch fields]"}

## Your Task
Return ONLY valid JSON matching this exact schema. No markdown, no explanation, just JSON.

{{
  "title": "Compelling title derived from blog (max 60 chars, punchy)",
  "subtitle": "One-line framing of the key insight or argument (max 90 chars)",
  "exec_summary": "3-4 sentence summary. Cover: what problem this addresses, the core argument or finding, who should care and why it matters NOW. Be specific, direct, substantive. Aim for 80-100 words.",
  "takeaways": [
    "Insight-driven takeaway 1 - a full sentence making a specific, actionable point (not a topic label). Aim for 20-30 words.",
    "Insight-driven takeaway 2 - a full sentence making a specific, actionable point. Aim for 20-30 words.",
    "Insight-driven takeaway 3 - a full sentence making a specific, actionable point. Aim for 20-30 words."
  ],
  "faqs": [
    {{
      "question": "Question extracted verbatim or near-verbatim from blog FAQ section",
      "answer": "Answer condensed to 1-2 sentences if longer. Max 40 words."
    }}
  ],
  "sections": [
    {{
      "header": "Meaningful section header that reflects blog content (not 'Section 1')",
      "body": "Substantive 4-6 sentence paragraph expanding on this angle. Include specific details, context, or implications from the blog. Aim for 100-120 words. No filler - every sentence must add information."
    }}
  ],
  "elevator_pitch_body": "Copy the elevator pitch or boilerplate WORD FOR WORD from the brand doc. Do NOT paraphrase, summarize, or rewrite. If not found in the brand doc, use empty string.",
  "cta_text": "CTA button/link text extracted from brand doc (e.g. 'Watch the demo'). If not found, use empty string.",
  "cta_url": "CTA URL from brand doc. If not found, use empty string.",
  "needs_extra_page": false,
  "image_suggestions": [
    {{
      "section_index": 0,
      "description": "What kind of image would work here and why (1 sentence)",
      "prompt": "Detailed image generation prompt if user wants AI to create it"
    }}
  ]
}}

## Rules
- faqs: MUST be output first, before sections. Always produce exactly 3 FAQ pairs. If the blog has an explicit FAQ section, extract those questions and answers verbatim or near-verbatim. If no FAQ section exists, synthesize 3 insightful Q&A pairs from the blog content - questions a reader would naturally ask, answered in 1-2 sentences using the blog's own language and evidence. Never leave faqs as an empty array.
- sections array: include exactly {section_count} sections. Each section body must be 100-120 words - do not truncate or pad with filler.
- exec_summary: 3-4 sentences, ~80-100 words. No em dashes, no smart quotes, no buzzword soup. Plain English.
- takeaways: derive real insights, not topic headings. Bad: "Security matters". Good: "Network-level isolation beats endpoint agents because it stops lateral movement before credentials are stolen, cutting breach radius by 80%."
- elevator_pitch_body: copy WORD FOR WORD from the brand doc's elevator pitch or boilerplate section. Never paraphrase. If not found, use empty string.
- image_suggestions: include 1-2 spots where a visual would genuinely help comprehension. Only suggest if it adds value.
- All text: no em dashes (use - or :), no smart quotes, use straight quotes only.
- Forbidden words: never use the word "landscape" anywhere in any field.
- IMPORTANT: Write to fill the page. Thin, short content defeats the purpose of the brief."""

    response = await litellm.acompletion(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=3800
    )

    raw = response.choices[0].message.content.strip()

    # Strip markdown code fences if present
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        # Try to extract JSON from response
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            data = json.loads(match.group())
        else:
            raise ValueError(f"LLM returned invalid JSON: {e}\n\nRaw response:\n{raw[:500]}")

    # Validate and fill defaults
    data = _validate_and_fill(data)
    return data


def _validate_and_fill(data: dict) -> dict:
    """Ensure all required fields exist with sensible defaults."""
    defaults = {
        "title": "Executive Brief",
        "subtitle": "",
        "exec_summary": "",
        "takeaways": ["", "", ""],
        "sections": [{"header": "Key Insights", "body": "Content could not be extracted."}, {"header": "What This Means", "body": "Content could not be extracted."}],
        "elevator_pitch_body": "",
        "cta_text": "",
        "cta_url": "",
        "needs_extra_page": False,
        "image_suggestions": [],
        "faqs": []
    }

    for key, default in defaults.items():
        if key not in data or data[key] is None:
            data[key] = default

    # Ensure takeaways has at least 3
    while len(data["takeaways"]) < 3:
        data["takeaways"].append("")
    data["takeaways"] = data["takeaways"][:3]

    # Ensure sections has at least 2
    while len(data["sections"]) < 2:
        data["sections"].append({"header": "Additional Context", "body": ""})

    # Normalize text (remove em dashes, smart quotes)
    def norm(s):
        if not s:
            return s
        for old, new in [("\u2014", "-"), ("\u2013", "-"), ("\u201c", '"'),
                          ("\u201d", '"'), ("\u2018", "'"), ("\u2019", "'")]:
            s = s.replace(old, new)
        return s

    data["title"] = norm(data["title"])
    data["subtitle"] = norm(data["subtitle"])
    data["exec_summary"] = norm(data["exec_summary"])
    data["elevator_pitch_body"] = norm(data["elevator_pitch_body"])
    data["takeaways"] = [norm(t) for t in data["takeaways"]]
    data["sections"] = [
        {"header": norm(s.get("header", "")), "body": norm(s.get("body", ""))}
        for s in data["sections"]
    ]
    data["faqs"] = [
        {"question": norm(f.get("question", "")), "answer": norm(f.get("answer", ""))}
        for f in data.get("faqs", [])
        if f.get("question") and f.get("answer")
    ][:3]  # max 3 FAQ pairs

    return data

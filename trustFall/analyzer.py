"""
trustFall — LLM diff scorer.
Compares two versions of a trust page and scores the change low/med/high.
"""
from __future__ import annotations

import difflib
import logging
import re
from dataclasses import dataclass
from typing import Optional

log = logging.getLogger(__name__)

# Phrases that strongly suggest a meaningful trust/AI change
HIGH_SIGNAL_PHRASES = [
    "train", "training data", "machine learning", "large language model", "llm",
    "ai model", "artificial intelligence", "generative", "opt out", "opt-out",
    "share your data", "share data with", "third party", "third-party",
    "sell your data", "data retention", "retain your data", "delete your data",
    "law enforcement", "government request", "subpoena",
    "license", "royalty", "intellectual property", "ownership",
]


@dataclass
class DiffResult:
    score: str                   # "low" | "medium" | "high"
    summary: str                 # plain English summary of what changed
    reasoning: str               # LLM's reasoning
    added_lines: list[str]
    removed_lines: list[str]
    high_signal_hits: list[str]  # which high-signal phrases appeared in changes


def _compute_diff(prev: str, curr: str) -> tuple[list[str], list[str]]:
    """Return added and removed lines between two text versions."""
    prev_lines = prev.splitlines()
    curr_lines = curr.splitlines()
    added, removed = [], []
    for line in difflib.unified_diff(prev_lines, curr_lines, lineterm="", n=0):
        if line.startswith("+") and not line.startswith("+++"):
            added.append(line[1:].strip())
        elif line.startswith("-") and not line.startswith("---"):
            removed.append(line[1:].strip())
    # Filter out blank lines
    added   = [l for l in added   if l]
    removed = [l for l in removed if l]
    return added, removed


def _check_high_signals(added: list[str], removed: list[str]) -> list[str]:
    """Find high-signal phrases in the changed lines."""
    changed_text = " ".join(added + removed).lower()
    return [p for p in HIGH_SIGNAL_PHRASES if p in changed_text]


async def score_diff(
    vendor_name: str,
    page_label: str,
    prev_text: str,
    curr_text: str,
) -> DiffResult:
    """
    Score the diff between two versions of a trust page.
    Returns a DiffResult with score, summary, and reasoning.
    """
    added, removed = _compute_diff(prev_text, curr_text)
    high_signals = _check_high_signals(added, removed)

    if not added and not removed:
        return DiffResult(
            score="low",
            summary="No meaningful text changes detected.",
            reasoning="Content hash differed but no line-level changes found — likely whitespace or formatting only.",
            added_lines=[],
            removed_lines=[],
            high_signal_hits=[],
        )

    # Build a compact diff for the LLM (cap at 3000 chars to save tokens)
    diff_excerpt = []
    if removed:
        diff_excerpt.append("REMOVED:\n" + "\n".join(f"- {l}" for l in removed[:30]))
    if added:
        diff_excerpt.append("ADDED:\n" + "\n".join(f"+ {l}" for l in added[:30]))
    diff_text = "\n\n".join(diff_excerpt)
    if len(diff_text) > 3000:
        diff_text = diff_text[:3000] + "\n... [truncated]"

    prompt = f"""You are a legal/privacy analyst reviewing changes to a vendor's trust or policy page.

Vendor: {vendor_name}
Page: {page_label}

The following text was changed on this page:

{diff_text}

{"NOTE: The following high-signal phrases appeared in the changes: " + ", ".join(high_signals) if high_signals else ""}

Your job:
1. Summarize what changed in 1-2 plain English sentences (write for a non-lawyer).
2. Score the change: low / medium / high
   - low: formatting, typos, nav changes, minor clarifications
   - medium: policy wording changes that may affect users but aren't alarming
   - high: changes to data usage, AI training, data sharing, opt-out rights, data retention, third-party sharing, or anything that materially affects user rights
3. Explain your reasoning in 1-2 sentences.

Respond in this exact format:
SCORE: <low|medium|high>
SUMMARY: <1-2 sentence summary>
REASONING: <1-2 sentence explanation>"""

    try:
        import litellm
        response = await litellm.acompletion(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=300,
        )
        content = response.choices[0].message.content.strip()

        score_match   = re.search(r'SCORE:\s*(low|medium|high)', content, re.IGNORECASE)
        summary_match = re.search(r'SUMMARY:\s*(.+?)(?=REASONING:|$)', content, re.IGNORECASE | re.DOTALL)
        reason_match  = re.search(r'REASONING:\s*(.+)', content, re.IGNORECASE | re.DOTALL)

        score     = score_match.group(1).lower()     if score_match   else _heuristic_score(high_signals, added, removed)
        summary   = summary_match.group(1).strip()   if summary_match else "Changes detected — review required."
        reasoning = reason_match.group(1).strip()    if reason_match  else content

        # Override to high if strong signals found regardless of LLM score
        if high_signals and score == "low":
            score = "medium"

        return DiffResult(
            score=score,
            summary=summary,
            reasoning=reasoning,
            added_lines=added,
            removed_lines=removed,
            high_signal_hits=high_signals,
        )

    except Exception as e:
        log.error("LLM scoring failed: %s", e)
        score = _heuristic_score(high_signals, added, removed)
        return DiffResult(
            score=score,
            summary=f"{len(added)} lines added, {len(removed)} lines removed. LLM scoring unavailable.",
            reasoning=f"Heuristic score based on change volume and signal phrases. Error: {e}",
            added_lines=added,
            removed_lines=removed,
            high_signal_hits=high_signals,
        )


def _heuristic_score(high_signals: list[str], added: list[str], removed: list[str]) -> str:
    """Fallback scoring without LLM."""
    if high_signals:
        return "high"
    total_changes = len(added) + len(removed)
    if total_changes > 20:
        return "medium"
    if total_changes > 5:
        return "low"
    return "low"

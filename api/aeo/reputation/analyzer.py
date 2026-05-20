"""LLM-driven reputation analysis — own business + competitor weaknesses.

Two async functions that take fetcher output and produce the shapes the
dashboard renders:

  analyze_own_reputation(reviews, business_name, perplexity_insight)
      Returns {strengths, weaknesses, summary} where each strength /
      weakness is {theme, detail, example, source}. Sources are
      resolved against the citation map prepended by the fetcher so
      the UI can attribute each item to Google / Yelp / BBB / etc.

  analyze_competitor_weaknesses(scored_competitors, country)
      Fetches competitor reviews + Perplexity insights in parallel,
      then runs a single LLM pass to extract common strengths /
      weaknesses across the local market. Returns {strengths, themes,
      avg_competitor_rating, opportunity_summary, competitors_analysed,
      reviews_analysed, perplexity_supplemented}.

Both use a local AIEngine instance configured via CONTENT_PROVIDER +
CONTENT_MODEL env vars (same defaults as the content generator). The
instance is module-level so it's created once at import time, matching
the pattern in coach/handler.py and content/generator.py.

Originally lived in api/aeo/router.py lines 1364-1609. Moved here during
Tier 4. Re-exported from router.py under the old underscored names.
"""
import asyncio
import json
import logging
import os
import re

from core.ai_engine import AIEngine

from .fetcher import fetch_competitor_perplexity, fetch_competitor_reviews


logger = logging.getLogger(__name__)

# Falls through to AI_PROVIDER + provider-specific *_MODEL env vars the
# same way content_llm in content/generator.py does — identical config so
# the two instances behave the same. We can consolidate to one shared
# instance once the audit engine moves out of router.py (Tier 6).
content_llm = AIEngine(
    provider=os.getenv("CONTENT_PROVIDER"),
    model=os.getenv("CONTENT_MODEL"),
)


async def analyze_competitor_weaknesses(scored_competitors: list[dict], country: str | None = None) -> dict:
    """Fetch reviews for all scored competitors that have a place_id, then run AI
    sentiment analysis to extract complaint themes. Returns a dict with:
      - themes: list of {theme, count, example} sorted by count desc
      - avg_competitor_rating: float
      - opportunity_summary: a short plain-language strategic opportunity string
      - competitors_analysed: int (how many had reviews)
    Returns an empty dict if no competitors have place_ids or reviews."""
    # All competitors are eligible — we resolve ChIJ place_ids via google_maps lookup
    competitors_with_ids = [c for c in scored_competitors if c.get("name")]
    if not competitors_with_ids:
        logger.debug("[AEO][W2] No competitors — skipping weak-point analysis")
        return {}

    # Fetch Google Maps reviews AND Perplexity multi-source insights in parallel
    review_results, perplexity_raw = await asyncio.gather(
        asyncio.gather(
            *[fetch_competitor_reviews(c["name"], c.get("city"), country) for c in competitors_with_ids],
            return_exceptions=True,
        ),
        asyncio.gather(
            *[fetch_competitor_perplexity(c["name"], c.get("city") or "") for c in competitors_with_ids],
            return_exceptions=True,
        ),
    )

    all_reviews: list[dict] = []
    ratings: list[float] = []
    competitors_analysed = 0
    for comp, reviews in zip(competitors_with_ids, review_results):
        if isinstance(reviews, Exception) or not reviews:
            continue
        competitors_analysed += 1
        all_reviews.extend(reviews)
        comp_rating = comp.get("rating")
        if comp_rating:
            ratings.append(float(comp_rating))

    # Collect valid Perplexity insights (non-empty, non-exception strings)
    perplexity_insights: list[tuple[str, str]] = []
    for comp, insight in zip(competitors_with_ids, perplexity_raw):
        if isinstance(insight, str) and insight.strip():
            perplexity_insights.append((comp["name"], insight.strip()))

    avg_rating = round(sum(ratings) / len(ratings), 1) if ratings else None

    if not all_reviews and not perplexity_insights:
        logger.debug("[AEO][W2] No competitor reviews or Perplexity insights — skipping analysis")
        return {}

    # Build prompt sections
    review_section = ""
    if all_reviews:
        snippets_for_prompt = all_reviews[:40]
        review_text = "\n".join(
            f"- ({r['rating']}★) {r['snippet']}" for r in snippets_for_prompt if r.get("snippet")
        )
        review_section = f"\nGoogle Reviews:\n{review_text}"

    perplexity_section = ""
    if perplexity_insights:
        insight_blocks = "\n\n".join(
            f"About {name}:\n{insight[:800]}" for name, insight in perplexity_insights
        )
        perplexity_section = f"\n\nMulti-source web insights (Yelp, BBB, RateMDs, etc.):\n{insight_blocks}"

    prompt = f"""You are analyzing competitor businesses in the same local service category.
Identify what customers consistently praise (strengths) and what they complain about (weaknesses).
For each theme, estimate how many sources or reviews mention it.
{review_section}{perplexity_section}

Respond ONLY with a JSON object in this exact format (no markdown, no explanation):
{{
  "strengths": [
    {{"theme": "Friendly and knowledgeable staff", "count": 12, "example": "staff took time to explain everything"}}
  ],
  "weaknesses": [
    {{"theme": "Long wait times", "count": 8, "example": "had to wait 45 minutes past my appointment"}},
    {{"theme": "Parking difficulties", "count": 5, "example": "no parking available on site"}}
  ],
  "opportunity_summary": "Most competitors struggle with [X] — you can stand out by [Y]."
}}

Return at most 3 strengths and at most 4 weaknesses. Only include genuine patterns with 2+ mentions."""

    try:
        raw = await content_llm.generate(
            prompt=prompt,
            max_tokens=400,
            temperature=0.2,
        )
        # Strip markdown code fences if present
        cleaned = re.sub(r'^```(?:json)?\s*|\s*```$', '', raw.strip(), flags=re.MULTILINE).strip()
        parsed = json.loads(cleaned)
        strengths = parsed.get("strengths", [])
        themes = parsed.get("weaknesses", parsed.get("themes", []))  # compat: old prompt used "themes"
        opportunity_summary = parsed.get("opportunity_summary", "")
        logger.info(
            f"[AEO][W2] Analysed {competitors_analysed} competitors, "
            f"{len(all_reviews)} reviews, {len(perplexity_insights)} Perplexity insights "
            f"→ {len(strengths)} strengths, {len(themes)} weaknesses"
        )
        return {
            "strengths": strengths,
            "themes": themes,
            "avg_competitor_rating": avg_rating,
            "opportunity_summary": opportunity_summary,
            "competitors_analysed": competitors_analysed,
            "reviews_analysed": len(all_reviews),
            "perplexity_supplemented": len(perplexity_insights) > 0,
        }
    except Exception as e:
        logger.warning(f"[AEO][W2] AI analysis failed: {e}")
        return {}


async def analyze_own_reputation(reviews: list[dict], business_name: str, perplexity_insight: str = "") -> dict:
    """AI analysis of own business reviews — extracts strengths and weaknesses with examples and sources."""
    review_text = "\n".join(
        f"- ({r['rating']}★) {r['snippet']}" for r in reviews[:60] if r.get("snippet")
    )
    has_perplexity = bool(perplexity_insight.strip())
    review_section = f"\nGoogle Reviews:\n{review_text}" if review_text else ""
    perplexity_section = f"\n\nMulti-source web signals (Yelp, Yellow Pages, BBB, and other directories):\n{perplexity_insight[:2500]}" if has_perplexity else ""
    source_note = (
        'For signals from Google Reviews use "source": "Google". '
        'For signals from the multi-source section, use the ACTUAL platform name mentioned in that text '
        '(e.g. "Yellow Pages", "Yelp", "BBB", "RateMDs", "HomeStars") — not just "Web". '
        'If the platform is unclear, use "Web".'
    ) if has_perplexity else 'Use "source": "Google" for all items.'
    prompt = f"""You are analyzing customer feedback for {business_name}.
Identify the main strengths (things customers consistently praise) and weaknesses (recurring complaints).
{review_section}{perplexity_section}

For each theme, include:
- "theme": a short label (4-7 words)
- "detail": a plain-English sentence explaining WHAT customers actually experienced (be specific — avoid vague words like "atmosphere")
- "example": a short verbatim-style quote or paraphrase from an actual review (max 15 words)
- "source": where this signal was found. {source_note}

Respond ONLY with a JSON object in this exact format (no markdown, no explanation):
{{
  "strengths": [
    {{"theme": "Fast and friendly service", "detail": "Staff greeted patients immediately and completed appointments ahead of schedule.", "example": "In and out in 30 minutes — incredibly efficient", "source": "Google"}},
    {{"theme": "Personal attention to each patient", "detail": "The physiotherapist spent enough time to understand and diagnose each patient's problem.", "example": "Gave personal attention and understood my issue", "source": "Yellow Pages"}}
  ],
  "weaknesses": [
    {{"theme": "Long wait times", "detail": "Patients report waiting 20-40 minutes past their scheduled appointment time.", "example": "Waited 40 min past my appointment", "source": "Google"}}
  ],
  "summary": "Customers love the friendly staff and personal care, but some mention wait times as a pain point."
}}

Return 2-5 strengths and 0-3 weaknesses. For strengths, only include patterns with 2+ mentions. For weaknesses, include any specific complaint that appears even once — a single negative experience is worth flagging to the business owner. Do not fabricate weaknesses if none appear in the data."""
    # Log a sample of the reviews being fed to the LLM so we can diagnose gaps
    low_star = [r for r in reviews if r.get("rating") and r["rating"] <= 3]
    logger.info(
        f"[AEO][OWN] Sending {len(reviews)} reviews to LLM ({len(low_star)} ≤3★), "
        f"perplexity={'yes' if has_perplexity else 'no'} for '{business_name}'"
    )
    if low_star:
        for r in low_star[:5]:
            logger.info(f"[AEO][OWN]  ≤3★ review: ({r.get('rating')}★) {r.get('snippet','')[:120]}")
    try:
        raw = await content_llm.generate(
            prompt=prompt,
            max_tokens=900,
            temperature=0.2,
        )
        cleaned = re.sub(r'^```(?:json)?\s*|\s*```$', '', raw.strip(), flags=re.MULTILINE).strip()
        parsed = json.loads(cleaned)
        weaknesses = parsed.get("weaknesses", [])
        logger.info(f"[AEO][OWN] LLM returned {len(parsed.get('strengths',[]))} strengths, {len(weaknesses)} weaknesses for '{business_name}'")
        if weaknesses:
            for w in weaknesses:
                logger.info(f"[AEO][OWN]  weakness: {w.get('theme')} — {w.get('detail','')[:80]}")
        return {
            "strengths": parsed.get("strengths", []),
            "weaknesses": weaknesses,
            "summary": parsed.get("summary", ""),
        }
    except Exception as e:
        logger.warning(f"[AEO][OWN] AI analysis failed: {e}")
        return {"strengths": [], "weaknesses": [], "summary": ""}

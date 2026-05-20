"""5-pillar scoring + competitor AI-citation matching.

Pure functions that take collected audit data and produce numeric scores
plus the breakdown the dashboard displays.

The three callable surfaces:

- `calculate_score(business, perplexity, google, website_check, chatgpt)`
  — main score for the audited business. Returns `{total, breakdown}`.
- `score_competitor(competitor, website_check, ...mentions)` — same
  formula applied to a competitor. Lets us draw the bar chart that
  compares the owner to up to 5 nearby competitors.
- `match_competitor_ai_citations(competitors, perplexity, google, chatgpt)`
  — pure text-scan over data we already paid for. Returns per-competitor
  hit flags. Costs $0 in API spend.

Two small helpers (`competitor_key`, `name_matches`) live here too since
they're tightly coupled to the scoring logic, but are also re-used by
competitor-list code in router.py (until that moves too).

The formula is duplicated between `calculate_score` and `score_competitor`
— if you change one, change the other. The duplication is intentional:
the competitor path doesn't always have full data, so it accepts
optional inputs and tracks `has_full_data` separately.

Originally lived in `api/aeo/router.py` lines 275-285 (`_name_matches`),
980-983 (`_competitor_key`), and 1015-1184 (the three scoring fns).
"""
import logging


logger = logging.getLogger(__name__)


def name_matches(candidate: str, search_name: str) -> bool:
    """Fuzzy business name match — requires at least 2 significant tokens to appear.
    Handles cases where SerpApi abbreviates the name (e.g. 'James Snow Physio'
    vs 'James Snow Physiotherapy & Rehabilitation Centre')."""
    tokens = [t for t in search_name.lower().split() if len(t) > 3]
    if not tokens:
        return search_name.lower() in candidate.lower()
    candidate_lower = candidate.lower()
    matches = sum(1 for t in tokens if t in candidate_lower)
    return matches >= min(2, len(tokens))


def competitor_key(competitor: dict) -> str | None:
    """Stable identifier for a competitor across the audit — place_id preferred, else lowered name."""
    return competitor.get("place_id") or (competitor.get("name") or "").strip().lower() or None


def match_competitor_ai_citations(
    competitors: list[dict],
    perplexity_result: dict,
    google_result: dict,
    chatgpt_result: dict,
) -> dict[str, dict]:
    """For each competitor, check whether their name appears in any of the per-query
    Perplexity, Google AI Overview, or ChatGPT answers we already fetched.
    Cost: $0 — pure text scanning over data we paid for during the user's audit.
    Returns a dict keyed by competitor_key() → {perplexity_mentioned, google_ai_mentioned, chatgpt_mentioned}."""
    perplexity_texts = [
        r.get("answer", "") for r in perplexity_result.get("per_query", [])
    ]
    google_ai_texts = [
        (r.get("ai_overview") or {}).get("text", "") for r in google_result.get("per_query", [])
    ]
    chatgpt_texts = [
        r.get("answer", "") for r in chatgpt_result.get("per_query", [])
    ]

    output: dict[str, dict] = {}
    for c in competitors:
        key = competitor_key(c)
        name = (c.get("name") or "").strip()
        if not key or not name:
            continue
        perplexity_hit = any(text and name_matches(text, name) for text in perplexity_texts)
        google_ai_hit  = any(text and name_matches(text, name) for text in google_ai_texts)
        chatgpt_hit    = any(text and name_matches(text, name) for text in chatgpt_texts)
        output[key] = {
            "perplexity_mentioned": perplexity_hit,
            "google_ai_mentioned":  google_ai_hit,
            "chatgpt_mentioned":    chatgpt_hit,
        }
    hits_per = sum(1 for v in output.values() if v["perplexity_mentioned"])
    hits_g   = sum(1 for v in output.values() if v["google_ai_mentioned"])
    hits_gpt = sum(1 for v in output.values() if v["chatgpt_mentioned"])
    logger.info(f"[AEO][COMP] AI citations: {hits_per}/{len(output)} Perplexity, {hits_g}/{len(output)} Google AI, {hits_gpt}/{len(output)} ChatGPT")
    return output


def calculate_score(business: dict, perplexity: dict, google: dict, website_check: dict, chatgpt: dict) -> dict:
    # If the formula here changes, update score_competitor() to match.
    # ai_citation max = 18: ChatGPT 6 + Perplexity 6 + Google AI 6
    kg = google["knowledge_graph"]
    lp = google["local_pack"]

    effective_rating = kg.get("rating") or lp.get("rating") or 0
    effective_reviews = kg.get("reviews_count") or lp.get("reviews") or 0
    has_gbp = kg["found"] or lp["present"]

    # Sometimes Google returns a Local Pack entry but no Knowledge Graph
    # card for the same business — happens often on category searches
    # (e.g. "dentist Burlington") vs branded searches. When that happens,
    # KG fields are null even though the actual GBP profile has them.
    # We must NOT penalize the owner for fields Google chose not to render
    # in this response — they look at their real GBP, see everything's
    # there, and lose trust in our score.
    #
    # If the business is found on Google (KG or LP), assume the GBP has
    # a category (Google requires one for the listing to exist) and
    # contact info (we also fall back to business.website from onboarding).
    has_category    = bool(kg.get("type")) or has_gbp
    has_contact     = bool(kg.get("website") or kg.get("phone") or business.get("website")) or has_gbp

    gbp = 0
    if has_gbp:       gbp += 10
    if effective_rating: gbp += 5
    if has_category:  gbp += 5
    if has_contact:   gbp += 5

    reviews = 0
    if effective_reviews >= 50: reviews += 12
    elif effective_reviews >= 10: reviews += 6
    if effective_rating >= 4.5: reviews += 10
    elif effective_rating >= 4.0: reviews += 5

    web = 0
    if website_check["reachable"]: web += 8
    if website_check["has_local_business_schema"]: web += 6
    if website_check["has_faq_schema"]: web += 6

    local = 0
    if google["local_pack"]["present"]: local += 10
    if google["organic"]["present"]: local += 5

    ai = 0
    if chatgpt["mentioned"]:               ai += 6
    if perplexity["mentioned"]:            ai += 6
    if google["ai_overview"]["mentioned"]: ai += 6

    total = gbp + reviews + web + local + ai
    return {
        "total": total,
        "breakdown": {
            "gbp": gbp,
            "reviews": reviews,
            "website": web,
            "local_search": local,
            "ai_citation": ai,
        },
    }


def score_competitor(
    competitor: dict,
    website_check: dict | None = None,
    perplexity_mentioned: bool | None = None,
    google_ai_mentioned: bool | None = None,
    chatgpt_mentioned: bool | None = None,
) -> dict:
    """Score a competitor using the same 5-pillar formula as calculate_score().
    If the formula in calculate_score() changes, update this function to match.

    Competitors are sourced from the SerpApi local pack, so local_pack presence is True
    by definition (worth 10 Local Search points). website_check and *_mentioned are
    optional — pass None when the data hasn't been collected yet, which leaves the
    corresponding pillar at 0 and sets has_full_data=False on the result."""
    rating = competitor.get("rating") or 0
    reviews_count = competitor.get("reviews") or 0

    # ─── GBP pillar (max 25) ─────────────────────────────────────
    gbp = 10  # in local pack ⇒ has_gbp
    if rating: gbp += 5
    if competitor.get("type"): gbp += 5
    if competitor.get("website") or competitor.get("phone"): gbp += 5

    # ─── Reviews pillar (max 22) ─────────────────────────────────
    rev = 0
    if reviews_count >= 50: rev += 12
    elif reviews_count >= 10: rev += 6
    if rating >= 4.5: rev += 10
    elif rating >= 4.0: rev += 5

    # ─── Website pillar (max 20) ─────────────────────────────────
    web = 0
    if website_check is not None:
        if website_check.get("reachable"):                  web += 8
        if website_check.get("has_local_business_schema"):  web += 6
        if website_check.get("has_faq_schema"):             web += 6

    # ─── Local Search pillar (max 15) ────────────────────────────
    local = 10

    # ─── AI Citation pillar (max 18): ChatGPT 6 + Perplexity 6 + Google AI 6 ──
    ai = 0
    if chatgpt_mentioned is True:    ai += 6
    if perplexity_mentioned is True: ai += 6
    if google_ai_mentioned is True:  ai += 6

    total = gbp + rev + web + local + ai
    has_full_data = (
        website_check is not None
        and perplexity_mentioned is not None
        and google_ai_mentioned is not None
        and chatgpt_mentioned is not None
    )

    return {
        "total": total,
        "breakdown": {
            "gbp":          gbp,
            "reviews":      rev,
            "website":      web,
            "local_search": local,
            "ai_citation":  ai,
        },
        "has_full_data": has_full_data,
    }

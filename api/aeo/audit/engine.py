"""Audit orchestration — the main pipeline that turns a business row into
a scored audit result.

This is the top of the audit stack. Everything below (`signals`, `geo`,
`scoring`, `recommendations`, `queries`, `verticals`, `maps`, `perplexity`,
`website`) is a pure-ish helper module that this file glues together.

Public surface:

  * `normalize_business_type(raw_type, business_name)` — LLM-normalises
    the free-form business category to a short generic search phrase.
  * `run_perplexity_multi` / `run_chatgpt_multi` / `run_google_multi` —
    fan-out helpers that issue every audit query against one AI engine
    and aggregate the per-query results.
  * `_run_audit_core(business)` — the full pipeline. Calls website
    check, the three multi runners in parallel, scoring, recommendations,
    competitor scoring, weak-point mining, and citation-gap analysis.
    Returns the dict that gets persisted to `aeo_audits.raw_results`.

Two LLM clients live at module level:

  * `audit_llm` — measures whether the audited business appears in a
    ChatGPT answer. AUDIT_PROVIDER should stay 'openai' so the
    "ChatGPT" pillar continues to mean "ChatGPT".
  * `content_llm` — normalises business types and (elsewhere) drives
    reputation analysis + content generation. Configured via
    CONTENT_PROVIDER + CONTENT_MODEL with fall-through to AI_PROVIDER.

Originally lived in api/aeo/router.py lines 98-918 (interleaved with
small helpers that are now in dedicated modules). Moved here during
Tier 6 of the refactor. Re-exported from router.py under the same
names so existing endpoint handlers (`run_audit`, `get_recommendations`,
`get_own_reputation`, `cron_monthly_audit`) keep resolving them via
`from aeo.router import ...`.
"""
import asyncio
import logging
import os
import re
from datetime import datetime, timezone

from core.ai_engine import AIEngine
from core.database import supabase_admin
from integrations import serpapi as serpapi_client

from .geo import (
    address_country_gl,
    country_to_gl,
    extract_search_name,
    province_to_gl,
)
from .maps import parse_relative_date
from .perplexity import _perplexity_one
from .queries import build_queries
from .recommendations import generate_recommendations
from .scoring import (
    calculate_score,
    competitor_key,
    match_competitor_ai_citations,
    name_matches,
    score_competitor,
)
from .signals import KNOWN_TYPES, extract_text_signals
from .verticals import (
    detect_directory_presence,
    is_healthcare_business,
    is_trades_business,
)
from .website import check_website


logger = logging.getLogger(__name__)


# ─── Per-workload LLM clients ─────────────────────────────────────────────
# AUDIT_PROVIDER + AUDIT_MODEL    -> ChatGPT pillar query (default
#     openai/gpt-4o-mini). Caveat: switching this changes the semantic
#     meaning of the "ChatGPT" AI Citations sub-pillar.
# CONTENT_PROVIDER + CONTENT_MODEL -> normalize_business_type only on
#     this module. Same env config is also read by content/generator.py
#     and reputation/analyzer.py — they all behave identically.
audit_llm = AIEngine(
    provider=os.getenv("AUDIT_PROVIDER", "openai"),
    model=os.getenv("AUDIT_MODEL", "gpt-4o-mini"),
)
content_llm = AIEngine(
    provider=os.getenv("CONTENT_PROVIDER"),
    model=os.getenv("CONTENT_MODEL"),
)
logger.info(
    f"[LLM] audit={audit_llm.provider}/{audit_llm._model} | "
    f"content={content_llm.provider}/{content_llm._model}"
)


# ─── Review-recency probe ─────────────────────────────────────────────────

async def _check_review_recency(place_id: str, country: str | None = None) -> dict:
    """Check when the most recent Google review was posted using SerpApi google_maps_reviews.
    Only called when the KG returned a place_id. Considers reviews stale after 90 days."""
    params = {
        "engine": "google_maps_reviews",
        "place_id": place_id,
        "hl": "en",
        "sort_by": "newestFirst",
    }
    gl = country_to_gl(country)
    if gl:
        params["gl"] = gl
    try:
        data = await serpapi_client.search(params, timeout=30.0)
        reviews = data.get("reviews", [])
        if not reviews:
            logger.debug(f"[AEO][RECENCY] No reviews returned for place_id={place_id}")
            return {"checked": True, "recent": False, "days_since_last": None, "last_review_date": None}
        latest_date_str = reviews[0].get("date")
        days = parse_relative_date(latest_date_str)
        recent = days is not None and days <= 90
        logger.debug(f"[AEO][RECENCY] place_id={place_id} latest='{latest_date_str}' days={days} recent={recent}")
        return {"checked": True, "recent": recent, "days_since_last": days, "last_review_date": latest_date_str}
    except Exception as e:
        logger.warning(f"[AEO][RECENCY] Failed for place_id={place_id}: {e}")
        return {"checked": False, "recent": None, "days_since_last": None, "last_review_date": None}


# ─── Business-type normalization ──────────────────────────────────────────

async def normalize_business_type(raw_type: str, business_name: str) -> str:
    if raw_type.lower() in KNOWN_TYPES:
        return raw_type
    # The business name is provided ONLY as disambiguation hint. We forbid the LLM
    # from echoing it back, because earlier prompts produced things like
    # "Mandi Afandi restaurant" which then poisoned every downstream search query
    # (searching for the user's own business → zero competitors found).
    result = await content_llm.generate(
        prompt=(
            f'Translate the business category "{raw_type}" into a short generic '
            f'English search phrase, max 4 words (e.g. "physiotherapy clinic", '
            f'"italian restaurant", "auto repair shop"). '
            f'Context (do NOT repeat in answer): business name is "{business_name}". '
            f'Reply with ONLY the generic category phrase. Do NOT include the '
            f'business name, any proper noun, or any city name.'
        ),
        max_tokens=20,
        temperature=0.0,
    )
    cleaned = result.strip().strip('"').strip("'")
    # Defensive scrub: if the LLM still echoed the business name, strip it out.
    # Token-by-token (case-insensitive) so "Mandi Afandi restaurant" becomes "restaurant".
    name_tokens = {t.lower() for t in business_name.split() if len(t) > 2}
    if name_tokens:
        kept = [w for w in cleaned.split() if w.lower() not in name_tokens]
        cleaned = " ".join(kept).strip() or raw_type
    return cleaned


# ─── Per-engine fan-out ───────────────────────────────────────────────────

async def run_perplexity_multi(
    business_name: str,
    business_type_en: str,
    city: str,
    province: str,
    postal_code: str | None = None,
    is_trades: bool = False,
    is_healthcare: bool = False,
    dietary_tags: list[str] | None = None,
    service_tags: list[str] | None = None,
    cuisine_hint: str | None = None,
    cuisine_hint_parent: str | None = None,
) -> dict:
    results = []
    for query in build_queries(business_type_en, city, province, postal_code, is_trades, is_healthcare,
                                business_name=business_name, dietary_tags=dietary_tags, service_tags=service_tags,
                                cuisine_hint=cuisine_hint, cuisine_hint_parent=cuisine_hint_parent):
        try:
            results.append(await _perplexity_one(business_name, query, city))
        except Exception as e:
            print(f"[AEO] Perplexity failed for '{query}': {e}")
            results.append({"mentioned": False, "snippet": None, "answer": "", "query": query})

    mentioned = any(r["mentioned"] for r in results)
    snippet = next((r["snippet"] for r in results if r["mentioned"]), None)
    return {
        "mentioned": mentioned,
        "snippet": snippet,
        "queries": [r["query"] for r in results],
        "per_query": results,
    }


async def _chatgpt_one(business_name: str, query: str, city: str) -> dict:
    """ChatGPT pillar measurement. Uses `audit_llm` (configured via
    AUDIT_PROVIDER + AUDIT_MODEL env, default openai/gpt-4o-mini).
    For semantic correctness AUDIT_PROVIDER should stay 'openai' since
    this measures whether the business is cited *by ChatGPT specifically*."""
    answer = await audit_llm.generate(
        prompt=query,
        system_prompt=(
            "You are a local business search assistant. "
            "A user is asking you to recommend businesses in their area. "
            "Answer based on your training knowledge, listing specific business names where you know them."
        ),
        max_tokens=500,
        temperature=0.0,
    )
    mentioned = extract_search_name(business_name, city).lower() in answer.lower()
    snippet = answer[:500] if mentioned else None
    print(f"[AEO] ChatGPT '{query}' → mentioned={mentioned}")
    return {"mentioned": mentioned, "snippet": snippet, "answer": answer[:2000], "query": query}


async def run_chatgpt_multi(
    business_name: str,
    business_type_en: str,
    city: str,
    province: str,
    postal_code: str | None = None,
    is_trades: bool = False,
    is_healthcare: bool = False,
    dietary_tags: list[str] | None = None,
    service_tags: list[str] | None = None,
    cuisine_hint: str | None = None,
    cuisine_hint_parent: str | None = None,
) -> dict:
    results = []
    for query in build_queries(business_type_en, city, province, postal_code, is_trades, is_healthcare,
                                business_name=business_name, dietary_tags=dietary_tags, service_tags=service_tags,
                                cuisine_hint=cuisine_hint, cuisine_hint_parent=cuisine_hint_parent):
        try:
            results.append(await _chatgpt_one(business_name, query, city))
        except Exception as e:
            print(f"[AEO] ChatGPT failed for '{query}': {e}")
            results.append({"mentioned": False, "snippet": None, "answer": "", "query": query})

    mentioned = any(r["mentioned"] for r in results)
    snippet = next((r["snippet"] for r in results if r["mentioned"]), None)
    return {
        "mentioned": mentioned,
        "snippet": snippet,
        "queries": [r["query"] for r in results],
        "per_query": results,
    }


# ─── SerpApi response parsers ─────────────────────────────────────────────

def check_organic(data: dict, search_name: str, website: str | None) -> dict:
    results = data.get("organic_results", [])
    domain = None
    if website:
        domain = re.sub(r'^https?://(www\.)?', '', website).rstrip('/').lower()
    for r in results:
        title = r.get("title", "").lower()
        link = r.get("link", "").lower()
        if name_matches(r.get("title", ""), search_name) or (domain and domain in link):
            return {"present": True, "position": r.get("position")}
    return {"present": False, "position": None}


def check_knowledge_graph(data: dict, search_name: str) -> dict:
    kg = data.get("knowledge_graph")
    if not kg:
        logger.debug("[AEO][KG] No knowledge_graph key in SerpApi response")
        return {"found": False, "title": None, "rating": None, "reviews_count": None, "type": None, "website": None, "phone": None}
    logger.debug(f"[AEO][KG] Raw knowledge_graph keys: {list(kg.keys())}")
    logger.debug(f"[AEO][KG] title='{kg.get('title')}' rating={kg.get('rating')} user_reviews={kg.get('user_reviews')} review_count={kg.get('review_count')} reviews_count={kg.get('reviews_count')} reviews_type={type(kg.get('reviews')).__name__}")
    if not name_matches(kg.get("title", ""), search_name):
        logger.debug(f"[AEO][KG] Title mismatch: search_name='{search_name}' not in kg_title='{kg.get('title')}'")
        return {"found": False, "title": None, "rating": None, "reviews_count": None, "type": None, "website": None, "phone": None}
    # SerpApi field names vary by query type:
    #   "review_count" → integer (most common in name-specific queries)
    #   "user_reviews" → string like "256" or "1,200+" (some query types)
    #   "reviews_count" → integer (older SerpApi versions)
    #   "reviews" → URL string (link to Google reviews page — NOT the count, skip it)
    raw_reviews = (
        kg.get("review_count")       # preferred: always an int
        or kg.get("user_reviews")    # string, parse below
        or kg.get("reviews_count")   # fallback integer
        # NOTE: kg.get("reviews") is a URL string — intentionally excluded
    )
    logger.debug(f"[AEO][KG] raw_reviews resolved to: {raw_reviews!r}")
    try:
        reviews_count = int(str(raw_reviews).replace(",", "").replace("+", "").strip()) if raw_reviews else None
    except (ValueError, TypeError):
        reviews_count = None
    logger.debug(f"[AEO][KG] parsed reviews_count={reviews_count}")
    return {
        "found": True,
        "place_id": kg.get("place_id"),
        "title": kg.get("title"),
        "rating": kg.get("rating"),
        "reviews_count": reviews_count,
        "type": kg.get("type"),
        "website": kg.get("website"),
        "phone": kg.get("phone"),
    }


def check_local_pack(data: dict, search_name: str) -> dict:
    places = data.get("local_results", {}).get("places", [])
    logger.debug(f"[AEO][LP] {len(places)} places in local pack. search_name='{search_name}'")
    for i, place in enumerate(places):
        logger.debug(f"[AEO][LP] place[{i}] title='{place.get('title')}' rating={place.get('rating')} reviews={place.get('reviews')}")
        if name_matches(place.get("title", ""), search_name):
            result = {"present": True, "position": i + 1, "rating": place.get("rating"), "reviews": place.get("reviews")}
            logger.debug(f"[AEO][LP] MATCH found: {result}")
            return result
    logger.debug(f"[AEO][LP] No match found for '{search_name}'")
    return {"present": False, "position": None, "rating": None, "reviews": None}


# ─── Google search runners ────────────────────────────────────────────────

async def _google_one(
    business_name: str,
    query: str,
    city: str,
    website: str | None,
    province: str | None = None,
    country: str | None = None,
    competitor_scope: str = "local",
) -> dict:
    # Imported inside the function so the import graph stays one-way
    # (engine → competitors). competitors.py also imports from audit/
    # — keeping this at function scope avoids any chance of cycles
    # during future refactors of either module.
    from ..competitors import extract_competitors

    # `competitor_scope` controls how broadly we search:
    #   local   -> location=city, gl=country  (default; matches existing behaviour)
    #   country -> no location, gl=country    (broader; thin local market)
    #   global  -> no location, no gl         (truly worldwide; SaaS-style)
    #
    # NOTE for `local` scope: location must be just `city`. SerpApi feeds it to
    # Google Places which only reliably matches bare city names. Adding province
    # ("Milton, Ontario") returns a different local pack that breaks KG and
    # competitor detection. Cross-country leakage (e.g. "Milton" matching Milton
    # Keynes, UK) is handled downstream by the address_country_gl cross-border
    # filter in run_google_multi.
    params: dict = {
        "engine": "google",
        "q": query,
        "hl": "en",
    }
    if competitor_scope == "local":
        params["location"] = city
    gl = country_to_gl(country) or province_to_gl(province)
    if gl and competitor_scope != "global":
        params["gl"] = gl
    data = await serpapi_client.search(params, timeout=30.0)

    search_name = extract_search_name(business_name, city)
    logger.debug(f"[AEO][SERP] query='{query}' search_name='{search_name}'")
    logger.debug(f"[AEO][SERP] Top-level keys in response: {list(data.keys())}")
    ai_overview = data.get("ai_overview", {})
    text_blocks = ai_overview.get("text_blocks", []) if ai_overview else []
    answer = " ".join(b.get("snippet", "") for b in text_blocks if b.get("snippet"))
    ai_mentioned = bool(answer) and search_name.lower() in answer.lower()

    local = check_local_pack(data, search_name)
    organic = check_organic(data, search_name, website)
    kg = check_knowledge_graph(data, search_name)
    competitors = extract_competitors(data, search_name, user_city=city, user_region=province, user_country=country, max_count=5)
    logger.info(f"[AEO] Google '{query}' → ai={ai_mentioned} local={local['present']}(reviews={local.get('reviews')}) organic={organic['present']} kg={kg['found']}(reviews={kg.get('reviews_count')}) competitors={len(competitors)}")

    return {
        "ai_overview": {
            "mentioned": ai_mentioned,
            "snippet":   answer[:500] if ai_mentioned else None,
            "text":      answer[:2000] if answer else "",
        },
        "local_pack": local,
        "organic": organic,
        # Trimmed raw organic results for citation-gap analysis (W3).
        # Top 10 per query is enough to detect directory listings without
        # bloating raw_results JSONB.
        "organic_results_raw": [
            {"link": r.get("link"), "title": r.get("title"), "snippet": r.get("snippet")}
            for r in (data.get("organic_results", []) or [])[:10]
        ],
        "knowledge_graph": kg,
        "competitors": competitors,
        "query": query,
    }


async def _google_name_lookup(
    business_name: str,
    city: str,
    website: str | None,
    province: str | None = None,
    country: str | None = None,
) -> dict:
    """4th SerpApi call: search the exact business name to force a knowledge_graph response.
    Used only to fill in review count / rating when category queries don't return them."""
    # Use cleaned name + city to avoid doubling the city when name already ends with "in {city}"
    clean_name = extract_search_name(business_name, city)
    query = f"{clean_name} {city}"
    try:
        return await _google_one(business_name, query, city, website, province, country)
    except Exception as e:
        print(f"[AEO] Google name-lookup failed for '{query}': {e}")
        return {
            "ai_overview": {"mentioned": False, "snippet": None, "text": ""},
            "local_pack": {"present": False, "position": None, "rating": None, "reviews": None},
            "organic": {"present": False, "position": None},
            "organic_results_raw": [],
            "knowledge_graph": {"found": False, "title": None, "rating": None, "reviews_count": None, "type": None, "website": None, "phone": None},
            "competitors": [],
            "query": query,
        }


async def _fetch_own_gbp_via_maps(business_name: str, city: str, country: str | None = None) -> dict | None:
    """Reliable GBP profile fetch via the `google_maps` engine.

    The `google` engine's knowledge_graph is unreliable: many legitimate
    businesses appear ONLY in the local pack and never get a KG card —
    even on a branded name search (Burlington Family Dentists is the
    canonical example: rating + reviews show via the local pack, but
    title/category/website/phone are blank because there's no KG to read
    them from). google_maps `place_results` reliably returns the full
    profile for a known business, so we fall back to it when the
    google-engine queries (including the branded lookup) produced no KG.

    Returns a knowledge_graph-shaped dict (so it can be slotted straight
    into `kg_data`) or None on miss. The returned place_id is ChIJ-format,
    which also lets the downstream review-recency check run for these
    businesses (it was previously skipped whenever the KG was absent)."""
    clean_name = extract_search_name(business_name, city)
    query = f"{clean_name} {city}" if city else clean_name
    params: dict[str, str] = {"engine": "google_maps", "q": query, "hl": "en"}
    gl = country_to_gl(country)
    if gl:
        params["gl"] = gl
    try:
        data = await serpapi_client.search(params, timeout=20.0)
    except Exception as e:
        logger.warning(f"[AEO][GBP] google_maps profile fetch failed for '{business_name}': {e}")
        return None

    # A branded q-search usually returns a single `place_results`. When it
    # returns a `local_results` list instead, take the first entry whose
    # name fuzzy-matches so we don't grab a competitor by mistake.
    place = data.get("place_results") or {}
    if not place:
        for r in data.get("local_results", []) or []:
            if name_matches(r.get("title", ""), clean_name):
                place = r
                break
    if not place or not place.get("title"):
        return None

    raw_reviews = place.get("reviews")
    try:
        reviews_count = int(str(raw_reviews).replace(",", "").replace("+", "").strip()) if raw_reviews else None
    except (ValueError, TypeError):
        reviews_count = None

    return {
        "found": True,
        "place_id": place.get("place_id"),
        "title": place.get("title"),
        "rating": place.get("rating"),
        "reviews_count": reviews_count,
        "type": place.get("type") or (place.get("types") or [None])[0],
        "website": place.get("website") or (place.get("links") or {}).get("website"),
        "phone": place.get("phone"),
    }


async def run_google_multi(
    business_name: str,
    business_type_en: str,
    city: str,
    province: str,
    website: str | None,
    country: str | None = None,
    postal_code: str | None = None,
    is_trades: bool = False,
    is_healthcare: bool = False,
    competitor_scope: str = "local",
    dietary_tags: list[str] | None = None,
    service_tags: list[str] | None = None,
    cuisine_hint: str | None = None,
    cuisine_hint_parent: str | None = None,
) -> dict:
    results = []
    for query in build_queries(business_type_en, city, province, postal_code, is_trades, is_healthcare,
                                business_name=business_name, dietary_tags=dietary_tags, service_tags=service_tags,
                                cuisine_hint=cuisine_hint, cuisine_hint_parent=cuisine_hint_parent):
        try:
            results.append(await _google_one(
                business_name, query, city, website, province, country,
                competitor_scope=competitor_scope,
            ))
        except Exception as e:
            print(f"[AEO] Google failed for '{query}': {e}")
            results.append({
                "ai_overview": {"mentioned": False, "snippet": None, "text": ""},
                "local_pack": {"present": False, "position": None, "rating": None, "reviews": None},
                "organic": {"present": False, "position": None},
                "knowledge_graph": {"found": False, "title": None, "rating": None, "reviews_count": None, "type": None, "website": None, "phone": None},
                "competitors": [],
                "query": query,
            })

    # Aggregate: any-of-3 for booleans, take most-detailed record for nested data
    ai_mentioned = any(r["ai_overview"]["mentioned"] for r in results)
    ai_snippet = next((r["ai_overview"]["snippet"] for r in results if r["ai_overview"]["mentioned"]), None)

    local_data = next((r["local_pack"] for r in results if r["local_pack"]["present"]), results[0]["local_pack"])
    organic_data = next((r["organic"] for r in results if r["organic"]["present"]), results[0]["organic"])
    kg_data = next((r["knowledge_graph"] for r in results if r["knowledge_graph"]["found"]), results[0]["knowledge_graph"])

    # Aggregate competitors across the 3 queries — dedupe by place_id (or normalized name),
    # keeping the entry with the most filled fields. Sort by best (lowest) position.
    seen: dict[str, dict] = {}
    for r in results:
        for c in r.get("competitors", []):
            key = c.get("place_id") or (c.get("name") or "").strip().lower()
            if not key:
                continue
            existing = seen.get(key)
            if existing is None or sum(1 for v in c.values() if v) > sum(1 for v in existing.values() if v):
                seen[key] = c
    deduped = sorted(seen.values(), key=lambda c: c.get("position") or 99)

    # Country-aware competitor selection:
    #  Same-country only — cross-border competitors are never shown because a
    #  business in another country is not a real local threat and confuses the owner.
    #  If we detect the user's country (via gl), we keep only competitors whose
    #  address matches that country (or whose country cannot be determined, which
    #  is common for domestic SerpApi results that omit the country name).
    #  If we have no `gl` for the user (unsupported country), no filtering — all kept.
    #
    #  `competitor_scope='global'` bypasses this filter entirely — the owner has
    #  explicitly asked for worldwide results (typical for SaaS / online services).
    user_gl = country_to_gl(country) or province_to_gl(province)
    if user_gl and competitor_scope != "global":
        same_country: list[dict] = []
        cross_border: list[dict] = []
        for c in deduped:
            # Check address first; if that's unrecognisable (e.g. hours shown as address),
            # fall back to checking the business name, which often includes the city
            # (e.g. "Blackberry Clinic Milton Keynes").
            candidate = (c.get("address") or "") + " " + (c.get("name") or "")
            cgl = address_country_gl(candidate)
            if cgl is None or cgl == user_gl:
                same_country.append(c)
            else:
                cross_border.append(c)
        if same_country:
            # Prefer same-country competitors. Only fall back to cross-border if
            # there are zero same-country results (truly thin local market).
            competitors_data = same_country[:3]
        else:
            # No same-country competitors at all — use cross-border so the section
            # isn't empty. This is a genuinely thin market, not a geo-leak.
            competitors_data = cross_border[:3]
        logger.info(f"[AEO][COMP] {len(same_country)} same-country, {len(cross_border)} cross-border → showing {len(competitors_data)} (user_gl={user_gl})")
    else:
        competitors_data = deduped[:3]

    logger.info(f"[AEO] Aggregated {len(competitors_data)} unique competitors across {len(results)} queries")

    # Branded name lookup — a 4th SerpApi call against the exact business
    # name. Two reasons to fire it:
    #
    #   1. We don't have review-count data yet. Rating alone isn't enough;
    #      review count drives the Reviews-pillar recommendation copy.
    #
    #   2. We don't have a Knowledge Graph card. Category searches like
    #      "best dentist Burlington" often return ONLY a local pack entry,
    #      while branded searches for the actual business name reliably
    #      return a KG card with title/category/phone/website. Without
    #      this fallback, GBP scoring and recommendations were penalising
    #      owners for missing fields that ARE on their real GBP — Google
    #      just chose not to render the KG for the category query (the
    #      "wrong info is dangerous" bug reported 2026-05-17).
    #
    # Cost: ~$0.005 per audit when triggered. At 100 customers running
    # weekly that's ~$2/month — trivial vs the trust win.
    has_review_data = bool(
        local_data.get("reviews") or kg_data.get("reviews_count")
    )
    has_kg = bool(kg_data.get("found"))
    name_result = None
    if not has_review_data or not has_kg:
        reason = "no KG" if not has_kg else "no review data"
        print(f"[AEO] Name lookup for '{business_name}' — {reason}")
        name_result = await _google_name_lookup(business_name, city, website, province, country)
        if name_result["knowledge_graph"]["found"]:
            kg_data = name_result["knowledge_graph"]
            print(f"[AEO] Name lookup found KG: title={kg_data.get('title')} type={kg_data.get('type')} rating={kg_data.get('rating')} reviews={kg_data.get('reviews_count')}")
        # Also grab local_pack review data from the name query — SerpApi often returns
        # reviews in local_pack even when knowledge_graph is absent
        if name_result["local_pack"]["present"] and name_result["local_pack"].get("reviews"):
            local_data = name_result["local_pack"]
            print(f"[AEO] Name lookup local_pack: reviews={local_data.get('reviews')} rating={local_data.get('rating')}")
        elif not local_data["present"] and name_result["local_pack"]["present"]:
            local_data = name_result["local_pack"]

    # Final GBP fallback — when neither the category queries nor the branded
    # google-engine lookup produced a knowledge_graph, the business is
    # almost certainly one Google renders local-pack-only. Pull the full
    # profile from the google_maps engine so title/category/website/phone
    # aren't left blank on the dashboard. Only fires when KG is still
    # missing, so it costs ~$0.005 only for the businesses that need it.
    if not kg_data.get("found"):
        maps_kg = await _fetch_own_gbp_via_maps(business_name, city, country)
        if maps_kg:
            kg_data = maps_kg
            print(f"[AEO] GBP via google_maps: title={maps_kg.get('title')} type={maps_kg.get('type')} "
                  f"website={bool(maps_kg.get('website'))} phone={bool(maps_kg.get('phone'))} reviews={maps_kg.get('reviews_count')}")

    return {
        "ai_overview": {"mentioned": ai_mentioned, "snippet": ai_snippet},
        "local_pack": local_data,
        "organic": organic_data,
        "knowledge_graph": kg_data,
        "competitors": competitors_data,
        "queries": [r["query"] for r in results],
        "per_query": results + ([name_result] if name_result else []),
    }


# ─── The full audit pipeline ──────────────────────────────────────────────

async def _run_audit_core(business: dict) -> dict:
    """Runs all audit queries and returns scored results without saving to DB."""
    # Function-scope imports for the cross-package siblings — keeps
    # `audit.engine` from sitting at the top of two import chains that
    # currently meet through router.py (competitors → reputation analyzer
    # uses scoring; reputation analyzer uses content_llm). Once router.py
    # stops being the central exchange there's nothing stopping these
    # from being hoisted.
    from ..competitors import (
        check_competitor_websites,
        lookup_competitor_by_place_id,
    )
    from ..reputation.analyzer import analyze_competitor_weaknesses

    business_name = business["name"]
    city = business["city"]
    province = business["province"]
    country = business.get("country") or "Canada"  # legacy default for pre-migration rows
    website = business.get("website")
    postal_code = business.get("postal_code")
    # local / country / global -- drives both SerpApi `location` param and the
    # cross-border filter inside run_google_multi. See migration 020.
    competitor_scope = business.get("competitor_scope") or "local"
    business_type_en = await normalize_business_type(business["type"], business_name)

    # Vertical flags drive the conditional query templates (FSA / emergency / weekend).
    # Use the original business type (the user's free-form entry) for vertical detection
    # since that's what the regex patterns are tuned against.
    is_trades_v     = is_trades_business(business.get("type"))
    is_healthcare_v = is_healthcare_business(business.get("type"))

    print(f"[AEO] Audit start — name='{business_name}' type='{business_type_en}' city='{city}, {province}, {country}' (gl={country_to_gl(country)}, trades={is_trades_v}, healthcare={is_healthcare_v}, fsa={postal_code[:3].upper() if postal_code and len(postal_code) >= 3 else 'n/a'})")

    # Fetch the website first — before the parallel AI calls — so dietary and
    # cuisine signals extracted from the homepage (halal, vegetarian, vegan,
    # kosher, cuisine type, etc.) can be injected into ALL three AI engines'
    # query sets.  The website check takes ~1-3 s; the full audit takes ~15-30 s,
    # so the net latency impact is minimal.
    # Pass the owner-declared business type so sub-specialty body matches
    # are suppressed when the type already conveys a specific identity
    # (e.g. "dentist" + a homepage that lists pediatric dentistry as one
    # of many services won't label the practice as a pediatric clinic).
    raw_business_type = business.get("type")
    website_check = await check_website(website, business_type=raw_business_type)
    dietary_tags_v: list[str] = list(website_check.get("dietary_tags") or [])
    service_tags_v: list[str] = list(website_check.get("service_tags") or [])
    cuisine_hint_v: str | None = website_check.get("cuisine_hint")
    cuisine_hint_parent_v: str | None = website_check.get("cuisine_hint_parent")

    # Gap 2: scan the user's free-form `services` field with the same regex banks.
    # Captures signals declared during onboarding ("Arabic food, halal, catering")
    # that aren't visible on the website yet — common for new businesses still
    # building their homepage. Website signals take precedence; services fills gaps.
    services_text = business.get("services") or ""
    if services_text:
        from_services = extract_text_signals(services_text, business_type=raw_business_type)
        for tag in from_services["dietary_tags"]:
            if tag not in dietary_tags_v:
                dietary_tags_v.append(tag)
        for tag in from_services["service_tags"]:
            if tag not in service_tags_v:
                service_tags_v.append(tag)
        if not cuisine_hint_v and from_services["cuisine"]:
            cuisine_hint_v = from_services["cuisine"]
            cuisine_hint_parent_v = from_services["cuisine_parent"]
            print(f"[AEO] Services cuisine hint: {cuisine_hint_v} (parent={cuisine_hint_parent_v}) — from onboarding services field")

    if cuisine_hint_v:
        print(f"[AEO] Cuisine hint resolved: {cuisine_hint_v} (parent={cuisine_hint_parent_v})")
    if dietary_tags_v:
        print(f"[AEO] Dietary tags (website ∪ services): {dietary_tags_v}")
    if service_tags_v:
        print(f"[AEO] Service tags (website ∪ services): {service_tags_v}")

    perplexity_result, google_result, chatgpt_result = await asyncio.gather(
        run_perplexity_multi(business_name, business_type_en, city, province,
                             postal_code=postal_code, is_trades=is_trades_v, is_healthcare=is_healthcare_v,
                             dietary_tags=dietary_tags_v, service_tags=service_tags_v,
                             cuisine_hint=cuisine_hint_v, cuisine_hint_parent=cuisine_hint_parent_v),
        run_google_multi(business_name, business_type_en, city, province, website, country,
                         postal_code=postal_code, is_trades=is_trades_v, is_healthcare=is_healthcare_v,
                         competitor_scope=competitor_scope, dietary_tags=dietary_tags_v, service_tags=service_tags_v,
                         cuisine_hint=cuisine_hint_v, cuisine_hint_parent=cuisine_hint_parent_v),
        run_chatgpt_multi(business_name, business_type_en, city, province,
                          postal_code=postal_code, is_trades=is_trades_v, is_healthcare=is_healthcare_v,
                          dietary_tags=dietary_tags_v, service_tags=service_tags_v,
                          cuisine_hint=cuisine_hint_v, cuisine_hint_parent=cuisine_hint_parent_v),
    )

    # Recency check — only if the KG gave us a place_id (i.e. business is indexed by Google)
    place_id = google_result["knowledge_graph"].get("place_id")
    recency = await _check_review_recency(place_id, country) if place_id else {"checked": False, "recent": None, "days_since_last": None, "last_review_date": None}

    scoring = calculate_score(business, perplexity_result, google_result, website_check, chatgpt_result)
    score = scoring["total"]
    breakdown = scoring["breakdown"]
    recommendations = generate_recommendations(business, perplexity_result, google_result, website_check, breakdown, recency, chatgpt_result)
    print(f"[AEO] Score: {score}/100  breakdown={breakdown}  recs={len(recommendations)}")

    # ─── User-locked competitor list (migration 021) ───────────────────────
    # If the owner has confirmed a competitor list, that list is the source of
    # truth -- not the local pack. Auto-discovered competitors from this audit
    # are still preserved on the response so the UI can offer them as
    # "suggestions" the owner can accept into their list. Each user-locked
    # entry is either matched against auto-detected data (free) or looked up
    # by place_id (1 SerpApi call per missing entry).
    user_competitors_locked = business.get("user_competitors")
    auto_competitors = google_result.get("competitors", [])
    auto_suggestions: list[dict] = []
    if user_competitors_locked is not None:
        auto_by_id = {c.get("place_id"): c for c in auto_competitors if c.get("place_id")}
        now_iso = datetime.now(timezone.utc).isoformat()
        resolved: list[dict] = []
        needs_lookup: list[dict] = []
        for uc in (user_competitors_locked or [])[:5]:
            pid = (uc or {}).get("place_id")
            if not pid:
                continue
            if pid in auto_by_id:
                # Refresh-in-place: use this audit's local-pack data, preserve the
                # owner's source/added_at metadata, bump last_seen_at.
                resolved.append({
                    **auto_by_id[pid],
                    "source":       uc.get("source", "manual"),
                    "added_at":     uc.get("added_at"),
                    "last_seen_at": now_iso,
                    "status":       "active",
                })
            else:
                needs_lookup.append(uc)
        if needs_lookup:
            lookup_results = await asyncio.gather(
                *[lookup_competitor_by_place_id((uc or {}).get("place_id"), country=country) for uc in needs_lookup],
                return_exceptions=True,
            )
            for uc, look in zip(needs_lookup, lookup_results):
                if isinstance(look, Exception) or not look:
                    # Place not found -- keep stub so the owner sees a "stale" flag
                    resolved.append({
                        "place_id":     uc.get("place_id"),
                        "name":         uc.get("name", "Unknown"),
                        "source":       uc.get("source", "manual"),
                        "added_at":     uc.get("added_at"),
                        "last_seen_at": uc.get("last_seen_at"),
                        "status":       "stale",
                    })
                else:
                    resolved.append({
                        **look,
                        "source":       uc.get("source", "manual"),
                        "added_at":     uc.get("added_at"),
                        "last_seen_at": now_iso,
                        "status":       "closed" if look.get("business_status") == "CLOSED_PERMANENTLY" else "active",
                    })
        competitors_raw = resolved
        # Auto-detected competitors NOT in the user list become suggestions
        locked_ids = {r.get("place_id") for r in resolved if r.get("place_id")}
        auto_suggestions = [c for c in auto_competitors if c.get("place_id") and c["place_id"] not in locked_ids]
        logger.info(f"[AEO][COMP] User-locked list: {len(resolved)} scored, {len(auto_suggestions)} fresh suggestions")
    else:
        competitors_raw = auto_competitors

    # ─── Competitor scoring ────────────────────────────────────────────────
    # Score the top N competitors apples-to-apples using the same pillar formula.
    # Website fetches + AI citation matching run in parallel — no extra API cost,
    # only $0 httpx fetches and free text scanning over data we already paid for.
    scored_competitors: list[dict] = []
    if competitors_raw:
        comp_websites, comp_ai = await asyncio.gather(
            check_competitor_websites(competitors_raw),
            asyncio.to_thread(match_competitor_ai_citations, competitors_raw, perplexity_result, google_result, chatgpt_result),
        )
        for c in competitors_raw:
            key = competitor_key(c)
            website_data = comp_websites.get(key) if key else None
            ai_data = comp_ai.get(key, {}) if key else {}
            scored = score_competitor(
                c,
                website_check=website_data,
                perplexity_mentioned=ai_data.get("perplexity_mentioned"),
                google_ai_mentioned=ai_data.get("google_ai_mentioned"),
                chatgpt_mentioned=ai_data.get("chatgpt_mentioned"),
            )
            scored_competitors.append({
                **c,
                "score":         scored["total"],
                "breakdown":     scored["breakdown"],
                "has_full_data": scored["has_full_data"],
                "website_check": website_data,
                "ai_citation":   ai_data,
            })
        print(f"[AEO] Scored {len(scored_competitors)} competitors")

    # ─── Competitor weak-point mining (W2) ────────────────────────────────
    # For each scored competitor that has a place_id, fetch their latest reviews
    # via google_maps_reviews and run AI sentiment analysis to surface complaint themes.
    # This runs in parallel across competitors and is gated on place_id availability.
    # Hard 30s cap: this phase fans out a Perplexity call PER competitor, so a single
    # slow upstream response can push total audit past 2 min and break the frontend
    # fetch. Score + recommendations + competitor list don't depend on W2 — if it
    # times out we degrade silently and ship the rest of the audit on time.
    try:
        competitor_insights = await asyncio.wait_for(
            analyze_competitor_weaknesses(scored_competitors, country),
            timeout=30.0,
        )
    except asyncio.TimeoutError:
        logger.warning("[AEO][W2] Timed out after 30s — skipping competitor weak-point analysis")
        competitor_insights = {}

    # ─── Citation gap analysis (W3) ───────────────────────────────────────
    # Walk organic_results across the 3 google queries, detect directory listings
    # (Yelp, BBB, Yellow Pages, etc.), and compute which directories competitors
    # appear on that the user does not. $0 cost — pure text scan over data we
    # already paid SerpApi for.
    citation_gaps = detect_directory_presence(
        google_result.get("per_query", []),
        business_name,
        [c.get("name") for c in scored_competitors if c.get("name")],
    )

    # Persist refreshed last_seen_at / status back to businesses.user_competitors
    # so the next page load sees the new state (without a separate API call).
    if user_competitors_locked is not None:
        try:
            updated_uc = [
                {
                    "place_id":     c.get("place_id"),
                    "name":         c.get("name"),
                    "source":       c.get("source", "manual"),
                    "added_at":     c.get("added_at"),
                    "last_seen_at": c.get("last_seen_at"),
                    "status":       c.get("status", "active"),
                }
                for c in scored_competitors
                if c.get("place_id")
            ]
            supabase_admin.table("businesses").update({
                "user_competitors": updated_uc
            }).eq("id", business["id"]).execute()
        except Exception as e:
            logger.warning(f"[AEO][COMP] Failed to refresh user_competitors metadata: {e}")

    return {
        "score":                score,
        "breakdown":            breakdown,
        "recommendations":      recommendations,
        "perplexity":           perplexity_result,
        "google":               google_result,
        "chatgpt":              chatgpt_result,
        "auto_suggestions":     auto_suggestions,
        "website":              website_check,
        "competitors":          scored_competitors,
        "competitor_insights":  competitor_insights,
        "citation_gaps":        citation_gaps,
        # Detected signals (website ∪ services) — surfaced on the dashboard
        # so the owner can verify what we picked up about their business.
        # Read-only for now; an edit affordance can come later if owners
        # report wrong detections.
        "detected_signals": {
            "cuisine":        cuisine_hint_v,
            "cuisine_parent": cuisine_hint_parent_v,
            "dietary_tags":   dietary_tags_v,
            "service_tags":   service_tags_v,
        },
    }

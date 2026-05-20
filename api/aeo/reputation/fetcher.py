"""Reputation data fetchers — Google Maps reviews + Perplexity narratives.

Four async functions, each best-effort (errors degrade to empty result
rather than raising):

  fetch_own_reviews(place_id, country, max_days, max_pages)
      Paginated google_maps_reviews fetch for the audited business.
      Stops early once results fall outside the date window.

  fetch_competitor_reviews(name, city, country)
      Resolves a ChIJ place_id by name then pulls newest-first reviews.
      Single-page only — competitor analysis only needs recent signal.

  fetch_own_perplexity_reputation(business_name, city, province, country)
      Asks Perplexity for multi-source customer feedback (Yelp, BBB,
      RateMDs, etc.) about the audited business. Appends a citation-
      source map at the top of the answer so the downstream analyzer
      can resolve [1][2][3] markers to platform names.

  fetch_competitor_perplexity(name, city)
      Same but focused on complaints/problems. Returns just the answer
      text — citations aren't used by the competitor analyzer.

Originally lived in api/aeo/router.py lines 1231-1540. Moved here during
Tier 4 of the refactor. Re-exported from router.py under the old
underscored names so existing handlers + the audit engine still resolve
them via `from aeo.router import _fetch_own_reviews` etc.
"""
import asyncio
import logging
import os
import re

import httpx

from integrations import serpapi as serpapi_client

from ..audit.geo import country_to_gl
from ..audit.maps import parse_relative_date, resolve_maps_place_id
from ..audit.perplexity import _perplexity_one


logger = logging.getLogger(__name__)

PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")


async def fetch_own_reviews(
    place_id: str,
    country: str | None = None,
    max_days: int = 90,
    max_pages: int = 3,
) -> list[dict]:
    """Fetch the own business's Google Maps reviews from the last `max_days` days via SerpApi.
    Reviews are sorted newest-first. Paginates through up to `max_pages` pages (~10 reviews
    each) and stops early once a review falls outside the date window.
    Re-uses the same engine as competitor review fetching — no Phase 2 reviews table involved."""
    base_params: dict[str, str] = {
        "engine": "google_maps_reviews",
        "place_id": place_id,
        "hl": "en",
        "sort_by": "newestFirst",
    }
    gl = country_to_gl(country)
    if gl:
        base_params["gl"] = gl

    collected: list[dict] = []
    next_page_token: str | None = None

    for page in range(max_pages):
        params = {**base_params}
        if next_page_token:
            params["next_page_token"] = next_page_token

        try:
            data = await serpapi_client.search(params, timeout=30.0)
        except Exception as e:
            logger.warning(f"[AEO][OWN] Failed to fetch reviews page {page+1} for place_id={place_id}: {e}")
            break

        reviews = data.get("reviews", [])
        if not reviews:
            break

        hit_cutoff = False
        for r in reviews:
            days = parse_relative_date(r.get("date"))
            # If we can parse the date and it's beyond the window, stop pagination entirely
            if days is not None and days > max_days:
                hit_cutoff = True
                break
            if r.get("snippet"):
                collected.append({"rating": r.get("rating"), "snippet": r.get("snippet", "")})

        logger.debug(f"[AEO][OWN] Page {page+1}: {len(reviews)} reviews fetched, {len(collected)} within {max_days}d window")

        if hit_cutoff:
            break

        # Advance to the next page if available
        serpapi_pagination = data.get("serpapi_pagination") or {}
        next_page_token = serpapi_pagination.get("next_page_token")
        if not next_page_token:
            break

    logger.info(f"[AEO][OWN] Collected {len(collected)} reviews within last {max_days} days across up to {max_pages} pages")
    return collected


async def fetch_competitor_reviews(name: str, city: str | None, country: str | None = None) -> list[dict]:
    """Resolve the ChIJ-format place_id for a competitor then fetch their recent reviews
    via SerpApi google_maps_reviews. Returns [] on any error."""
    place_id = await resolve_maps_place_id(name, city, country)
    if not place_id:
        logger.debug(f"[AEO][W2] No ChIJ place_id resolved for '{name}' — skipping")
        return []
    params: dict[str, str] = {
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
        return [
            {"rating": r.get("rating"), "snippet": r.get("snippet", "")}
            for r in reviews
            if r.get("snippet")
        ]
    except Exception as e:
        logger.warning(f"[AEO][W2] Failed to fetch reviews for '{name}' ({place_id}): {e}")
        return []


# Domain → friendly platform name map for Perplexity citation resolution.
# Extracted from the inline dict in fetch_own_perplexity_reputation so the
# table is easier to extend without re-touching the function body.
_CITATION_PLATFORM_NAMES: dict[str, str] = {
    "yellowpages.ca": "Yellow Pages", "yellowpages.com": "Yellow Pages",
    "yelp.ca": "Yelp", "yelp.com": "Yelp",
    "bbb.org": "BBB",
    "homestars.com": "HomeStars",
    "trustedpros.ca": "TrustedPros",
    "ratemds.com": "RateMDs",
    "tripadvisor.com": "TripAdvisor", "tripadvisor.ca": "TripAdvisor",
    "facebook.com": "Facebook",
    "reddit.com": "Reddit",
    "birdeye.com": "Birdeye", "reviews.birdeye.com": "Birdeye",
    "fresha.com": "Fresha",
    "zocdoc.com": "Zocdoc",
    "opencare.com": "Opencare",
    "healthgrades.com": "Healthgrades",
}


# Canadian province codes → full names. Used to expand "ON" → "Ontario" before
# sending location to Perplexity, otherwise it sometimes resolves "Burlington,
# ON" to Burlington, NC. Kept local to this module rather than imported from
# audit/geo because the geo table maps abbr→full for many US states too, and
# we only want the Canadian subset for the is_canada heuristic.
_CA_PROVINCES = {
    "AB": "Alberta", "BC": "British Columbia", "MB": "Manitoba",
    "NB": "New Brunswick", "NL": "Newfoundland and Labrador",
    "NS": "Nova Scotia", "NT": "Northwest Territories", "NU": "Nunavut",
    "ON": "Ontario", "PE": "Prince Edward Island", "QC": "Quebec",
    "SK": "Saskatchewan", "YT": "Yukon",
}


async def fetch_own_perplexity_reputation(
    business_name: str,
    city: str,
    province: str | None = None,
    country: str | None = None,
) -> str:
    """Ask Perplexity what customers say about this business across all platforms.
    Used to supplement Google Maps reviews with Yelp, BBB, RateMDs, etc. signals.
    Returns the answer text (up to 2000 chars) or '' on failure."""
    if not PERPLEXITY_API_KEY:
        return ""

    # Expand Canadian province abbreviations so Perplexity doesn't mistake
    # "Burlington, ON" for Burlington, NC or "Milton, ON" for a US city.
    province_full = _CA_PROVINCES.get((province or "").upper(), province) if province else None
    is_canada = (
        country in ("CA", "Canada", "ca")
        or (province or "").upper() in _CA_PROVINCES
        or (province_full or "").lower() in {v.lower() for v in _CA_PROVINCES.values()}
    )
    if province_full:
        location = f"{city}, {province_full}, Canada" if is_canada else f"{city}, {province_full}"
    else:
        location = f"{city}, Canada" if is_canada else city

    query = (
        f"What do customers say about {business_name} in {location}? "
        f"Search across Google, Yelp, BBB, RateMDs, TrustedPros, HomeStars, and any local directories. "
        f"What are they consistently praised for? What complaints or problems appear repeatedly? "
        f"Be specific and cite your sources."
    )
    for attempt in range(2):
        try:
            result = await _perplexity_one(business_name, query, city)
            answer = result.get("answer", "")
            citations = result.get("citations") or []
            # Append a numbered source map so the LLM can resolve [1][2][3] references
            # to actual platform names (e.g. "[3] yellowpages.ca → Yellow Pages").
            if citations:
                source_lines = []
                for i, url in enumerate(citations, 1):
                    # Map domain to a friendly platform name where possible
                    domain = re.sub(r"^https?://", "", url).split("/")[0].lstrip("www.")
                    friendly = next(
                        (n for d, n in _CITATION_PLATFORM_NAMES.items() if d in domain),
                        domain,
                    )
                    source_lines.append(f"[{i}] {friendly}")
                # Put the citation map at the START so it is never lost by truncation
                citation_header = "Citation sources:\n" + "\n".join(source_lines) + "\n\n"
                answer = citation_header + answer
            return answer
        except httpx.HTTPStatusError as e:
            body = e.response.text[:300] if e.response else "(no body)"
            logger.warning(
                f"[AEO][OWN] Perplexity HTTP {e.response.status_code} for '{business_name}' "
                f"(attempt {attempt+1}): {body}"
            )
            if e.response.status_code == 429 and attempt == 0:
                await asyncio.sleep(3)  # back off and retry once on rate-limit
                continue
            return ""
        except Exception as e:
            logger.warning(f"[AEO][OWN] Perplexity reputation fetch failed for '{business_name}' (attempt {attempt+1}): {e}")
            return ""
    return ""


async def fetch_competitor_perplexity(name: str, city: str) -> str:
    """Ask Perplexity for multi-source complaint signals about a competitor.
    Returns the answer text (up to 2000 chars) or '' on failure."""
    if not PERPLEXITY_API_KEY:
        return ""
    query = (
        f"What complaints, negative reviews, or recurring problems do customers report about "
        f"{name} in {city}? Search across Google, Yelp, BBB, RateMDs, TrustedPros, HomeStars, "
        f"and any local review directories. Focus on: service quality issues, billing disputes, "
        f"wait times, staff complaints, or unresolved problems. Be specific and cite your sources."
    )
    try:
        result = await _perplexity_one(name, query, city)
        return result.get("answer", "")
    except Exception as e:
        logger.warning(f"[AEO][W2] Perplexity weakness fetch failed for '{name}': {e}")
        return ""

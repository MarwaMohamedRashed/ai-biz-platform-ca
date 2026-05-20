"""Competitor management — extraction, scoring, lookup, owner-curated list.

Split from api/aeo/router.py during Tier 5 of the refactor. This module owns:

  * `extract_location_from_address` — parse "city, region, country" out of
    SerpApi addresses. Drives the cross_city / cross_border flagging.
  * `extract_competitors` — pull the top-N local-pack entries out of a
    Google search response, attach the parsed location, exclude the
    audited business via fuzzy name match.
  * `check_competitor_websites` — parallel check_website() calls for
    every competitor that has a URL. Returns dict keyed by competitor_key().
  * `lookup_competitor_by_place_id` — google_maps place_results lookup
    for owner-added competitors that didn't appear in the audit.
  * `score_user_competitor` — end-to-end score for one user-curated
    competitor (place_id lookup + website + AI citation match + scoring).
  * Two FastAPI endpoints, mounted on the same `/api/v1/aeo` prefix as
    the rest of the AEO surface via `router.include_router` in router.py:
      GET  /competitor-search   search Google Maps for an owner-named business
      POST /competitors         persist the owner's curated competitor list

The endpoints + `score_user_competitor` are reached through a sub-router
(`router = APIRouter()` in this module) so they show up under the same
URL prefix as before — no client-side path changes.

Notes on dependencies kept inside the function bodies rather than as
top-level imports:
  - `check_website` (router.py) is imported lazily inside
    `check_competitor_websites` to avoid a circular import (router.py
    imports competitors.py to mount the sub-router).
"""
import asyncio
import logging
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from core.auth import get_current_user
from core.database import get_business_by_user, supabase_admin
from integrations import serpapi as serpapi_client

from .audit.geo import country_to_gl
from .audit.scoring import (
    competitor_key,
    match_competitor_ai_citations,
    name_matches,
    score_competitor,
)
from .audit.website import check_website


logger = logging.getLogger(__name__)
router = APIRouter()


# ─── Pydantic models ──────────────────────────────────────────────────────

class CompetitorEntry(BaseModel):
    place_id: str
    name: str
    source: str = "manual"  # 'auto' | 'manual'


class CompetitorListRequest(BaseModel):
    competitors: list[CompetitorEntry]


# ─── Address parsing ──────────────────────────────────────────────────────

def extract_location_from_address(address: str | None) -> tuple[str | None, str | None, str | None]:
    """Extract (city, region, country) from a comma-separated address string.

    SerpApi returns addresses in the format most common for the business's country.
    Strategy: split by comma and work backwards.
      - Last segment: 'Region PostalCode', a bare postal code, or a country name.
      - Second-to-last: the city (possibly with a bundled region abbreviation).
      - If the last segment is a plain word with no digits or abbreviation pattern,
        treat it as the country name and look one segment further for region.
      - If no country word, infer country from postal-code shape (UK 'MK9 1AB' is
        unmistakable, Canadian 'L9T 0A1' is too, etc.) -- this catches cross-border
        results where SerpApi omitted the country word (e.g. 'Milton Keynes, MK9 1AB'
        leaking into a Canadian Milton search).

    Examples:
      '3500 Dundas St W, Burlington, ON L7M 0J6' → ('Burlington', 'ON', 'Canada')
      '221B Baker St, London, England, UK'        → ('London', None, 'UK')
      'Milton Keynes, MK9 1AB'                    → ('Milton Keynes', None, 'United Kingdom')
      '10 Rue de Rivoli, Paris, France'           → ('Paris', None, 'France')
      '1 Main St, Milton, ON L9T 0A1'             → ('Milton', 'ON', 'Canada')
      '5 High St, Melbourne VIC, Australia'       → ('Melbourne', 'VIC', 'Australia')

    Returns (None, None, None) if city cannot be determined.
    """
    if not address:
        return None, None, None

    parts = [p.strip() for p in address.split(',') if p.strip()]
    if len(parts) < 2:
        return None, None, None

    country: str | None = None
    region: str | None = None

    # Check whether the last segment looks like a country name:
    # a country name is all letters/spaces, no digits, length > 3, not a 2-3 letter abbreviation
    last = parts[-1]
    is_country = bool(re.match(r'^[A-Za-z][A-Za-z\s\.]{3,}$', last) and not re.match(r'^[A-Z]{2,3}$', last))
    if is_country:
        country = last
        parts = parts[:-1]  # remove country, re-evaluate the remaining parts
        if len(parts) < 2:
            return None, None, country

    # Now last segment is 'Region PostalCode' or just a postal/region code
    last = parts[-1]
    region_match = re.match(r'^([A-Z]{2,3})\b', last)
    region = region_match.group(1) if region_match else None

    # City is the second-to-last part; strip any trailing region abbreviation
    # that got bundled in (e.g. "Burlington ON" when there's no postal code)
    city_raw = parts[-2]
    city = re.sub(r'\s+[A-Z]{2,3}$', '', city_raw).strip()

    # Sanity check — if city looks like a street number or is empty, bail
    if not city or re.match(r'^\d+$', city):
        return None, None, country

    # Postal-code-shape country inference: SerpApi often omits the country word
    # for international results (e.g., "Milton Keynes, MK9 1AB" leaking into a
    # Canadian Milton search). When no country word was present, infer it from
    # the postal-code format. Each country has a distinctive shape.
    if country is None:
        postal_text = parts[-1]  # last segment — usually 'REGION POSTAL' or 'POSTAL'
        # UK: AA9 9AA, A9 9AA, A9A 9AA, AA9A 9AA (one or two letters, digit, optional letter, space, digit, two letters)
        if re.search(r'\b[A-Z]{1,2}\d[A-Z\d]?\s?\d[A-Z]{2}\b', postal_text):
            country = "United Kingdom"
        # Canadian: A9A 9A9 (letter-digit-letter, space, digit-letter-digit)
        elif re.search(r'\b[A-Z]\d[A-Z]\s?\d[A-Z]\d\b', postal_text):
            country = "Canada"
        # US ZIP: 5 digits or 5+4 (only if region is a 2-letter US state code)
        elif region and len(region) == 2 and re.search(r'\b\d{5}(?:-\d{4})?\b', postal_text):
            country = "United States"
        # Australian: 4 digits, only if region is a 2-3 letter AU state (NSW, VIC, QLD, etc.)
        elif region in {"NSW", "VIC", "QLD", "WA", "SA", "TAS", "ACT", "NT"} and re.search(r'\b\d{4}\b', postal_text):
            country = "Australia"

    return city, region, country


# ─── Local-pack extraction ────────────────────────────────────────────────

def extract_competitors(
    data: dict,
    search_name: str,
    user_city: str | None = None,
    user_region: str | None = None,
    user_country: str | None = None,
    max_count: int = 3,
) -> list[dict]:
    """Pull top N competitors out of the SerpApi local pack, excluding the audited business.
    Returns lightweight dicts — full pillar scoring happens later in score_competitor()."""
    places = data.get("local_results", {}).get("places", [])
    competitors: list[dict] = []
    for i, place in enumerate(places):
        title = place.get("title", "")
        if not title or name_matches(title, search_name):
            continue
        address = place.get("address")
        competitor_city, competitor_region, competitor_country = extract_location_from_address(address)

        # cross_city: same country + same region + different city.
        # Require all three to match so that e.g. Milton ON Canada vs Milton ON Australia
        # is NOT treated as cross_city (it's cross_border instead).
        # When country/region is absent from competitor address, we give benefit of doubt
        # and assume same (SerpApi localizes via `gl` so domestic results rarely include country).
        same_country = (
            not user_country
            or not competitor_country
            or user_country.lower() == competitor_country.lower()
        )
        same_region = (
            not user_region
            or not competitor_region
            or user_region.upper() == competitor_region.upper()
        )
        cross_city = bool(
            user_city
            and competitor_city
            and competitor_city.lower() != user_city.lower()
            and same_country
            and same_region
        )
        competitors.append({
            "name":       title,
            "place_id":   place.get("place_id"),
            "rating":     place.get("rating"),
            "reviews":    place.get("reviews"),
            "type":       place.get("type"),
            "website":    place.get("website") or place.get("links", {}).get("website"),
            "phone":      place.get("phone"),
            "address":    address,
            "city":       competitor_city,
            "region":     competitor_region,
            "country":    competitor_country,
            "cross_city": cross_city,
            "position":   i + 1,
        })
        if len(competitors) >= max_count:
            break
    logger.debug(f"[AEO][COMP] Extracted {len(competitors)} competitors from local pack")
    return competitors


async def check_competitor_websites(competitors: list[dict]) -> dict[str, dict]:
    """Run check_website() for every competitor that has a URL — in parallel via asyncio.gather.
    Returns a dict keyed by competitor_key() → website check result.
    Competitors without a URL or whose check raises are silently skipped (key absent)."""
    keys: list[str] = []
    tasks: list = []
    for c in competitors:
        url = c.get("website")
        key = competitor_key(c)
        if not url or not key:
            continue
        keys.append(key)
        tasks.append(check_website(url))

    if not tasks:
        logger.debug("[AEO][COMP] No competitor websites to check")
        return {}

    logger.info(f"[AEO][COMP] Checking {len(tasks)} competitor websites in parallel")
    results = await asyncio.gather(*tasks, return_exceptions=True)
    output: dict[str, dict] = {}
    for key, result in zip(keys, results):
        if isinstance(result, Exception):
            logger.warning(f"[AEO][COMP] Website check failed for '{key}': {result}")
            continue
        output[key] = result
    logger.info(f"[AEO][COMP] {len(output)}/{len(tasks)} competitor websites returned data")
    return output


# ─── Manual-add competitor scoring ────────────────────────────────────────

async def lookup_competitor_by_place_id(place_id: str, country: str | None = None) -> dict | None:
    """Resolve a Google Maps place_id to a competitor dict in the same shape as
    extract_competitors() output. Used when a user adds a competitor manually
    that we never saw in the audit's local pack queries.

    Returns None when SerpApi can't find the place (closed, deleted, bad id)."""
    if not place_id:
        return None
    gl = country_to_gl(country) or "ca"
    params: dict[str, str] = {
        "engine":   "google_maps",
        "place_id": place_id,
        "hl":       "en",
        "gl":       gl,
    }
    try:
        data = await serpapi_client.search(params, timeout=20.0)
    except Exception as e:
        logger.warning(f"[AEO][COMP] place_id lookup failed for {place_id}: {e}")
        return None
    place = data.get("place_results") or {}
    if not place:
        return None
    return {
        "name":            place.get("title", ""),
        "place_id":        place_id,
        "rating":          place.get("rating"),
        "reviews":         place.get("reviews"),
        "type":            place.get("type") or (place.get("types") or [None])[0],
        "website":         place.get("website") or (place.get("links") or {}).get("website"),
        "phone":           place.get("phone"),
        "address":         place.get("address"),
        "business_status": place.get("business_status"),  # 'OPERATIONAL' | 'CLOSED_TEMPORARILY' | 'CLOSED_PERMANENTLY'
        "position":        0,
    }


async def score_user_competitor(
    entry: dict,
    country: str | None = None,
    perplexity_result: dict | None = None,
    google_result: dict | None = None,
    chatgpt_result: dict | None = None,
) -> dict:
    """Score one user-locked competitor end-to-end: place_id lookup, website
    check, AI citation matching (when audit results provided), and the 5-pillar
    formula. Used by POST /aeo/competitors when an owner adds a competitor that
    wasn't found by the audit's local pack queries."""
    base = await lookup_competitor_by_place_id(entry["place_id"], country=country)
    if not base:
        return {
            "place_id":     entry["place_id"],
            "name":         entry.get("name", "Unknown"),
            "source":       entry.get("source", "manual"),
            "added_at":     entry.get("added_at"),
            "last_seen_at": datetime.now(timezone.utc).isoformat(),
            "status":       "stale",
            "score":        0,
            "has_full_data": False,
        }

    # Website check + AI citation matching against the latest audit (when provided).
    # Each is best-effort; failures degrade the score, not the response.
    website_check_results = await check_competitor_websites([base])
    website_check = website_check_results.get(competitor_key(base))

    perplexity_m = google_ai_m = chatgpt_m = None
    if perplexity_result and google_result and chatgpt_result:
        matches = match_competitor_ai_citations([base], perplexity_result, google_result, chatgpt_result)
        m = matches.get(competitor_key(base))
        if m:
            perplexity_m = m["perplexity_mentioned"]
            google_ai_m  = m["google_ai_mentioned"]
            chatgpt_m    = m["chatgpt_mentioned"]

    scored = score_competitor(
        base,
        website_check=website_check,
        perplexity_mentioned=perplexity_m,
        google_ai_mentioned=google_ai_m,
        chatgpt_mentioned=chatgpt_m,
    )

    status = "closed" if base.get("business_status") == "CLOSED_PERMANENTLY" else "active"
    return {
        **base,
        "score":         scored["total"],
        "breakdown":     scored["breakdown"],
        "has_full_data": scored["has_full_data"],
        "website_check": website_check,
        "ai_citation": {
            "perplexity_mentioned": perplexity_m,
            "google_ai_mentioned":  google_ai_m,
            "chatgpt_mentioned":    chatgpt_m,
        },
        "source":       entry.get("source", "manual"),
        "added_at":     entry.get("added_at") or datetime.now(timezone.utc).isoformat(),
        "last_seen_at": datetime.now(timezone.utc).isoformat(),
        "status":       status,
    }


# ─── Endpoints ────────────────────────────────────────────────────────────

@router.get("/competitor-search")
async def competitor_search(
    q: str = Query(..., min_length=2),
    current_user: dict = Depends(get_current_user),
):
    """Search Google Maps for businesses matching `q`, scoped to the user's
    city/country. Used by the CompetitorPicker UI to let owners add a specific
    competitor by name. Cost: ~$0.005 per search (SerpApi google_maps engine)."""
    business = await get_business_by_user(current_user["id"])
    if not business:
        raise HTTPException(status_code=404, detail="Business profile not found")

    city     = business.get("city") or ""
    province = business.get("province") or ""

    # google_maps engine does NOT support `location` or `gl` — those are for
    # the regular `google` engine. Geo-scope by appending city+province to `q`.
    loc_suffix = ""
    if city:
        loc_suffix = f" {city}, {province}" if province else f" {city}"
    q_scoped = f"{q}{loc_suffix}"

    params: dict[str, str] = {
        "engine":  "google_maps",
        "q":       q_scoped,
        "hl":      "en",
    }

    try:
        data = await serpapi_client.search(params, timeout=20.0)
    except Exception as e:
        logger.warning(f"[AEO][COMP-SEARCH] '{q}' failed: {e}")
        raise HTTPException(status_code=502, detail="Search failed")

    places = data.get("local_results") or []
    if isinstance(places, dict):
        places = places.get("places", [])

    results = []
    for p in places[:8]:
        pid = p.get("place_id")
        if not pid:
            continue
        results.append({
            "place_id": pid,
            "name":     p.get("title", ""),
            "address":  p.get("address"),
            "rating":   p.get("rating"),
            "reviews":  p.get("reviews"),
            "type":     p.get("type"),
            "website":  p.get("website") or (p.get("links") or {}).get("website"),
            "phone":    p.get("phone"),
        })
    return {"results": results}


@router.post("/competitors")
async def save_competitor_list(
    request: CompetitorListRequest,
    current_user: dict = Depends(get_current_user),
):
    """Save the owner's confirmed competitor list (capped at 5). Diffs against
    the existing list to find newly-added entries; scores each in parallel via
    `score_user_competitor` so the UI gets back a fully scored list it can
    render immediately. Updates `businesses.user_competitors` and patches the
    latest audit's `raw_results.competitors` with the scored entries so the
    Competitors page reflects them on the next page load.

    Cost: ~$0.015 per newly-added competitor (SerpApi reviews + Perplexity +
    LLM). Reused entries cost $0 — we just refresh metadata."""
    business = await get_business_by_user(current_user["id"])
    if not business:
        raise HTTPException(status_code=404, detail="Business profile not found")

    country = business.get("country") or "Canada"

    # Dedupe + cap at 5
    seen_ids: set[str] = set()
    incoming: list[dict] = []
    now_iso = datetime.now(timezone.utc).isoformat()
    for c in request.competitors[:5]:
        if not c.place_id or c.place_id in seen_ids:
            continue
        seen_ids.add(c.place_id)
        incoming.append({
            "place_id": c.place_id,
            "name":     c.name,
            "source":   c.source if c.source in ("auto", "manual") else "manual",
            "added_at": now_iso,
        })

    # Pull the latest audit so we can reuse existing scores (zero-cost path)
    audits = (
        supabase_admin.table("aeo_audits")
        .select("id, raw_results")
        .eq("business_id", business["id"])
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    latest_audit = audits.data[0] if audits.data else None
    latest_raw   = (latest_audit or {}).get("raw_results") or {}
    existing_scored = {
        c.get("place_id"): c
        for c in (latest_raw.get("competitors") or [])
        if c.get("place_id")
    }

    # Preserve original added_at when an entry already exists
    existing_uc = {
        e.get("place_id"): e
        for e in (business.get("user_competitors") or [])
        if isinstance(e, dict) and e.get("place_id")
    }

    final_list: list[dict] = []
    needs_scoring: list[dict] = []
    for entry in incoming:
        pid = entry["place_id"]
        added_at = (existing_uc.get(pid) or {}).get("added_at") or entry["added_at"]
        if pid in existing_scored:
            scored = dict(existing_scored[pid])
            scored.update({
                "source":       entry["source"],
                "added_at":     added_at,
                "last_seen_at": now_iso,
                "status":       scored.get("status") or "active",
            })
            final_list.append(scored)
        else:
            needs_scoring.append({**entry, "added_at": added_at})

    if needs_scoring:
        perp = latest_raw.get("perplexity") or {}
        goog = latest_raw.get("google") or {}
        chat = latest_raw.get("chatgpt") or {}
        scored_results = await asyncio.gather(
            *[
                score_user_competitor(entry, country, perp, goog, chat)
                for entry in needs_scoring
            ],
            return_exceptions=True,
        )
        for entry, scored in zip(needs_scoring, scored_results):
            if isinstance(scored, Exception):
                logger.warning(f"[AEO][COMP] Score failed for {entry['place_id']}: {scored}")
                final_list.append({
                    "place_id":     entry["place_id"],
                    "name":         entry["name"],
                    "source":       entry["source"],
                    "added_at":     entry["added_at"],
                    "last_seen_at": now_iso,
                    "status":       "stale",
                    "score":        0,
                    "has_full_data": False,
                })
            else:
                final_list.append(scored)

    # Persist minimal metadata to businesses.user_competitors
    storage = [
        {
            "place_id":     c.get("place_id"),
            "name":         c.get("name"),
            "source":       c.get("source", "manual"),
            "added_at":     c.get("added_at"),
            "last_seen_at": c.get("last_seen_at"),
            "status":       c.get("status", "active"),
        }
        for c in final_list
    ]
    supabase_admin.table("businesses").update({
        "user_competitors": storage
    }).eq("id", business["id"]).execute()

    # Patch the latest audit's raw_results with the freshly-scored list so the
    # Competitors page immediately reflects the new state
    if latest_audit:
        updated_raw = {**latest_raw, "competitors": final_list}
        try:
            supabase_admin.table("aeo_audits").update({
                "raw_results": updated_raw
            }).eq("id", latest_audit["id"]).execute()
        except Exception as e:
            logger.warning(f"[AEO][COMP] Failed to patch audit raw_results: {e}")

    return {"competitors": final_list, "count": len(final_list)}

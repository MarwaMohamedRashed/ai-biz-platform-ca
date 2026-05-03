from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from core.ai_engine import ai_engine
from core.auth import get_current_user
from core.database import supabase_admin, get_business_by_user
from core.notifications import send_email
import asyncio
import httpx
import json
import os
import logging
import re

logger = logging.getLogger(__name__)
router = APIRouter()

PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")
SERPAPI_KEY = os.getenv("SERPAPI_KEY")
CRON_SECRET = os.getenv("CRON_SECRET")
KNOWN_TYPES = {"restaurant", "salon", "retail", "plumber", "cafe"}

# Map full country names (as stored on businesses.country, set in onboarding) to
# Google's ISO 3166-1 alpha-2 region codes used by the SerpApi `gl` parameter.
# Keys must match the values in apps/web/components/onboarding/StepBusinessInfo.tsx COUNTRIES.
COUNTRY_TO_GL: dict[str, str] = {
    "Canada":         "ca",
    "United States":  "us",
    "United Kingdom": "gb",
    "Australia":      "au",
    "France":         "fr",
    "Germany":        "de",
    "Spain":          "es",
    "Italy":          "it",
    "Netherlands":    "nl",
    "Belgium":        "be",
    "Switzerland":    "ch",
    "New Zealand":    "nz",
    "Ireland":        "ie",
    "Portugal":       "pt",
    "Mexico":         "mx",
    "Brazil":         "br",
    "India":          "in",
    "Japan":          "jp",
    "South Korea":    "kr",
    "Singapore":      "sg",
    "South Africa":   "za",
}


def country_to_gl(country: str | None) -> str | None:
    """Maps a country name to a SerpApi `gl` code. Returns None if unknown — caller
    should omit the gl param so Google can fall back to its own location signals."""
    if not country:
        return None
    return COUNTRY_TO_GL.get(country.strip())


# Maps a gl code to regex patterns that strongly indicate that country in a SerpApi
# address string. Word-boundaries (\b) prevent false positives like "uk" matching
# inside "Lukas Avenue". Every gl code in COUNTRY_TO_GL must have an entry here.
COUNTRY_ADDRESS_MARKERS: dict[str, list[str]] = {
    "ca": [r"\bcanada\b"],
    "us": [r"\bunited states\b", r"\busa\b", r"\bu\.s\.a?\.?\b"],
    "gb": [r"\bunited kingdom\b", r"\bu\.?k\.?\b", r"\bengland\b", r"\bscotland\b", r"\bwales\b"],
    "au": [r"\baustralia\b"],
    "fr": [r"\bfrance\b"],
    "de": [r"\bgermany\b", r"\bdeutschland\b"],
    "es": [r"\bspain\b", r"\bespaña\b"],
    "it": [r"\bitaly\b", r"\bitalia\b"],
    "nl": [r"\bnetherlands\b", r"\bholland\b", r"\bnederland\b"],
    "be": [r"\bbelgium\b", r"\bbelgique\b", r"\bbelgië\b"],
    "ch": [r"\bswitzerland\b", r"\bsuisse\b", r"\bschweiz\b"],
    "nz": [r"\bnew zealand\b"],
    "ie": [r"\bireland\b", r"\béire\b"],
    "pt": [r"\bportugal\b"],
    "mx": [r"\bmexico\b", r"\bméxico\b"],
    "br": [r"\bbrazil\b", r"\bbrasil\b"],
    "in": [r"\bindia\b"],
    "jp": [r"\bjapan\b"],
    "kr": [r"\bsouth korea\b", r"\bkorea\b"],
    "sg": [r"\bsingapore\b"],
    "za": [r"\bsouth africa\b"],
}

# Sanity-check: every supported country must have an entry in both maps.
assert set(COUNTRY_TO_GL.values()) == set(COUNTRY_ADDRESS_MARKERS.keys()), \
    "COUNTRY_TO_GL and COUNTRY_ADDRESS_MARKERS must cover the same gl codes"


def address_country_gl(address: str | None) -> str | None:
    """Identify which country an address is in. Returns gl code, or None if no
    clear country marker found (in which case the address is given the benefit
    of the doubt — kept rather than dropped)."""
    if not address:
        return None
    a = address.lower()
    for gl, patterns in COUNTRY_ADDRESS_MARKERS.items():
        if any(re.search(p, a) for p in patterns):
            return gl
    return None

# Maps common province/state abbreviations to full names recognised by SerpApi's geocoder.
# "City, ON" returns 0 results; "City, Ontario" returns correct Canadian local pack.
PROVINCE_ABBR_TO_FULL: dict[str, str] = {
    # Canadian provinces & territories
    "AB": "Alberta", "BC": "British Columbia", "MB": "Manitoba",
    "NB": "New Brunswick", "NL": "Newfoundland and Labrador",
    "NS": "Nova Scotia", "NT": "Northwest Territories",
    "NU": "Nunavut", "ON": "Ontario", "PE": "Prince Edward Island",
    "QC": "Quebec", "SK": "Saskatchewan", "YT": "Yukon",
    # US states (common ones — SerpApi handles the rest)
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
    "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
    "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming", "DC": "District of Columbia",
}


def expand_province(province: str | None) -> str | None:
    """Return the full province/state name for SerpApi's geocoder.
    If already a full name or unknown, returns as-is."""
    if not province:
        return None
    upper = province.strip().upper()
    return PROVINCE_ABBR_TO_FULL.get(upper, province.strip())


QUERY_TEMPLATES = [
    "best {type} in {city}, {province}",
    "{type} near {city}",
    "top {type} {city} {province}",
]


def extract_search_name(business_name: str, city: str) -> str:
    return re.sub(rf'\s+in\s+{re.escape(city)}\s*$', '', business_name, flags=re.IGNORECASE).strip()


def _parse_relative_date(date_str: str | None) -> int | None:
    """Convert SerpApi relative date strings to approximate number of days.
    Examples: '2 days ago' → 2, '3 weeks ago' → 21, '2 months ago' → 60, 'a year ago' → 365.
    Returns None if the string cannot be parsed."""
    if not date_str:
        return None
    s = date_str.lower().strip()
    m = re.match(r'(\d+|a|an)\s+(day|week|month|year)s?\s+ago', s)
    if not m:
        return None
    n_str, unit = m.group(1), m.group(2)
    n = 1 if n_str in ('a', 'an') else int(n_str)
    return n * {'day': 1, 'week': 7, 'month': 30, 'year': 365}[unit]


async def _check_review_recency(place_id: str, country: str | None = None) -> dict:
    """Check when the most recent Google review was posted using SerpApi google_maps_reviews.
    Only called when the KG returned a place_id. Considers reviews stale after 90 days."""
    params = {
        "api_key": SERPAPI_KEY,
        "engine": "google_maps_reviews",
        "place_id": place_id,
        "hl": "en",
        "sort_by": "newestFirst",
    }
    gl = country_to_gl(country)
    if gl:
        params["gl"] = gl
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://serpapi.com/search",
                params=params,
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()
        reviews = data.get("reviews", [])
        if not reviews:
            logger.debug(f"[AEO][RECENCY] No reviews returned for place_id={place_id}")
            return {"checked": True, "recent": False, "days_since_last": None, "last_review_date": None}
        latest_date_str = reviews[0].get("date")
        days = _parse_relative_date(latest_date_str)
        recent = days is not None and days <= 90
        logger.debug(f"[AEO][RECENCY] place_id={place_id} latest='{latest_date_str}' days={days} recent={recent}")
        return {"checked": True, "recent": recent, "days_since_last": days, "last_review_date": latest_date_str}
    except Exception as e:
        logger.warning(f"[AEO][RECENCY] Failed for place_id={place_id}: {e}")
        return {"checked": False, "recent": None, "days_since_last": None, "last_review_date": None}


def _name_matches(candidate: str, search_name: str) -> bool:
    """Fuzzy business name match — requires at least 2 significant tokens to appear.
    Handles cases where SerpApi abbreviates the name (e.g. 'James Snow Physio'
    vs 'James Snow Physiotherapy & Rehabilitation Centre')."""
    tokens = [t for t in search_name.lower().split() if len(t) > 3]
    if not tokens:
        return search_name.lower() in candidate.lower()
    candidate_lower = candidate.lower()
    matches = sum(1 for t in tokens if t in candidate_lower)
    return matches >= min(2, len(tokens))


async def normalize_business_type(raw_type: str, business_name: str) -> str:
    if raw_type.lower() in KNOWN_TYPES:
        return raw_type
    result = await ai_engine.generate(
        prompt=f'Given business name: "{business_name}" and type: "{raw_type}", translate to a short English phrase for a search query (e.g. "physiotherapy clinic", "italian restaurant"). Reply with only the phrase.',
        max_tokens=20,
        temperature=0.0,
    )
    return result.strip()


def build_queries(business_type_en: str, city: str, province: str) -> list[str]:
    return [t.format(type=business_type_en, city=city, province=province) for t in QUERY_TEMPLATES]


async def _perplexity_one(business_name: str, query: str, city: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.perplexity.ai/chat/completions",
            headers={
                "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "sonar",
                "messages": [{"role": "user", "content": query}],
            },
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()

    answer = data["choices"][0]["message"]["content"]
    mentioned = extract_search_name(business_name, city).lower() in answer.lower()
    snippet = answer[:500] if mentioned else None
    print(f"[AEO] Perplexity '{query}' → mentioned={mentioned}")
    return {"mentioned": mentioned, "snippet": snippet, "answer": answer[:2000], "query": query}


async def run_perplexity_multi(business_name: str, business_type_en: str, city: str, province: str) -> dict:
    results = []
    for query in build_queries(business_type_en, city, province):
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


def check_organic(data: dict, search_name: str, website: str | None) -> dict:
    results = data.get("organic_results", [])
    domain = None
    if website:
        domain = re.sub(r'^https?://(www\.)?', '', website).rstrip('/').lower()
    for r in results:
        title = r.get("title", "").lower()
        link = r.get("link", "").lower()
        if _name_matches(r.get("title", ""), search_name) or (domain and domain in link):
            return {"present": True, "position": r.get("position")}
    return {"present": False, "position": None}


def check_knowledge_graph(data: dict, search_name: str) -> dict:
    kg = data.get("knowledge_graph")
    if not kg:
        logger.debug("[AEO][KG] No knowledge_graph key in SerpApi response")
        return {"found": False, "title": None, "rating": None, "reviews_count": None, "type": None, "website": None, "phone": None}
    logger.debug(f"[AEO][KG] Raw knowledge_graph keys: {list(kg.keys())}")
    logger.debug(f"[AEO][KG] title='{kg.get('title')}' rating={kg.get('rating')} user_reviews={kg.get('user_reviews')} review_count={kg.get('review_count')} reviews_count={kg.get('reviews_count')} reviews_type={type(kg.get('reviews')).__name__}")
    if not _name_matches(kg.get("title", ""), search_name):
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
        if _name_matches(place.get("title", ""), search_name):
            result = {"present": True, "position": i + 1, "rating": place.get("rating"), "reviews": place.get("reviews")}
            logger.debug(f"[AEO][LP] MATCH found: {result}")
            return result
    logger.debug(f"[AEO][LP] No match found for '{search_name}'")
    return {"present": False, "position": None, "rating": None, "reviews": None}


def _extract_location_from_address(address: str | None) -> tuple[str | None, str | None, str | None]:
    """Extract (city, region, country) from a comma-separated address string.

    SerpApi returns addresses in the format most common for the business's country.
    Strategy: split by comma and work backwards.
      - Last segment: 'Region PostalCode', a bare postal code, or a country name.
      - Second-to-last: the city (possibly with a bundled region abbreviation).
      - If the last segment is a plain word with no digits or abbreviation pattern,
        treat it as the country name and look one segment further for region.

    Examples:
      '3500 Dundas St W, Burlington, ON L7M 0J6' → ('Burlington', 'ON', None)
      '221B Baker St, London, England, UK'        → ('London', None, 'UK')
      '10 Rue de Rivoli, Paris, France'           → ('Paris', None, 'France')
      '1 Main St, Milton, ON L9T 0A1'             → ('Milton', 'ON', None)
      '5 High St, Melbourne VIC, Australia'       → ('Melbourne', 'VIC', 'Australia')

    When country is not present in the address (most domestic SerpApi results),
    returns None for country — callers should treat this as 'same country as search'.
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

    return city, region, country


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
        if not title or _name_matches(title, search_name):
            continue
        address = place.get("address")
        competitor_city, competitor_region, competitor_country = _extract_location_from_address(address)

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


async def _google_one(
    business_name: str,
    query: str,
    city: str,
    website: str | None,
    province: str | None = None,
    country: str | None = None,
) -> dict:
    # NOTE: location must be just `city` — SerpApi feeds it to Google Places which
    # only reliably matches bare city names. Adding province (e.g. "Milton, Ontario")
    # returns a different local pack that breaks KG and competitor detection.
    # Cross-country leakage (e.g. "Milton" matching Milton Keynes, UK) is handled
    # downstream by the address_country_gl cross-border filter in run_google_multi.
    params = {
        "api_key": SERPAPI_KEY,
        "engine": "google",
        "q": query,
        "location": city,
        "hl": "en",
    }
    gl = country_to_gl(country)
    if gl:
        params["gl"] = gl
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://serpapi.com/search",
            params=params,
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()

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
    competitors = extract_competitors(data, search_name, user_city=city, user_region=province, user_country=country)
    logger.info(f"[AEO] Google '{query}' → ai={ai_mentioned} local={local['present']}(reviews={local.get('reviews')}) organic={organic['present']} kg={kg['found']}(reviews={kg.get('reviews_count')}) competitors={len(competitors)}")

    return {
        "ai_overview": {
            "mentioned": ai_mentioned,
            "snippet":   answer[:500] if ai_mentioned else None,
            "text":      answer[:2000] if answer else "",
        },
        "local_pack": local,
        "organic": organic,
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
            "knowledge_graph": {"found": False, "title": None, "rating": None, "reviews_count": None, "type": None, "website": None, "phone": None},
            "competitors": [],
            "query": query,
        }


async def run_google_multi(
    business_name: str,
    business_type_en: str,
    city: str,
    province: str,
    website: str | None,
    country: str | None = None,
) -> dict:
    results = []
    for query in build_queries(business_type_en, city, province):
        try:
            results.append(await _google_one(business_name, query, city, website, province, country))
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
    user_gl = country_to_gl(country)
    if user_gl:
        same_country: list[dict] = []
        excluded_cross_border = 0
        for c in deduped:
            cgl = address_country_gl(c.get("address"))
            if cgl is None or cgl == user_gl:
                same_country.append(c)
            else:
                excluded_cross_border += 1
        competitors_data = same_country[:3]
        logger.info(f"[AEO][COMP] {len(same_country)} same-country kept, {excluded_cross_border} cross-border excluded → showing {len(competitors_data)} (user_gl={user_gl})")
    else:
        competitors_data = deduped[:3]

    logger.info(f"[AEO] Aggregated {len(competitors_data)} unique competitors across {len(results)} queries")

    # If category queries didn't return review count, run a 4th name-based lookup
    # to force Google to return the knowledge graph for this specific business.
    # Note: rating alone is NOT enough — SerpApi often returns rating without review
    # count from the local pack. We need review count for recommendations to be accurate.
    has_review_data = bool(
        local_data.get("reviews") or kg_data.get("reviews_count")
    )
    name_result = None
    if not has_review_data:
        print(f"[AEO] No review data from category queries — running name lookup for '{business_name}'")
        name_result = await _google_name_lookup(business_name, city, website, province, country)
        if name_result["knowledge_graph"]["found"]:
            kg_data = name_result["knowledge_graph"]
            print(f"[AEO] Name lookup found KG: rating={kg_data.get('rating')} reviews={kg_data.get('reviews_count')}")
        # Also grab local_pack review data from the name query — SerpApi often returns
        # reviews in local_pack even when knowledge_graph is absent
        if name_result["local_pack"]["present"] and name_result["local_pack"].get("reviews"):
            local_data = name_result["local_pack"]
            print(f"[AEO] Name lookup local_pack: reviews={local_data.get('reviews')} rating={local_data.get('rating')}")
        elif not local_data["present"] and name_result["local_pack"]["present"]:
            local_data = name_result["local_pack"]

    return {
        "ai_overview": {"mentioned": ai_mentioned, "snippet": ai_snippet},
        "local_pack": local_data,
        "organic": organic_data,
        "knowledge_graph": kg_data,
        "competitors": competitors_data,
        "queries": [r["query"] for r in results],
        "per_query": results + ([name_result] if name_result else []),
    }


async def check_website(website: str | None) -> dict:
    if not website:
        return {"reachable": False, "has_local_business_schema": False, "has_faq_schema": False}

    url = website if website.startswith("http") else f"https://{website}"
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=10.0) as client:
            response = await client.get(url, headers={"User-Agent": "Mozilla/5.0 (LeapOne AEO Audit Bot)"})
            response.raise_for_status()
            html = response.text.lower()
    except Exception as e:
        print(f"[AEO] Website fetch failed for {url}: {e}")
        return {"reachable": False, "has_local_business_schema": False, "has_faq_schema": False}

    has_local_business = '"@type":"localbusiness"' in html.replace(" ", "") or '"@type": "localbusiness"' in html
    has_faq = '"@type":"faqpage"' in html.replace(" ", "") or '"@type": "faqpage"' in html
    print(f"[AEO] Website: reachable=True local_schema={has_local_business} faq_schema={has_faq}")
    return {
        "reachable": True,
        "has_local_business_schema": has_local_business,
        "has_faq_schema": has_faq,
    }


def _competitor_key(competitor: dict) -> str | None:
    """Stable identifier for a competitor across the audit — place_id preferred, else lowered name."""
    return competitor.get("place_id") or (competitor.get("name") or "").strip().lower() or None


async def check_competitor_websites(competitors: list[dict]) -> dict[str, dict]:
    """Run check_website() for every competitor that has a URL — in parallel via asyncio.gather.
    Returns a dict keyed by _competitor_key() → website check result.
    Competitors without a URL or whose check raises are silently skipped (key absent)."""
    keys: list[str] = []
    tasks: list = []
    for c in competitors:
        url = c.get("website")
        key = _competitor_key(c)
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


def match_competitor_ai_citations(
    competitors: list[dict],
    perplexity_result: dict,
    google_result: dict,
) -> dict[str, dict]:
    """For each competitor, check whether their name appears in any of the per-query
    Perplexity answers or Google AI Overview text snippets we already fetched.
    Cost: $0 — pure text scanning over data we paid for during the user's audit.
    Returns a dict keyed by _competitor_key() → {perplexity_mentioned, google_ai_mentioned}."""
    perplexity_texts = [
        r.get("answer", "") for r in perplexity_result.get("per_query", [])
    ]
    google_ai_texts = [
        (r.get("ai_overview") or {}).get("text", "") for r in google_result.get("per_query", [])
    ]

    output: dict[str, dict] = {}
    for c in competitors:
        key = _competitor_key(c)
        name = (c.get("name") or "").strip()
        if not key or not name:
            continue
        perplexity_hit = any(text and _name_matches(text, name) for text in perplexity_texts)
        google_ai_hit = any(text and _name_matches(text, name) for text in google_ai_texts)
        output[key] = {
            "perplexity_mentioned": perplexity_hit,
            "google_ai_mentioned":  google_ai_hit,
        }
    hits_per = sum(1 for v in output.values() if v["perplexity_mentioned"])
    hits_g = sum(1 for v in output.values() if v["google_ai_mentioned"])
    logger.info(f"[AEO][COMP] AI citations: {hits_per}/{len(output)} Perplexity, {hits_g}/{len(output)} Google AI")
    return output


def calculate_score(business: dict, perplexity: dict, google: dict, website_check: dict) -> dict:
    # If the formula here changes, update score_competitor() to match.
    kg = google["knowledge_graph"]
    lp = google["local_pack"]

    effective_rating = kg.get("rating") or lp.get("rating") or 0
    effective_reviews = kg.get("reviews_count") or lp.get("reviews") or 0
    has_gbp = kg["found"] or lp["present"]

    gbp = 0
    if has_gbp: gbp += 10
    if effective_rating: gbp += 5
    if kg.get("type"): gbp += 5                          # only if KG has a category set
    if kg.get("website") or kg.get("phone") or business.get("website"): gbp += 5

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
    if perplexity["mentioned"]: ai += 10
    if google["ai_overview"]["mentioned"]: ai += 8

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
    # In local pack by definition. Organic check is not run for competitors (would cost
    # extra SerpApi calls per competitor and the local pack signal is the dominant one).
    local = 10

    # ─── AI Citation pillar (max 18) ─────────────────────────────
    ai = 0
    if perplexity_mentioned is True: ai += 10
    if google_ai_mentioned is True:  ai += 8

    total = gbp + rev + web + local + ai
    has_full_data = website_check is not None and perplexity_mentioned is not None and google_ai_mentioned is not None

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


def generate_recommendations(
    business: dict,
    perplexity: dict,
    google: dict,
    website_check: dict,
    breakdown: dict,
    recency: dict,
) -> list[dict]:
    """
    Maps each pillar gap to a specific, actionable recommendation.
    Returns a list sorted by impact (highest points first).
    """
    recs = []
    kg = google["knowledge_graph"]
    lp = google["local_pack"]
    has_gbp = kg["found"] or lp["present"]
    rating = kg.get("rating") or lp.get("rating") or 0
    reviews_count = kg.get("reviews_count") or lp.get("reviews") or 0

    # ─── GBP pillar ──────────────────────────────────────────
    if not has_gbp:
        recs.append({
            "pillar": "gbp",
            "title": "Claim your Google Business Profile",
            "description": "Your business doesn't appear in Google's local listings. A claimed GBP is the single most important signal for local AI search.",
            "action": "Visit business.google.com and claim or create your listing for this business.",
            "difficulty": "easy",
            "impact": 15,
            "url": "https://business.google.com",
        })
    else:
        if not kg.get("type") and breakdown["gbp"] < 25:
            recs.append({
                "pillar": "gbp",
                "title": "Set your primary GBP category",
                "description": "Your Google Business Profile doesn't have a primary category set. Categories are the #1 local pack ranking factor.",
                "action": "In your GBP dashboard, set your primary business category (e.g. 'Physiotherapy clinic'). Add 2-3 secondary categories.",
                "difficulty": "easy",
                "impact": 5,
                "url": "https://business.google.com",
            })
        if not (kg.get("website") or kg.get("phone")) and not business.get("website"):
            recs.append({
                "pillar": "gbp",
                "title": "Add a phone number and website to your GBP",
                "description": "Customers need a way to contact you directly from Google.",
                "action": "Add your business phone and website URL in your GBP profile.",
                "difficulty": "easy",
                "impact": 5,
                "url": "https://business.google.com",
            })
        # Business appears in local pack but Google hasn't generated a Knowledge Panel —
        # the profile is claimed but thin. Earning a KG panel = +5pts and unlocks recency data.
        if lp["present"] and not kg["found"]:
            recs.append({
                "pillar": "gbp",
                "title": "Enrich your GBP to earn a Google Knowledge Panel",
                "description": "Your business appears in Google Maps but doesn't have a Knowledge Panel (the sidebar card). AI engines use the Knowledge Panel as a primary trust signal — businesses without one are rarely cited.",
                "action": "Add a detailed business description, upload at least 10 photos, set your primary category, add your website and phone. Post a GBP update weekly for 4 weeks.",
                "difficulty": "medium",
                "impact": 8,
                "url": "https://business.google.com",
            })

    # ─── Reviews pillar ──────────────────────────────────────
    count_label = str(reviews_count) if reviews_count else "unknown"
    if not reviews_count or reviews_count < 10:
        recs.append({
            "pillar": "reviews",
            "title": f"Get to 10+ Google reviews (current: {count_label})",
            "description": "AI search engines use review count as a strong trust signal. Below 10 reviews, your business looks new or unestablished.",
            "action": "Send a review request link to your last 10 customers. Use Google's free 'Get more reviews' QR code generator in your GBP dashboard.",
            "difficulty": "medium",
            "impact": 6,
        })
    elif reviews_count < 50:
        recs.append({
            "pillar": "reviews",
            "title": f"Get to 50+ Google reviews (current: {reviews_count})",
            "description": "50+ reviews puts you in the top tier for review volume in your category.",
            "action": "Set up a recurring system: ask every customer for a review at the moment of service completion.",
            "difficulty": "medium",
            "impact": 6,
        })

    if rating > 0 and rating < 4.0:
        recs.append({
            "pillar": "reviews",
            "title": f"Improve your rating above 4.0 (current: {rating})",
            "description": "Ratings below 4.0 actively hurt AI citations. AI engines avoid recommending businesses with mixed reputations.",
            "action": "Respond to every negative review professionally. Identify the top complaint pattern and address it operationally.",
            "difficulty": "hard",
            "impact": 10,
        })
    elif rating > 0 and rating < 4.5:
        recs.append({
            "pillar": "reviews",
            "title": f"Push your rating above 4.5 (current: {rating})",
            "description": "4.5+ is the threshold for 'highly rated' in most AI engines.",
            "action": "Respond to every review. Encourage your most satisfied customers to leave 5-star feedback.",
            "difficulty": "medium",
            "impact": 5,
        })

    # Recency check — only shown when we successfully checked and the business is stale
    if recency.get("checked") and recency.get("recent") is False:
        days = recency.get("days_since_last")
        last = recency.get("last_review_date") or "more than 3 months ago"
        days_label = f"{days} days ago" if days else last
        recs.append({
            "pillar": "reviews",
            "title": f"You haven't received new reviews in 3+ months (last: {days_label})",
            "description": "Review recency is a trust signal for AI engines. A business with stale reviews looks inactive, even with a high total count.",
            "action": "Re-activate your review request process. Text or email your last 20 customers a direct link to your Google review page. Consider adding a QR code at your front desk.",
            "difficulty": "medium",
            "impact": 7,
        })

    # ─── Website & Schema pillar ─────────────────────────────
    if not business.get("website"):
        recs.append({
            "pillar": "website",
            "title": "Add your website URL to your profile",
            "description": "Without a website, AI engines have no authoritative source to cite about your business.",
            "action": "Add your website URL in the LeapOne profile settings. If you don't have one, free options include Google Sites or a one-page Carrd.",
            "difficulty": "medium",
            "impact": 8,
        })
    elif not website_check["reachable"]:
        recs.append({
            "pillar": "website",
            "title": "Your website is unreachable",
            "description": "Our crawler couldn't reach your website. AI engines can't cite content they can't access.",
            "action": "Test your site in an incognito browser. If it's down, contact your hosting provider. If it returns errors, check for SSL or redirect issues.",
            "difficulty": "medium",
            "impact": 8,
        })
    else:
        if not website_check["has_local_business_schema"]:
            recs.append({
                "pillar": "website",
                "title": "Add LocalBusiness schema to your homepage",
                "description": "JSON-LD schema markup tells search engines exactly what your business does, where you are, and how to contact you. AI engines rely heavily on it.",
                "action": "Use the LocalBusiness schema we generated for you in the Content tab. Paste it into your website's <head> tag.",
                "difficulty": "medium",
                "impact": 6,
            })
        if not website_check["has_faq_schema"]:
            recs.append({
                "pillar": "website",
                "title": "Add an FAQ page with FAQ schema",
                "description": "FAQ schema is the most-cited type of structured data by AI engines like ChatGPT and Perplexity.",
                "action": "Create an FAQ page on your website using the questions we generated in the Content tab. Wrap each Q&A in FAQ schema markup.",
                "difficulty": "medium",
                "impact": 6,
            })

    # ─── Local Search Presence pillar ────────────────────────
    if not google["local_pack"]["present"]:
        recs.append({
            "pillar": "local_search",
            "title": "Get into Google's local 'map pack'",
            "description": "You're not appearing in Google's top-3 local results for your category. The local pack is where most customers click first.",
            "action": "Optimize your GBP: complete every field, upload 10+ photos, post weekly updates, get reviews. Make sure your address is verified and your service area is set correctly.",
            "difficulty": "hard",
            "impact": 10,
        })
    if not google["organic"]["present"]:
        recs.append({
            "pillar": "local_search",
            "title": "Get listed in local directories",
            "description": "Your business doesn't appear in regular Google search results for your category. Citations from local directories build the authority that fixes this.",
            "action": "List your business on Yelp, Yellow Pages Canada, BBB, and 2-3 industry-specific directories. Use identical NAP (name, address, phone) on every listing.",
            "difficulty": "medium",
            "impact": 5,
        })

    # ─── AI Citation pillar ──────────────────────────────────
    if not perplexity["mentioned"]:
        recs.append({
            "pillar": "ai_citation",
            "title": "Get cited by Perplexity",
            "description": "Perplexity favors authoritative sources like Wikipedia, Reddit, news sites, and well-structured business listings.",
            "action": "Create or update your business listing on directories Perplexity crawls: Yelp, BBB, Yellow Pages, Foursquare. Ensure your website has clear, factual content about your services.",
            "difficulty": "hard",
            "impact": 10,
        })
    if not google["ai_overview"]["mentioned"]:
        recs.append({
            "pillar": "ai_citation",
            "title": "Optimize for Google AI Overview",
            "description": "Google AI Overview cites businesses with strong content + GBP + schema together. It's harder to influence than Perplexity but possible.",
            "action": "Add a 150-200 word business description on your homepage that directly answers 'what do you do, where, and for whom'. Use the description we generated for you in the Content tab.",
            "difficulty": "hard",
            "impact": 8,
        })

    # Sort by impact (highest first)
    recs.sort(key=lambda r: r["impact"], reverse=True)
    return recs


async def _run_audit_core(business: dict) -> dict:
    """Runs all audit queries and returns scored results without saving to DB."""
    business_name = business["name"]
    city = business["city"]
    province = business["province"]
    country = business.get("country") or "Canada"  # legacy default for pre-migration rows
    website = business.get("website")
    business_type_en = await normalize_business_type(business["type"], business_name)
    print(f"[AEO] Audit start — name='{business_name}' type='{business_type_en}' city='{city}, {province}, {country}' (gl={country_to_gl(country)})")

    perplexity_result = await run_perplexity_multi(business_name, business_type_en, city, province)
    google_result = await run_google_multi(business_name, business_type_en, city, province, website, country)
    website_check = await check_website(website)

    # Recency check — only if the KG gave us a place_id (i.e. business is indexed by Google)
    place_id = google_result["knowledge_graph"].get("place_id")
    recency = await _check_review_recency(place_id, country) if place_id else {"checked": False, "recent": None, "days_since_last": None, "last_review_date": None}

    scoring = calculate_score(business, perplexity_result, google_result, website_check)
    score = scoring["total"]
    breakdown = scoring["breakdown"]
    recommendations = generate_recommendations(business, perplexity_result, google_result, website_check, breakdown, recency)
    print(f"[AEO] Score: {score}/100  breakdown={breakdown}  recs={len(recommendations)}")

    # ─── Competitor scoring ────────────────────────────────────────────────
    # Score the top 3 competitors apples-to-apples using the same pillar formula.
    # Website fetches + AI citation matching run in parallel — no extra API cost,
    # only $0 httpx fetches and free text scanning over data we already paid for.
    competitors_raw = google_result.get("competitors", [])
    scored_competitors: list[dict] = []
    if competitors_raw:
        comp_websites, comp_ai = await asyncio.gather(
            check_competitor_websites(competitors_raw),
            asyncio.to_thread(match_competitor_ai_citations, competitors_raw, perplexity_result, google_result),
        )
        for c in competitors_raw:
            key = _competitor_key(c)
            website_data = comp_websites.get(key) if key else None
            ai_data = comp_ai.get(key, {}) if key else {}
            scored = score_competitor(
                c,
                website_check=website_data,
                perplexity_mentioned=ai_data.get("perplexity_mentioned"),
                google_ai_mentioned=ai_data.get("google_ai_mentioned"),
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
    competitor_insights = await _analyze_competitor_weaknesses(scored_competitors, country)

    return {
        "score":                score,
        "breakdown":            breakdown,
        "recommendations":      recommendations,
        "perplexity":           perplexity_result,
        "google":               google_result,
        "website":              website_check,
        "competitors":          scored_competitors,
        "competitor_insights":  competitor_insights,
    }


async def _resolve_maps_place_id(name: str, city: str | None, country: str | None = None) -> str | None:
    """Resolve a ChIJ-format Google Maps place_id for a business by searching
    the google_maps engine. The numeric CIDs returned by google search local_results
    are not accepted by google_maps_reviews, so we need to look up the real place_id.
    Returns None on any error."""
    query = f"{name} {city}" if city else name
    params: dict[str, str] = {
        "api_key": SERPAPI_KEY,
        "engine": "google_maps",
        "q": query,
        "hl": "en",
    }
    gl = country_to_gl(country)
    if gl:
        params["gl"] = gl
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://serpapi.com/search",
                params=params,
                timeout=20.0,
            )
            response.raise_for_status()
            data = response.json()
        # google_maps returns either place_results (single match) or local_results list
        place = data.get("place_results") or {}
        pid = place.get("place_id")
        if not pid:
            for result in data.get("local_results", []):
                pid = result.get("place_id")
                if pid and pid.startswith("ChIJ"):
                    break
        return pid if (pid and pid.startswith("ChIJ")) else None
    except Exception as e:
        logger.warning(f"[AEO][W2] Could not resolve maps place_id for '{name}': {e}")
        return None


async def _fetch_competitor_reviews(name: str, city: str | None, country: str | None = None) -> list[dict]:
    """Resolve the ChIJ-format place_id for a competitor then fetch their recent reviews
    via SerpApi google_maps_reviews. Returns [] on any error."""
    place_id = await _resolve_maps_place_id(name, city, country)
    if not place_id:
        logger.debug(f"[AEO][W2] No ChIJ place_id resolved for '{name}' — skipping")
        return []
    params: dict[str, str] = {
        "api_key": SERPAPI_KEY,
        "engine": "google_maps_reviews",
        "place_id": place_id,
        "hl": "en",
        "sort_by": "newestFirst",
    }
    gl = country_to_gl(country)
    if gl:
        params["gl"] = gl
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://serpapi.com/search",
                params=params,
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()
        reviews = data.get("reviews", [])
        return [
            {"rating": r.get("rating"), "snippet": r.get("snippet", "")}
            for r in reviews
            if r.get("snippet")
        ]
    except Exception as e:
        logger.warning(f"[AEO][W2] Failed to fetch reviews for '{name}' ({place_id}): {e}")
        return []


async def _analyze_competitor_weaknesses(scored_competitors: list[dict], country: str | None = None) -> dict:
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

    # Fetch reviews for all competitors in parallel
    # _fetch_competitor_reviews does a google_maps lookup first to resolve the ChIJ place_id
    review_results = await asyncio.gather(
        *[_fetch_competitor_reviews(c["name"], c.get("city"), country) for c in competitors_with_ids],
        return_exceptions=True,
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

    if not all_reviews:
        logger.debug("[AEO][W2] No competitor reviews fetched — skipping analysis")
        return {}

    avg_rating = round(sum(ratings) / len(ratings), 1) if ratings else None

    # Build a concise prompt — send snippets only, cap at 40 reviews to control tokens
    snippets_for_prompt = all_reviews[:40]
    review_text = "\n".join(
        f"- ({r['rating']}★) {r['snippet']}" for r in snippets_for_prompt if r.get("snippet")
    )

    prompt = f"""You are analyzing customer reviews of competitor businesses in the same local category.
Identify the top complaint themes (things customers are unhappy about).
For each theme, estimate how many reviews mention it.

Reviews:
{review_text}

Respond ONLY with a JSON object in this exact format (no markdown, no explanation):
{{
  "themes": [
    {{"theme": "Long wait times", "count": 8, "example": "had to wait 45 minutes past my appointment"}},
    {{"theme": "Parking difficulties", "count": 5, "example": "no parking available on site"}}
  ],
  "opportunity_summary": "Most competitors struggle with [X] — you can stand out by [Y]."
}}

Return at most 5 themes. Only include genuine complaints with 2+ mentions. If there are no clear complaints, return empty themes array."""

    try:
        raw = await ai_engine.generate(
            prompt=prompt,
            max_tokens=400,
            temperature=0.2,
        )
        # Strip markdown code fences if present
        cleaned = re.sub(r'^```(?:json)?\s*|\s*```$', '', raw.strip(), flags=re.MULTILINE).strip()
        parsed = json.loads(cleaned)
        themes = parsed.get("themes", [])
        opportunity_summary = parsed.get("opportunity_summary", "")
        logger.info(f"[AEO][W2] Analysed {competitors_analysed} competitors, {len(all_reviews)} reviews → {len(themes)} themes")
        return {
            "themes": themes,
            "avg_competitor_rating": avg_rating,
            "opportunity_summary": opportunity_summary,
            "competitors_analysed": competitors_analysed,
            "reviews_analysed": len(all_reviews),
        }
    except Exception as e:
        logger.warning(f"[AEO][W2] AI analysis failed: {e}")
        return {}


async def _fetch_own_reviews(place_id: str, country: str | None = None) -> list[dict]:
    """Fetch the own business's latest Google Maps reviews via SerpApi google_maps_reviews.
    Re-uses the same engine as competitor review fetching — no Phase 2 reviews table involved."""
    params: dict[str, str] = {
        "api_key": SERPAPI_KEY,
        "engine": "google_maps_reviews",
        "place_id": place_id,
        "hl": "en",
        "sort_by": "newestFirst",
    }
    gl = country_to_gl(country)
    if gl:
        params["gl"] = gl
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://serpapi.com/search",
                params=params,
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()
        reviews = data.get("reviews", [])
        return [
            {"rating": r.get("rating"), "snippet": r.get("snippet", "")}
            for r in reviews
            if r.get("snippet")
        ]
    except Exception as e:
        logger.warning(f"[AEO][OWN] Failed to fetch own reviews for place_id={place_id}: {e}")
        return []


async def _analyze_own_reputation(reviews: list[dict], business_name: str) -> dict:
    """AI analysis of own business reviews — extracts strengths and weaknesses as short phrases."""
    review_text = "\n".join(
        f"- ({r['rating']}★) {r['snippet']}" for r in reviews[:40] if r.get("snippet")
    )
    prompt = f"""You are analyzing customer reviews of {business_name}.
Identify the main strengths (things customers consistently praise) and weaknesses (recurring complaints).

Reviews:
{review_text}

Respond ONLY with a JSON object in this exact format (no markdown, no explanation):
{{
  "strengths": ["Fast and friendly service", "Clean facility"],
  "weaknesses": ["Long wait times", "Difficult parking"],
  "summary": "Customers love the friendly staff, but many mention wait times as a pain point."
}}

Return 2-5 strengths and 0-3 weaknesses as short phrases. Only include patterns mentioned by multiple reviewers."""
    try:
        raw = await ai_engine.generate(
            prompt=prompt,
            max_tokens=300,
            temperature=0.2,
        )
        cleaned = re.sub(r'^```(?:json)?\s*|\s*```$', '', raw.strip(), flags=re.MULTILINE).strip()
        parsed = json.loads(cleaned)
        return {
            "strengths": parsed.get("strengths", []),
            "weaknesses": parsed.get("weaknesses", []),
            "summary": parsed.get("summary", ""),
        }
    except Exception as e:
        logger.warning(f"[AEO][OWN] AI analysis failed: {e}")
        return {"strengths": [], "weaknesses": [], "summary": ""}


async def send_score_change_alert(owner_email: str, business_name: str, prev_score: int, new_score: int) -> None:
    delta = new_score - prev_score
    direction = "improved" if delta > 0 else "dropped"
    sign = "+" if delta > 0 else ""
    color = "#16a34a" if delta > 0 else "#dc2626"
    await send_email(
        to=owner_email,
        subject=f"Your AEO score {direction} {sign}{delta} points — {business_name}",
        body_html=f"""
            <div style="font-family:sans-serif;max-width:480px;margin:0 auto">
                <h2 style="color:#1e293b">Your AEO Readiness Score Changed</h2>
                <p>Your score for <strong>{business_name}</strong> has {direction}:</p>
                <p style="font-size:28px;font-weight:bold;color:{color};margin:16px 0">
                    {prev_score} → {new_score}
                    <span style="font-size:18px">({sign}{delta} pts)</span>
                </p>
                <p style="color:#64748b">Log in to see what changed and your recommended next steps.</p>
                <a href="https://app.leapone.ca/dashboard"
                   style="display:inline-block;background:#4f46e5;color:white;padding:10px 20px;
                          border-radius:8px;text-decoration:none;font-weight:600;margin-top:8px">
                    View Dashboard →
                </a>
            </div>
        """,
    )


class AuditRequest(BaseModel):
    business_id: str


class BusinessProfileRequest(BaseModel):
    name: str
    type: str
    city: str
    province: str | None = None
    country: str | None = "Canada"
    website: str | None = None
    services: str | None = None


@router.get("/business")
async def get_business_profile(current_user: dict = Depends(get_current_user)):
    """Returns the current user's business profile fields used in the audit."""
    business = await get_business_by_user(current_user["id"])
    if not business:
        raise HTTPException(status_code=404, detail="Business profile not found")
    return {
        "id":       str(business["id"]),
        "name":     business.get("name"),
        "type":     business.get("type"),
        "city":     business.get("city"),
        "province": business.get("province"),
        "country":  business.get("country"),
        "website":  business.get("website"),
        "services": business.get("services"),
    }


@router.put("/business")
async def update_business_profile(
    request: BusinessProfileRequest,
    current_user: dict = Depends(get_current_user),
):
    """Updates business profile fields that drive the AEO audit."""
    business = await get_business_by_user(current_user["id"])
    if not business:
        raise HTTPException(status_code=404, detail="Business profile not found")

    name = request.name.strip()
    city = request.city.strip()
    if not name or not city:
        raise HTTPException(status_code=422, detail="Business name and city are required")

    supabase_admin.table("businesses").update({
        "name":     name,
        "type":     request.type.strip() if request.type else business.get("type"),
        "city":     city,
        "province": request.province.strip() if request.province else None,
        "country":  request.country or "Canada",
        "website":  request.website.strip() if request.website else None,
        "services": request.services.strip() if request.services else None,
    }).eq("id", business["id"]).execute()

    return {"message": "Business profile updated"}


@router.post("/audit")
async def run_audit(
    request: AuditRequest,
    current_user: dict = Depends(get_current_user),
):
    business = await get_business_by_user(current_user["id"])
    if not business:
        raise HTTPException(status_code=404, detail="Business profile not found")
    if str(business["id"]) != request.business_id:
        raise HTTPException(status_code=403, detail="Access denied")

    prev_audits = supabase_admin.table("aeo_audits") \
        .select("score") \
        .eq("business_id", business["id"]) \
        .order("created_at", desc=True) \
        .limit(1) \
        .execute()
    prev_score = prev_audits.data[0]["score"] if prev_audits.data else None

    result = await _run_audit_core(business)

    supabase_admin.table("aeo_audits").insert({
        "business_id":          business["id"],
        "score":                result["score"],
        "score_breakdown":      result["breakdown"],
        "perplexity_mentioned": result["perplexity"]["mentioned"],
        "perplexity_snippet":   result["perplexity"]["snippet"],
        "google_ai_mentioned":  result["google"]["ai_overview"]["mentioned"],
        "google_ai_snippet":    result["google"]["ai_overview"]["snippet"],
        "raw_results": {
            "perplexity":           result["perplexity"],
            "google":               result["google"],
            "website":              result["website"],
            "recommendations":      result["recommendations"],
            "competitors":          result.get("competitors", []),
            "competitor_insights":  result.get("competitor_insights", {}),
        },
    }).execute()

    if prev_score is not None and abs(result["score"] - prev_score) >= 10:
        await send_score_change_alert(
            current_user["email"], business["name"], prev_score, result["score"]
        )

    # Attach raw_results so the frontend receives the same structure stored in the DB
    result["raw_results"] = {
        "perplexity":          result["perplexity"],
        "google":              result["google"],
        "website":             result["website"],
        "recommendations":     result["recommendations"],
        "competitors":         result.get("competitors", []),
        "competitor_insights": result.get("competitor_insights", {}),
    }
    return result


@router.get("/recommendations/{business_id}")
async def get_recommendations(
    business_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Returns recommendations from the most recent audit for the given business."""
    business = await get_business_by_user(current_user["id"])
    if not business or str(business["id"]) != business_id:
        raise HTTPException(status_code=403, detail="Access denied")

    latest = supabase_admin.table("aeo_audits") \
        .select("raw_results, score, score_breakdown, created_at") \
        .eq("business_id", business_id) \
        .order("created_at", desc=True) \
        .limit(1) \
        .execute()

    if not latest.data:
        return {"recommendations": [], "score": None, "breakdown": None, "audit_at": None}

    audit = latest.data[0]
    raw = audit.get("raw_results") or {}
    return {
        "recommendations": raw.get("recommendations", []),
        "score":           audit.get("score"),
        "breakdown":       audit.get("score_breakdown"),
        "audit_at":        audit.get("created_at"),
    }


@router.get("/own-reputation")
async def get_own_reputation(
    current_user: dict = Depends(get_current_user),
):
    """GET /api/v1/aeo/own-reputation
    Fetches the business's own Google Maps reviews via SerpApi (same pipeline as competitor
    analysis — does NOT use the Phase 2 reviews table) and runs AI analysis to extract
    strengths and weaknesses as short phrases.

    Result is cached in the latest audit's raw_results.own_reputation. It is re-computed
    only when the cached entry is absent (i.e. once per audit run)."""
    business = await get_business_by_user(current_user["id"])
    if not business:
        raise HTTPException(status_code=404, detail="Business profile not found")

    audits = (
        supabase_admin.table("aeo_audits")
        .select("id, raw_results, created_at")
        .eq("business_id", business["id"])
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    if not audits.data:
        raise HTTPException(status_code=404, detail="No audit found — run an AEO audit first")

    audit = audits.data[0]
    raw = audit.get("raw_results") or {}

    # Return cached result if already present for this audit
    cached = raw.get("own_reputation")
    if cached and isinstance(cached, dict) and cached.get("strengths") is not None:
        return {**cached, "cached": True}

    # Resolve place_id from the audit's knowledge_graph
    google_data = raw.get("google") or {}
    kg = google_data.get("knowledge_graph") or {}
    place_id = kg.get("place_id")
    country = business.get("country")

    if not place_id:
        return {
            "strengths": [], "weaknesses": [], "summary": "",
            "review_count": 0, "avg_rating": None, "cached": False,
            "error": "no_place_id",
        }

    reviews = await _fetch_own_reviews(place_id, country)
    if not reviews:
        return {
            "strengths": [], "weaknesses": [], "summary": "",
            "review_count": 0, "avg_rating": None, "cached": False,
        }

    ratings = [r["rating"] for r in reviews if r.get("rating")]
    avg_rating = round(sum(ratings) / len(ratings), 1) if ratings else None

    result = await _analyze_own_reputation(reviews, business["name"])
    result["review_count"] = len(reviews)
    result["avg_rating"] = avg_rating

    # Cache into this audit's raw_results so we don't re-call SerpApi + AI unnecessarily
    updated_raw = {**raw, "own_reputation": result}
    supabase_admin.table("aeo_audits").update(
        {"raw_results": updated_raw}
    ).eq("id", audit["id"]).execute()

    return {**result, "cached": False}


@router.post("/cron-monthly")
async def cron_monthly_audit(authorization: str | None = Header(default=None)):
    """Monthly auto-audit for all businesses. Called by Vercel Cron via the Next.js proxy route."""
    if not CRON_SECRET or authorization != f"Bearer {CRON_SECRET}":
        raise HTTPException(status_code=401, detail="Unauthorized")

    businesses = supabase_admin.table("businesses").select("*").execute()
    summary = []

    for business in businesses.data:
        try:
            prev_audits = supabase_admin.table("aeo_audits") \
                .select("score") \
                .eq("business_id", business["id"]) \
                .order("created_at", desc=True) \
                .limit(1) \
                .execute()
            prev_score = prev_audits.data[0]["score"] if prev_audits.data else None

            result = await _run_audit_core(business)

            supabase_admin.table("aeo_audits").insert({
                "business_id":          business["id"],
                "score":                result["score"],
                "score_breakdown":      result["breakdown"],
                "perplexity_mentioned": result["perplexity"]["mentioned"],
                "perplexity_snippet":   result["perplexity"]["snippet"],
                "google_ai_mentioned":  result["google"]["ai_overview"]["mentioned"],
                "google_ai_snippet":    result["google"]["ai_overview"]["snippet"],
                "raw_results": {
                    "perplexity":      result["perplexity"],
                    "google":          result["google"],
                    "website":         result["website"],
                    "recommendations": result["recommendations"],
                    "competitors":     result.get("competitors", []),
                },
            }).execute()

            if prev_score is not None and abs(result["score"] - prev_score) >= 10:
                user_resp = supabase_admin.auth.admin.get_user_by_id(business["user_id"])
                owner_email = user_resp.user.email if user_resp and user_resp.user else None
                if owner_email:
                    await send_score_change_alert(owner_email, business["name"], prev_score, result["score"])

            summary.append({"business_id": str(business["id"]), "score": result["score"], "status": "ok"})
            print(f"[CRON] Audited {business['name']}: {result['score']}/100")
        except Exception as e:
            print(f"[CRON] Failed to audit {business.get('name', business['id'])}: {e}")
            summary.append({"business_id": str(business["id"]), "error": str(e), "status": "error"})

    return {"audited": len(summary), "results": summary}


@router.post("/generate-content")
async def generate_content(
    request: AuditRequest,
    current_user: dict = Depends(get_current_user),
):
    business = await get_business_by_user(current_user["id"])
    if not business:
        raise HTTPException(status_code=404, detail="Business profile not found")

    if str(business["id"]) != request.business_id:
        raise HTTPException(status_code=403, detail="Access denied")

    latest_audit = supabase_admin.table("aeo_audits") \
        .select("*") \
        .eq("business_id", business["id"]) \
        .order("created_at", desc=True) \
        .limit(1) \
        .execute()

    audit = latest_audit.data[0] if latest_audit.data else None

    name     = business["name"]
    btype    = business["type"]
    city     = business["city"]
    services = business.get("services") or ""
    website  = business.get("website") or ""

    audit_context = ""
    if audit:
        gaps = []
        if not audit["perplexity_mentioned"]: gaps.append("Perplexity")
        if not audit["google_ai_mentioned"]:  gaps.append("Google AI Overview")
        if gaps:
            audit_context = f"The business is NOT currently appearing in: {', '.join(gaps)}. "

    base_context = f"""
Business name: {name}
Business type: {btype}
City: {city}
Services: {services}
Website: {website}
{audit_context}
"""

    description = await ai_engine.generate(
        prompt=f"{base_context}\nWrite a 150-200 word business description optimized to appear in AI search engine answers (ChatGPT, Perplexity, Google AI Overview). Be specific, mention the city and key services. Write in third person.",
        max_tokens=400,
        temperature=0.7,
    )

    faq_raw = await ai_engine.generate(
        prompt=f"{base_context}\nGenerate 5 FAQ questions and answers that potential customers would ask about this business. Format as JSON array: [{{\"question\": \"...\", \"answer\": \"...\"}}]. Return only valid JSON.",
        system_prompt="Return only valid JSON, no markdown.",
        max_tokens=800,
        temperature=0.5,
    )

    schema_raw = await ai_engine.generate(
        prompt=f"{base_context}\nGenerate a JSON-LD schema markup (LocalBusiness type) for this business. Include name, type, address (city), and description. Return only the JSON-LD script tag content.",
        system_prompt="Return only valid JSON-LD, no explanation.",
        max_tokens=600,
        temperature=0.2,
    )

    social_bio = await ai_engine.generate(
        prompt=f"{base_context}\nWrite a 150-character social media bio for Instagram/Facebook for this business. Be punchy and include the city and main service.",
        max_tokens=100,
        temperature=0.8,
    )

    import json
    try:
        faq = json.loads(re.sub(r'^```(?:json)?\s*|\s*```$', '', faq_raw.strip(), flags=re.MULTILINE))
    except Exception:
        faq = []

    supabase_admin.table("aeo_content").insert({
        "business_id":    business["id"],
        "description":    description,
        "faq":            faq,
        "schema_markup":  schema_raw,
        "social_bio":     social_bio,
    }).execute()

    return {
        "description":   description,
        "faq":           faq,
        "schema_markup": schema_raw,
        "social_bio":    social_bio,
    }

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from core.ai_engine import ai_engine
from core.auth import get_current_user
from core.database import supabase_admin, get_business_by_user, get_active_subscription
from core.notifications import send_email
import asyncio
import httpx
import json
import os
import logging
import re
from openai import AsyncOpenAI
from .schema_builder import build_schema, build_faq_schema, find_missing_required_fields
_audit_openai = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

logger = logging.getLogger(__name__)
router = APIRouter()

PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SERPAPI_KEY = os.getenv("SERPAPI_KEY")
CRON_SECRET = os.getenv("CRON_SECRET")
BILLING_ENABLED = os.getenv("BILLING_ENABLED", "false").lower() == "true"
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


def build_queries(
    business_type_en: str,
    city: str,
    province: str,
    postal_code: str | None = None,
    is_trades: bool = False,
    is_healthcare: bool = False,
) -> list[str]:
    """
    Returns the list of search-query strings to run against each AI engine.

    Base set: 3 templates (Best/near/Top) — runs for every audit.

    Conditional additions (only added when the gating condition is true,
    keeping cost predictable):
      * FSA-prefix query when postal_code is set — uniquely Canadian
        search pattern, ~20% of locals search by FSA prefix
      * Emergency / 24-7 query for trades + healthcare — high-intent
        urgency searches
      * Weekend-availability query for trades + healthcare — common
        intent for after-hours services
    """
    queries = [t.format(type=business_type_en, city=city, province=province)
               for t in QUERY_TEMPLATES]

    if postal_code and len(postal_code.strip()) >= 3:
        fsa = postal_code.strip()[:3].upper()
        queries.append(f"{business_type_en} near {fsa}")

    if is_trades or is_healthcare:
        queries.append(f"Emergency {business_type_en} {city} 24/7")
        queries.append(f"{business_type_en} open weekends {city}")

    return queries


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


async def run_perplexity_multi(
    business_name: str,
    business_type_en: str,
    city: str,
    province: str,
    postal_code: str | None = None,
    is_trades: bool = False,
    is_healthcare: bool = False,
) -> dict:
    results = []
    for query in build_queries(business_type_en, city, province, postal_code, is_trades, is_healthcare):
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
    response = await _audit_openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a local business search assistant. "
                    "A user is asking you to recommend businesses in their area. "
                    "Answer based on your training knowledge, listing specific business names where you know them."
                ),
            },
            {"role": "user", "content": query},
        ],
        max_tokens=500,
        temperature=0.0,
    )
    answer = response.choices[0].message.content.strip()
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
) -> dict:
    results = []
    for query in build_queries(business_type_en, city, province, postal_code, is_trades, is_healthcare):
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
) -> dict:
    results = []
    for query in build_queries(business_type_en, city, province, postal_code, is_trades, is_healthcare):
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
        cross_border: list[dict] = []
        for c in deduped:
            cgl = address_country_gl(c.get("address"))
            if cgl is None or cgl == user_gl:
                same_country.append(c)
            else:
                cross_border.append(c)
        if len(same_country) >= 3:
            competitors_data = same_country[:3]
        else:
            # Not enough same-country competitors — pad with cross-border rather
            # than showing a shorter list. Cross-border is still better than nothing.
            competitors_data = (same_country + cross_border)[:3]
        logger.info(f"[AEO][COMP] {len(same_country)} same-country, {len(cross_border)} cross-border → showing {len(competitors_data)} (user_gl={user_gl})")
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
    chatgpt_result: dict,
) -> dict[str, dict]:
    """For each competitor, check whether their name appears in any of the per-query
    Perplexity, Google AI Overview, or ChatGPT answers we already fetched.
    Cost: $0 — pure text scanning over data we paid for during the user's audit.
    Returns a dict keyed by _competitor_key() → {perplexity_mentioned, google_ai_mentioned, chatgpt_mentioned}."""
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
        key = _competitor_key(c)
        name = (c.get("name") or "").strip()
        if not key or not name:
            continue
        perplexity_hit = any(text and _name_matches(text, name) for text in perplexity_texts)
        google_ai_hit  = any(text and _name_matches(text, name) for text in google_ai_texts)
        chatgpt_hit    = any(text and _name_matches(text, name) for text in chatgpt_texts)
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

    gbp = 0
    if has_gbp: gbp += 10
    if effective_rating: gbp += 5
    if kg.get("type"): gbp += 5
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


def generate_recommendations(
    business: dict,
    perplexity: dict,
    google: dict,
    website_check: dict,
    breakdown: dict,
    recency: dict,
    chatgpt: dict | None = None,
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
    if chatgpt and not chatgpt["mentioned"]:
        recs.append({
            "pillar": "ai_citation",
            "title": "Build your presence in ChatGPT's training data",
            "description": (
                "ChatGPT answers from its training knowledge, not live search. "
                "Your business isn't prominent enough yet to appear in its responses. "
                "These actions build the web footprint that gets picked up in future AI model updates (typically 6–12 months)."
            ),
            "action": (
                "1. Claim and fully complete your Yelp, TripAdvisor, and Yellow Pages profiles — "
                "these platforms are heavily indexed in AI training data. "
                "2. Get listed in your local Chamber of Commerce and BBB. "
                "3. Seek a mention in a local news article or industry publication. "
                "4. Add a detailed FAQ page to your website — Q&A content is exactly what LLMs train on."
            ),
            "difficulty": "hard",
            "impact": 6,
        })
    if not perplexity["mentioned"]:
        recs.append({
            "pillar": "ai_citation",
            "title": "Get cited by Perplexity",
            "description": "Perplexity searches the web in real time. It favors authoritative sources like Yelp, Reddit, news sites, and well-structured business listings.",
            "action": "Create or update your business listing on directories Perplexity crawls: Yelp, BBB, Yellow Pages, Foursquare. Ensure your website has clear, factual content about your services.",
            "difficulty": "hard",
            "impact": 6,
        })
    if not google["ai_overview"]["mentioned"]:
        recs.append({
            "pillar": "ai_citation",
            "title": "Optimize for Google AI Overview",
            "description": "Google AI Overview cites businesses with strong GBP + content + schema together. It's the hardest AI engine to influence but rewards a complete profile.",
            "action": "Add a 150-200 word business description on your homepage that directly answers 'what do you do, where, and for whom'. Use the description we generated for you in the Content tab.",
            "difficulty": "hard",
            "impact": 6,
        })

    # ─── Canadian vertical-specific directory recommendations ─────
    # Each block is gated by a vertical detector AND by whether the user
    # is already detected on that directory in their organic results.
    # Compute user_dirs once, lazily — only when at least one vertical fires.
    btype = business.get("type")
    needs_vertical_check = (
        _is_trades_business(btype)
        or _is_healthcare_business(btype)
        or _is_food_business(btype)
        or _is_legal_business(btype)
        or _is_realtor_business(btype)
    )
    user_dirs: set[str] = set()
    if needs_vertical_check:
        user_dirs = _user_directories_only(
            google.get("per_query", []),
            business.get("name", ""),
        )

    # Trades — HomeStars + TrustedPros
    if _is_trades_business(btype):
        if "HomeStars" not in user_dirs:
            recs.append({
                "pillar": "ai_citation",
                "title": "Claim your HomeStars profile",
                "description": "HomeStars is Canada's largest trades directory and one of the most-cited sources by AI engines (ChatGPT, Perplexity, Google AI Overview) when answering 'best contractor in <city>' questions. Trades businesses without a HomeStars profile are dramatically less likely to be cited.",
                "action": "Create a free contractor profile at homestars.com/create-account. Complete your services, service area, and request reviews from your last 5 satisfied customers.",
                "difficulty": "easy",
                "impact": 4,
                "url": "https://homestars.com/create-account",
            })
        if "TrustedPros" not in user_dirs:
            recs.append({
                "pillar": "ai_citation",
                "title": "Claim your TrustedPros profile",
                "description": "TrustedPros is the second-largest Canadian trades directory and a trusted citation source for AI engines. Combined with a HomeStars listing, it materially boosts your chance of being cited in AI answers about local trades.",
                "action": "Sign up as a contractor at trustedpros.ca. Verify your business details and request a few customer reviews to bootstrap your rating.",
                "difficulty": "easy",
                "impact": 3,
                "url": "https://www.trustedpros.ca/contractor",
            })

    # Healthcare — RateMDs (any healthcare) + Opencare (dentists specifically)
    if _is_healthcare_business(btype):
        if "RateMDs" not in user_dirs:
            recs.append({
                "pillar": "ai_citation",
                "title": "Claim your RateMDs profile",
                "description": "RateMDs is Canada's largest healthcare-provider rating site. AI engines cite it heavily when patients search 'best dentist/doctor/physiotherapist near me'. Healthcare businesses without a RateMDs profile are routinely missed in AI answers about local care.",
                "action": "Find your existing RateMDs listing (created automatically from public records) at ratemds.com and claim it, or create a new profile. Verify your credentials, hours, and services.",
                "difficulty": "easy",
                "impact": 4,
                "url": "https://www.ratemds.com",
            })
        if _is_dentist_business(btype) and "Opencare" not in user_dirs:
            recs.append({
                "pillar": "ai_citation",
                "title": "Claim your Opencare profile",
                "description": "Opencare is the dominant Canadian directory for dental practices and is regularly cited by ChatGPT and Perplexity for 'best dentist in <city>' queries. Dentists not on Opencare miss a category-specific citation source.",
                "action": "Sign up as a dental practice at opencare.com/dentists/join. Complete your services, accepted insurance, and office hours.",
                "difficulty": "easy",
                "impact": 3,
                "url": "https://www.opencare.com/dentists/join/",
            })

    # Food — OpenTable + TripAdvisor
    if _is_food_business(btype):
        if "OpenTable" not in user_dirs:
            recs.append({
                "pillar": "ai_citation",
                "title": "Claim your OpenTable listing",
                "description": "OpenTable is the most-cited restaurant-discovery source for AI engines in Canada. Even if you don't take reservations through them, the directory presence alone boosts visibility in AI search answers about local dining.",
                "action": "Sign up at restaurant.opentable.com. You can list your restaurant for discovery without enabling reservations.",
                "difficulty": "easy",
                "impact": 4,
                "url": "https://restaurant.opentable.com",
            })
        if "TripAdvisor" not in user_dirs:
            recs.append({
                "pillar": "ai_citation",
                "title": "Claim your TripAdvisor business listing",
                "description": "TripAdvisor is widely cited by Perplexity and Google AI Overview for restaurant queries — especially when the searcher includes 'best' or 'top'. A complete TripAdvisor profile is one of the highest-ROI citations for restaurants in Canada.",
                "action": "Claim your business at tripadvisor.com/Owners. Add photos, menu, and respond to recent reviews.",
                "difficulty": "easy",
                "impact": 3,
                "url": "https://www.tripadvisor.com/Owners",
            })

    # Legal — LawyerLocate
    if _is_legal_business(btype) and "LawyerLocate" not in user_dirs:
        recs.append({
            "pillar": "ai_citation",
            "title": "Claim your LawyerLocate profile",
            "description": "LawyerLocate is a Canadian-specific lawyer directory that ranks well in AI engine answers about legal services. Combined with a LinkedIn presence, it materially boosts AI citation rates for solo practitioners and small firms.",
            "action": "Register at lawyerlocate.ca/lawyers/register. List your practice areas, jurisdictions, and contact details.",
            "difficulty": "easy",
            "impact": 3,
            "url": "https://www.lawyerlocate.ca/lawyers/register",
        })

    # Realtor — Realtor.ca (CREA-national)
    if _is_realtor_business(btype) and "Realtor.ca" not in user_dirs:
        recs.append({
            "pillar": "ai_citation",
            "title": "Ensure you appear on Realtor.ca",
            "description": "Realtor.ca is the national directory operated by the Canadian Real Estate Association (CREA). It is the single most-cited source by AI engines for Canadian real estate queries. Active CREA membership puts you on Realtor.ca automatically — verify your listing is complete and current.",
            "action": "Confirm your CREA membership is active via your provincial real estate board, then verify your Realtor.ca profile shows current listings, photo, contact details, and specializations.",
            "difficulty": "easy",
            "impact": 4,
            "url": "https://www.crea.ca/membership/",
        })

    # ─── Universal AI-engine listings (any vertical) ──────────────
    # Apple Business Connect feeds Apple Maps + Apple Intelligence.
    # Bing Places feeds Microsoft Copilot. Both are growing AI citation
    # sources; both are free and under-claimed by Canadian SMBs.
    # We can't easily detect presence from SerpApi (Apple Maps + Bing Places
    # don't surface in Google's index) so we fire for all businesses at
    # low impact — the cost of ignoring is much higher than the noise of
    # showing one extra rec.
    recs.append({
        "pillar": "ai_citation",
        "title": "Claim your Apple Business Connect listing",
        "description": "Apple Business Connect (free) controls how your business shows up in Apple Maps and is increasingly cited by Apple Intelligence on iPhone/iPad. Most Canadian SMBs have not claimed their listing — this is one of the lowest-effort, highest-incremental-reach citations available right now.",
        "action": "Visit businessconnect.apple.com, sign in with your Apple ID, find your business, and verify ownership. Takes 5–10 minutes.",
        "difficulty": "easy",
        "impact": 2,
        "url": "https://businessconnect.apple.com",
    })
    recs.append({
        "pillar": "ai_citation",
        "title": "Claim your Bing Places listing",
        "description": "Bing Places feeds Microsoft Copilot's local search answers. With Copilot integrated into Windows 11 and Microsoft 365, Bing Places presence is a growing AI citation factor. Bing Places will auto-import your Google Business Profile data — you just need to verify ownership.",
        "action": "Visit bingplaces.com, import from Google, verify ownership, and confirm your details. Takes 5 minutes.",
        "difficulty": "easy",
        "impact": 2,
        "url": "https://www.bingplaces.com",
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
    postal_code = business.get("postal_code")
    business_type_en = await normalize_business_type(business["type"], business_name)

    # Vertical flags drive the conditional query templates (FSA / emergency / weekend).
    # Use the original business type (the user's free-form entry) for vertical detection
    # since that's what the regex patterns are tuned against.
    is_trades_v     = _is_trades_business(business.get("type"))
    is_healthcare_v = _is_healthcare_business(business.get("type"))

    print(f"[AEO] Audit start — name='{business_name}' type='{business_type_en}' city='{city}, {province}, {country}' (gl={country_to_gl(country)}, trades={is_trades_v}, healthcare={is_healthcare_v}, fsa={postal_code[:3].upper() if postal_code and len(postal_code) >= 3 else 'n/a'})")

    perplexity_result, google_result, chatgpt_result = await asyncio.gather(
        run_perplexity_multi(business_name, business_type_en, city, province,
                             postal_code=postal_code, is_trades=is_trades_v, is_healthcare=is_healthcare_v),
        run_google_multi(business_name, business_type_en, city, province, website, country,
                         postal_code=postal_code, is_trades=is_trades_v, is_healthcare=is_healthcare_v),
        run_chatgpt_multi(business_name, business_type_en, city, province,
                          postal_code=postal_code, is_trades=is_trades_v, is_healthcare=is_healthcare_v),
    )
    website_check = await check_website(website)

    # Recency check — only if the KG gave us a place_id (i.e. business is indexed by Google)
    place_id = google_result["knowledge_graph"].get("place_id")
    recency = await _check_review_recency(place_id, country) if place_id else {"checked": False, "recent": None, "days_since_last": None, "last_review_date": None}

    scoring = calculate_score(business, perplexity_result, google_result, website_check, chatgpt_result)
    score = scoring["total"]
    breakdown = scoring["breakdown"]
    recommendations = generate_recommendations(business, perplexity_result, google_result, website_check, breakdown, recency, chatgpt_result)
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
            asyncio.to_thread(match_competitor_ai_citations, competitors_raw, perplexity_result, google_result, chatgpt_result),
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
    competitor_insights = await _analyze_competitor_weaknesses(scored_competitors, country)

    # ─── Citation gap analysis (W3) ───────────────────────────────────────
    # Walk organic_results across the 3 google queries, detect directory listings
    # (Yelp, BBB, Yellow Pages, etc.), and compute which directories competitors
    # appear on that the user does not. $0 cost — pure text scan over data we
    # already paid SerpApi for.
    citation_gaps = _detect_directory_presence(
        google_result.get("per_query", []),
        business_name,
        [c.get("name") for c in scored_competitors if c.get("name")],
    )

    return {
        "score":                score,
        "breakdown":            breakdown,
        "recommendations":      recommendations,
        "perplexity":           perplexity_result,
        "google":               google_result,
        "chatgpt":              chatgpt_result,
        "website":              website_check,
        "competitors":          scored_competitors,
        "competitor_insights":  competitor_insights,
        "citation_gaps":        citation_gaps,
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


async def _fetch_own_reviews(
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
        "api_key": SERPAPI_KEY,
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
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://serpapi.com/search",
                    params=params,
                    timeout=30.0,
                )
                response.raise_for_status()
                data = response.json()
        except Exception as e:
            logger.warning(f"[AEO][OWN] Failed to fetch reviews page {page+1} for place_id={place_id}: {e}")
            break

        reviews = data.get("reviews", [])
        if not reviews:
            break

        hit_cutoff = False
        for r in reviews:
            days = _parse_relative_date(r.get("date"))
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


async def _analyze_own_reputation(reviews: list[dict], business_name: str) -> dict:
    """AI analysis of own business reviews — extracts strengths and weaknesses as short phrases."""
    review_text = "\n".join(
        f"- ({r['rating']}★) {r['snippet']}" for r in reviews[:60] if r.get("snippet")
    )
    prompt = f"""You are analyzing customer reviews from the last 3 months for {business_name}.
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


class GenerateContentRequest(BaseModel):
    business_id: str
    language: str = "en"  # 'en' | 'fr'


# ─── Directory presence (citation gap analysis) ───────────────────────────
# Known directory/citation domains that we recognise in organic results.
# Mix of US + Canadian + international + niche health/professional sites.
DIRECTORY_DOMAINS: dict[str, str] = {
    "yelp.com":             "Yelp",
    "yelp.ca":              "Yelp",
    "yellowpages.com":      "Yellow Pages",
    "yellowpages.ca":       "Yellow Pages",
    "ypg.com":              "Yellow Pages",
    "bbb.org":              "BBB",
    "tripadvisor.com":      "TripAdvisor",
    "tripadvisor.ca":       "TripAdvisor",
    "facebook.com":         "Facebook",
    "instagram.com":        "Instagram",
    "linkedin.com":         "LinkedIn",
    "foursquare.com":       "Foursquare",
    "nextdoor.com":         "Nextdoor",
    "ratemds.com":          "RateMDs",
    "healthgrades.com":     "Healthgrades",
    "411.ca":               "411.ca",
    "canada411.ca":         "Canada411",
    "mapquest.com":         "MapQuest",
    "opencare.com":         "Opencare",
    "zocdoc.com":           "Zocdoc",
    "wellness.com":         "Wellness.com",
    "houzz.com":            "Houzz",
    "homestars.com":        "HomeStars",
    "trustedpros.ca":       "TrustedPros",
    "angi.com":             "Angi",
    "thumbtack.com":        "Thumbtack",
    # Canadian general directories (added 2026-05-08)
    "n49.com":              "n49",
    "cylex-canada.ca":      "Cylex Canada",
    # Canadian vertical-specific directories
    "realtor.ca":           "Realtor.ca",
    "lawyerlocate.ca":      "LawyerLocate",
    "opentable.com":        "OpenTable",
    "opentable.ca":         "OpenTable",
}

# Canadian trades-business detector — used by recommendations engine
# to suggest HomeStars/TrustedPros listings for plumbers, electricians, etc.
_TRADES_PATTERN = re.compile(
    r"\bplumb\w+|\belectric(ian|al)\b|\bhvac\b|\bheating\b|\bcooling\b|"
    r"\bair\s+conditioning|\broof\w+|\bcontractor\b|\bgeneral\s+contractor|"
    r"\bconstruction|\bhouse\s*painter|\bpainting\s+contractor|\blocksmith|"
    r"\bhandyman|\blandscap\w+|\bcarpent\w+|\bflooring\b|\brenovat\w+",
    re.IGNORECASE,
)


def _is_trades_business(business_type: str | None) -> bool:
    """True if the business looks like a Canadian trades business — used to
    gate HomeStars/TrustedPros recommendations."""
    if not business_type:
        return False
    return bool(_TRADES_PATTERN.search(business_type))


# Vertical detectors used to gate Canadian-specific recommendations.
# Each pattern is intentionally narrow — false positives mean the wrong rec
# fires for the wrong business, which is more damaging than a missed rec.

_HEALTHCARE_PATTERN = re.compile(
    r"\bdentist|\bdental\b|\bdoctor\b|\bphysician\b|\bphysiotherap\w*|"
    r"\bphysical\s+therap\w*|\bchiropract\w+|\boptometr\w+|\beye\s+care|"
    r"\bvet(erinary)?\b|\banimal\s+hospital|\bpharm\w+|\bmedical\s+clinic|"
    r"\bclinic\b|\bnaturopath\w*|\bmassage\s+therap\w*|\baudiologist|"
    r"\bpsychologist|\bcounsell?ing|\btherapist",
    re.IGNORECASE,
)

_DENTIST_PATTERN = re.compile(r"\bdentist|\bdental\b|\borthodont\w+", re.IGNORECASE)

_FOOD_PATTERN = re.compile(
    r"\brestaurant|\bdiner\b|\bsteakhouse|\bsushi|\bpizza|\bcaf[eé]\b|"
    r"\bcoffee\s+shop|\bbakery|\bbar\b|\bpub\b|\bbrewery|\bbistro|\beatery",
    re.IGNORECASE,
)

_LEGAL_PATTERN = re.compile(
    r"\blawyer|\battorney|\blegal\s+service|\blaw\s+(firm|office)|"
    r"\bparalegal|\bnotary\s+public",
    re.IGNORECASE,
)

_REALTOR_PATTERN = re.compile(
    r"\breal\s+estate|\brealtor\b|\brealty\b",
    re.IGNORECASE,
)


def _is_healthcare_business(business_type: str | None) -> bool:
    return bool(business_type and _HEALTHCARE_PATTERN.search(business_type))


def _is_dentist_business(business_type: str | None) -> bool:
    return bool(business_type and _DENTIST_PATTERN.search(business_type))


def _is_food_business(business_type: str | None) -> bool:
    return bool(business_type and _FOOD_PATTERN.search(business_type))


def _is_legal_business(business_type: str | None) -> bool:
    return bool(business_type and _LEGAL_PATTERN.search(business_type))


def _is_realtor_business(business_type: str | None) -> bool:
    return bool(business_type and _REALTOR_PATTERN.search(business_type))


def _user_directories_only(per_query_results: list[dict], business_name: str) -> set[str]:
    """Lightweight helper: which directories does the user appear on?
    Used by generate_recommendations() — same matching logic as
    _detect_directory_presence() but skips the competitor side."""
    user_dirs: set[str] = set()
    user_short = _name_short(business_name)
    if not user_short:
        return user_dirs

    for q in per_query_results or []:
        for r in q.get("organic_results_raw", []) or []:
            link = r.get("link") or ""
            domain = _domain_from_url(link)
            label = None
            for d_domain, d_label in DIRECTORY_DOMAINS.items():
                if domain == d_domain or domain.endswith("." + d_domain):
                    label = d_label
                    break
            if not label:
                continue
            haystack = ((r.get("title") or "") + " " + (r.get("snippet") or "")).lower()
            if user_short in haystack:
                user_dirs.add(label)
    return user_dirs


def _domain_from_url(url: str) -> str:
    """Strip scheme/path/www; return bare domain in lowercase."""
    if not url:
        return ""
    u = url.lower()
    u = re.sub(r"^https?://", "", u)
    u = u.split("/", 1)[0]
    u = re.sub(r"^www\.", "", u)
    return u


def _name_short(name: str | None) -> str:
    """First 3 words of a business name, lowercased — used as a lenient
    substring match against organic-result snippets."""
    if not name:
        return ""
    return " ".join(name.lower().strip().split()[:3])


def _detect_directory_presence(
    per_query_results: list[dict],
    business_name: str,
    competitor_names: list[str],
) -> dict:
    """
    Walk organic_results across all queries and determine which directories
    the user and each competitor appear on.
    Heuristic: a business is "on" a directory if its first three name words
    appear in the title or snippet of an organic result whose URL is on that
    directory's domain. Approximate but practical given SerpApi data.

    Returns:
      {
        "user":        ["Yelp", "BBB"],
        "competitors": {<comp_name>: ["Yelp", ...]},
        "gaps":        ["TripAdvisor", "Yellow Pages"]
      }
    """
    user_dirs: set[str] = set()
    competitor_dirs: dict[str, set[str]] = {n: set() for n in competitor_names if n}

    user_short = _name_short(business_name)
    competitor_shorts = {n: _name_short(n) for n in competitor_dirs}

    for q in per_query_results or []:
        for r in q.get("organic_results_raw", []) or []:
            link = r.get("link") or ""
            domain = _domain_from_url(link)
            label = None
            for d_domain, d_label in DIRECTORY_DOMAINS.items():
                if domain == d_domain or domain.endswith("." + d_domain):
                    label = d_label
                    break
            if not label:
                continue
            haystack = ((r.get("title") or "") + " " + (r.get("snippet") or "")).lower()

            if user_short and user_short in haystack:
                user_dirs.add(label)
            for name, n_short in competitor_shorts.items():
                if n_short and n_short in haystack:
                    competitor_dirs[name].add(label)

    all_competitor_dirs: set[str] = set()
    for s in competitor_dirs.values():
        all_competitor_dirs |= s

    gaps = sorted(all_competitor_dirs - user_dirs)

    return {
        "user":        sorted(user_dirs),
        "competitors": {n: sorted(s) for n, s in competitor_dirs.items()},
        "gaps":        gaps,
    }


# ─── Profile-field validators (used by PUT /business) ──────────────────────
_CANADIAN_POSTAL = re.compile(
    r"^[ABCEGHJ-NPRSTVXY]\d[ABCEGHJ-NPRSTV-Z][ -]?\d[ABCEGHJ-NPRSTV-Z]\d$",
    re.IGNORECASE,
)
_HOURS_RANGE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)-([01]\d|2[0-3]):([0-5]\d)$")
_ALLOWED_PRICE_RANGES = {"$", "$$", "$$$", "$$$$"}
_WEEKDAYS = {"monday", "tuesday", "wednesday", "thursday",
             "friday", "saturday", "sunday"}

def _clean_postal(postal: str | None, country: str | None) -> str | None:
    if not postal or not postal.strip():
        return None
    p = postal.strip().upper()
    if (country or "Canada") == "Canada" and not _CANADIAN_POSTAL.match(p):
        raise HTTPException(status_code=422,
            detail="postal_code: invalid Canadian postal code (e.g. K1P 5N7)")
    return p

def _clean_image_url(url: str | None) -> str | None:
    if not url or not url.strip():
        return None
    u = url.strip()
    if not (u.startswith("http://") or u.startswith("https://")):
        raise HTTPException(status_code=422,
            detail="image_url must start with http:// or https://")
    return u

def _clean_price_range(pr: str | None) -> str | None:
    if not pr or not pr.strip():
        return None
    p = pr.strip()
    if p not in _ALLOWED_PRICE_RANGES:
        raise HTTPException(status_code=422,
            detail="price_range must be one of '$', '$$', '$$$', '$$$$'")
    return p

def _clean_hours(hours: dict | None) -> dict | None:
    if hours is None:
        return None
    if not isinstance(hours, dict):
        raise HTTPException(status_code=422, detail="hours must be an object")
    out: dict[str, str] = {}
    for day, val in hours.items():
        d = str(day).lower().strip()
        if d not in _WEEKDAYS:
            raise HTTPException(status_code=422,
                detail=f"hours: invalid day '{day}'")
        if val is None or str(val).strip() == "":
            continue
        v = str(val).strip().lower()
        if v == "closed":
            out[d] = "closed"
        elif _HOURS_RANGE.match(v):
            out[d] = v
        else:
            raise HTTPException(status_code=422,
                detail=f"hours[{d}]: must be 'closed' or 'HH:MM-HH:MM'")
    return out or None


class BusinessProfileRequest(BaseModel):
    name: str
    type: str
    city: str
    province: str | None = None
    country: str | None = "Canada"
    website: str | None = None
    services: str | None = None
    street_address: str | None = None
    postal_code: str | None = None
    phone: str | None = None
    image_url: str | None = None
    price_range: str | None = None
    hours: dict | None = None  # {"monday": "09:00-17:00", "tuesday": "closed", ...}


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
        "street_address": business.get("street_address"),
        "postal_code": business.get("postal_code"),
        "phone": business.get("phone"),
        "image_url": business.get("image_url"),
        "price_range": business.get("price_range"),
        "hours": business.get("hours"),
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

    country = request.country or "Canada"

    supabase_admin.table("businesses").update({
        "name":           name,
        "type":           request.type.strip() if request.type else business.get("type"),
        "city":           city,
        "province":       request.province.strip() if request.province else None,
        "country":        country,
        "website":        request.website.strip() if request.website else None,
        "services":       request.services.strip() if request.services else None,
        "street_address": request.street_address.strip() if request.street_address else None,
        "postal_code":    _clean_postal(request.postal_code, country),
        "phone":          request.phone.strip() if request.phone else None,
        "image_url":      _clean_image_url(request.image_url),
        "price_range":    _clean_price_range(request.price_range),
        "hours":          _clean_hours(request.hours),
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

    if BILLING_ENABLED:
        subscription = await get_active_subscription(str(business["id"]))
        if not subscription:
            raise HTTPException(status_code=402, detail="Active subscription required")

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
        "chatgpt_mentioned":    result["chatgpt"]["mentioned"],
        "chatgpt_snippet":      result["chatgpt"]["snippet"],
        "raw_results": {
            "perplexity":           result["perplexity"],
            "google":               result["google"],
            "chatgpt":              result["chatgpt"],
            "website":              result["website"],
            "recommendations":      result["recommendations"],
            "competitors":          result.get("competitors", []),
            "competitor_insights":  result.get("competitor_insights", {}),
            "citation_gaps":        result.get("citation_gaps", {}),
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
        "chatgpt":             result["chatgpt"],
        "website":             result["website"],
        "recommendations":     result["recommendations"],
        "competitors":         result.get("competitors", []),
        "competitor_insights": result.get("competitor_insights", {}),
        "citation_gaps":       result.get("citation_gaps", {}),
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
                "chatgpt_mentioned":    result["chatgpt"]["mentioned"],
                "chatgpt_snippet":      result["chatgpt"]["snippet"],
                "raw_results": {
                    "perplexity":          result["perplexity"],
                    "google":              result["google"],
                    "chatgpt":             result["chatgpt"],
                    "website":             result["website"],
                    "recommendations":     result["recommendations"],
                    "competitors":         result.get("competitors", []),
                    "competitor_insights": result.get("competitor_insights", {}),
                    "citation_gaps":       result.get("citation_gaps", {}),
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


# ─── Content-generation helpers ───────────────────────────────────────────
async def _fetch_people_also_ask(business_type: str, city: str,
                                  country: str, language: str = "en") -> list[str]:
    """Pull `related_questions` from SerpApi for a generic Google search.
    Best-effort: returns [] on any failure (no error to caller)."""
    if not SERPAPI_KEY or not business_type or not city:
        return []
    try:
        gl = COUNTRY_TO_GL.get(country, "ca")
        hl = "fr" if language == "fr" else "en"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://serpapi.com/search",
                params={
                    "q":       f"{business_type} in {city}",
                    "engine":  "google",
                    "gl":      gl,
                    "hl":      hl,
                    "api_key": SERPAPI_KEY,
                },
            )
            data = resp.json()
            related = data.get("related_questions", []) or []
            return [r.get("question") for r in related if r.get("question")][:8]
    except Exception as e:
        logger.warning(f"[PAA] fetch failed: {e}")
        return []


def _build_content_prompts(language: str, base_context: str, services: str,
                           paa_questions: list[str]) -> dict[str, str]:
    """Localized prompt templates for the four LLM calls."""
    services_line_en = f"\nServices to highlight: {services}" if services else ""
    services_line_fr = f"\nServices à mettre en avant : {services}" if services else ""
    paa_block_en = ""
    paa_block_fr = ""
    if paa_questions:
        joined = "\n- ".join(paa_questions[:8])
        paa_block_en = (
            "\nUse these real customer questions as inspiration (rewrite to fit "
            "this business; if one doesn't apply, write a relevant variant):\n- "
            + joined
        )
        paa_block_fr = (
            "\nUtilise ces vraies questions de clients comme inspiration (réécris pour "
            "cadrer avec l'entreprise; si une ne s'applique pas, écris une variante pertinente):\n- "
            + joined
        )

    if language == "fr":
        return {
            "website_desc": (
                f"{base_context}\nÉcris une description d'entreprise de 300-400 mots optimisée pour les "
                "moteurs de recherche IA (ChatGPT, Perplexity, Google AI Overview). Sois précis, mentionne "
                "la ville et les principaux services. Ton professionnel à la troisième personne."
                + services_line_fr
            ),
            "gbp_desc": (
                f"{base_context}\nÉcris une description Google Business Profile, MAXIMUM 700 caractères. "
                "Va droit au but, mentionne la ville et les services, orientée bénéfices client."
                + services_line_fr
            ),
            "yelp_desc": (
                f"{base_context}\nÉcris une description style Yelp de 200-250 mots, ton concis, "
                "troisième personne, mentionne les services."
                + services_line_fr
            ),
            "social_bio": (
                f"{base_context}\nÉcris une biographie de 150 caractères MAXIMUM pour Instagram/Facebook. "
                "Style punchy, mentionne la ville et le service principal."
            ),
            "faq": (
                f"{base_context}\nGénère 10 questions et réponses FAQ qu'un client poserait sur cette entreprise.\n"
                "Chaque réponse doit faire 40-80 mots, être factuelle et utile pour citation par les IA.\n"
                "Format: tableau JSON [{\"question\": \"...\", \"answer\": \"...\"}]. "
                "Retourne uniquement du JSON valide."
                + paa_block_fr
            ),
        }

    return {
        "website_desc": (
            f"{base_context}\nWrite a 300-400 word business description optimized to appear in AI search "
            "engine answers (ChatGPT, Perplexity, Google AI Overview). Be specific, mention the city and "
            "key services. Write in third person, professional tone."
            + services_line_en
        ),
        "gbp_desc": (
            f"{base_context}\nWrite a Google Business Profile description, MAX 700 characters. "
            "Direct, benefit-focused, mention the city and main services."
            + services_line_en
        ),
        "yelp_desc": (
            f"{base_context}\nWrite a Yelp-style description, 200-250 words, concise tone, third person, "
            "mention services."
            + services_line_en
        ),
        "social_bio": (
            f"{base_context}\nWrite a 150-character MAX social bio for Instagram/Facebook. Punchy, "
            "include city and main service."
        ),
        "faq": (
            f"{base_context}\nGenerate 10 FAQ questions and answers a customer would ask about this business.\n"
            "Each answer should be 40-80 words, factual, and useful for AI to cite verbatim.\n"
            "Format as JSON array: [{\"question\": \"...\", \"answer\": \"...\"}]. "
            "Return only valid JSON."
            + paa_block_en
        ),
    }


def _truncate_at_word(text: str, limit: int) -> str:
    """Hard-cap a string at `limit` chars without splitting a word."""
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit - 1].rsplit(' ', 1)[0] + "…"


def _validate_content(descriptions: dict, faq: list, social_bio: str) -> list[str]:
    """Return a list of validation warnings (empty list = clean)."""
    warnings: list[str] = []
    if not descriptions.get("website") or len(descriptions["website"].split()) < 100:
        warnings.append("website_description_too_short")
    if not descriptions.get("gbp"):
        warnings.append("gbp_description_missing")
    elif len(descriptions["gbp"]) > 750:
        warnings.append("gbp_description_too_long")
    if not faq or len(faq) < 8:
        warnings.append("faq_too_few_items")
    if not social_bio or len(social_bio) > 150:
        warnings.append("social_bio_invalid_length")
    return warnings


@router.post("/generate-content")
async def generate_content(
    request: GenerateContentRequest,
    current_user: dict = Depends(get_current_user),
):
    business = await get_business_by_user(current_user["id"])
    if not business:
        raise HTTPException(status_code=404, detail="Business profile not found")
    if str(business["id"]) != request.business_id:
        raise HTTPException(status_code=403, detail="Access denied")

    if BILLING_ENABLED:
        subscription = await get_active_subscription(str(business["id"]))
        if not subscription:
            raise HTTPException(status_code=402, detail="Active subscription required")

    language = "fr" if request.language == "fr" else "en"

    latest_audit = supabase_admin.table("aeo_audits") \
        .select("*").eq("business_id", business["id"]) \
        .order("created_at", desc=True).limit(1).execute()
    audit = latest_audit.data[0] if latest_audit.data else None

    name     = business["name"]
    btype    = business["type"]
    city     = business["city"]
    province = business.get("province") or ""
    services = business.get("services") or ""
    website  = business.get("website") or ""
    country  = business.get("country") or "Canada"

    audit_context = ""
    if audit:
        gaps = []
        if not audit.get("perplexity_mentioned"): gaps.append("Perplexity")
        if not audit.get("google_ai_mentioned"):  gaps.append("Google AI Overview")
        if not audit.get("chatgpt_mentioned"):    gaps.append("ChatGPT")
        if gaps:
            audit_context = f"The business is NOT currently cited by: {', '.join(gaps)}. "

    base_context = (
        f"Business name: {name}\n"
        f"Business type: {btype}\n"
        f"City: {city}{', ' + province if province else ''}\n"
        f"Services: {services}\n"
        f"Website: {website}\n"
        f"{audit_context}"
    )

    # People-Also-Ask seeds for FAQ grounding (best-effort)
    paa_questions = await _fetch_people_also_ask(btype, city, country, language)

    prompts = _build_content_prompts(language, base_context, services, paa_questions)

    # Run all 5 LLM calls in parallel
    website_desc, gbp_desc, yelp_desc, social_bio_raw, faq_raw = await asyncio.gather(
        ai_engine.generate(prompt=prompts["website_desc"], max_tokens=700, temperature=0.7),
        ai_engine.generate(prompt=prompts["gbp_desc"],     max_tokens=350, temperature=0.7),
        ai_engine.generate(prompt=prompts["yelp_desc"],    max_tokens=500, temperature=0.7),
        ai_engine.generate(prompt=prompts["social_bio"],   max_tokens=120, temperature=0.8),
        ai_engine.generate(prompt=prompts["faq"],          max_tokens=2500, temperature=0.5,
                           system_prompt="Return only valid JSON, no markdown."),
    )

    # Parse FAQ JSON, tolerant of fenced code blocks the LLM sometimes emits
    try:
        faq = json.loads(re.sub(r'^```(?:json)?\s*|\s*```$', '', faq_raw.strip(),
                                flags=re.MULTILINE))
        if not isinstance(faq, list):
            faq = []
    except Exception:
        faq = []

    # Apply hard caps
    social_bio = _truncate_at_word(social_bio_raw, 150)
    descriptions = {
        "website": (website_desc or "").strip(),
        "gbp":     _truncate_at_word(gbp_desc, 700),
        "yelp":    (yelp_desc or "").strip(),
    }

    # Server-side validation (warnings only -- still ship the content)
    validation_warnings = _validate_content(descriptions, faq, social_bio)

    # Deterministic schema -- never LLM-generated
    schema_obj = build_schema(business, description=descriptions["website"], content_language=language)
    schema_raw = json.dumps(schema_obj, indent=2, ensure_ascii=False)
    schema_missing = find_missing_required_fields(business)

    # Deterministic FAQPage schema from the LLM-generated Q&A list
    faq_schema_obj = build_faq_schema(faq) if faq else None
    faq_schema_raw = (json.dumps(faq_schema_obj, indent=2, ensure_ascii=False)
                      if faq_schema_obj else None)

    supabase_admin.table("aeo_content").insert({
        "business_id":   business["id"],
        "description":   descriptions["website"],   # legacy column for backward compat
        "descriptions":  descriptions,
        "faq":           faq,
        "faq_schema":    faq_schema_raw,
        "schema_markup": schema_raw,
        "social_bio":    social_bio,
        "language":      language,
        "paa_questions": paa_questions,
    }).execute()

    return {
        "language":              language,
        "descriptions":          descriptions,
        "social_bio":            social_bio,
        "faq":                   faq,
        "faq_schema":            faq_schema_raw,
        "schema_markup":         schema_raw,
        "schema_missing_fields": schema_missing,
        "paa_questions":         paa_questions,
        "validation_warnings":   validation_warnings,
    }

from fastapi import APIRouter, Depends, HTTPException, Header, Query
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
from datetime import datetime, timezone
from core.ai_engine import AIEngine
from .schema_builder import build_schema, build_faq_schema, find_missing_required_fields
from . import knowledge as kb

logger = logging.getLogger(__name__)
router = APIRouter()

# ─── Per-workload LLM clients (env-configurable) ──────────────────────────
# Each AI workload runs on its own provider+model picked via env vars so
# swapping providers / handling deprecated models is a config change, not
# a code release.
#
# AUDIT_PROVIDER + AUDIT_MODEL    -> ChatGPT pillar query (default
#     openai/gpt-4o-mini). Caveat: switching this changes the semantic
#     meaning of the "ChatGPT" AI Citations sub-pillar.
# CONTENT_PROVIDER + CONTENT_MODEL -> Description/FAQ/social-bio gen.
#     Defaults fall through to AI_PROVIDER + matching *_MODEL for back-
#     compat with the original config.
# COACH_PROVIDER + COACH_MODEL    -> AI execution coach (default
#     gemini/gemini-3-flash -- cheapest with good chat quality).
audit_llm = AIEngine(
    provider=os.getenv("AUDIT_PROVIDER", "openai"),
    model=os.getenv("AUDIT_MODEL", "gpt-4o-mini"),
)
content_llm = AIEngine(
    provider=os.getenv("CONTENT_PROVIDER"),  # falls back to AI_PROVIDER
    model=os.getenv("CONTENT_MODEL"),         # falls back to provider-specific *_MODEL
)
coach_llm = AIEngine(
    provider=os.getenv("COACH_PROVIDER", "gemini"),
    # gemini-3.1-flash-lite is the cost-optimal default for chat-style
    # coaching. If you notice the model dropping subtler instructions
    # (Quebec French register, the 'offer to write the email' rule, etc.)
    # in testing, override with COACH_MODEL=gemini-3.1-pro in .env.
    model=os.getenv("COACH_MODEL", "gemini-3.1-flash-lite"),
)
logger.info(
    f"[LLM] audit={audit_llm.provider}/{audit_llm._model} | "
    f"content={content_llm.provider}/{content_llm._model} | "
    f"coach={coach_llm.provider}/{coach_llm._model}"
)

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


# ISO 2-letter country codes → gl (handles databases that store "CA" instead of "Canada")
_COUNTRY_ISO_TO_GL: dict[str, str] = {
    "CA": "ca", "US": "us", "GB": "gb", "UK": "gb", "AU": "au",
    "FR": "fr", "DE": "de", "ES": "es", "IT": "it", "NL": "nl",
    "BE": "be", "CH": "ch", "NZ": "nz", "IE": "ie", "PT": "pt",
    "MX": "mx", "BR": "br", "IN": "in", "JP": "jp", "KR": "kr",
    "SG": "sg", "ZA": "za",
}

# Canadian province/territory codes — any of these implies gl="ca"
_CA_PROVINCE_CODES: frozenset[str] = frozenset(
    {"AB", "BC", "MB", "NB", "NL", "NS", "NT", "NU", "ON", "PE", "QC", "SK", "YT"}
)


def country_to_gl(country: str | None) -> str | None:
    """Maps a country name or ISO-2 code to a SerpApi `gl` code.
    Returns None if unknown — caller should omit the gl param."""
    if not country:
        return None
    c = country.strip()
    return COUNTRY_TO_GL.get(c) or _COUNTRY_ISO_TO_GL.get(c.upper())


def province_to_gl(province: str | None) -> str | None:
    """Infer gl from province abbreviation when country field is absent or unrecognised.
    Currently handles Canadian provinces (→ 'ca'). Returns None if unclear."""
    if not province:
        return None
    if province.strip().upper() in _CA_PROVINCE_CODES:
        return "ca"
    return None


# Maps a gl code to regex patterns that strongly indicate that country in a SerpApi
# address string. Word-boundaries (\b) prevent false positives like "uk" matching
# inside "Lukas Avenue". Every gl code in COUNTRY_TO_GL must have an entry here.
COUNTRY_ADDRESS_MARKERS: dict[str, list[str]] = {
    "ca": [r"\bcanada\b", r"\b[A-Z]\d[A-Z][\s\-]?\d[A-Z]\d\b"],  # Canadian postal: A1A 1A1
    "us": [r"\bunited states\b", r"\busa\b", r"\bu\.s\.a?\.?\b",
           r"\b[A-Z]{2}\s+\d{5}(?:-\d{4})?\b"],  # US state + ZIP: "NJ 08060", "WA 98101-1234"
    "gb": [r"\bunited kingdom\b", r"\bu\.?k\.?\b", r"\bengland\b", r"\bscotland\b", r"\bwales\b",
           r"\bmilton keynes\b", r"\bbirmingham\b uk", r"\bsouth london\b", r"\bnorth london\b",
           r"\b[A-Z]{1,2}\d{1,2}[A-Z]?\s\d[A-Z]{2}\b"],  # UK postal: MK2 2EE, SW1A 1AA
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
        for p in patterns:
            # Postal code patterns use uppercase [A-Z] — match against original address.
            # All other text patterns match against lowercased address.
            if re.search(p, address if "[A-Z]" in p else a):
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
    result = await content_llm.generate(
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
    # Perplexity returns a citations list alongside the answer — capture it so callers
    # can resolve [1][2][3] references to actual platform names (Yellow Pages, Yelp, etc.)
    citations: list[str] = data.get("citations") or []
    mentioned = extract_search_name(business_name, city).lower() in answer.lower()
    snippet = answer[:500] if mentioned else None
    print(f"[AEO] Perplexity '{query}' → mentioned={mentioned}")
    return {"mentioned": mentioned, "snippet": snippet, "answer": answer[:2000], "query": query, "citations": citations}


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
    competitor_scope: str = "local",
) -> dict:
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
        "api_key": SERPAPI_KEY,
        "engine": "google",
        "q": query,
        "hl": "en",
    }
    if competitor_scope == "local":
        params["location"] = city
    gl = country_to_gl(country) or province_to_gl(province)
    if gl and competitor_scope != "global":
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
    competitor_scope: str = "local",
) -> dict:
    results = []
    for query in build_queries(business_type_en, city, province, postal_code, is_trades, is_healthcare):
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
    # We always compute user_dirs because Reddit detection is universal
    # (fires for every business) so we always need the directory presence
    # data anyway.
    btype = business.get("type")
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

    # B2B / professional services — LinkedIn Company Page
    # AI engines (especially Perplexity and Google AI Overview) cite
    # LinkedIn pages heavily when answering questions about professional
    # services, B2B vendors, lawyers, accountants, etc.
    if _is_b2b_business(btype) and "LinkedIn" not in user_dirs:
        recs.append({
            "pillar": "ai_citation",
            "title": "Activate your LinkedIn Company Page",
            "description": "For B2B and professional services, LinkedIn is one of the highest-leverage AI citation surfaces. AI engines weight LinkedIn pages heavily when answering 'find me a <profession> in <city>' queries. Static profiles are ignored — pages with weekly posting and active engagement get cited far more often.",
            "action": "Create or activate your LinkedIn Company Page. Commit to one industry-relevant post per week. Have employees and clients follow the page. Pin a clear value-proposition post at the top.",
            "difficulty": "medium",
            "impact": 3,
            "url": "https://www.linkedin.com/company/setup/new/",
        })

    # ─── Reddit (community citation surface, every vertical) ──────
    # Reddit is a top-3 AI citation domain after Google's $60M Reddit data
    # licensing deal. Citations come from organic discussion (you can't
    # claim a Reddit listing the way you do Yelp), so the action is
    # community engagement — explicitly framed as long-term, not a quick
    # win. We surface this for every vertical because it applies broadly.
    if "Reddit" not in user_dirs:
        city = business.get("city") or ""
        subreddit_url = _city_to_subreddit_url(city)
        recs.append({
            "pillar": "ai_citation",
            "title": "Build authentic Reddit presence",
            "description": "Reddit is one of the most-cited AI citation sources in 2026 — Google licensed Reddit data for $60M and AI Overview / Perplexity / ChatGPT all weight Reddit threads heavily for 'best X in <city>' queries. Reddit citations come from real community discussion, not paid listings. This is a long-term play, not a quick win.",
            "action": (
                f"Engage authentically in r/{CITY_SUBREDDITS.get(city.strip().lower(), 'your city subreddit')} "
                "and industry-relevant subreddits. Answer questions in your area of expertise without "
                "self-promoting. Ask satisfied customers to share their experience when relevant threads "
                "come up. Avoid astroturfing — Reddit detects and bans it fast, and the public shaming "
                "is worse than no presence."
            ),
            "difficulty": "hard",
            "impact": 3,
            "url": subreddit_url,
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
    # local / country / global -- drives both SerpApi `location` param and the
    # cross-border filter inside run_google_multi. See migration 020.
    competitor_scope = business.get("competitor_scope") or "local"
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
                         postal_code=postal_code, is_trades=is_trades_v, is_healthcare=is_healthcare_v,
                         competitor_scope=competitor_scope),
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
                *[_lookup_competitor_by_place_id((uc or {}).get("place_id"), country=country) for uc in needs_lookup],
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
    }


async def _lookup_competitor_by_place_id(place_id: str, country: str | None = None) -> dict | None:
    """Resolve a Google Maps place_id to a competitor dict in the same shape as
    extract_competitors() output. Used when a user adds a competitor manually
    that we never saw in the audit's local pack queries.

    Returns None when SerpApi can't find the place (closed, deleted, bad id)."""
    if not place_id:
        return None
    gl = country_to_gl(country) or "ca"
    params: dict[str, str] = {
        "api_key":  SERPAPI_KEY,
        "engine":   "google_maps",
        "place_id": place_id,
        "hl":       "en",
        "gl":       gl,
    }
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("https://serpapi.com/search", params=params, timeout=20.0)
            response.raise_for_status()
            data = response.json()
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


async def _score_user_competitor(
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
    base = await _lookup_competitor_by_place_id(entry["place_id"], country=country)
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
    website_check = website_check_results.get(_competitor_key(base))

    perplexity_m = google_ai_m = chatgpt_m = None
    if perplexity_result and google_result and chatgpt_result:
        matches = match_competitor_ai_citations([base], perplexity_result, google_result, chatgpt_result)
        m = matches.get(_competitor_key(base))
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


async def _fetch_competitor_perplexity(name: str, city: str) -> str:
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


async def _fetch_own_perplexity_reputation(business_name: str, city: str, province: str | None = None, country: str | None = None) -> str:
    """Ask Perplexity what customers say about this business across all platforms.
    Used to supplement Google Maps reviews with Yelp, BBB, RateMDs, etc. signals.
    Returns the answer text (up to 2000 chars) or '' on failure."""
    if not PERPLEXITY_API_KEY:
        return ""

    # Expand Canadian province abbreviations so Perplexity doesn't mistake
    # "Burlington, ON" for Burlington, NC or "Milton, ON" for a US city.
    CA_PROVINCES = {
        "AB": "Alberta", "BC": "British Columbia", "MB": "Manitoba",
        "NB": "New Brunswick", "NL": "Newfoundland and Labrador",
        "NS": "Nova Scotia", "NT": "Northwest Territories", "NU": "Nunavut",
        "ON": "Ontario", "PE": "Prince Edward Island", "QC": "Quebec",
        "SK": "Saskatchewan", "YT": "Yukon",
    }
    province_full = CA_PROVINCES.get((province or "").upper(), province) if province else None
    is_canada = (
        country in ("CA", "Canada", "ca")
        or (province or "").upper() in CA_PROVINCES
        or (province_full or "").lower() in {v.lower() for v in CA_PROVINCES.values()}
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
                        (name for d, name in {
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
                        }.items() if d in domain),
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

    # Fetch Google Maps reviews AND Perplexity multi-source insights in parallel
    review_results, perplexity_raw = await asyncio.gather(
        asyncio.gather(
            *[_fetch_competitor_reviews(c["name"], c.get("city"), country) for c in competitors_with_ids],
            return_exceptions=True,
        ),
        asyncio.gather(
            *[_fetch_competitor_perplexity(c["name"], c.get("city") or "") for c in competitors_with_ids],
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


async def _analyze_own_reputation(reviews: list[dict], business_name: str, perplexity_insight: str = "") -> dict:
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


class ExistingFaq(BaseModel):
    """One owner-supplied Q+A pair already published on their site.
    Preserved verbatim in the final FAQ; never rewritten by the LLM."""
    question: str
    answer: str


class GenerateContentRequest(BaseModel):
    business_id: str
    language: str = "en"  # 'en' | 'fr'
    # Phase 2 — owner provides questions they hear from real customers.
    # Used verbatim as the first N entries in the generated FAQ. Remaining
    # slots are LLM-generated. Capped to 10 items, 200 chars each.
    custom_faq_seeds: list[str] = []
    # Phase 4 — owner's existing Q+A pairs from their website. Preserved
    # verbatim (LLM never rewrites these). LLM generates additional Q&As
    # that don't duplicate the topics covered here, filling to 15 total.
    # Capped to 50 items, 200 char Q + 1000 char A.
    existing_faqs: list[ExistingFaq] = []


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
    # Community / UGC citation surfaces (added 2026-05-08)
    # Reddit is a top-3 AI citation domain since Google's $60M Reddit data
    # licensing deal. Detection works the same as for directories, but the
    # frontend treats it specially -- you don't "claim" a Reddit listing.
    "reddit.com":           "Reddit",
}


# City -> subreddit name mapping for Canadian recommendations.
# Used by Reddit recommendation to send users to the most relevant local
# subreddit. Falls back to a Reddit search when city isn't mapped.
CITY_SUBREDDITS: dict[str, str] = {
    "toronto":         "toronto",
    "ottawa":          "ottawa",
    "vancouver":       "vancouver",
    "montreal":        "montreal",
    "montréal":        "montreal",
    "calgary":         "Calgary",
    "edmonton":        "Edmonton",
    "halifax":         "halifax",
    "winnipeg":        "Winnipeg",
    "quebec city":     "quebeccity",
    "québec":          "quebeccity",
    "quebec":          "quebeccity",
    "mississauga":     "mississauga",
    "brampton":        "brampton",
    "hamilton":        "Hamilton",
    "london":          "londonontario",
    "kitchener":       "waterloo",
    "waterloo":        "waterloo",
    "saskatoon":       "saskatoon",
    "regina":          "Regina",
    "victoria":        "VictoriaBC",
    "windsor":         "windsorontario",
    "burnaby":         "burnaby",
    "richmond":        "richmondbc",
    "surrey":          "surreybc",
    "markham":         "markham",
    "vaughan":         "Vaughan",
    "oakville":        "oakville",
    "burlington":      "burlingtonontario",
    "guelph":          "Guelph",
    "barrie":          "Barrie",
    "kelowna":         "kelowna",
}


def _city_to_subreddit_url(city: str | None) -> str:
    """Returns a Reddit URL pointing at the city's subreddit if known,
    otherwise a Reddit search for the city name."""
    if not city:
        return "https://www.reddit.com/r/canada"
    sub = CITY_SUBREDDITS.get(city.strip().lower())
    if sub:
        return f"https://www.reddit.com/r/{sub}"
    return f"https://www.reddit.com/search/?q={city.replace(' ', '+')}"

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

# B2B / professional services detector — gates the LinkedIn Company Page
# recommendation. Intentionally broad: covers services where LinkedIn
# presence is a real AI citation signal beyond just consumer-facing reviews.
_B2B_PATTERN = re.compile(
    r"\blawyer|\battorney|\blegal\s+service|\blaw\s+(firm|office)|\bparalegal|\bnotary"
    r"|\baccount\w+|\bbookkeep\w+|\bcpa\b|\bauditor"
    r"|\bconsult\w+|\badvisor\b|\badvisory"
    r"|\bIT\s+services|\bmanaged\s+services|\bIT\s+consulting|\btech\s+consult"
    r"|\bmarketing\s+agency|\badvertising\s+agency|\bdigital\s+agency|\bweb\s+design"
    r"|\bfinancial\s+(advisor|planner)|\bwealth\s+management"
    r"|\bbusiness\s+coach|\bexecutive\s+coach"
    r"|\brecruit\w+|\bstaffing"
    r"|\breal\s+estate|\brealtor\b"
    r"|\barchitect|\bengineering\s+firm|\bsoftware\s+(company|consult)|\bSaaS",
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


def _is_b2b_business(business_type: str | None) -> bool:
    """True for professional services / B2B verticals where a LinkedIn
    Company Page is a meaningful AI citation signal. Intentionally
    overlaps with _is_legal_business and _is_realtor_business -- a lawyer
    benefits from BOTH the LawyerLocate rec AND the LinkedIn rec; they
    serve different surfaces."""
    return bool(business_type and _B2B_PATTERN.search(business_type))


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
    competitor_scope: str | None = None  # 'local' | 'country' | 'global'; see migration 020


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
        "competitor_scope": business.get("competitor_scope") or "local",
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

    # Reject unknown competitor_scope values; fall back to existing or 'local'.
    requested_scope = (request.competitor_scope or "").strip().lower()
    competitor_scope = (
        requested_scope if requested_scope in ("local", "country", "global")
        else (business.get("competitor_scope") or "local")
    )

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
        "competitor_scope": competitor_scope,
    }).eq("id", business["id"]).execute()

    return {"message": "Business profile updated"}


class CompetitorEntry(BaseModel):
    place_id: str
    name: str
    source: str = "manual"  # 'auto' | 'manual'


class CompetitorListRequest(BaseModel):
    competitors: list[CompetitorEntry]


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
    country  = business.get("country") or "Canada"
    province = business.get("province") or ""
    gl = country_to_gl(country) or province_to_gl(province) or "ca"

    params: dict[str, str] = {
        "api_key": SERPAPI_KEY,
        "engine":  "google_maps",
        "q":       q,
        "hl":      "en",
        "gl":      gl,
    }
    if city:
        params["location"] = f"{city}, {province}" if province else city

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("https://serpapi.com/search", params=params, timeout=20.0)
            response.raise_for_status()
            data = response.json()
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
    `_score_user_competitor` so the UI gets back a fully scored list it can
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
                _score_user_competitor(entry, country, perp, goog, chat)
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
    refresh: bool = Query(default=False, description="Force re-fetch even if a cached result exists"),
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

    # Return cached result if already computed for this audit run (skip if refresh=True)
    cached = raw.get("own_reputation")
    if cached and not refresh:
        logger.info(f"[AEO][OWN] Returning cached own_reputation for audit {audit['id']}")
        return {**cached, "cached": True}

    # Resolve place_id from the audit's knowledge_graph
    google_data = raw.get("google") or {}
    kg = google_data.get("knowledge_graph") or {}
    place_id = kg.get("place_id")
    country = business.get("country")

    # KG sometimes doesn't match (title mismatch) so place_id is absent.
    # Also reject CID-format IDs (numeric) — google_maps_reviews only accepts ChIJ format.
    # Fall back to a direct Google Maps lookup — same approach used for competitor reviews.
    if not place_id or not place_id.startswith("ChIJ"):
        place_id = await _resolve_maps_place_id(business["name"], business.get("city"), country)

    if not place_id:
        return {
            "strengths": [], "weaknesses": [], "summary": "",
            "review_count": 0, "avg_rating": None, "cached": False,
            "error": "no_place_id",
        }

    # Fetch Google Maps reviews AND a Perplexity reputation query in parallel —
    # same pattern as competitor analysis so we get multi-source signals (Yelp, BBB, etc.).
    # Use 180 days to capture enough reviews to surface both strengths and rare weaknesses.
    reviews, perplexity_text = await asyncio.gather(
        _fetch_own_reviews(place_id, country, max_days=365, max_pages=5),
        _fetch_own_perplexity_reputation(business["name"], business.get("city") or "", business.get("province"), business.get("country")),
    )
    logger.info(f"[AEO][OWN] Reputation fetch: {len(reviews)} reviews, perplexity={'yes' if perplexity_text else 'no'} for '{business['name']}'")
    if perplexity_text:
        logger.info(f"[AEO][OWN] Perplexity snippet: {perplexity_text[:400]}")
    else:
        logger.warning(f"[AEO][OWN] Perplexity returned EMPTY for '{business['name']}' — check PERPLEXITY_API_KEY")

    if not reviews and not perplexity_text:
        return {
            "strengths": [], "weaknesses": [], "summary": "",
            "review_count": 0, "avg_rating": None, "cached": False,
        }

    ratings = [r["rating"] for r in reviews if r.get("rating")]
    avg_rating = round(sum(ratings) / len(ratings), 1) if ratings else None

    result = await _analyze_own_reputation(reviews, business["name"], perplexity_text)
    result["review_count"] = len(reviews)
    result["avg_rating"] = avg_rating

    # Persist to DB so repeat loads are instant (invalidated automatically by next audit run)
    try:
        updated_raw = {**raw, "own_reputation": result}
        supabase_admin.table("aeo_audits").update({"raw_results": updated_raw}).eq("id", audit["id"]).execute()
        logger.info(f"[AEO][OWN] Saved own_reputation to audit {audit['id']}")
    except Exception as e:
        logger.warning(f"[AEO][OWN] Failed to save own_reputation: {e}")

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


FAQ_TARGET_COUNT = 15  # 2026 sweet spot per AEO research (10 was low-end)


def _build_content_prompts(language: str, base_context: str, services: str,
                           paa_questions: list[str],
                           custom_faq_seeds: list[str] | None = None,
                           existing_faqs: list[dict] | None = None) -> dict[str, str]:
    """Localized prompt templates for the four LLM calls.

    `custom_faq_seeds` (Phase 2): owner-provided questions they hear from
    real customers. Used verbatim as the first N items in the generated FAQ.

    `existing_faqs` (Phase 4): owner-supplied Q+A pairs already on their
    website. Passed to the LLM as 'topics already covered — generate NEW
    questions that don't duplicate these'. The LLM only writes new Qs+As;
    the owner's existing pairs are merged back verbatim by the caller.

    The LLM is told to generate enough new Qs+As to bring the TOTAL
    (existing + custom seeds + new) to FAQ_TARGET_COUNT (15)."""
    services_line_en = f"\nServices to highlight: {services}" if services else ""
    services_line_fr = f"\nServices à mettre en avant : {services}" if services else ""

    # AEO best-practices knowledge appended to the FAQ prompt so the LLM
    # produces citation-optimized Q&As. Loaded from
    # api/knowledge/faq_generation_aeo.md at module import time.
    faq_aeo_kb = kb.for_faq()
    faq_kb_block = f"\n\n=== AEO BEST PRACTICES — APPLY EVERY ONE ===\n{faq_aeo_kb}\n=== END BEST PRACTICES ===\n" if faq_aeo_kb else ""

    # Phase 2 — owner's custom seed questions (verbatim Qs the LLM answers).
    seeds = [s.strip() for s in (custom_faq_seeds or []) if s and s.strip()][:10]

    # Phase 4 — owner's existing Q+A pairs from their website. The LLM is
    # told these topics are ALREADY COVERED — write NEW questions. Existing
    # pairs are merged back into the final FAQ list by the caller (verbatim).
    existing = []
    for f in (existing_faqs or [])[:50]:
        q = (f.get("question") or "").strip()[:200] if isinstance(f, dict) else ""
        a = (f.get("answer")   or "").strip()[:1000] if isinstance(f, dict) else ""
        if q and a:
            existing.append({"question": q, "answer": a})

    # How many NEW Q+As (LLM picks both Q and A on a topic NOT already
    # covered by existing or seeds). Total target (existing + seeds + new)
    # = FAQ_TARGET_COUNT, but never less than 5 new ones — even an owner
    # with 20 existing FAQs still gets fresh AEO-optimized content from us.
    new_target = max(5, FAQ_TARGET_COUNT - len(existing) - len(seeds))
    # llm_output_count = what the LLM writes in its JSON array. This includes
    # the seed Qs (LLM writes their answers) PLUS the new_target new Q+A pairs.
    # Existing pairs are NOT in this count -- they're merged in by the caller
    # after the LLM call.
    llm_output_count = len(seeds) + new_target

    # Build the existing-FAQs block — what the LLM should NOT duplicate.
    # Note: existing pairs are NOT in the LLM's output array; they're merged
    # back by the caller after the LLM call.
    existing_block_en = ""
    existing_block_fr = ""
    if existing:
        existing_listing = "\n".join(
            f"  {i+1}. Q: {f['question']}\n     A: {f['answer']}"
            for i, f in enumerate(existing)
        )
        existing_block_en = (
            f"\n\n=== TOPICS ALREADY COVERED ON OWNER'S WEBSITE — DO NOT DUPLICATE ===\n"
            f"The owner already has {len(existing)} Q+A pair(s) on their site. "
            f"DO NOT write questions that cover the same topics. None of your "
            f"{llm_output_count} output items should duplicate any of these. "
            f"The owner's existing FAQs are merged back automatically.\n"
            f"{existing_listing}\n=== END EXISTING TOPICS ===\n"
        )
        existing_block_fr = (
            f"\n\n=== SUJETS DÉJÀ COUVERTS SUR LE SITE DU PROPRIÉTAIRE — NE PAS DUPLIQUER ===\n"
            f"Le propriétaire a déjà {len(existing)} paire(s) Q+R sur son site. NE PAS "
            f"écrire de questions sur les mêmes sujets. Aucun de tes {llm_output_count} "
            f"éléments de sortie ne doit dupliquer ceux-ci. Les FAQ existantes "
            f"sont fusionnées automatiquement.\n{existing_listing}\n"
            f"=== FIN SUJETS EXISTANTS ===\n"
        )

    # Custom seed questions block — owner's verbatim Qs, LLM writes answers.
    # These count toward llm_output_count.
    custom_seed_block_en = ""
    custom_seed_block_fr = ""
    if seeds:
        joined = "\n".join(f'  {i+1}. "{s}"' for i, s in enumerate(seeds))
        remaining_after_seeds = llm_output_count - len(seeds)
        custom_seed_block_en = (
            f"\n\n=== OWNER'S CUSTOM QUESTIONS — USE VERBATIM ===\n"
            f"The owner says these are real questions they hear from customers. "
            f"Use them EXACTLY as the first {len(seeds)} questions in your output "
            f"(do not rephrase or rewrite). Write high-quality answers for each "
            f"that follow the best practices below. Then generate "
            f"{remaining_after_seeds} additional NEW Q+A pairs to complete your "
            f"set of {llm_output_count}.\n{joined}\n=== END CUSTOM QUESTIONS ===\n"
        )
        custom_seed_block_fr = (
            f"\n\n=== QUESTIONS PERSONNALISÉES DU PROPRIÉTAIRE — UTILISE TELLES QUELLES ===\n"
            f"Le propriétaire dit que ce sont de vraies questions qu'il entend des "
            f"clients. Utilise-les EXACTEMENT comme les {len(seeds)} premières "
            f"questions de ta sortie (ne reformule pas). Écris des réponses de "
            f"qualité pour chacune. Génère ensuite {remaining_after_seeds} paires "
            f"Q+R additionnelles pour compléter ton ensemble de {llm_output_count}.\n"
            f"{joined}\n=== FIN QUESTIONS PERSONNALISÉES ===\n"
        )

    # Total count instruction — what the LLM puts in its JSON array.
    faq_count_instruction_en = (
        f"\nOutput {llm_output_count} Q+A pairs in a single JSON array."
    )
    faq_count_instruction_fr = (
        f"\nProduis {llm_output_count} paires Q+R dans un seul tableau JSON."
    )
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

    # Hard format rule appended to every prose-content prompt to prevent
    # the LLM from emitting markdown headers, alternative versions, or
    # character-count commentary on top of the actual content.
    no_markdown_en = (
        "\n\nIMPORTANT: Output only the description text in plain prose. "
        "No markdown headers (# ##). No bold/italic markers. No 'Here is...' "
        "preamble. No 'Alternative version' sections. No character-count "
        "notes. No labels like 'Description:'. Just the prose itself."
    )
    no_markdown_fr = (
        "\n\nIMPORTANT : Retourne uniquement le texte de description en prose. "
        "Pas de titres markdown (# ##). Pas de gras/italique. Pas de préambule "
        "« Voici... ». Pas de sections « Version alternative ». Pas de notes "
        "sur le nombre de caractères. Pas d'étiquettes comme « Description : ». "
        "Juste la prose."
    )
    bio_format_en = (
        "\n\nIMPORTANT: Output ONLY the bio text — a single sentence or short "
        "phrase under 150 characters. No markdown. No headers. No quotation "
        "marks around the bio. No 'Bio:' label. No alternatives. No character-"
        "count notes. No commentary. Just the bio words."
    )
    bio_format_fr = (
        "\n\nIMPORTANT : Retourne UNIQUEMENT le texte de la biographie — une "
        "seule phrase ou courte expression de moins de 150 caractères. Pas "
        "de markdown. Pas de titres. Pas de guillemets. Pas d'étiquette « Bio : ». "
        "Pas d'alternatives. Pas de notes sur le nombre de caractères. Juste "
        "les mots de la biographie."
    )

    if language == "fr":
        return {
            "website_desc": (
                f"{base_context}\nÉcris une description d'entreprise de 300-400 mots optimisée pour les "
                "moteurs de recherche IA (ChatGPT, Perplexity, Google AI Overview). Sois précis, mentionne "
                "la ville et les principaux services. Ton professionnel à la troisième personne."
                + services_line_fr
                + no_markdown_fr
            ),
            "gbp_desc": (
                f"{base_context}\nÉcris une description Google Business Profile, MAXIMUM 700 caractères. "
                "Va droit au but, mentionne la ville et les services, orientée bénéfices client."
                + services_line_fr
                + no_markdown_fr
            ),
            "yelp_desc": (
                f"{base_context}\nÉcris une description style Yelp de 200-250 mots, ton concis, "
                "troisième personne, mentionne les services."
                + services_line_fr
                + no_markdown_fr
            ),
            "social_bio": (
                f"{base_context}\nÉcris une biographie de 150 caractères MAXIMUM pour Instagram/Facebook. "
                "Style punchy, mentionne la ville et le service principal."
                + bio_format_fr
            ),
            "faq": (
                f"{base_context}{faq_count_instruction_fr}\n"
                "Chaque réponse doit faire 40-60 mots, être factuelle et utile pour citation par les IA.\n"
                "Format: tableau JSON [{\"question\": \"...\", \"answer\": \"...\"}]. "
                "Retourne uniquement du JSON valide."
                + existing_block_fr
                + custom_seed_block_fr
                + paa_block_fr
                + faq_kb_block
            ),
        }

    return {
        "website_desc": (
            f"{base_context}\nWrite a 300-400 word business description optimized to appear in AI search "
            "engine answers (ChatGPT, Perplexity, Google AI Overview). Be specific, mention the city and "
            "key services. Write in third person, professional tone."
            + services_line_en
            + no_markdown_en
        ),
        "gbp_desc": (
            f"{base_context}\nWrite a Google Business Profile description, MAX 700 characters. "
            "Direct, benefit-focused, mention the city and main services."
            + services_line_en
            + no_markdown_en
        ),
        "yelp_desc": (
            f"{base_context}\nWrite a Yelp-style description, 200-250 words, concise tone, third person, "
            "mention services."
            + services_line_en
            + no_markdown_en
        ),
        "social_bio": (
            f"{base_context}\nWrite a 150-character MAX social bio for Instagram/Facebook. Punchy, "
            "include city and main service."
            + bio_format_en
        ),
        "faq": (
            f"{base_context}{faq_count_instruction_en}\n"
            "Each answer should be 40-60 words, factual, and useful for AI to cite verbatim.\n"
            "Format as JSON array: [{\"question\": \"...\", \"answer\": \"...\"}]. "
            "Return only valid JSON."
            + existing_block_en
            + custom_seed_block_en
            + paa_block_en
            + faq_kb_block
        ),
    }


def _truncate_at_word(text: str, limit: int) -> str:
    """Hard-cap a string at `limit` chars without splitting a word."""
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit - 1].rsplit(' ', 1)[0] + "…"


# Markers we consider end-of-bio when the LLM tries to add commentary or
# alternatives below the actual bio text. Order doesn't matter -- we cut at
# the earliest match. Case-insensitive substring match.
_BIO_END_MARKERS = (
    "\n---", "\n***",
    "\nalternative", "\nalt:", "\nalt.",
    "\n*character count", "\n(character count",
    "\n*note:", "\n_(",
    "\n# ", "\n## ",
    "\n**bio", "\n**social",
    "\nbio:", "\nsocial bio:",
    "\nversion 2", "\nversion 1",
    "\nor:", "\nor,",
    "\nhere is", "\nhere's",
    "\nlet me know",
)

_BIO_LABEL_PREFIX = re.compile(
    r"^(?:bio|social\s+bio|instagram\s+bio|facebook\s+bio|caption|tagline)\s*:\s*",
    re.IGNORECASE,
)
_BIO_HEADING_LINE = re.compile(r"^#+\s+.*?\n+", re.MULTILINE)
_BIO_BOLD_WRAPPER = re.compile(r"^\*\*(.+?)\*\*\s*$")


def _clean_bio(raw: str) -> str:
    """Extract clean bio text from an LLM response.

    Defends against the LLM producing:
      - markdown headers ("# LeapOne Bio")
      - bold wrappers ("**actual bio**")
      - character-count meta ("*Character count: 50*")
      - "Alternative if..." sections
      - leading "Bio:" / "Social Bio:" labels
      - surrounding quotes
    Returns the first clean bio sentence/line.
    """
    if not raw:
        return ""
    s = raw.strip()

    # Cut at the first end-marker (case-insensitive)
    s_lower = s.lower()
    cut = len(s)
    for marker in _BIO_END_MARKERS:
        idx = s_lower.find(marker)
        if 0 < idx < cut:
            cut = idx
    s = s[:cut].strip()

    # Strip leading markdown heading line
    s = _BIO_HEADING_LINE.sub("", s, count=1).strip()
    # Strip leading "Bio:" / "Social Bio:" / etc.
    s = _BIO_LABEL_PREFIX.sub("", s).strip()
    # Take first non-empty line (bios are one line)
    lines = [line.strip() for line in s.split("\n") if line.strip()]
    if lines:
        s = lines[0]
    # Strip **bold** wrapper if the whole line is wrapped in it
    m = _BIO_BOLD_WRAPPER.match(s)
    if m:
        s = m.group(1).strip()
    # Strip surrounding quotes
    s = s.strip("\"'").strip()
    return s


def _clean_description(raw: str) -> str:
    """Light cleanup for descriptions.

    Less aggressive than _clean_bio because descriptions are paragraph-form
    and we want to preserve content. Only strips leading markdown headers
    and obvious meta-prefixes ("Description:", "Here is the description:").
    """
    if not raw:
        return ""
    s = raw.strip()
    # Strip leading "Here is..." / "Here's..." preambles
    s = re.sub(r"^(here is|here's|here are)\s+(the\s+)?(\w+\s+){0,4}description:?\s*\n*",
               "", s, count=1, flags=re.IGNORECASE).strip()
    # Strip a leading markdown heading
    s = _BIO_HEADING_LINE.sub("", s, count=1).strip()
    # Strip a leading "Description:" / "Website Description:" label
    s = re.sub(
        r"^(?:description|website\s+description|google\s+description|gbp\s+description|"
        r"google\s+business\s+profile\s+description|yelp\s+description)\s*:\s*",
        "", s, flags=re.IGNORECASE,
    ).strip()
    return s


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

    # Phase 2: owner's custom seed questions. Sanitize: cap length per item
    # and total count, drop empties.
    custom_faq_seeds = [
        s.strip()[:200] for s in (request.custom_faq_seeds or [])
        if s and s.strip()
    ][:10]

    # Phase 4: owner's existing Q+A pairs from their site. Sanitize:
    # cap count + lengths, drop empties or malformed pairs.
    existing_faqs = []
    for f in (request.existing_faqs or [])[:50]:
        q = (f.question or "").strip()[:200]
        a = (f.answer   or "").strip()[:1000]
        if q and a:
            existing_faqs.append({"question": q, "answer": a})

    prompts = _build_content_prompts(language, base_context, services,
                                     paa_questions, custom_faq_seeds,
                                     existing_faqs)

    # System prompts enforce output format at the model level (more reliable
    # than user-prompt instructions). Particularly important for the bio,
    # which the LLM otherwise treats as a creative-writing assignment and
    # responds with markdown headers + alternatives + character-count notes.
    desc_system = (
        "You produce only the description text in plain prose. "
        "No markdown headers, no bold/italic, no preamble, no alternatives, "
        "no character counts, no labels. Output starts with the first word "
        "of the description itself."
    )
    bio_system = (
        "You produce only the bio text — a single short sentence or phrase "
        "under 150 characters. No markdown, no headers, no quotation marks, "
        "no labels, no alternatives, no character counts. Output starts and "
        "ends with the bio words themselves."
    )

    # Run all 5 LLM calls in parallel
    website_desc, gbp_desc, yelp_desc, social_bio_raw, faq_raw = await asyncio.gather(
        content_llm.generate(prompt=prompts["website_desc"], max_tokens=700, temperature=0.7,
                           system_prompt=desc_system),
        content_llm.generate(prompt=prompts["gbp_desc"],     max_tokens=350, temperature=0.7,
                           system_prompt=desc_system),
        content_llm.generate(prompt=prompts["yelp_desc"],    max_tokens=500, temperature=0.7,
                           system_prompt=desc_system),
        content_llm.generate(prompt=prompts["social_bio"],   max_tokens=120, temperature=0.5,
                           system_prompt=bio_system),
        content_llm.generate(prompt=prompts["faq"],          max_tokens=2500, temperature=0.5,
                           system_prompt="Return only valid JSON, no markdown."),
    )

    # Parse FAQ JSON, tolerant of fenced code blocks the LLM sometimes emits
    try:
        llm_faq = json.loads(re.sub(r'^```(?:json)?\s*|\s*```$', '', faq_raw.strip(),
                                     flags=re.MULTILINE))
        if not isinstance(llm_faq, list):
            llm_faq = []
    except Exception:
        llm_faq = []

    # Phase 4 — merge: owner's existing Q+A pairs come FIRST (verbatim),
    # then the LLM-generated new ones. Existing pairs preserve the owner's
    # exact wording for content already published on their website.
    faq: list[dict] = []
    for f in existing_faqs:
        faq.append({"question": f["question"], "answer": f["answer"]})
    for item in llm_faq:
        if isinstance(item, dict) and item.get("question") and item.get("answer"):
            faq.append({
                "question": str(item["question"]).strip(),
                "answer":   str(item["answer"]).strip(),
            })

    # Clean LLM output (strip markdown headers, "Alternative" sections,
    # bold-line wrappers, character-count meta) BEFORE applying char caps,
    # so we don't end up truncating 150 chars of markdown garbage.
    social_bio = _truncate_at_word(_clean_bio(social_bio_raw), 150)
    descriptions = {
        "website": _clean_description(website_desc),
        "gbp":     _truncate_at_word(_clean_description(gbp_desc), 700),
        "yelp":    _clean_description(yelp_desc),
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

    insert_res = supabase_admin.table("aeo_content").insert({
        "business_id":   business["id"],
        "description":   descriptions["website"],   # legacy column for backward compat
        "descriptions":  descriptions,
        "faq":           faq,
        "faq_schema":    faq_schema_raw,
        "schema_markup": schema_raw,
        "social_bio":    social_bio,
        "language":      language,
        "paa_questions": paa_questions,
        "custom_faq_seeds": custom_faq_seeds,
        "existing_faqs": existing_faqs,
    }).execute()
    content_id = (insert_res.data[0]["id"]
                  if insert_res.data and insert_res.data[0].get("id") else None)

    return {
        "id":                    content_id,
        "language":              language,
        "descriptions":          descriptions,
        "social_bio":            social_bio,
        "faq":                   faq,
        "faq_schema":            faq_schema_raw,
        "schema_markup":         schema_raw,
        "schema_missing_fields": schema_missing,
        "paa_questions":         paa_questions,
        "custom_faq_seeds":      custom_faq_seeds,
        "existing_faqs":         existing_faqs,
        "validation_warnings":   validation_warnings,
        "verified":              {},
    }


# ─── Verify-and-edit endpoints (migration 017) ────────────────────────────
# Pattern: AI generates content -> owner reviews -> owner edits inline OR
# regenerates with notes -> owner verifies. Mirrors the reviews-module
# pattern. Three endpoints below: PATCH for edits, /verify for the
# verified-state toggle, /regenerate-item for "rewrite this with these
# notes." All scoped to the calling user's business via RLS + manual check.


class ContentPatchRequest(BaseModel):
    """Body of PATCH /content/{id}. updates is a flat map of dotted-path keys
    to new string values. Keys: 'description.<website|gbp|yelp>', 'social_bio',
    'faq.<idx>.<question|answer>'."""
    updates: dict[str, str]


class ContentVerifyRequest(BaseModel):
    key: str       # 'description.website' | 'social_bio' | 'faq.<idx>'
    verified: bool


class ContentRegenerateItemRequest(BaseModel):
    key: str       # same as verify.key but only the supported regenerate keys
    notes: str = ""


# Dotted-path keys the verified-state map is allowed to track. Anything else
# raises a 422 to prevent typos from silently storing weird state.
_VERIFY_KEY_RE = re.compile(
    r"^(description\.(website|gbp|yelp)|social_bio|faq\.\d+)$"
)
_PATCH_KEY_RE = re.compile(
    r"^(description\.(website|gbp|yelp)|social_bio|faq\.\d+\.(question|answer))$"
)
_REGENERATE_KEY_RE = re.compile(
    r"^(description\.(website|gbp|yelp)|social_bio|faq\.\d+)$"
)


def _apply_content_patch(row: dict, key: str, value: str) -> None:
    """Mutate `row` to apply a single dotted-path update. Raises ValueError
    on bad keys or out-of-range FAQ indices."""
    if not _PATCH_KEY_RE.match(key):
        raise ValueError(f"Invalid update key: {key}")

    if key.startswith("description."):
        sub = key.split(".", 1)[1]
        descs = dict(row.get("descriptions") or {})
        descs[sub] = value
        row["descriptions"] = descs
        # Keep legacy `description` column synced when website variant changes,
        # so anything still reading the old shape sees the latest text.
        if sub == "website":
            row["description"] = value
        return

    if key == "social_bio":
        row["social_bio"] = value
        return

    if key.startswith("faq."):
        _, idx_str, field = key.split(".", 2)
        idx = int(idx_str)
        faq = list(row.get("faq") or [])
        if not (0 <= idx < len(faq)):
            raise ValueError(f"FAQ index {idx} out of range (0..{len(faq) - 1})")
        item = dict(faq[idx])
        item[field] = value
        faq[idx] = item
        row["faq"] = faq
        return

    raise ValueError(f"Unknown key: {key}")  # unreachable given the regex


async def _load_content_for_user(content_id: str, current_user: dict) -> tuple[dict, dict]:
    """Fetch an aeo_content row + verify it belongs to the calling user's
    business. Returns (content_row, business_row). Raises HTTPException
    on miss / access denied."""
    business = await get_business_by_user(current_user["id"])
    if not business:
        raise HTTPException(status_code=404, detail="Business profile not found")

    res = supabase_admin.table("aeo_content") \
        .select("*").eq("id", content_id).limit(1).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Content not found")
    content = res.data[0]

    if str(content.get("business_id")) != str(business["id"]):
        raise HTTPException(status_code=403, detail="Access denied")

    return content, business


@router.patch("/content/{content_id}")
async def patch_content(
    content_id: str,
    request: ContentPatchRequest,
    current_user: dict = Depends(get_current_user),
):
    """Apply inline edits to one aeo_content row. Body: { updates: {key: value, ...} }
    where keys are dotted paths (description.website, social_bio, faq.0.answer, etc).
    Multiple updates apply atomically (single supabase write).
    Also rebuilds the FAQ schema if any FAQ field changes (keeps JSON-LD in sync)."""
    content, _ = await _load_content_for_user(content_id, current_user)

    if not request.updates:
        raise HTTPException(status_code=422, detail="No updates provided")

    # Apply each update. Validation errors -> 422 with the offending key.
    faq_changed = False
    for key, value in request.updates.items():
        try:
            _apply_content_patch(content, key, value)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        if key.startswith("faq."):
            faq_changed = True

    # If any FAQ Q/A changed, rebuild the FAQPage JSON-LD so the schema
    # stays in sync with the human-readable Q&As.
    if faq_changed:
        faq_items = content.get("faq") or []
        if faq_items:
            schema_obj = build_faq_schema(faq_items)
            content["faq_schema"] = json.dumps(schema_obj, indent=2, ensure_ascii=False)
        else:
            content["faq_schema"] = None

    # Persist
    update_payload = {
        "descriptions":   content.get("descriptions"),
        "description":    content.get("description"),
        "social_bio":     content.get("social_bio"),
        "faq":            content.get("faq"),
        "faq_schema":     content.get("faq_schema"),
        "last_edited_at": "now()",
    }
    supabase_admin.table("aeo_content").update(update_payload).eq("id", content_id).execute()

    return {
        "id":          content_id,
        "descriptions": content.get("descriptions"),
        "social_bio":   content.get("social_bio"),
        "faq":          content.get("faq"),
        "faq_schema":   content.get("faq_schema"),
    }


@router.post("/content/{content_id}/verify")
async def verify_content_item(
    content_id: str,
    request: ContentVerifyRequest,
    current_user: dict = Depends(get_current_user),
):
    """Toggle the verified state for a single item key. Stored as JSONB map
    on aeo_content.verified. Used to track which items the owner has
    reviewed and approved before they're considered safe to publish."""
    content, _ = await _load_content_for_user(content_id, current_user)

    if not _VERIFY_KEY_RE.match(request.key):
        raise HTTPException(status_code=422, detail=f"Invalid verify key: {request.key}")

    verified = dict(content.get("verified") or {})
    if request.verified:
        verified[request.key] = True
    else:
        verified.pop(request.key, None)

    supabase_admin.table("aeo_content").update({"verified": verified}) \
        .eq("id", content_id).execute()
    return {"id": content_id, "verified": verified}


def _build_regenerate_prompts(
    business: dict, language: str, services: str, notes: str,
) -> dict[str, tuple[str, int, float]]:
    """Map regenerate keys -> (prompt, max_tokens, temperature) tuples.
    Notes are appended as 'User notes:' to whichever base prompt is used."""
    btype    = business["type"]
    name     = business["name"]
    city     = business["city"]
    province = business.get("province") or ""
    website  = business.get("website") or ""

    base_context = (
        f"Business name: {name}\n"
        f"Business type: {btype}\n"
        f"City: {city}{', ' + province if province else ''}\n"
        f"Services: {services}\n"
        f"Website: {website}\n"
    )

    # Re-use the same prompt builder that generate_content uses, with empty
    # paa_questions (we don't re-fetch PAA on per-item regenerate -- it's
    # already in the DB and the user's notes are the new signal).
    prompts = _build_content_prompts(language, base_context, services, [])
    notes_block = f"\n\nUser notes for this regenerate: {notes.strip()}\n" if notes.strip() else ""

    out: dict[str, tuple[str, int, float]] = {
        "description.website": (prompts["website_desc"] + notes_block, 700, 0.7),
        "description.gbp":     (prompts["gbp_desc"]     + notes_block, 350, 0.7),
        "description.yelp":    (prompts["yelp_desc"]    + notes_block, 500, 0.7),
        "social_bio":          (prompts["social_bio"]   + notes_block, 120, 0.5),
    }
    return out


@router.post("/content/{content_id}/regenerate-item")
async def regenerate_content_item(
    content_id: str,
    request: ContentRegenerateItemRequest,
    current_user: dict = Depends(get_current_user),
):
    """Regenerate a single item with optional user notes ('make it shorter',
    'remove Invisalign — we don't do that'). Saves the new value AND clears
    that item's verified flag (it's a new value, owner needs to re-verify)."""
    content, business = await _load_content_for_user(content_id, current_user)

    if not _REGENERATE_KEY_RE.match(request.key):
        raise HTTPException(status_code=422,
            detail=f"Cannot regenerate item with key: {request.key}")

    if BILLING_ENABLED:
        sub = await get_active_subscription(str(business["id"]))
        if not sub:
            raise HTTPException(status_code=402, detail="Active subscription required")

    language = (content.get("language") == "fr" and "fr") or "en"
    services = business.get("services") or ""

    # ─── Description / social bio ─────────────────────────────────────────
    if request.key.startswith("description.") or request.key == "social_bio":
        prompts_map = _build_regenerate_prompts(business, language, services, request.notes)
        prompt, max_tokens, temperature = prompts_map[request.key]

        if request.key == "social_bio":
            sys_prompt = (
                "You produce only the bio text — a single short sentence or phrase "
                "under 150 characters. No markdown, no headers, no quotation marks, "
                "no labels, no alternatives, no character counts."
            )
        else:
            sys_prompt = (
                "You produce only the description text in plain prose. "
                "No markdown, no preamble, no alternatives, no character counts, no labels."
            )

        raw = await content_llm.generate(
            prompt=prompt, max_tokens=max_tokens, temperature=temperature,
            system_prompt=sys_prompt,
        )

        if request.key == "social_bio":
            value = _truncate_at_word(_clean_bio(raw), 150)
        elif request.key == "description.gbp":
            value = _truncate_at_word(_clean_description(raw), 700)
        else:
            value = _clean_description(raw)

        # Save + clear verified flag for this item (new value -> needs re-review)
        try:
            _apply_content_patch(content, request.key, value)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        verified = dict(content.get("verified") or {})
        verified.pop(request.key, None)

        supabase_admin.table("aeo_content").update({
            "descriptions":   content.get("descriptions"),
            "description":    content.get("description"),
            "social_bio":     content.get("social_bio"),
            "verified":       verified,
            "last_edited_at": "now()",
        }).eq("id", content_id).execute()

        return {"key": request.key, "value": value, "verified": verified}

    # ─── FAQ item ─────────────────────────────────────────────────────────
    # Regenerate one Q&A pair. Prompt asks for ONE question and answer in
    # JSON. Notes ("the answer is wrong about Invisalign") drive a rewrite.
    if request.key.startswith("faq."):
        idx = int(request.key.split(".", 1)[1])
        existing = (content.get("faq") or [])
        if not (0 <= idx < len(existing)):
            raise HTTPException(status_code=422, detail=f"FAQ index out of range")

        original = existing[idx]
        original_q = original.get("question", "")
        original_a = original.get("answer", "")

        notes_block = f"\nUser notes: {request.notes.strip()}\n" if request.notes.strip() else ""
        if language == "fr":
            faq_prompt = (
                f"Entreprise: {business['name']} ({business['type']}, {business['city']})\n"
                f"Question FAQ existante: {original_q}\n"
                f"Réponse existante: {original_a}\n"
                f"{notes_block}"
                f"Réécris cette FAQ. La réponse doit faire 40-80 mots, factuelle, "
                f"utile pour citation par les IA. Format JSON: "
                f"{{\"question\": \"...\", \"answer\": \"...\"}}. "
                f"Retourne uniquement du JSON valide."
            )
        else:
            faq_prompt = (
                f"Business: {business['name']} ({business['type']}, {business['city']})\n"
                f"Existing FAQ question: {original_q}\n"
                f"Existing answer: {original_a}\n"
                f"{notes_block}"
                f"Rewrite this Q&A. The answer should be 40-80 words, factual, "
                f"useful for AI to cite verbatim. Format as JSON: "
                f"{{\"question\": \"...\", \"answer\": \"...\"}}. "
                f"Return only valid JSON."
            )

        raw = await content_llm.generate(
            prompt=faq_prompt, max_tokens=400, temperature=0.5,
            system_prompt="Return only valid JSON, no markdown.",
        )
        try:
            new_item = json.loads(re.sub(r'^```(?:json)?\s*|\s*```$', '',
                                          raw.strip(), flags=re.MULTILINE))
            if not isinstance(new_item, dict) or "question" not in new_item or "answer" not in new_item:
                raise ValueError("Bad shape")
        except Exception:
            raise HTTPException(status_code=502, detail="Regenerate failed -- LLM returned invalid JSON")

        # Apply
        faq = list(content.get("faq") or [])
        faq[idx] = {"question": str(new_item["question"]), "answer": str(new_item["answer"])}
        content["faq"] = faq

        # Rebuild FAQ schema since the item changed
        schema_obj = build_faq_schema(faq)
        new_faq_schema = json.dumps(schema_obj, indent=2, ensure_ascii=False)

        # Clear verified flag for this item
        verified = dict(content.get("verified") or {})
        verified.pop(request.key, None)

        supabase_admin.table("aeo_content").update({
            "faq":            faq,
            "faq_schema":     new_faq_schema,
            "verified":       verified,
            "last_edited_at": "now()",
        }).eq("id", content_id).execute()

        return {"key": request.key, "value": faq[idx], "verified": verified}

    # Should be unreachable given the regex check above
    raise HTTPException(status_code=422, detail=f"Unsupported key: {request.key}")


# ─── AI execution coach (recommendation help chat) ────────────────────────
# Headline differentiation feature: a chat coach attached to each
# recommendation. SMB owners get told what to do but rarely get walked
# through how -- this fills that gap. Non-streaming for v1 (simpler).
# Tier gating shipping in a separate commit.

class CoachMessage(BaseModel):
    role: str           # 'user' | 'assistant'
    content: str


class CoachRecommendation(BaseModel):
    """Subset of the recommendation shape needed to ground the coach prompt.
    We pass this from the frontend so the coach knows exactly which rec
    the owner is working on without us having to look it up server-side."""
    title: str
    description: str = ""
    action: str = ""
    pillar: str = ""
    url: str | None = None
    impact: int = 0


class CoachRequest(BaseModel):
    recommendation: CoachRecommendation
    messages: list[CoachMessage] = []  # full chat history (excluding the new message)
    new_message: str
    language: str = "en"               # 'en' | 'fr'


# Hard cap on conversation history sent to the LLM. Keeps cost bounded
# and prevents prompt-stuffing abuse. ~10 turns of normal chat.
_COACH_HISTORY_CAP = 20
# Hard cap on a single user message. Most coach questions are 1-3 sentences.
_COACH_MESSAGE_CAP = 2000


def _build_coach_system_prompt(rec: CoachRecommendation, business: dict, language: str) -> str:
    """Builds the system prompt that grounds the coach in (a) this specific
    recommendation, (b) the owner's business context, (c) platform-specific
    knowledge from api/knowledge/<key>.md when available, and (d) the tone +
    behaviour rules that make the coach genuinely useful for non-technical
    Canadian SMB owners."""
    biz_name     = business.get("name", "the business")
    biz_type     = business.get("type", "small business")
    biz_city     = business.get("city", "")
    biz_province = business.get("province", "")
    biz_country  = business.get("country", "Canada")
    biz_website  = business.get("website") or ""

    # Load platform-specific knowledge for THIS recommendation if we have a
    # matching entry. Lets the coach answer Canadian-specific platform
    # questions (HomeStars HST/GST format, RateMDs auto-claim flow, etc.)
    # that generic LLM training data gets wrong or out of date.
    rec_kb = kb.for_recommendation(rec.title)
    kb_block_en = (
        "\n\n=== PLATFORM-SPECIFIC KNOWLEDGE (use this — more accurate "
        "than your general training data on Canadian platforms) ===\n"
        f"{rec_kb}\n"
        "=== END PLATFORM KNOWLEDGE ===\n"
    ) if rec_kb else ""
    kb_block_fr = (
        "\n\n=== CONNAISSANCES SPÉCIFIQUES À LA PLATEFORME (utilise-les — "
        "plus précises que tes données d'entraînement générales sur les "
        "plateformes canadiennes) ===\n"
        f"{rec_kb}\n"
        "=== FIN CONNAISSANCES PLATEFORME ===\n"
    ) if rec_kb else ""

    if language == "fr":
        return (
            "Tu es un coach IA attentionné qui aide un propriétaire de PME canadienne "
            "à exécuter une recommandation spécifique pour améliorer sa visibilité "
            "dans la recherche IA. Le propriétaire n'est PAS technique — il peut "
            "avoir du mal avec des termes comme « zone de service », « code de "
            "vérification », « balisage de schéma ». Sois chaleureux, donne des "
            "instructions étape par étape, pose des questions de clarification au "
            "besoin, et ne suppose jamais de connaissances techniques.\n\n"
            f"Recommandation en cours :\n"
            f"- Titre : {rec.title}\n"
            f"- Pourquoi c'est important : {rec.description}\n"
            f"- Action : {rec.action}\n"
            f"- Lien : {rec.url or 'aucun'}\n\n"
            f"Contexte de l'entreprise :\n"
            f"- Nom : {biz_name}\n"
            f"- Type : {biz_type}\n"
            f"- Ville : {biz_city}, {biz_province}, {biz_country}\n"
            f"- Site web : {biz_website or 'non fourni'}\n\n"
            "Règles :\n"
            "1. Réponses courtes (2-4 paragraphes courts MAX). Pas de leçons.\n"
            "2. Pose des questions si tu n'es pas sûr de ce dont la personne a besoin.\n"
            "3. Langage simple. Si un terme technique est inévitable, définis-le en une phrase.\n"
            "4. Si la personne est bloquée sur un bouton ou écran spécifique, donne le libellé exact à cliquer.\n"
            "5. Si la personne est bloquée ou frustrée, propose de rédiger un courriel "
            "pour son administrateur web.\n"
            "6. Termine par « Autre chose ? » ou une question similaire pour maintenir la conversation.\n"
            "7. N'invente jamais d'étapes. Si tu n'es pas sûr du fonctionnement d'une plateforme, dis-le honnêtement.\n"
            "8. Réponds en français du Québec, naturellement, comme un humain.\n"
            + kb_block_fr
        )

    return (
        "You are a patient, friendly AI coach helping a Canadian small business "
        "owner execute a specific recommendation from their AI-search-visibility "
        "tool. The owner is NOT technical — they may struggle with terms like "
        "'service area', 'verification code', 'schema markup'. Be warm, give "
        "specific step-by-step instructions, ask clarifying questions if you're "
        "not sure what they need, and never assume technical knowledge.\n\n"
        f"The recommendation they're working on:\n"
        f"- Title: {rec.title}\n"
        f"- Why it matters: {rec.description}\n"
        f"- What to do: {rec.action}\n"
        f"- Link: {rec.url or 'none'}\n\n"
        f"Business context:\n"
        f"- Name: {biz_name}\n"
        f"- Type: {biz_type}\n"
        f"- City: {biz_city}, {biz_province}, {biz_country}\n"
        f"- Website: {biz_website or 'not provided'}\n\n"
        "Rules:\n"
        "1. Keep replies SHORT (2-4 short paragraphs MAX). Don't lecture.\n"
        "2. Ask clarifying questions if you're unsure what the owner needs.\n"
        "3. Use plain language. If a technical term is unavoidable, define it in one short sentence.\n"
        "4. If the owner is stuck on a specific button or screen, give them the exact label to click.\n"
        "5. If the owner is frustrated or stuck, offer to write an email they can send to a "
        "web administrator or developer to do the technical part for them.\n"
        "6. End each reply with 'Anything else stuck?' or a similar prompt that keeps "
        "the door open for follow-up questions.\n"
        "7. Never invent steps. If you're not sure how a specific platform works, "
        "say so honestly and suggest they check the platform's help docs or ask their developer.\n"
        "8. Be conversational. You're a coach, not a manual.\n"
        + kb_block_en
    )


@router.post("/recommendation-help")
async def recommendation_help(
    request: CoachRequest,
    current_user: dict = Depends(get_current_user),
):
    """AI execution coach. Takes a recommendation context + conversation
    history + new user message, returns the next assistant reply.
    Non-streaming. Pro-tier only when BILLING_ENABLED."""
    # ─── Input validation ─────────────────────────────────────────────────
    if not request.new_message or not request.new_message.strip():
        raise HTTPException(status_code=422, detail="new_message is required")
    if len(request.new_message) > _COACH_MESSAGE_CAP:
        raise HTTPException(status_code=422,
            detail=f"new_message exceeds {_COACH_MESSAGE_CAP} chars")
    if not request.recommendation.title.strip():
        raise HTTPException(status_code=422, detail="recommendation.title is required")

    # Trim history to the most recent N turns to bound cost
    history = request.messages[-_COACH_HISTORY_CAP:]
    for m in history:
        if m.role not in ("user", "assistant"):
            raise HTTPException(status_code=422,
                detail=f"Invalid message role: {m.role}")

    # ─── Get business context ─────────────────────────────────────────────
    business = await get_business_by_user(current_user["id"])
    if not business:
        raise HTTPException(status_code=404, detail="Business profile not found")

    # ─── Tier gating: Pro only when billing is enabled ────────────────────
    # The coach is the headline differentiation feature for Pro. Starter
    # users see the upgrade CTA on the frontend instead of the chat input.
    if BILLING_ENABLED:
        sub = await get_active_subscription(str(business["id"]))
        if not sub or sub.get("plan_tier") != "pro":
            raise HTTPException(status_code=402, detail="pro_required")

    language = "fr" if request.language == "fr" else "en"
    system_prompt = _build_coach_system_prompt(request.recommendation, business, language)

    # ─── Build the chat transcript ────────────────────────────────────────
    # Serialised inside the prompt so it works with any LLM provider.
    # Token budget is small because we trimmed history above.
    transcript = "\n".join(
        f"{'Owner' if m.role == 'user' else 'Coach'}: {m.content}"
        for m in history
    )
    if transcript:
        transcript += "\n"
    full_prompt = (
        f"{transcript}"
        f"Owner: {request.new_message.strip()}\n"
        f"Coach:"
    )

    # ─── Call the LLM ─────────────────────────────────────────────────────
    # Routes through `coach_llm` (configured via COACH_PROVIDER + COACH_MODEL).
    try:
        reply = await coach_llm.generate(
            prompt=full_prompt,
            system_prompt=system_prompt,
            max_tokens=600,
            temperature=0.5,
        )
    except Exception as e:
        logger.warning(f"[COACH] LLM call failed: {e}")
        raise HTTPException(status_code=502, detail="Coach is temporarily unavailable. Try again in a moment.")

    return {"reply": (reply or "").strip()}
"""DataForSEO client — keyword discovery + SERP for the market-intelligence layer.

Async wrapper over the DataForSEO `/live` endpoints validated in Phase 0
(see docs/market-intelligence-architecture.md and
scripts/dataforseo_test/runner.py). The runner was sync (one-off script);
this is the async production client, matching the other integrations
(serpapi.py, perplexity.py).

Auth: HTTP Basic with DATAFORSEO_LOGIN / DATAFORSEO_PASSWORD from env.
Every endpoint POSTs a single-task body (a list with one dict) and nests
results 3 levels deep under tasks[0].result — the get_* helpers unwrap that.

Endpoints exposed (cost per call from Phase 0):
  - keywords_for_keywords  ~$0.075  CITY-level discovery (the primary path)
  - serp_advanced          ~$0.002  PAA / related questions for one keyword
  - search_volume          ~$0.075  per-keyword volume + monthly_searches
  - keywords_for_site      ~$0.015  what a customer's domain ranks for

Phase 0 finding baked in here: DataForSEO Labs is country-only (94
locations worldwide), so city-level discovery MUST use the Keywords Data
family with an integer `location_code`. CITY_LOCATION_CODES holds the
common Ontario cities; resolve_location_code() is the runtime fallback for
any city not in the table.

This module is dormant until Phase 2 wires it into the refresh worker — it
makes no calls at import time.
"""
import logging
import os

import httpx


logger = logging.getLogger(__name__)

API_BASE = "https://api.dataforseo.com"
TIMEOUT = 60.0

DATAFORSEO_LOGIN = os.getenv("DATAFORSEO_LOGIN")
DATAFORSEO_PASSWORD = os.getenv("DATAFORSEO_PASSWORD")


# City → DataForSEO Google Ads location_code (integer). Labs API can't do
# city level, so the Keywords Data family addresses cities by these codes.
# Sourced from /v3/keywords_data/google_ads/locations during Phase 0. Extend
# as new cities sign up; resolve_location_code() covers anything missing.
CITY_LOCATION_CODES: dict[str, int] = {
    "Burlington":  1002197,
    "Mississauga": 1002350,
    "Milton":      1002347,
    "Oakville":    1002371,
    "Brampton":    1002191,
    "Toronto":     1002451,
}


# Per-vertical baseline seed terms for keyword discovery. Kept minimal — Google
# Ads' related-keyword graph expands them broadly. Per-business augmentation
# (from website signal extraction) is layered on at audit time; these are just
# the cached-market floor. Keys are the canonical vertical keys from onboarding
# (apps/web/components/onboarding/StepBusinessInfo.tsx TYPES[].key).
BASELINE_SEEDS: dict[str, list[str]] = {
    "dentist":          ["dentist", "dental clinic", "family dentist"],
    "restaurant":       ["restaurant", "dining", "food near me"],
    "physiotherapist":  ["physiotherapy", "physiotherapist", "physio clinic", "rehabilitation"],
    "chiropractor":     ["chiropractor", "chiropractic clinic"],
    "optometrist":      ["optometrist", "eye doctor", "eye exam"],
    "family_doctor":    ["family doctor", "walk in clinic", "medical clinic"],
    "veterinarian":     ["veterinarian", "vet clinic", "pet hospital"],
    "salon":            ["hair salon", "beauty salon", "nail salon"],
    "lawyer":           ["lawyer", "law firm", "legal services"],
    "accountant":       ["accountant", "tax preparation", "bookkeeping"],
    "realtor":          ["realtor", "real estate agent", "homes for sale"],
    "plumber":          ["plumber", "plumbing service", "emergency plumber"],
    "auto_repair":      ["auto repair", "mechanic", "car service"],
    "cleaning_service": ["cleaning service", "house cleaners", "maid service"],
    "personal_trainer": ["personal trainer", "fitness coach", "gym"],
    "cafe":             ["cafe", "coffee shop", "breakfast"],
    "retail":           ["store", "shop"],
    "other":            [],   # forces seed augmentation from the services field
}


def _auth() -> tuple[str, str]:
    if not DATAFORSEO_LOGIN or not DATAFORSEO_PASSWORD:
        raise RuntimeError("DATAFORSEO_LOGIN and DATAFORSEO_PASSWORD not set")
    return (DATAFORSEO_LOGIN, DATAFORSEO_PASSWORD)


async def _post(path: str, body: list[dict], *, timeout: float = TIMEOUT) -> dict:
    """POST a single-task body to a DataForSEO /live endpoint. Returns parsed
    JSON. Retries once on a 5xx / transport error, then raises."""
    last_exc: Exception | None = None
    async with httpx.AsyncClient(auth=_auth(), timeout=timeout,
                                 headers={"Content-Type": "application/json"}) as client:
        for attempt in (1, 2):
            try:
                resp = await client.post(f"{API_BASE}{path}", json=body)
            except httpx.RequestError as exc:
                last_exc = exc
                if attempt == 2:
                    raise
                continue
            if resp.status_code >= 500 and attempt == 1:
                continue
            resp.raise_for_status()
            return resp.json()
    # Unreachable in practice — the loop either returns or raises above.
    raise last_exc or RuntimeError("dataforseo: unreachable")


# ── Endpoint helpers ────────────────────────────────────────────────────────

async def keywords_for_keywords(seeds: list[str], location_code: int, *, limit: int = 200) -> dict:
    """City-level keyword discovery from seed terms (Keywords Data API).
    location_code is an integer city code (see CITY_LOCATION_CODES). Returns the
    raw response; use get_keywords() to flatten to {keyword, search_volume, ...}.
    Primary discovery path for the cached market-intelligence layer."""
    return await _post(
        "/v3/keywords_data/google_ads/keywords_for_keywords/live",
        [{
            "keywords": seeds,
            "location_code": location_code,
            "language_name": "English",
            "limit": limit,
        }],
    )


async def serp_advanced(keyword: str, location_name: str = "Canada") -> dict:
    """Full Google SERP for one keyword (organic + people_also_ask +
    related_searches). Used to expand the top questions via PAA. PAA isn't
    always rendered (healthcare in mid-cities often omits it) — callers should
    fall back to related_searches and never fail on an absent PAA block."""
    return await _post(
        "/v3/serp/google/organic/live/advanced",
        [{
            "language_code": "en",
            "location_name": location_name,
            "keyword": keyword,
            "device": "desktop",
        }],
    )


async def search_volume(
    keywords: list[str],
    *,
    location_code: int | None = None,
    location_name: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict:
    """Per-keyword search volume + monthly_searches history. Prefer
    location_code (city-level); falls back to location_name (country). Pass
    date_from/date_to to populate monthly_searches for trend analysis.
    Volumes below ~10/mo come back null — treat null as 'below threshold',
    not zero."""
    body: dict = {
        "keywords": keywords,
        "language_name": "English",
        "include_serp_info": False,
    }
    if location_code is not None:
        body["location_code"] = location_code
    else:
        body["location_name"] = location_name or "Canada"
    if date_from:
        body["date_from"] = date_from
    if date_to:
        body["date_to"] = date_to
    return await _post("/v3/keywords_data/google_ads/search_volume/live", [body])


async def keywords_for_site(target: str, *, location_name: str = "Canada", limit: int = 50) -> dict:
    """Keywords a domain already ranks for (Labs API, country-level). `target`
    must be a bare domain — use normalize_domain() first."""
    return await _post(
        "/v3/dataforseo_labs/google/keywords_for_site/live",
        [{
            "target": target,
            "location_name": location_name,
            "language_name": "English",
            "limit": limit,
        }],
    )


async def resolve_location_code(city: str, province: str | None = None,
                                country: str = "Canada") -> int | None:
    """Look up the Google Ads location_code for a city not in CITY_LOCATION_CODES.
    Checks the hardcoded table first, then queries /locations (zero cost) and
    matches on a 'City,Province,Country' name prefix. Returns None if unresolved
    — caller should skip the city-level path and degrade gracefully."""
    if city in CITY_LOCATION_CODES:
        return CITY_LOCATION_CODES[city]
    try:
        data = await _post("/v3/keywords_data/google_ads/locations", [])
    except Exception as e:
        logger.warning(f"[DFS] location lookup failed for '{city}': {e}")
        return None
    result = get_result(data)
    items = result if isinstance(result, list) else result.get("items", []) if isinstance(result, dict) else []
    needle = city.strip().lower()
    region = (province or "").strip().lower()
    best: int | None = None
    for loc in items or []:
        name = (loc.get("location_name") or "").lower()
        if loc.get("location_type") not in (None, "City", "Municipality"):
            continue
        parts = [p.strip() for p in name.split(",")]
        if parts and parts[0] == needle and (not region or region in name):
            code = loc.get("location_code")
            if isinstance(code, int):
                best = code
                break
    if best is not None:
        CITY_LOCATION_CODES[city] = best  # cache for the process lifetime
    else:
        logger.warning(f"[DFS] no location_code resolved for '{city}, {province}, {country}'")
    return best


# ── Response parsing ────────────────────────────────────────────────────────
# DataForSEO nests payloads under tasks[0].result. Shapes differ slightly
# between the SERP family (result[0].items) and the Keywords Data family
# (result is a flat list). These helpers normalize both.

def get_result(response: dict) -> dict | list:
    try:
        return response["tasks"][0]["result"] or {}
    except (KeyError, IndexError, TypeError):
        return {}


def get_items(response: dict) -> list[dict]:
    """items array from tasks[0].result[0].items (SERP-family responses)."""
    try:
        return response["tasks"][0]["result"][0]["items"] or []
    except (KeyError, IndexError, TypeError):
        return []


def get_keywords(response: dict) -> list[dict]:
    """Flatten a keywords_for_keywords / search_volume response to a uniform
    list of {keyword, search_volume, cpc, competition, monthly_searches}.
    Also handles the Labs keyword_ideas shape (result[0].items with nested
    keyword_info) in case that path is used later."""
    try:
        result = response["tasks"][0]["result"]
    except (KeyError, IndexError, TypeError):
        return []
    if not result:
        return []

    # Labs keyword_ideas shape: result == [{items: [...]}] with nested keyword_info
    if (isinstance(result, list) and result and isinstance(result[0], dict)
            and "items" in result[0]):
        out: list[dict] = []
        for k in result[0].get("items") or []:
            info = k.get("keyword_info") or {}
            out.append({
                "keyword": k.get("keyword"),
                "search_volume": info.get("search_volume"),
                "cpc": info.get("cpc"),
                "competition": info.get("competition"),
                "monthly_searches": info.get("monthly_searches"),
            })
        return out

    # Keywords Data flat-list shape (keywords_for_keywords, search_volume)
    if isinstance(result, list):
        return [k for k in result if isinstance(k, dict) and "keyword" in k]
    return []

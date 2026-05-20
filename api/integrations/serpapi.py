"""SerpApi GET /search wrapper.

One function: `search(params, *, timeout=30.0)`. Injects `api_key` from env
and returns the parsed JSON response. Callers pass `engine=...` plus any
engine-specific params (q, place_id, location, gl, hl, sort_by, …) and
extract what they need from the response.

Pulled out of api/aeo/router.py during Tier 3 of the AEO refactor. The
inline pattern it replaces was:

    params = {"api_key": SERPAPI_KEY, "engine": "google", ...}
    async with httpx.AsyncClient() as client:
        response = await client.get("https://serpapi.com/search", params=params, timeout=30.0)
        response.raise_for_status()
        data = response.json()

…repeated at seven call sites with subtly different timeouts and param
shapes. Now collapsed to:

    data = await serpapi.search({"engine": "google", ...}, timeout=30.0)

If SERPAPI_KEY is unset, raises RuntimeError. The PAA helper in
api/aeo/content/generator.py guards SERPAPI_KEY separately and returns []
on miss, so this exception is only hit by misconfigured environments.

Engines we currently call here (see callers for response-shape handling):
  - google                  (KG, local pack, organic, ai_overview, related_questions)
  - google_maps             (place_results | local_results — for place_id lookup)
  - google_maps_reviews     (newest-first reviews list with pagination)
"""
import os

import httpx


SERPAPI_KEY = os.getenv("SERPAPI_KEY")


async def search(params: dict, *, timeout: float = 30.0) -> dict:
    """GET https://serpapi.com/search with the given params + api_key.

    `params` is merged with the api_key — caller doesn't include it.
    Returns parsed JSON. Raises on HTTP errors or transport failures —
    callers wrap in try/except where graceful degradation is wanted."""
    if not SERPAPI_KEY:
        raise RuntimeError("SERPAPI_KEY not set")
    full_params = {"api_key": SERPAPI_KEY, **params}
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://serpapi.com/search",
            params=full_params,
            timeout=timeout,
        )
        response.raise_for_status()
        return response.json()

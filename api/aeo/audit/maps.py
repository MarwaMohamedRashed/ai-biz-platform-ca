"""Google Maps lookup helpers used across audit + reputation + competitor code.

Two helpers:

- `parse_relative_date(s)` — convert SerpApi's "3 weeks ago" / "a year ago"
  strings to approximate day counts. Used by the review-recency check and
  by reputation pagination to stop early once results fall outside the
  date window.

- `resolve_maps_place_id(name, city, country)` — look up the ChIJ-format
  Google Maps place_id for a business by searching the `google_maps`
  engine. The numeric CIDs returned by `google` local_results aren't
  accepted by `google_maps_reviews`, so we need a separate lookup to get
  a reviews-compatible id.

Originally lived in api/aeo/router.py (lines 83-95 and 1201-1236). Moved
here during Tier 4 so reputation/fetcher.py + future competitors.py can
import without a circular dep into router.py. Re-exported from router.py
under the old underscored names so existing callers keep working.
"""
import logging
import re

from integrations import serpapi as serpapi_client

from .geo import country_to_gl


logger = logging.getLogger(__name__)


def parse_relative_date(date_str: str | None) -> int | None:
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


async def resolve_maps_place_id(name: str, city: str | None, country: str | None = None) -> str | None:
    """Resolve a ChIJ-format Google Maps place_id for a business by searching
    the google_maps engine. The numeric CIDs returned by google search local_results
    are not accepted by google_maps_reviews, so we need to look up the real place_id.
    Returns None on any error."""
    query = f"{name} {city}" if city else name
    params: dict[str, str] = {
        "engine": "google_maps",
        "q": query,
        "hl": "en",
    }
    gl = country_to_gl(country)
    if gl:
        params["gl"] = gl
    try:
        data = await serpapi_client.search(params, timeout=20.0)
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

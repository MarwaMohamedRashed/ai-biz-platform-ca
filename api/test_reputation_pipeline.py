"""
Standalone test for the reputation / review fetching pipeline.
Tests each step independently so we can see exactly where it breaks.

Usage:
    python test_reputation_pipeline.py

It will prompt you for business name and city.
"""
import asyncio
import httpx
import os
import sys
from dotenv import load_dotenv

load_dotenv(override=True)

SERPAPI_KEY = os.getenv("SERPAPI_KEY")
if not SERPAPI_KEY:
    print("ERROR: SERPAPI_KEY not found in .env — cannot continue")
    sys.exit(1)

SEP = "-" * 60


# ─── Step 1: google_maps lookup to get ChIJ place_id ─────────────────────

async def _maps_lookup(query: str, gl: str = "ca") -> dict | None:
    """Raw SerpApi google_maps call — returns the full response dict, or None on 429."""
    params = {
        "api_key": SERPAPI_KEY,
        "engine": "google_maps",
        "q": query,
        "hl": "en",
        "gl": gl,
    }
    async with httpx.AsyncClient() as client:
        resp = await client.get("https://serpapi.com/search", params=params, timeout=20.0)
        if resp.status_code == 429:
            print(f"  ⚠ SerpApi rate limit (429) — waiting 5 seconds before retry...")
            await asyncio.sleep(5)
            resp = await client.get("https://serpapi.com/search", params=params, timeout=20.0)
        resp.raise_for_status()
        return resp.json()


def _pick_chij(data: dict) -> str | None:
    """Extract the first ChIJ-format place_id from a google_maps response."""
    place = data.get("place_results") or {}
    pr_id = place.get("place_id")
    if pr_id and str(pr_id).startswith("ChIJ"):
        return pr_id
    for r in data.get("local_results", []):
        lid = r.get("place_id")
        if lid and str(lid).startswith("ChIJ"):
            return lid
    return None


def _show_data(data: dict, query: str):
    """Print a summary of one google_maps response."""
    place = data.get("place_results") or {}
    pr_id = place.get("place_id")
    local = data.get("local_results", [])
    pr_fmt = "ChIJ ✓" if pr_id and str(pr_id).startswith("ChIJ") else ("CID ✗" if pr_id else "absent")
    print(f"  query            : {query!r}")
    print(f"  place_results    : title={place.get('title')!r}  place_id={pr_id!r}  [{pr_fmt}]")
    print(f"  local_results    : {len(local)} entries")
    for i, r in enumerate(local[:5]):
        lid = r.get("place_id")
        fmt = "ChIJ ✓" if lid and str(lid).startswith("ChIJ") else "CID/None ✗"
        print(f"    [{i}] {str(r.get('title'))[:50]:50s}  {lid!r}  [{fmt}]")


async def test_step1_resolve_place_id(name: str, city: str, province: str = "", postal: str = "", country: str = "Canada"):
    """
    Tries multiple query combinations in order of specificity.
    Shows us the raw SerpApi response so we can see what place_id format it returns.
    """
    print(f"\n{SEP}")
    print("STEP 1: Resolve ChIJ place_id via google_maps engine")
    print(f"  business : {name!r}")
    print(f"  city     : {city!r}")
    print(f"  province : {province!r}")
    print(f"  postal   : {postal!r}")
    print(f"  country  : {country!r}")

    # Build candidate queries from most specific to least
    queries: list[str] = []
    if postal:
        queries.append(f"{name} {postal}")
    if province:
        queries.append(f"{name} {city} {province}")
    queries.append(f"{name} {city}")
    queries.append(name)  # name only — last resort

    chosen_pid: str | None = None
    last_data: dict = {}

    for i, q in enumerate(queries):
        if i > 0:
            await asyncio.sleep(2)  # avoid SerpApi rate limit between queries
        print(f"\n  --- trying query: {q!r}")
        data = await _maps_lookup(q)
        if data is None:
            print(f"  ✗ Rate limited even after retry — skipping this query")
            continue
        last_data = data
        _show_data(data, q)
        pid = _pick_chij(data)
        if pid:
            chosen_pid = pid
            print(f"\n  ✓ Found ChIJ with query: {q!r}")
            break
        else:
            print(f"  ✗ No ChIJ found for this query, trying next...")

    print(f"\n  RESULT → chosen ChIJ place_id: {chosen_pid!r}")
    if not chosen_pid:
        print("  ✗ NO ChIJ place_id found from any query variant")
    else:
        print("  ✓ Proceeding to Step 2")

    return chosen_pid, last_data


# ─── Step 2: fetch reviews with google_maps_reviews ──────────────────────

async def test_step2_fetch_reviews(place_id: str, country: str = "Canada"):
    print(f"\n{SEP}")
    print("STEP 2: Fetch reviews via google_maps_reviews engine")
    print(f"  place_id : {place_id!r}")

    params = {
        "api_key": SERPAPI_KEY,
        "engine": "google_maps_reviews",
        "place_id": place_id,
        "hl": "en",
        "sort_by": "newestFirst",
        "gl": "ca",
    }

    async with httpx.AsyncClient() as client:
        resp = await client.get("https://serpapi.com/search", params=params, timeout=30.0)
        resp.raise_for_status()
        data = resp.json()

    print(f"  SerpApi top-level keys: {list(data.keys())}")

    reviews = data.get("reviews", [])
    print(f"  reviews count: {len(reviews)}")

    if reviews:
        print("\n  First 3 reviews:")
        for r in reviews[:3]:
            print(f"    ★{r.get('rating')}  {r.get('date')!r:20s}  {str(r.get('snippet',''))[:80]!r}")
        print("\n  ✓ Reviews fetched successfully")
    else:
        print("  ✗ No reviews returned")
        # Check for error fields
        if data.get("error"):
            print(f"  SerpApi error: {data['error']!r}")

    return reviews


# ─── Main ─────────────────────────────────────────────────────────────────

async def main():
    print("=" * 60)
    print("LeapOne — Reputation Pipeline Diagnostic")
    print("=" * 60)

    name     = input("\nBusiness name  (e.g. 'James Snow Physiotherapy & Rehabilitation Centre in Milton'): ").strip()
    city     = input("City           (e.g. 'Milton'): ").strip()
    province = input("Province       (e.g. 'ON' or 'Ontario', leave blank if unsure): ").strip()
    postal   = input("Postal code    (e.g. 'L9T 0A1', leave blank if unsure): ").strip()

    # Step 1: resolve place_id — tries postal, then city+province, then city, then name-only
    place_id, raw_data = await test_step1_resolve_place_id(name, city, province, postal)

    # Step 2: fetch reviews if we have a place_id
    if place_id:
        await test_step2_fetch_reviews(place_id)
    else:
        print(f"\n{SEP}")
        print("CANNOT PROCEED — no ChIJ place_id resolved from any query variant.")
        print("This is the root cause: SerpApi only returns numeric CID for this business.")

    print(f"\n{SEP}")
    print("DONE")


if __name__ == "__main__":
    asyncio.run(main())

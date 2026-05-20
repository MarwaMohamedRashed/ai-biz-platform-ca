"""Per-query Perplexity runner with audit-side extraction.

One async function, `_perplexity_one`, that:

  * Issues a single Perplexity chat completion via integrations.perplexity
  * Extracts the answer text and citations from the response
  * Computes whether the audited business name appears in the answer
    (the "mentioned" boolean used by the AI Citations pillar)
  * Returns a normalized dict every caller in the audit / reputation
    layers can consume.

This is the shared seam between two callers with slightly different needs:

  - `run_perplexity_multi` (audit pillar measurement) — uses `mentioned`,
    `snippet`, `answer`, `query`.
  - reputation/fetcher.py (`_fetch_own_perplexity_reputation`,
    `_fetch_competitor_perplexity`) — uses `answer` (full text) and
    `citations` for source-mapping. Ignores `mentioned`.

Originally lived in api/aeo/router.py lines 171-181. Moved here during
Tier 4 of the refactor so reputation/fetcher.py can import without
needing a circular dep into router.py. Re-exported from router.py under
the same name so existing audit-side callers keep working.
"""
from integrations import perplexity as perplexity_client

from .geo import extract_search_name


async def _perplexity_one(business_name: str, query: str, city: str) -> dict:
    """Run one Perplexity query and return audit-shaped fields.

    Keys returned:
      mentioned  — bool, whether the business name appears in the answer
      snippet    — first 500 chars of the answer when mentioned, else None
      answer     — first 2000 chars of the full answer text
      query      — echoed back for downstream aggregation
      citations  — list[str] of source URLs Perplexity returned
    """
    data = await perplexity_client.chat(query)

    answer = data["choices"][0]["message"]["content"]
    # Perplexity returns a citations list alongside the answer — capture it so callers
    # can resolve [1][2][3] references to actual platform names (Yellow Pages, Yelp, etc.)
    citations: list[str] = data.get("citations") or []
    mentioned = extract_search_name(business_name, city).lower() in answer.lower()
    snippet = answer[:500] if mentioned else None
    print(f"[AEO] Perplexity '{query}' → mentioned={mentioned}")
    return {"mentioned": mentioned, "snippet": snippet, "answer": answer[:2000], "query": query, "citations": citations}

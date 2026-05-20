"""Thin clients for external paid APIs we depend on.

Each module here is a single-purpose wrapper:

- serpapi.py     SerpApi Google search (KG, local pack, organic, maps, reviews)
- perplexity.py  Perplexity citations API
- dataforseo.py  DataForSEO Keywords Data + SERP family (Phase 1, market intel)

The pattern: one async function per endpoint, no business logic. Anything
LLM-heavy or aggregation-flavoured stays in the audit/content/reputation
packages — this layer only handles HTTP + auth + retries.

Originally these calls were scattered throughout api/aeo/router.py.
Extracting them into a separate package was made cheaper by the Phase 0
DataForSEO work (see docs/market-intelligence-architecture.md) since the
new client naturally lives here. Existing SerpApi / Perplexity extraction
happens incrementally as the AEO refactor progresses.
"""

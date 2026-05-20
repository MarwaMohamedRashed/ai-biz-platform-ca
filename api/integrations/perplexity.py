"""Perplexity chat completions wrapper.

Single endpoint: POST /chat/completions. Returns the raw JSON response so
callers can decide what to extract (answer text, citations, etc.) — see
`_perplexity_one` in api/aeo/router.py for the usual extraction pattern.

Pulled out of api/aeo/router.py during Tier 3 of the AEO refactor. The key
behaviours kept identical to the inline version it replaced:

  * Uses `Bearer {PERPLEXITY_API_KEY}` header from env
  * Default `sonar` model (cheapest tier with citations support)
  * Per-request httpx.AsyncClient (no shared session — keeps timeouts
    bounded per call and avoids dangling connections during long audits)
  * `response.raise_for_status()` — caller handles HTTPStatusError and
    other exceptions. Don't swallow inside the wrapper.

If PERPLEXITY_API_KEY is unset, raises RuntimeError. Reputation fetchers
guard the key separately to degrade gracefully (returning empty insights),
so this exception path is only hit by misconfigured environments.
"""
import os

import httpx


PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")


async def chat(
    query: str,
    *,
    model: str = "sonar",
    timeout: float = 30.0,
) -> dict:
    """Run a single-turn user query against Perplexity chat completions.

    Returns the raw JSON response. Notable fields:
      data["choices"][0]["message"]["content"]  -> answer text
      data.get("citations")                     -> list[str] of source URLs

    Caller is responsible for extracting mention flags, snippets, and
    resolving citations to platform names — that logic lives in the audit
    and reputation layers."""
    if not PERPLEXITY_API_KEY:
        raise RuntimeError("PERPLEXITY_API_KEY not set")
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.perplexity.ai/chat/completions",
            headers={
                "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [{"role": "user", "content": query}],
            },
            timeout=timeout,
        )
        response.raise_for_status()
        return response.json()

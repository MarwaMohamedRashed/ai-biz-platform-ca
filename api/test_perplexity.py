"""
End-to-end test for the Perplexity → LLM reputation pipeline.
Mirrors exactly what the /own-reputation endpoint does:
  1. Call Perplexity and build the citation map
  2. Feed the enriched text + any Google reviews to gpt-4o-mini
  3. Print the final JSON the card would display

Run from the api/ directory:
    python test_perplexity.py
"""
import asyncio
import json
import os
import re
import sys
import httpx
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"), override=True)

# Use the same AIEngine the router uses so provider/model/keys match exactly
sys.path.insert(0, os.path.dirname(__file__))
from core.ai_engine import AIEngine

PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")

# Content LLM — mirrors the router's content_llm instantiation
content_llm = AIEngine(
    provider=os.getenv("CONTENT_PROVIDER"),
    model=os.getenv("CONTENT_MODEL"),
)

# ── Edit these to match the business you're testing ──────────────────────────
BUSINESS_NAME = "Burlington Family Dentists"
CITY = "Burlington"
PROVINCE = "ON"   # 2-letter codes are auto-expanded to "Ontario, Canada" by the router
# Paste a few real Google review snippets here to test the combined analysis.
# Leave empty to test with Perplexity-only (no Google reviews).
SAMPLE_REVIEWS: list[dict] = [
    # {"rating": 5, "snippet": "Excellent staff, very professional and caring."},
    # {"rating": 2, "snippet": "Had trouble reaching the clinic, voicemail always full."},
]
# ─────────────────────────────────────────────────────────────────────────────

DOMAIN_FRIENDLY = {
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
}


def build_citation_map(citations: list[str]) -> str:
    """Mirrors the router: build a 'Citation sources:' header placed at the start."""
    if not citations:
        return ""
    lines = []
    for i, url in enumerate(citations, 1):
        domain = re.sub(r"^https?://", "", url).split("/")[0].lstrip("www.")
        friendly = next((name for d, name in DOMAIN_FRIENDLY.items() if d in domain), domain)
        lines.append(f"[{i}] {friendly}")
    return "Citation sources:\n" + "\n".join(lines) + "\n\n"


async def fetch_perplexity(query: str) -> tuple[str, list[str]]:
    """Returns (answer_text, citations_list)."""
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
    citations = data.get("citations") or []
    return answer, citations


async def analyze_reputation(perplexity_text: str, reviews: list[dict]) -> dict:
    """Mirrors _analyze_own_reputation exactly — same prompt, same model."""
    review_text = "\n".join(
        f"- ({r['rating']}★) {r['snippet']}" for r in reviews[:60] if r.get("snippet")
    )
    has_perplexity = bool(perplexity_text.strip())
    review_section = f"\nGoogle Reviews:\n{review_text}" if review_text else ""
    perplexity_section = (
        f"\n\nMulti-source web signals (Yelp, Yellow Pages, BBB, and other directories):\n{perplexity_text[:2500]}"
        if has_perplexity else ""
    )
    source_note = (
        'For signals from Google Reviews use "source": "Google". '
        'For signals from the multi-source section, use the ACTUAL platform name mentioned in that text '
        '(e.g. "Yellow Pages", "Yelp", "BBB", "RateMDs", "HomeStars") — not just "Web". '
        'If the platform is unclear, use "Web".'
    ) if has_perplexity else 'Use "source": "Google" for all items.'

    prompt = f"""You are analyzing customer feedback for {BUSINESS_NAME}.
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

Return 2-5 strengths and 0-3 weaknesses. For strengths, only include patterns with 2+ mentions. For weaknesses, include any specific complaint that appears even once. Do not fabricate weaknesses if none appear in the data."""

    raw = await content_llm.generate(prompt=prompt, max_tokens=900, temperature=0.2)
    cleaned = re.sub(r'^```(?:json)?\s*|\s*```$', '', raw.strip(), flags=re.MULTILINE).strip()
    return json.loads(cleaned)


async def main():
    print(f"Business : {BUSINESS_NAME}")
    print(f"City     : {CITY}, {PROVINCE}")
    print(f"Reviews  : {len(SAMPLE_REVIEWS)} provided")
    print("=" * 70)

    # ── Step 1: Perplexity ────────────────────────────────────────────────
    print("\n[1/3] Calling Perplexity...")
    location = f"{CITY}, {PROVINCE}"
    query = (
        f"What do customers say about {BUSINESS_NAME} in {location}? "
        f"Search across Google, Yelp, BBB, RateMDs, TrustedPros, HomeStars, and any local directories. "
        f"What are they consistently praised for? What complaints or problems appear repeatedly? "
        f"Be specific and cite your sources."
    )
    answer, citations = await fetch_perplexity(query)
    print(f"    Answer: {len(answer)} chars, {len(citations)} citations")
    for i, url in enumerate(citations, 1):
        domain = re.sub(r"^https?://", "", url).split("/")[0].lstrip("www.")
        print(f"    [{i}] {domain}")

    # ── Step 2: Build enriched text (same as router) ──────────────────────
    print("\n[2/3] Building enriched Perplexity text...")
    citation_header = build_citation_map(citations)
    enriched = citation_header + answer
    print(f"    Enriched text starts with:\n    {enriched[:300]!r}")

    # ── Step 3: LLM analysis ──────────────────────────────────────────────
    print("\n[3/3] Calling gpt-4o-mini for analysis...")
    result = await analyze_reputation(enriched, SAMPLE_REVIEWS)

    print("\n" + "=" * 70)
    print("FINAL RESULT (what the reputation card would show):\n")
    print(json.dumps(result, indent=2, ensure_ascii=False))

    print("\n── Source breakdown ──")
    all_items = result.get("strengths", []) + result.get("weaknesses", [])
    from collections import Counter
    sources = Counter(item.get("source", "?") for item in all_items)
    for src, count in sources.most_common():
        print(f"  {src}: {count} item(s)")


if __name__ == "__main__":
    asyncio.run(main())


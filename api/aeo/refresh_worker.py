"""Phase 2 — Market Intelligence Refresh Worker.

Discovers top questions for a (vertical, city, country) market, runs them
through ChatGPT / Perplexity / Google AI, extracts structured mention data,
and persists results to market_intelligence + market_intelligence_history.

Public surface:

    run_refresh(market_id, vertical, city, province, country, target_month)
        Main entry point. Idempotent: re-running a month that already
        succeeded is a no-op (no AI calls burned). Snapshot-before-overwrite
        ensures history always has the state prior to the new data.

Phase 0 caveats baked in:
    - PAA is not always returned (healthcare + mid-cities). Falls back to
      related_searches, then skips gracefully.
    - Null search_volume means "below threshold" — excluded from volume
      weighting but counted in question coverage.
    - Cap at _MAX_QUESTIONS (30). Benchmarks hidden when sample_size < 5.
    - AI engine calls are retried once; per-question failures are logged
      and skipped rather than aborting the entire job.
"""
import asyncio
import json
import logging
import os
from datetime import date, datetime, timezone
from typing import Optional

from core.ai_engine import AIEngine
from core.database import supabase_admin
from integrations import dataforseo
from integrations import perplexity as perplexity_client
from integrations import serpapi as serpapi_client

from .audit.geo import country_to_gl
from .audit.maps import resolve_maps_place_id
from .audit.scoring import name_matches
from .market_intelligence import mention_weight


logger = logging.getLogger(__name__)

# ── LLM instances ─────────────────────────────────────────────────────────────
# ChatGPT pillar: must stay openai/gpt-4o-mini so "ChatGPT" means ChatGPT.
_audit_llm = AIEngine(
    provider=os.getenv("AUDIT_PROVIDER", "openai"),
    model=os.getenv("AUDIT_MODEL", "gpt-4o-mini"),
)
# Mention extraction (structured JSON): one call per AI-engine response.
_extraction_llm = AIEngine(
    provider=os.getenv("CONTENT_PROVIDER"),
    model=os.getenv("CONTENT_MODEL"),
)

# ── Constants ─────────────────────────────────────────────────────────────────
_MAX_QUESTIONS = 30
_PAA_TOP_N = 5          # how many top questions to expand via PAA
_SEMAPHORE_LIMIT = 5    # concurrent AI calls during mention extraction
_MIN_BENCHMARKS_SAMPLE = 5   # hide benchmarks when fewer unique businesses

_COMMERCIAL_SIGNALS = frozenset([
    "near me", "best", "top", "recommend", "cost", "price", "affordable",
    "cheap", "reviews", "trusted", "local", "book", "appointment", "hours",
    "open", "walk-in", "same day", "emergency",
])
_INFO_SIGNALS = frozenset([
    "how to", "what is", "what are", "why", "when", "which is", "difference",
    "vs", " vs ", "explained", "meaning of",
])

_EXTRACT_SYSTEM = (
    "You are a structured-data extractor. Extract all businesses mentioned in "
    "the following AI assistant response. For each business return a JSON object "
    "with keys: name (string), position (int, order first mentioned, 1-based), "
    "strength (string: 'strong' = explicitly recommended, 'moderate' = mentioned "
    "positively, 'weak' = listed or mentioned neutrally), sentiment (float 0.0-1.0, "
    "0.5 = neutral). Return ONLY a valid JSON array. If no businesses are mentioned "
    "return []."
)


# ── Intent scoring ────────────────────────────────────────────────────────────

def _score_intent(keyword: str) -> float:
    kw = keyword.lower()
    if any(sig in kw for sig in _COMMERCIAL_SIGNALS):
        return 1.0
    if any(sig in kw for sig in _INFO_SIGNALS):
        return 0.4
    return 0.6


# ── Question discovery ────────────────────────────────────────────────────────

async def _discover_questions(
    vertical: str,
    city: str,
    province: str,
    country: str = "Canada",
) -> list[dict]:
    """Run DataForSEO keyword discovery and return top-N question entries.

    Returns a list of dicts with question/search_volume/intent/competition/
    cpc/monthly_searches ready to be stored in market_intelligence.questions.
    Each entry has an empty `mentions` dict — filled by _process_question later.
    """
    seeds = dataforseo.BASELINE_SEEDS.get(vertical) or []
    if not seeds:
        logger.warning(f"[REFRESH] No baseline seeds for vertical='{vertical}' — skipping discovery")
        return []

    location_code = await dataforseo.resolve_location_code(city, province, country)
    if not location_code:
        logger.warning(f"[REFRESH] No location_code for '{city}, {province}' — cannot discover keywords")
        return []

    try:
        raw = await dataforseo.keywords_for_keywords(seeds, location_code, limit=300)
    except Exception as e:
        logger.error(f"[REFRESH] DataForSEO keywords_for_keywords failed for ({vertical}, {city}): {e}")
        return []

    keywords = dataforseo.get_keywords(raw)

    # Separate has-volume from null-volume; both included but volume-weighted ranking
    with_volume = [k for k in keywords if k.get("search_volume") is not None]
    null_volume  = [k for k in keywords if k.get("search_volume") is None]

    # Rank by volume × intent. Null-volume keywords appended at the end.
    def _rank_key(k: dict) -> float:
        return (k.get("search_volume") or 0) * _score_intent(k.get("keyword", ""))

    ranked = sorted(with_volume, key=_rank_key, reverse=True)
    ranked += null_volume[:max(0, _MAX_QUESTIONS - len(ranked))]
    top = ranked[:_MAX_QUESTIONS]

    now_str = datetime.now(timezone.utc).isoformat()
    entries = []
    for k in top:
        kw = k.get("keyword", "")
        intent = "commercial" if _score_intent(kw) >= 0.9 else (
            "informational" if _score_intent(kw) <= 0.4 else "mixed"
        )
        entries.append({
            "question":        kw,
            "intent":          intent,
            "search_volume":   k.get("search_volume"),   # may be None
            "competition":     k.get("competition"),
            "cpc":             k.get("cpc"),
            "monthly_searches": k.get("monthly_searches") or [],
            "last_seen":       now_str,
            "mentions":        {"chatgpt": [], "perplexity": [], "google_ai": []},
        })

    logger.info(f"[REFRESH] ({vertical}, {city}) discovered {len(entries)} questions "
                f"({len(with_volume)} with volume, {len(null_volume)} null-volume)")
    return entries


# ── PAA expansion ─────────────────────────────────────────────────────────────

async def _expand_paa(
    questions: list[dict],
    city: str,
    country: str = "Canada",
) -> list[str]:
    """Pull People Also Ask + related_searches for the top-N questions.

    Returns additional question strings (not yet scored/ranked) to merge
    into the question list. Gracefully handles missing PAA blocks.
    """
    extra: list[str] = []
    top = questions[:_PAA_TOP_N]
    for entry in top:
        kw = entry["question"]
        try:
            raw = await dataforseo.serp_advanced(kw, location_name=f"{city}, {country}")
            items = dataforseo.get_items(raw)
            added_from_paa = False
            for item in items:
                if item.get("type") == "people_also_ask":
                    for paa in item.get("items") or []:
                        q = paa.get("title") or paa.get("question")
                        if q:
                            extra.append(q)
                    added_from_paa = True
                    break
            if not added_from_paa:
                # Fall back to related_searches
                for item in items:
                    if item.get("type") == "related_searches":
                        for rs in item.get("items") or []:
                            q = rs.get("query")
                            if q:
                                extra.append(q)
                        break
        except Exception as e:
            logger.warning(f"[REFRESH] PAA expansion failed for '{kw}': {e}")
    logger.info(f"[REFRESH] PAA expansion added {len(extra)} candidate questions")
    return extra


def _merge_paa(discovered: list[dict], paa_extras: list[str]) -> list[dict]:
    """Append PAA questions not already in the discovered set.

    PAA questions don't have volume data (null); they're appended after the
    volume-ranked list so they don't displace high-signal keywords. Capped
    at _MAX_QUESTIONS total.
    """
    existing = {e["question"].lower() for e in discovered}
    now_str = datetime.now(timezone.utc).isoformat()
    result = list(discovered)
    for q in paa_extras:
        if len(result) >= _MAX_QUESTIONS:
            break
        if q.lower() not in existing:
            result.append({
                "question":        q,
                "intent":          "commercial" if _score_intent(q) >= 0.9 else "mixed",
                "search_volume":   None,
                "competition":     None,
                "cpc":             None,
                "monthly_searches": [],
                "last_seen":       now_str,
                "mentions":        {"chatgpt": [], "perplexity": [], "google_ai": []},
            })
            existing.add(q.lower())
    return result


# ── Mention extraction ────────────────────────────────────────────────────────

async def _extract_mentions_from_text(response_text: str) -> list[dict]:
    """LLM-structured extraction of business mentions from an AI response text.

    Returns a list of {name, position, strength, sentiment} dicts.
    Returns [] on LLM failure or JSON parse error.
    """
    if not response_text or not response_text.strip():
        return []
    try:
        raw = await _extraction_llm.generate(
            prompt=response_text[:3000],
            system_prompt=_EXTRACT_SYSTEM,
            max_tokens=800,
            temperature=0.0,
        )
        cleaned = raw.strip()
        # Strip markdown code fences if the LLM wrapped it
        if cleaned.startswith("```"):
            cleaned = cleaned.split("```")[1]
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]
        parsed = json.loads(cleaned)
        if not isinstance(parsed, list):
            return []
        validated = []
        for item in parsed:
            if not isinstance(item, dict) or not item.get("name"):
                continue
            validated.append({
                "name":     str(item["name"])[:200],
                "position": int(item.get("position") or 1),
                "strength": item.get("strength", "weak") if item.get("strength") in ("strong", "moderate", "weak") else "weak",
                "sentiment": float(max(0.0, min(1.0, item.get("sentiment") or 0.5))),
                "place_id": None,  # resolved later in aggregation
            })
        return validated
    except Exception as e:
        logger.warning(f"[REFRESH] Mention extraction LLM failed: {e}")
        return []


async def _query_chatgpt(question: str) -> str:
    """Single ChatGPT call for a market question. Returns raw answer text."""
    try:
        return await _audit_llm.generate(
            prompt=question,
            system_prompt=(
                "You are a local business search assistant. "
                "A user is asking you to recommend businesses in their area. "
                "Answer based on your training knowledge, listing specific business names where you know them."
            ),
            max_tokens=500,
            temperature=0.0,
        )
    except Exception as e:
        logger.warning(f"[REFRESH] ChatGPT call failed for '{question}': {e}")
        return ""


async def _query_perplexity(question: str) -> str:
    """Single Perplexity call for a market question. Returns raw answer text."""
    try:
        data = await perplexity_client.chat(question)
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        logger.warning(f"[REFRESH] Perplexity call failed for '{question}': {e}")
        return ""


async def _query_google_ai(question: str, city: str, country: Optional[str] = None) -> str:
    """Single SerpApi google call for a market question. Returns AI Overview text."""
    params: dict = {
        "engine": "google",
        "q": question,
        "location": city,
        "hl": "en",
    }
    gl = country_to_gl(country)
    if gl:
        params["gl"] = gl
    try:
        data = await serpapi_client.search(params, timeout=30.0)
        ai_overview = data.get("ai_overview") or {}
        text_blocks = ai_overview.get("text_blocks") or []
        return " ".join(b.get("snippet", "") for b in text_blocks if b.get("snippet"))
    except Exception as e:
        logger.warning(f"[REFRESH] Google AI call failed for '{question}': {e}")
        return ""


async def _process_question(
    entry: dict,
    city: str,
    country: str,
    sem: asyncio.Semaphore,
) -> dict:
    """Run one question through all 3 AI engines and extract mentions.

    Returns the entry dict with `mentions` populated. Errors per-engine
    are logged and that engine's mentions become [].
    """
    question = entry["question"]
    async with sem:
        chatgpt_text, perplexity_text, google_text = await asyncio.gather(
            _query_chatgpt(question),
            _query_perplexity(question),
            _query_google_ai(question, city, country),
        )

    chatgpt_mentions, perplexity_mentions, google_mentions = await asyncio.gather(
        _extract_mentions_from_text(chatgpt_text),
        _extract_mentions_from_text(perplexity_text),
        _extract_mentions_from_text(google_text),
    )

    result = dict(entry)
    result["mentions"] = {
        "chatgpt":    chatgpt_mentions,
        "perplexity": perplexity_mentions,
        "google_ai":  google_mentions,
    }
    logger.debug(
        f"[REFRESH] '{question}' → "
        f"chatgpt={len(chatgpt_mentions)} perplexity={len(perplexity_mentions)} "
        f"google={len(google_mentions)} mentions"
    )
    return result


# ── Aggregation ───────────────────────────────────────────────────────────────

async def _aggregate_top_businesses(
    questions: list[dict],
    city: str,
    country: str,
) -> list[dict]:
    """Aggregate per-question mention data into a ranked top-businesses list.

    Resolves place_ids for unique business names (one SerpApi google_maps
    call per unique name). Businesses that can't be resolved are marked
    `verified: false` and still appear in the list (helps owners spot
    mis-spellings).

    Returns sorted descending by weighted_score.
    """
    # Accumulate across questions and engines
    accum: dict[str, dict] = {}  # key: lower-cased name

    for q_entry in questions:
        sv = q_entry.get("search_volume") or 0
        for engine, mentions in (q_entry.get("mentions") or {}).items():
            for mention in (mentions or []):
                name = (mention.get("name") or "").strip()
                if not name:
                    continue
                key = name.lower()
                w = mention_weight(
                    mention.get("position", 1),
                    mention.get("strength", "weak"),
                    mention.get("sentiment") or 0.5,
                )
                if key not in accum:
                    accum[key] = {
                        "name":          name,
                        "place_id":      None,
                        "verified":      False,
                        "mention_count": 0,
                        "weighted_score": 0.0,
                        "positions":     [],
                        "sentiments":    [],
                    }
                accum[key]["mention_count"]  += 1
                accum[key]["weighted_score"] += w * max(sv, 1)  # volume-weight the score
                accum[key]["positions"].append(mention.get("position", 1))
                accum[key]["sentiments"].append(mention.get("sentiment") or 0.5)

    if not accum:
        return []

    # Resolve place_ids in parallel (once per unique business name)
    resolve_tasks = {
        key: resolve_maps_place_id(data["name"], city, country)
        for key, data in accum.items()
    }
    resolved = await asyncio.gather(*resolve_tasks.values(), return_exceptions=True)
    for (key, _), place_id in zip(resolve_tasks.items(), resolved):
        if isinstance(place_id, str):
            accum[key]["place_id"] = place_id
            accum[key]["verified"] = True

    results = []
    for data in accum.values():
        positions = data["positions"]
        sentiments = data["sentiments"]
        results.append({
            "name":          data["name"],
            "place_id":      data["place_id"],
            "verified":      data["verified"],
            "mention_count": data["mention_count"],
            "weighted_score": round(data["weighted_score"], 4),
            "avg_position":  round(sum(positions) / len(positions), 2) if positions else None,
            "sentiment_avg": round(sum(sentiments) / len(sentiments), 3) if sentiments else None,
        })

    results.sort(key=lambda x: x["weighted_score"], reverse=True)
    return results[:50]  # cap at 50 in the aggregated list


def _compute_benchmarks(
    questions: list[dict],
    top_businesses: list[dict],
) -> dict:
    """Compute vertical benchmarks and category-volume summary."""
    now_str = datetime.now(timezone.utc).isoformat()

    # Vertical benchmarks: distribution of weighted_score across businesses
    scores = [b["weighted_score"] for b in top_businesses if b.get("weighted_score")]
    sample_size = len(scores)
    if sample_size >= _MIN_BENCHMARKS_SAMPLE:
        sorted_scores = sorted(scores)
        avg = sum(sorted_scores) / sample_size
        p75_idx = int(sample_size * 0.75)
        avg_mention_share  = round(avg, 4)
        p75_mention_share  = round(sorted_scores[min(p75_idx, sample_size - 1)], 4)
        top_mention_share  = round(sorted_scores[-1], 4)
    else:
        avg_mention_share = p75_mention_share = top_mention_share = None

    # Category-volume summary: aggregated from the question list
    questions_with_volume = [q for q in questions if q.get("search_volume") is not None]
    total_volume = sum(q["search_volume"] for q in questions_with_volume)
    top_5 = sorted(
        [{"keyword": q["question"], "search_volume": q["search_volume"]} for q in questions_with_volume],
        key=lambda x: x["search_volume"],
        reverse=True,
    )[:5]

    # Rising keywords: compare last 2 monthly_searches entries (DataForSEO provides history)
    rising = []
    for q in questions_with_volume:
        history = q.get("monthly_searches") or []
        if len(history) >= 2:
            sorted_history = sorted(history, key=lambda m: (m.get("year", 0), m.get("month", 0)))
            prev_vol = sorted_history[-2].get("search_volumes") or 0
            curr_vol = sorted_history[-1].get("search_volumes") or 0
            if prev_vol and curr_vol > prev_vol:
                change_pct = round((curr_vol - prev_vol) / prev_vol, 3)
                rising.append({"keyword": q["question"], "change_pct": change_pct})
    rising.sort(key=lambda x: x["change_pct"], reverse=True)

    category_volume_summary = {
        "total_volume": total_volume,
        "top_5_keywords": top_5,
        "n_with_volume": len(questions_with_volume),
        "rising_keywords": rising[:10],
    }

    return {
        "avg_mention_share":  avg_mention_share,
        "p75_mention_share":  p75_mention_share,
        "top_mention_share":  top_mention_share,
        "sample_size":        sample_size,
        "computed_at":        now_str,
        "category_volume_summary": category_volume_summary,
    }


# ── History snapshot ──────────────────────────────────────────────────────────

def _snapshot_to_history(
    market_id: str,
    snapshot_month: str,
    questions: list,
    top_businesses: list,
    benchmarks: dict,
) -> None:
    """Write a market_intelligence snapshot to history. ON CONFLICT DO NOTHING
    so re-runs are idempotent — the first successful snapshot wins."""
    try:
        supabase_admin.table("market_intelligence_history").insert(
            {
                "market_id":      market_id,
                "snapshot_month": snapshot_month,
                "questions":      questions,
                "top_businesses": top_businesses,
                "benchmarks":     benchmarks,
            },
            # upsert=False means INSERT; unique constraint (market_id, snapshot_month)
            # causes silent no-op on duplicate, matching Supabase behavior when
            # the default ignore_duplicates=False raises an error. We handle via try/except.
        ).execute()
        logger.info(f"[REFRESH] Snapshot written: market_id={market_id} month={snapshot_month}")
    except Exception as e:
        # Unique constraint violation = already snapshotted this month. OK.
        if "unique" in str(e).lower() or "duplicate" in str(e).lower() or "23505" in str(e):
            logger.info(f"[REFRESH] Snapshot already exists for market_id={market_id} month={snapshot_month}")
        else:
            logger.error(f"[REFRESH] Snapshot write failed for market_id={market_id}: {e}")
            raise


# ── Main entry ────────────────────────────────────────────────────────────────

async def run_refresh(
    market_id: str,
    vertical: str,
    city: str,
    province: str,
    country: str = "Canada",
    target_month: Optional[str] = None,
) -> dict:
    """Idempotent monthly refresh for one (vertical, city) market.

    target_month: ISO date string for the first of the month, e.g. '2026-05-01'.
    Defaults to the current month.

    Returns a dict with status, market_id, and summary stats.
    Raises on unrecoverable errors (caller marks the job as failed).
    """
    if target_month is None:
        today = date.today()
        target_month = today.replace(day=1).isoformat()

    # 1. Idempotency: skip if already refreshed this month
    try:
        market_row_resp = (
            supabase_admin.table("market_intelligence")
            .select("id,refresh_status,refreshed_at,questions,top_businesses,benchmarks")
            .eq("id", market_id)
            .limit(1)
            .execute()
        )
        if not market_row_resp.data:
            logger.error(f"[REFRESH] market_id={market_id} not found")
            return {"status": "not_found", "market_id": market_id}

        market_row = market_row_resp.data[0]
        refreshed_at_str = market_row.get("refreshed_at")
        if market_row.get("refresh_status") == "fresh" and refreshed_at_str:
            refreshed_at = datetime.fromisoformat(refreshed_at_str.replace("Z", "+00:00"))
            target_dt = datetime.fromisoformat(target_month).replace(tzinfo=timezone.utc)
            if (refreshed_at.year == target_dt.year and refreshed_at.month == target_dt.month):
                logger.info(f"[REFRESH] Already fresh for {market_id} / {target_month} — skipping")
                return {"status": "already_done", "market_id": market_id}
    except Exception as e:
        logger.error(f"[REFRESH] Pre-check failed for {market_id}: {e}")
        return {"status": "error", "market_id": market_id, "error": str(e)}

    # 2. Acquire refresh lock (prevents concurrent runs for the same market)
    try:
        lock_resp = (
            supabase_admin.table("market_intelligence")
            .update({"refresh_status": "refreshing"})
            .eq("id", market_id)
            .neq("refresh_status", "refreshing")
            .execute()
        )
        if not lock_resp.data:
            logger.warning(f"[REFRESH] Lock contention for market_id={market_id} — another worker running")
            return {"status": "locked", "market_id": market_id}
    except Exception as e:
        logger.error(f"[REFRESH] Lock acquisition failed for {market_id}: {e}")
        return {"status": "error", "market_id": market_id, "error": str(e)}

    try:
        # 3. Question discovery
        questions = await _discover_questions(vertical, city, province, country)
        if not questions:
            logger.warning(f"[REFRESH] No questions discovered for ({vertical}, {city}) — aborting")
            supabase_admin.table("market_intelligence").update(
                {"refresh_status": "failed", "refresh_error": "No questions discovered"}
            ).eq("id", market_id).execute()
            return {"status": "no_questions", "market_id": market_id}

        # 4. PAA expansion
        paa_extras = await _expand_paa(questions, city, country)
        questions = _merge_paa(questions, paa_extras)

        # 5. Mention extraction (concurrency-limited)
        sem = asyncio.Semaphore(_SEMAPHORE_LIMIT)
        questions = await asyncio.gather(
            *[_process_question(q, city, country, sem) for q in questions]
        )
        questions = list(questions)

        # 6. Aggregate
        top_businesses = await _aggregate_top_businesses(questions, city, country)
        benchmarks = _compute_benchmarks(questions, top_businesses)

        # 7. Snapshot BEFORE overwrite (idempotent — ON CONFLICT is no-op)
        _snapshot_to_history(
            market_id,
            target_month,
            market_row.get("questions") or [],
            market_row.get("top_businesses") or [],
            market_row.get("benchmarks") or {},
        )

        # 8. Write new data to market_intelligence
        supabase_admin.table("market_intelligence").update({
            "questions":      questions,
            "top_businesses": top_businesses,
            "benchmarks":     benchmarks,
            "refresh_status": "fresh",
            "refreshed_at":   datetime.now(timezone.utc).isoformat(),
            "refresh_error":  None,
        }).eq("id", market_id).execute()

        n_with_vol = sum(1 for q in questions if q.get("search_volume"))
        logger.info(
            f"[REFRESH] Done: market_id={market_id} ({vertical}, {city}) "
            f"questions={len(questions)} ({n_with_vol} with volume) "
            f"businesses={len(top_businesses)}"
        )
        return {
            "status":         "ok",
            "market_id":      market_id,
            "questions_total": len(questions),
            "questions_with_volume": n_with_vol,
            "top_businesses": len(top_businesses),
            "snapshot_month": target_month,
        }

    except Exception as e:
        logger.error(f"[REFRESH] Refresh failed for {market_id} ({vertical}, {city}): {e}", exc_info=True)
        try:
            supabase_admin.table("market_intelligence").update({
                "refresh_status": "failed",
                "refresh_error":  str(e)[:500],
            }).eq("id", market_id).execute()
        except Exception:
            pass
        raise

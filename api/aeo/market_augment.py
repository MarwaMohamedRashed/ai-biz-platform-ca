"""Phase 3 — Per-business market augmentation + market_visibility computation.

Two concerns:

1. Market setup at audit time (fire-and-forget):
   `setup_market_background(vertical, city, province, country)` — ensures the
   market_intelligence row exists for this (vertical, city, country) and triggers
   a background refresh if the row is stale. Does NOT block the audit.

2. Per-business keyword augmentation:
   `get_augmented_questions(service_tags, cuisine_hint, cuisine_hint_parent,
   dietary_tags, vertical, city, province, country)` — one DataForSEO call with
   seeds derived from the business's detected_signals, returning a volume list
   that Phase 4 (ROI v2 Formula A) uses for the denominator. $0.075 per audit.
   Cap: 15 seeds (Phase 0 finding: beyond 15, returns are duplicative).

3. Market visibility snapshot:
   `compute_market_visibility(business_name, city, market_row)` — reads cached
   market_intelligence.questions to find where this business is mentioned, then
   computes mention share, coverage, and vertical benchmarks. Pure Python — no
   API calls, uses data already in the cache. Returns the `market_visibility`
   block written to audits.raw_results.

Competitor scope gate: when competitor_scope != 'local', all three functions
return immediately without any market_intelligence interaction. The scope gate
lives in the caller (engine.py) so it's applied once.
"""
import asyncio
import logging
from datetime import date, timezone, datetime
from typing import Optional

from integrations import dataforseo

from .audit.scoring import name_matches
from .market_intelligence import (
    canonical_vertical,
    get_or_create,
    mention_weight,
    normalize_city,
)


logger = logging.getLogger(__name__)

_MAX_AUGMENT_SEEDS = 15


# ── Seed construction ─────────────────────────────────────────────────────────

def build_augmentation_seeds(
    service_tags: list[str],
    cuisine_hint: Optional[str],
    cuisine_hint_parent: Optional[str],
    dietary_tags: list[str],
    vertical: str,
) -> list[str]:
    """Convert business-detected signals into DataForSEO seed terms.

    service_tags use snake_case (from signals.py). Cuisine and dietary tags
    get human-readable suffixes so Google Ads returns relevant commercial terms.
    Capped at _MAX_AUGMENT_SEEDS; deduplicates case-insensitively.
    """
    seen: set[str] = set()
    seeds: list[str] = []

    def _add(s: str) -> None:
        s = s.strip().lower()
        if s and s not in seen:
            seen.add(s)
            seeds.append(s)

    # Service tags: "massage_therapy" → "massage therapy"
    for tag in (service_tags or []):
        _add(tag.replace("_", " "))

    # Cuisine: more specific first, then parent
    if cuisine_hint:
        _add(f"{cuisine_hint} restaurant")
    if cuisine_hint_parent and cuisine_hint_parent != cuisine_hint:
        _add(f"{cuisine_hint_parent} restaurant")

    # Dietary tags: "halal" → "halal restaurant", "vegan" → "vegan restaurant"
    for tag in (dietary_tags or []):
        if tag in ("halal", "kosher", "jain"):
            _add(f"{tag} food")
        else:
            _add(f"{tag} restaurant")

    return seeds[:_MAX_AUGMENT_SEEDS]


# ── Per-business augmentation call ───────────────────────────────────────────

async def get_augmented_questions(
    service_tags: list[str],
    cuisine_hint: Optional[str],
    cuisine_hint_parent: Optional[str],
    dietary_tags: list[str],
    vertical: str,
    city: str,
    province: str,
    country: str = "Canada",
) -> list[dict]:
    """Run one DataForSEO city-level keyword call using business-specific seeds.

    Returns question-entry dicts (same shape as market_intelligence.questions
    entries) with empty `mentions` — these are volume-only signals for ROI math.
    Returns [] when seeds are empty, location unresolvable, or the call fails.

    Cost: ~$0.075 per call. Called once per audit when service/cuisine/dietary
    signals exist. Phase 0 proved this is critical for multi-service businesses
    (James Snow Physiotherapy: 3 keywords baseline vs 1,642 augmented).
    """
    seeds = build_augmentation_seeds(service_tags, cuisine_hint, cuisine_hint_parent, dietary_tags, vertical)
    if not seeds:
        logger.debug(f"[MI][AUG] No augmentation seeds for ({vertical}, {city}) — skipping call")
        return []

    location_code = await dataforseo.resolve_location_code(city, province, country)
    if not location_code:
        logger.warning(f"[MI][AUG] No location_code for '{city}' — skipping augmentation")
        return []

    try:
        raw = await dataforseo.keywords_for_keywords(seeds, location_code, limit=200)
    except Exception as e:
        logger.warning(f"[MI][AUG] DataForSEO call failed for ({vertical}, {city}): {e}")
        return []

    keywords = dataforseo.get_keywords(raw)
    now_str = datetime.now(timezone.utc).isoformat()
    return [
        {
            "question":        k["keyword"],
            "intent":          "mixed",
            "search_volume":   k.get("search_volume"),
            "competition":     k.get("competition"),
            "cpc":             k.get("cpc"),
            "monthly_searches": k.get("monthly_searches") or [],
            "last_seen":       now_str,
            "mentions":        {},   # no mention data — volume only
        }
        for k in keywords
        if k.get("keyword")
    ]


# ── Market visibility computation ─────────────────────────────────────────────

def compute_market_visibility(
    business_name: str,
    city: str,
    market_row: dict,
    augmented_questions: Optional[list[dict]] = None,
) -> dict:
    """Compute this business's AI-visibility share across the cached market questions.

    Reads market_intelligence.questions[].mentions to find where this business
    appears. Returns the market_visibility block written to audits.raw_results.

    augmented_questions: optional per-business augmented keyword list (volume only).
    When provided, adds augmented_volume_total and augmented_n_with_volume to the
    result for Phase 4 ROI v2 to use.

    Returns a minimal placeholder dict when the market row has no questions yet
    (e.g. first-signup, refresh not yet complete).
    """
    market_id = str(market_row.get("id") or "")
    questions = market_row.get("questions") or []
    benchmarks = market_row.get("benchmarks") or {}

    if not questions:
        result = {
            "market_id":              market_id,
            "questions_covered":      0,
            "questions_total":        0,
            "total_volume":           0,
            "weighted_mention_share": None,
            "position_avg":           None,
            "sentiment_avg":          None,
            "vertical_avg_share":     benchmarks.get("avg_mention_share"),
            "vertical_p75_share":     benchmarks.get("p75_mention_share"),
            "data_ready":             False,
        }
        if augmented_questions is not None:
            _attach_augmented_volume(result, augmented_questions)
        return result

    business_score_sum = 0.0
    total_score_sum = 0.0
    questions_covered = 0
    positions: list[float] = []
    sentiments: list[float] = []
    total_volume = 0

    for q_entry in questions:
        sv = q_entry.get("search_volume") or 1  # treat null as "below threshold" = 1
        mentions = q_entry.get("mentions") or {}

        # Accumulate total measurable volume (null → excluded from this sum)
        raw_sv = q_entry.get("search_volume")
        if raw_sv is not None:
            total_volume += raw_sv

        # Compute total weighted score for ALL businesses in this question
        q_total_score = 0.0
        q_business_score = 0.0
        q_positions: list[int] = []
        q_sentiments: list[float] = []
        found_in_question = False

        for engine_mentions in mentions.values():
            for mention in (engine_mentions or []):
                mname = (mention.get("name") or "").strip()
                w = mention_weight(
                    mention.get("position", 1),
                    mention.get("strength", "weak"),
                    mention.get("sentiment") or 0.5,
                )
                q_total_score += w
                if name_matches(mname, business_name):
                    q_business_score += w
                    found_in_question = True
                    q_positions.append(mention.get("position", 1))
                    q_sentiments.append(mention.get("sentiment") or 0.5)

        business_score_sum += q_business_score * sv
        total_score_sum += q_total_score * sv

        if found_in_question:
            questions_covered += 1
            positions.extend(q_positions)
            sentiments.extend(q_sentiments)

    weighted_share = (business_score_sum / total_score_sum) if total_score_sum > 0 else 0.0
    position_avg = round(sum(positions) / len(positions), 2) if positions else None
    sentiment_avg = round(sum(sentiments) / len(sentiments), 3) if sentiments else None

    result = {
        "market_id":              market_id,
        "questions_covered":      questions_covered,
        "questions_total":        len(questions),
        "total_volume":           total_volume,
        "weighted_mention_share": round(weighted_share, 4),
        "position_avg":           position_avg,
        "sentiment_avg":          sentiment_avg,
        "vertical_avg_share":     benchmarks.get("avg_mention_share"),
        "vertical_p75_share":     benchmarks.get("p75_mention_share"),
        "data_ready":             True,
    }
    if augmented_questions is not None:
        _attach_augmented_volume(result, augmented_questions)
    return result


def _attach_augmented_volume(result: dict, augmented: list[dict]) -> None:
    """Add per-business augmented keyword volume stats to a market_visibility dict."""
    with_vol = [q for q in augmented if q.get("search_volume") is not None]
    result["augmented_volume_total"] = sum(q["search_volume"] for q in with_vol)
    result["augmented_n_with_volume"] = len(with_vol)


# ── Market setup fire-and-forget ─────────────────────────────────────────────

async def _setup_market_task(
    vertical: str,
    city_norm: str,
    province: str,
    country: str,
) -> None:
    """Background coroutine: ensure market row exists and trigger refresh if stale."""
    from .refresh_worker import run_refresh

    market_row = await get_or_create(vertical, city_norm, province, country)
    if not market_row:
        logger.warning(f"[MI] setup_market_background: get_or_create returned None for ({vertical}, {city_norm})")
        return

    if market_row.get("refresh_status") in ("stale", "failed"):
        target_month = date.today().replace(day=1).isoformat()
        try:
            await run_refresh(
                str(market_row["id"]),
                vertical,
                city_norm,
                province,
                country,
                target_month,
            )
        except Exception as e:
            logger.warning(f"[MI] Background refresh failed for ({vertical}, {city_norm}): {e}")


def setup_market_background(
    vertical: str,
    city: str,
    province: str,
    country: str = "Canada",
) -> None:
    """Fire-and-forget market setup. Safe to call from within an async context.

    Creates the market_intelligence row if needed (status='stale') and triggers
    a background refresh. Never raises — errors are logged only. The running
    audit continues without waiting for the refresh to complete.
    """
    if not vertical or not city:
        return
    city_norm = normalize_city(city)
    vertical_key = canonical_vertical(vertical)
    try:
        task = asyncio.create_task(
            _setup_market_task(vertical_key, city_norm, province, country)
        )
        task.add_done_callback(
            lambda t: logger.warning(f"[MI] setup task error: {t.exception()}")
            if not t.cancelled() and t.exception() else None
        )
    except RuntimeError:
        # No event loop (e.g. tests run synchronously). Skip silently.
        logger.debug("[MI] setup_market_background: no event loop, skipping")

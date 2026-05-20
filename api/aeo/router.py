from fastapi import APIRouter, Depends, HTTPException, Header, Query
from pydantic import BaseModel
from core.auth import get_current_user
from core.database import supabase_admin, get_business_by_user, get_active_subscription
from core.notifications import send_email
import asyncio
import os
import logging
import re
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)
router = APIRouter()

# Per-workload LLM clients (audit_llm, content_llm) moved to
# api/aeo/audit/engine.py during Tier 6. Coach LLM lives in
# api/aeo/coach/handler.py. Reputation LLM lives in
# api/aeo/reputation/analyzer.py. All read the same AUDIT_PROVIDER/MODEL,
# CONTENT_PROVIDER/MODEL, COACH_PROVIDER/MODEL env vars they always did.

PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SERPAPI_KEY = os.getenv("SERPAPI_KEY")
CRON_SECRET = os.getenv("CRON_SECRET")
BILLING_ENABLED = os.getenv("BILLING_ENABLED", "false").lower() == "true"
# Signal extraction (KNOWN_TYPES, cuisine/dietary/clinic patterns, scanners)
# moved to api/aeo/audit/signals.py. Imported here so router-side callers
# (normalize_business_type, check_website, _run_audit_core, build_queries)
# keep working without path changes.
from .audit.signals import (  # noqa: F401
    KNOWN_TYPES,
    RESTAURANT_RE as _RESTAURANT_RE,
    DIETARY_PATTERNS as _DIETARY_PATTERNS,
    CLINIC_SERVICE_PATTERNS as _CLINIC_SERVICE_PATTERNS,
    extract_text_signals as _extract_text_signals,
    detect_cuisine as _detect_cuisine,
    is_specific_type_for_subspecialty as _is_specific_type_for_subspecialty,
)

# Country/province/address geocoding helpers moved to api/aeo/audit/geo.py.
# Re-exported here so router-side callers + downstream sub-modules that
# already import these by name keep working without path changes.
from .audit.geo import (  # noqa: F401
    COUNTRY_TO_GL,
    COUNTRY_ISO_TO_GL as _COUNTRY_ISO_TO_GL,
    CA_PROVINCE_CODES as _CA_PROVINCE_CODES,
    COUNTRY_ADDRESS_MARKERS,
    PROVINCE_ABBR_TO_FULL,
    country_to_gl,
    province_to_gl,
    address_country_gl,
    expand_province,
    extract_search_name,
)
# Maps helpers (place_id resolution + relative-date parsing) moved to
# api/aeo/audit/maps.py. Re-exported under the old underscored names so
# router-side callers (_check_review_recency, /own-reputation endpoint)
# keep resolving them without path changes.
from .audit.maps import (  # noqa: F401
    parse_relative_date as _parse_relative_date,
    resolve_maps_place_id as _resolve_maps_place_id,
)
# Per-query Perplexity runner moved to api/aeo/audit/perplexity.py so the
# reputation fetchers can import it without a circular dep into router.py.
from .audit.perplexity import _perplexity_one  # noqa: F401



# Scoring + name-match helpers moved to api/aeo/audit/scoring.py.
# Re-exported under the old underscored names so existing router-side
# callers (competitor handling, _run_audit_core) keep working.
from .audit.scoring import (  # noqa: F401
    name_matches as _name_matches,
    competitor_key as _competitor_key,
    match_competitor_ai_citations,
    calculate_score,
    score_competitor,
)
from .audit.recommendations import generate_recommendations  # noqa: F401
from .audit.queries import build_queries, QUERY_TEMPLATES  # noqa: F401

# Audit engine — orchestration, per-engine fan-outs, SERP parsers, and the
# full `_run_audit_core` pipeline. Moved to api/aeo/audit/engine.py during
# Tier 6. Re-exported under the existing names so the endpoint handlers in
# this file (`run_audit`, `cron_monthly_audit`, `get_own_reputation`) keep
# resolving them via the original names without code changes. New audit-
# layer code should import directly from `api.aeo.audit.engine`.
from .audit.engine import (  # noqa: F401
    _check_review_recency,
    _chatgpt_one,
    _fetch_own_gbp_via_maps,
    _google_name_lookup,
    _google_one,
    _run_audit_core,
    audit_llm,
    check_knowledge_graph,
    check_local_pack,
    check_organic,
    content_llm,
    normalize_business_type,
    run_chatgpt_multi,
    run_google_multi,
    run_perplexity_multi,
)
from .audit.website import check_website  # noqa: F401


# Reputation fetchers + analyzers moved to api/aeo/reputation/.
# Re-exported under the old underscored names so the audit engine
# (_run_audit_core) and the /own-reputation endpoint keep resolving
# them via aeo.router without import-path churn. New code should
# import directly from api.aeo.reputation.fetcher / .analyzer.
from .reputation.fetcher import (  # noqa: F401
    fetch_competitor_perplexity as _fetch_competitor_perplexity,
    fetch_competitor_reviews as _fetch_competitor_reviews,
    fetch_own_perplexity_reputation as _fetch_own_perplexity_reputation,
    fetch_own_reviews as _fetch_own_reviews,
)
from .reputation.analyzer import (  # noqa: F401
    analyze_competitor_weaknesses as _analyze_competitor_weaknesses,
    analyze_own_reputation as _analyze_own_reputation,
)


async def send_score_change_alert(owner_email: str, business_name: str, prev_score: int, new_score: int) -> None:
    delta = new_score - prev_score
    direction = "improved" if delta > 0 else "dropped"
    sign = "+" if delta > 0 else ""
    color = "#16a34a" if delta > 0 else "#dc2626"
    await send_email(
        to=owner_email,
        subject=f"Your AEO score {direction} {sign}{delta} points — {business_name}",
        body_html=f"""
            <div style="font-family:sans-serif;max-width:480px;margin:0 auto">
                <h2 style="color:#1e293b">Your AEO Readiness Score Changed</h2>
                <p>Your score for <strong>{business_name}</strong> has {direction}:</p>
                <p style="font-size:28px;font-weight:bold;color:{color};margin:16px 0">
                    {prev_score} → {new_score}
                    <span style="font-size:18px">({sign}{delta} pts)</span>
                </p>
                <p style="color:#64748b">Log in to see what changed and your recommended next steps.</p>
                <a href="https://app.leapone.ca/dashboard"
                   style="display:inline-block;background:#4f46e5;color:white;padding:10px 20px;
                          border-radius:8px;text-decoration:none;font-weight:600;margin-top:8px">
                    View Dashboard →
                </a>
            </div>
        """,
    )


class AuditRequest(BaseModel):
    business_id: str


# ─── Vertical detection + directory presence (moved to audit/verticals.py) ─
# Re-exported here under the old underscored names so existing test imports
# (test_canadian_verticals.py, test_reddit_linkedin.py, test_trades_recs.py)
# and current router callers keep working. New code should import directly
# from api.aeo.audit.verticals.
from .audit.verticals import (  # noqa: F401
    DIRECTORY_DOMAINS,
    CITY_SUBREDDITS,
    city_to_subreddit_url as _city_to_subreddit_url,
    is_trades_business as _is_trades_business,
    is_healthcare_business as _is_healthcare_business,
    is_dentist_business as _is_dentist_business,
    is_food_business as _is_food_business,
    is_legal_business as _is_legal_business,
    is_realtor_business as _is_realtor_business,
    is_b2b_business as _is_b2b_business,
    user_directories_only as _user_directories_only,
    domain_from_url as _domain_from_url,
    name_short as _name_short,
    detect_directory_presence as _detect_directory_presence,
)


# ─── Profile-field validators (used by PUT /business) ──────────────────────
_CANADIAN_POSTAL = re.compile(
    r"^[ABCEGHJ-NPRSTVXY]\d[ABCEGHJ-NPRSTV-Z][ -]?\d[ABCEGHJ-NPRSTV-Z]\d$",
    re.IGNORECASE,
)
_HOURS_RANGE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)-([01]\d|2[0-3]):([0-5]\d)$")
_ALLOWED_PRICE_RANGES = {"$", "$$", "$$$", "$$$$"}
_WEEKDAYS = {"monday", "tuesday", "wednesday", "thursday",
             "friday", "saturday", "sunday"}

def _clean_postal(postal: str | None, country: str | None) -> str | None:
    if not postal or not postal.strip():
        return None
    p = postal.strip().upper()
    if (country or "Canada") == "Canada" and not _CANADIAN_POSTAL.match(p):
        raise HTTPException(status_code=422,
            detail="postal_code: invalid Canadian postal code (e.g. K1P 5N7)")
    return p

def _clean_image_url(url: str | None) -> str | None:
    if not url or not url.strip():
        return None
    u = url.strip()
    if not (u.startswith("http://") or u.startswith("https://")):
        raise HTTPException(status_code=422,
            detail="image_url must start with http:// or https://")
    return u

def _clean_price_range(pr: str | None) -> str | None:
    if not pr or not pr.strip():
        return None
    p = pr.strip()
    if p not in _ALLOWED_PRICE_RANGES:
        raise HTTPException(status_code=422,
            detail="price_range must be one of '$', '$$', '$$$', '$$$$'")
    return p

def _clean_hours(hours: dict | None) -> dict | None:
    if hours is None:
        return None
    if not isinstance(hours, dict):
        raise HTTPException(status_code=422, detail="hours must be an object")
    out: dict[str, str] = {}
    for day, val in hours.items():
        d = str(day).lower().strip()
        if d not in _WEEKDAYS:
            raise HTTPException(status_code=422,
                detail=f"hours: invalid day '{day}'")
        if val is None or str(val).strip() == "":
            continue
        v = str(val).strip().lower()
        if v == "closed":
            out[d] = "closed"
        elif _HOURS_RANGE.match(v):
            out[d] = v
        else:
            raise HTTPException(status_code=422,
                detail=f"hours[{d}]: must be 'closed' or 'HH:MM-HH:MM'")
    return out or None


class BusinessProfileRequest(BaseModel):
    name: str
    type: str
    city: str
    province: str | None = None
    country: str | None = "Canada"
    website: str | None = None
    services: str | None = None
    street_address: str | None = None
    postal_code: str | None = None
    phone: str | None = None
    image_url: str | None = None
    price_range: str | None = None
    hours: dict | None = None  # {"monday": "09:00-17:00", "tuesday": "closed", ...}
    competitor_scope: str | None = None  # 'local' | 'country' | 'global'; see migration 020
    # ROI MVP (migration 022). All nullable -- dashboard falls back to vertical
    # defaults when these are missing.
    avg_customer_value_cad: float | None = None
    monthly_new_online_customers: int | None = None
    ltv_multiple_override: float | None = None


@router.get("/business")
async def get_business_profile(current_user: dict = Depends(get_current_user)):
    """Returns the current user's business profile fields used in the audit."""
    business = await get_business_by_user(current_user["id"])
    if not business:
        raise HTTPException(status_code=404, detail="Business profile not found")
    return {
        "id":       str(business["id"]),
        "name":     business.get("name"),
        "type":     business.get("type"),
        "city":     business.get("city"),
        "province": business.get("province"),
        "country":  business.get("country"),
        "website":  business.get("website"),
        "services": business.get("services"),
        "street_address": business.get("street_address"),
        "postal_code": business.get("postal_code"),
        "phone": business.get("phone"),
        "image_url": business.get("image_url"),
        "price_range": business.get("price_range"),
        "hours": business.get("hours"),
        "competitor_scope": business.get("competitor_scope") or "local",
        "avg_customer_value_cad":       business.get("avg_customer_value_cad"),
        "monthly_new_online_customers": business.get("monthly_new_online_customers"),
        "ltv_multiple_override":        business.get("ltv_multiple_override"),
    }


@router.put("/business")
async def update_business_profile(
    request: BusinessProfileRequest,
    current_user: dict = Depends(get_current_user),
):
    """Updates business profile fields that drive the AEO audit."""
    business = await get_business_by_user(current_user["id"])
    if not business:
        raise HTTPException(status_code=404, detail="Business profile not found")

    name = request.name.strip()
    city = request.city.strip()
    if not name or not city:
        raise HTTPException(status_code=422, detail="Business name and city are required")

    country = request.country or "Canada"

    # Reject unknown competitor_scope values; fall back to existing or 'local'.
    requested_scope = (request.competitor_scope or "").strip().lower()
    competitor_scope = (
        requested_scope if requested_scope in ("local", "country", "global")
        else (business.get("competitor_scope") or "local")
    )

    # Sanitize ROI numeric inputs — null on out-of-range/junk, clamp to a
    # generous upper bound so a typo can't blow up the dashboard math.
    def _clean_positive_number(v, upper):
        try:
            n = float(v) if v is not None else None
        except (TypeError, ValueError):
            return None
        if n is None or n < 0 or n > upper:
            return None
        return n

    avg_value = _clean_positive_number(request.avg_customer_value_cad, 1_000_000)
    monthly_online_raw = _clean_positive_number(request.monthly_new_online_customers, 100_000)
    monthly_online = int(round(monthly_online_raw)) if monthly_online_raw is not None else None
    ltv_override = _clean_positive_number(request.ltv_multiple_override, 200)

    supabase_admin.table("businesses").update({
        "name":           name,
        "type":           request.type.strip() if request.type else business.get("type"),
        "city":           city,
        "province":       request.province.strip() if request.province else None,
        "country":        country,
        "website":        request.website.strip() if request.website else None,
        "services":       request.services.strip() if request.services else None,
        "street_address": request.street_address.strip() if request.street_address else None,
        "postal_code":    _clean_postal(request.postal_code, country),
        "phone":          request.phone.strip() if request.phone else None,
        "image_url":      _clean_image_url(request.image_url),
        "price_range":    _clean_price_range(request.price_range),
        "hours":          _clean_hours(request.hours),
        "competitor_scope": competitor_scope,
        "avg_customer_value_cad":       avg_value,
        "monthly_new_online_customers": monthly_online,
        "ltv_multiple_override":        ltv_override,
    }).eq("id", business["id"]).execute()

    return {"message": "Business profile updated"}



@router.post("/audit")
async def run_audit(
    request: AuditRequest,
    current_user: dict = Depends(get_current_user),
):
    business = await get_business_by_user(current_user["id"])
    if not business:
        raise HTTPException(status_code=404, detail="Business profile not found")
    if str(business["id"]) != request.business_id:
        raise HTTPException(status_code=403, detail="Access denied")

    if BILLING_ENABLED:
        subscription = await get_active_subscription(str(business["id"]))
        if not subscription:
            raise HTTPException(status_code=402, detail="Active subscription required")

    # Reuse-recent-audit guard. If a successful audit ran in the last 10 minutes
    # (e.g. user refreshed the onboarding page while the previous audit's
    # response was still in flight), return the existing row instead of firing
    # a duplicate. Stops SerpApi rate-limit cascades on slow audits.
    recent = supabase_admin.table("aeo_audits") \
        .select("id, score, score_breakdown, raw_results, created_at") \
        .eq("business_id", business["id"]) \
        .gte("created_at", (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()) \
        .order("created_at", desc=True) \
        .limit(1) \
        .execute()
    if recent.data:
        row = recent.data[0]
        raw = row.get("raw_results") or {}
        logger.info(f"[AEO] Returning recent audit {row.get('id')} (no rerun)")
        return {
            "score":                row.get("score"),
            "breakdown":             row.get("score_breakdown"),
            "recommendations":       (raw.get("recommendations") or []),
            "perplexity":            raw.get("perplexity") or {},
            "google":                raw.get("google") or {},
            "chatgpt":               raw.get("chatgpt") or {},
            "website":               raw.get("website") or {},
            "competitors":           raw.get("competitors") or [],
            "competitor_insights":   raw.get("competitor_insights") or {},
            "citation_gaps":         raw.get("citation_gaps") or {},
            "auto_suggestions":      raw.get("auto_suggestions") or [],
            "market_visibility":     raw.get("market_visibility"),
            "raw_results":           raw,
            "reused": True,
        }

    prev_audits = supabase_admin.table("aeo_audits") \
        .select("score") \
        .eq("business_id", business["id"]) \
        .order("created_at", desc=True) \
        .limit(1) \
        .execute()
    prev_score = prev_audits.data[0]["score"] if prev_audits.data else None

    result = await _run_audit_core(business)

    supabase_admin.table("aeo_audits").insert({
        "business_id":          business["id"],
        "score":                result["score"],
        "score_breakdown":      result["breakdown"],
        "perplexity_mentioned": result["perplexity"]["mentioned"],
        "perplexity_snippet":   result["perplexity"]["snippet"],
        "google_ai_mentioned":  result["google"]["ai_overview"]["mentioned"],
        "google_ai_snippet":    result["google"]["ai_overview"]["snippet"],
        "chatgpt_mentioned":    result["chatgpt"]["mentioned"],
        "chatgpt_snippet":      result["chatgpt"]["snippet"],
        "raw_results": {
            "perplexity":           result["perplexity"],
            "google":               result["google"],
            "chatgpt":              result["chatgpt"],
            "website":              result["website"],
            "recommendations":      result["recommendations"],
            "competitors":          result.get("competitors", []),
            "competitor_insights":  result.get("competitor_insights", {}),
            "citation_gaps":        result.get("citation_gaps", {}),
            "auto_suggestions":     result.get("auto_suggestions", []),
            "market_visibility":    result.get("market_visibility"),
        },
    }).execute()

    if prev_score is not None and abs(result["score"] - prev_score) >= 10:
        await send_score_change_alert(
            current_user["email"], business["name"], prev_score, result["score"]
        )

    # Attach raw_results so the frontend receives the same structure stored in the DB
    result["raw_results"] = {
        "perplexity":          result["perplexity"],
        "google":              result["google"],
        "chatgpt":             result["chatgpt"],
        "website":             result["website"],
        "recommendations":     result["recommendations"],
        "competitors":         result.get("competitors", []),
        "competitor_insights": result.get("competitor_insights", {}),
        "citation_gaps":       result.get("citation_gaps", {}),
        "auto_suggestions":    result.get("auto_suggestions", []),
        "market_visibility":   result.get("market_visibility"),
    }
    return result


@router.get("/recommendations/{business_id}")
async def get_recommendations(
    business_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Returns recommendations from the most recent audit for the given business."""
    business = await get_business_by_user(current_user["id"])
    if not business or str(business["id"]) != business_id:
        raise HTTPException(status_code=403, detail="Access denied")

    latest = supabase_admin.table("aeo_audits") \
        .select("raw_results, score, score_breakdown, created_at") \
        .eq("business_id", business_id) \
        .order("created_at", desc=True) \
        .limit(1) \
        .execute()

    if not latest.data:
        return {"recommendations": [], "score": None, "breakdown": None, "audit_at": None}

    audit = latest.data[0]
    raw = audit.get("raw_results") or {}
    return {
        "recommendations": raw.get("recommendations", []),
        "score":           audit.get("score"),
        "breakdown":       audit.get("score_breakdown"),
        "audit_at":        audit.get("created_at"),
    }


@router.get("/own-reputation")
async def get_own_reputation(
    refresh: bool = Query(default=False, description="Force re-fetch even if a cached result exists"),
    current_user: dict = Depends(get_current_user),
):
    """GET /api/v1/aeo/own-reputation
    Fetches the business's own Google Maps reviews via SerpApi (same pipeline as competitor
    analysis — does NOT use the Phase 2 reviews table) and runs AI analysis to extract
    strengths and weaknesses as short phrases.

    Result is cached in the latest audit's raw_results.own_reputation. It is re-computed
    only when the cached entry is absent (i.e. once per audit run)."""
    business = await get_business_by_user(current_user["id"])
    if not business:
        raise HTTPException(status_code=404, detail="Business profile not found")

    audits = (
        supabase_admin.table("aeo_audits")
        .select("id, raw_results, created_at")
        .eq("business_id", business["id"])
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    if not audits.data:
        raise HTTPException(status_code=404, detail="No audit found — run an AEO audit first")

    audit = audits.data[0]
    raw = audit.get("raw_results") or {}

    # Return cached result if already computed for this audit run (skip if refresh=True)
    cached = raw.get("own_reputation")
    if cached and not refresh:
        logger.info(f"[AEO][OWN] Returning cached own_reputation for audit {audit['id']}")
        return {**cached, "cached": True}

    # Resolve place_id from the audit's knowledge_graph
    google_data = raw.get("google") or {}
    kg = google_data.get("knowledge_graph") or {}
    place_id = kg.get("place_id")
    country = business.get("country")

    # KG sometimes doesn't match (title mismatch) so place_id is absent.
    # Also reject CID-format IDs (numeric) — google_maps_reviews only accepts ChIJ format.
    # Fall back to a direct Google Maps lookup — same approach used for competitor reviews.
    if not place_id or not place_id.startswith("ChIJ"):
        place_id = await _resolve_maps_place_id(business["name"], business.get("city"), country)

    if not place_id:
        return {
            "strengths": [], "weaknesses": [], "summary": "",
            "review_count": 0, "avg_rating": None, "cached": False,
            "error": "no_place_id",
        }

    # Fetch Google Maps reviews AND a Perplexity reputation query in parallel —
    # same pattern as competitor analysis so we get multi-source signals (Yelp, BBB, etc.).
    # Use 180 days to capture enough reviews to surface both strengths and rare weaknesses.
    reviews, perplexity_text = await asyncio.gather(
        _fetch_own_reviews(place_id, country, max_days=365, max_pages=5),
        _fetch_own_perplexity_reputation(business["name"], business.get("city") or "", business.get("province"), business.get("country")),
    )
    logger.info(f"[AEO][OWN] Reputation fetch: {len(reviews)} reviews, perplexity={'yes' if perplexity_text else 'no'} for '{business['name']}'")
    if perplexity_text:
        logger.info(f"[AEO][OWN] Perplexity snippet: {perplexity_text[:400]}")
    else:
        logger.warning(f"[AEO][OWN] Perplexity returned EMPTY for '{business['name']}' — check PERPLEXITY_API_KEY")

    if not reviews and not perplexity_text:
        return {
            "strengths": [], "weaknesses": [], "summary": "",
            "review_count": 0, "avg_rating": None, "cached": False,
        }

    ratings = [r["rating"] for r in reviews if r.get("rating")]
    avg_rating = round(sum(ratings) / len(ratings), 1) if ratings else None

    result = await _analyze_own_reputation(reviews, business["name"], perplexity_text)
    result["review_count"] = len(reviews)
    result["avg_rating"] = avg_rating

    # Persist to DB so repeat loads are instant (invalidated automatically by next audit run)
    try:
        updated_raw = {**raw, "own_reputation": result}
        supabase_admin.table("aeo_audits").update({"raw_results": updated_raw}).eq("id", audit["id"]).execute()
        logger.info(f"[AEO][OWN] Saved own_reputation to audit {audit['id']}")
    except Exception as e:
        logger.warning(f"[AEO][OWN] Failed to save own_reputation: {e}")

    return {**result, "cached": False}


@router.post("/cron-monthly")
async def cron_monthly_audit(authorization: str | None = Header(default=None)):
    """Monthly auto-audit for all businesses. Called by Vercel Cron via the Next.js proxy route."""
    if not CRON_SECRET or authorization != f"Bearer {CRON_SECRET}":
        raise HTTPException(status_code=401, detail="Unauthorized")

    businesses = supabase_admin.table("businesses").select("*").execute()
    summary = []

    for business in businesses.data:
        try:
            prev_audits = supabase_admin.table("aeo_audits") \
                .select("score") \
                .eq("business_id", business["id"]) \
                .order("created_at", desc=True) \
                .limit(1) \
                .execute()
            prev_score = prev_audits.data[0]["score"] if prev_audits.data else None

            result = await _run_audit_core(business)

            supabase_admin.table("aeo_audits").insert({
                "business_id":          business["id"],
                "score":                result["score"],
                "score_breakdown":      result["breakdown"],
                "perplexity_mentioned": result["perplexity"]["mentioned"],
                "perplexity_snippet":   result["perplexity"]["snippet"],
                "google_ai_mentioned":  result["google"]["ai_overview"]["mentioned"],
                "google_ai_snippet":    result["google"]["ai_overview"]["snippet"],
                "chatgpt_mentioned":    result["chatgpt"]["mentioned"],
                "chatgpt_snippet":      result["chatgpt"]["snippet"],
                "raw_results": {
                    "perplexity":          result["perplexity"],
                    "google":              result["google"],
                    "chatgpt":             result["chatgpt"],
                    "website":             result["website"],
                    "recommendations":     result["recommendations"],
                    "competitors":         result.get("competitors", []),
                    "competitor_insights": result.get("competitor_insights", {}),
                    "citation_gaps":       result.get("citation_gaps", {}),
                    "market_visibility":   result.get("market_visibility"),
                },
            }).execute()

            if prev_score is not None and abs(result["score"] - prev_score) >= 10:
                user_resp = supabase_admin.auth.admin.get_user_by_id(business["user_id"])
                owner_email = user_resp.user.email if user_resp and user_resp.user else None
                if owner_email:
                    await send_score_change_alert(owner_email, business["name"], prev_score, result["score"])

            summary.append({"business_id": str(business["id"]), "score": result["score"], "status": "ok"})
            print(f"[CRON] Audited {business['name']}: {result['score']}/100")
        except Exception as e:
            print(f"[CRON] Failed to audit {business.get('name', business['id'])}: {e}")
            summary.append({"business_id": str(business["id"]), "error": str(e), "status": "error"})

    return {"audited": len(summary), "results": summary}


@router.post("/cron-refresh-markets")
async def cron_refresh_markets(authorization: str | None = Header(default=None)):
    """Monthly market-intelligence refresh for every (vertical, city) combo with
    at least one active local-scope business. Idempotent: markets already fresh
    for the current month are skipped. Called by the scheduled cron (same
    CRON_SECRET auth as /cron-monthly)."""
    if not CRON_SECRET or authorization != f"Bearer {CRON_SECRET}":
        raise HTTPException(status_code=401, detail="Unauthorized")
    from .refresh_worker import refresh_all_markets
    return await refresh_all_markets()



# ─── Content generation (handlers in api/aeo/content/generator.py) ──────
# Mounted on the same prefix so existing endpoint URLs stay stable:
#   POST   /generate-content
#   PATCH  /content/{content_id}
#   POST   /content/{content_id}/verify
#   POST   /content/{content_id}/regenerate-item
from .content.generator import router as _content_router
router.include_router(_content_router)

# Re-export content internals for existing test imports (test_content_helpers.py,
# test_verify_and_edit.py). New code should import directly from content/.
from .content.validators import (  # noqa: F401
    truncate_at_word as _truncate_at_word,
    clean_bio as _clean_bio,
    clean_description as _clean_description,
    validate_content as _validate_content,
)
from .content.prompts import build_content_prompts as _build_content_prompts  # noqa: F401
from .content.generator import (  # noqa: F401
    _apply_content_patch,
    _VERIFY_KEY_RE,
    _PATCH_KEY_RE,
    _REGENERATE_KEY_RE,
)


# ─── AI execution coach (handler in api/aeo/coach/handler.py) ─────────────
# Mounted on the same prefix as the rest of /api/v1/aeo so endpoint paths
# (notably /recommendation-help) keep their URLs after the refactor.
from .coach.handler import router as _coach_router
router.include_router(_coach_router)

# Re-export coach internals for existing test imports (test_coach.py).
from .coach.prompts import (  # noqa: F401
    build_coach_system_prompt as _build_coach_system_prompt,
    CoachRecommendation,
)
from .coach.handler import _COACH_HISTORY_CAP, _COACH_MESSAGE_CAP  # noqa: F401


# ─── Competitor management (handlers in api/aeo/competitors.py) ───────────
# Mounted on the same prefix so endpoint URLs stay stable:
#   GET  /competitor-search
#   POST /competitors
from .competitors import router as _competitor_router
router.include_router(_competitor_router)

# Re-export competitor internals for the audit engine + existing test imports
# (test_address_parsing.py). New code should import directly from
# api.aeo.competitors.
from .competitors import (  # noqa: F401
    extract_location_from_address as _extract_location_from_address,
    extract_competitors,
    check_competitor_websites,
    lookup_competitor_by_place_id as _lookup_competitor_by_place_id,
    score_user_competitor as _score_user_competitor,
    CompetitorEntry,
    CompetitorListRequest,
)

"""Content generation endpoints (split from api/aeo/router.py).

Four endpoints, all mounted on the same /api/v1/aeo prefix as the rest
of the AEO surface so URLs stay stable across the refactor:

  POST   /generate-content                generate the full bundle
  PATCH  /content/{content_id}            inline edits to descriptions / FAQ
  POST   /content/{content_id}/verify     mark an item as owner-verified
  POST   /content/{content_id}/regenerate-item   regenerate one item with notes

All four share the same Pydantic model surface (defined below) and the
prompt/validator helpers in this package.
"""
import asyncio
import json
import logging
import os
import re

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core.ai_engine import AIEngine
from core.auth import get_current_user
from core.database import (
    get_business_by_user,
    get_active_subscription,
    supabase_admin,
)
from integrations import serpapi as serpapi_client

from ..schema_builder import build_schema, build_faq_schema, find_missing_required_fields
from .prompts import build_content_prompts, build_regenerate_prompts
from .validators import clean_bio, clean_description, truncate_at_word, validate_content
from ..audit.geo import COUNTRY_TO_GL


logger = logging.getLogger(__name__)
router = APIRouter()

# ─── Module-level config ──────────────────────────────────────────────────
# content_llm is also instantiated in api/aeo/router.py for audit-side reuse
# (normalize_business_type, reputation summaries). The two instances share
# env-var config so behavior is identical. They'll consolidate to a single
# shared instance when the audit engine moves out of router.py.
content_llm = AIEngine(
    provider=os.getenv("CONTENT_PROVIDER"),
    model=os.getenv("CONTENT_MODEL"),
)

SERPAPI_KEY = os.getenv("SERPAPI_KEY")
BILLING_ENABLED = os.getenv("BILLING_ENABLED", "false").lower() == "true"


# ─── Pydantic models ──────────────────────────────────────────────────────

class ExistingFaq(BaseModel):
    """One owner-supplied Q+A pair already published on their site.
    Preserved verbatim in the final FAQ; never rewritten by the LLM."""
    question: str
    answer: str


class GenerateContentRequest(BaseModel):
    business_id: str
    language: str = "en"  # 'en' | 'fr'
    # Phase 2 — owner provides questions they hear from real customers.
    # Used verbatim as the first N entries in the generated FAQ. Remaining
    # slots are LLM-generated. Capped to 10 items, 200 chars each.
    custom_faq_seeds: list[str] = []
    # Phase 4 — owner's existing Q+A pairs from their website. Preserved
    # verbatim (LLM never rewrites these). LLM generates additional Q&As
    # that don't duplicate the topics covered here, filling to 15 total.
    # Capped to 50 items, 200 char Q + 1000 char A.
    existing_faqs: list[ExistingFaq] = []


class ContentPatchRequest(BaseModel):
    """Body of PATCH /content/{id}. updates is a flat map of dotted-path keys
    to new string values. Keys: 'description.<website|gbp|yelp>', 'social_bio',
    'faq.<idx>.<question|answer>'."""
    updates: dict[str, str]


class ContentVerifyRequest(BaseModel):
    key: str       # 'description.website' | 'social_bio' | 'faq.<idx>'
    verified: bool


class ContentRegenerateItemRequest(BaseModel):
    key: str       # same as verify.key but only the supported regenerate keys
    notes: str = ""


# Dotted-path keys the verified-state map is allowed to track. Anything else
# raises a 422 to prevent typos from silently storing weird state.
_VERIFY_KEY_RE = re.compile(
    r"^(description\.(website|gbp|yelp)|social_bio|faq\.\d+)$"
)
_PATCH_KEY_RE = re.compile(
    r"^(description\.(website|gbp|yelp)|social_bio|faq\.\d+\.(question|answer))$"
)
_REGENERATE_KEY_RE = re.compile(
    r"^(description\.(website|gbp|yelp)|social_bio|faq\.\d+)$"
)


# ─── PAA fetcher (SerpApi) ────────────────────────────────────────────────

async def _fetch_people_also_ask(business_type: str, city: str,
                                  country: str, language: str = "en") -> list[str]:
    """Pull `related_questions` from SerpApi for a generic Google search.
    Best-effort: returns [] on any failure (no error to caller)."""
    if not SERPAPI_KEY or not business_type or not city:
        return []
    try:
        gl = COUNTRY_TO_GL.get(country, "ca")
        hl = "fr" if language == "fr" else "en"
        data = await serpapi_client.search(
            {
                "q":      f"{business_type} in {city}",
                "engine": "google",
                "gl":     gl,
                "hl":     hl,
            },
            timeout=10.0,
        )
        related = data.get("related_questions", []) or []
        return [r.get("question") for r in related if r.get("question")][:8]
    except Exception as e:
        logger.warning(f"[PAA] fetch failed: {e}")
        return []


# ─── Patch / verify helpers ───────────────────────────────────────────────

def _apply_content_patch(row: dict, key: str, value: str) -> None:
    """Mutate `row` to apply a single dotted-path update. Raises ValueError
    on bad keys or out-of-range FAQ indices."""
    if not _PATCH_KEY_RE.match(key):
        raise ValueError(f"Invalid update key: {key}")

    if key.startswith("description."):
        sub = key.split(".", 1)[1]
        descs = dict(row.get("descriptions") or {})
        descs[sub] = value
        row["descriptions"] = descs
        # Keep legacy `description` column synced when website variant changes,
        # so anything still reading the old shape sees the latest text.
        if sub == "website":
            row["description"] = value
        return

    if key == "social_bio":
        row["social_bio"] = value
        return

    if key.startswith("faq."):
        _, idx_str, field = key.split(".", 2)
        idx = int(idx_str)
        faq = list(row.get("faq") or [])
        if not (0 <= idx < len(faq)):
            raise ValueError(f"FAQ index {idx} out of range (0..{len(faq) - 1})")
        item = dict(faq[idx])
        item[field] = value
        faq[idx] = item
        row["faq"] = faq
        return

    raise ValueError(f"Unknown key: {key}")  # unreachable given the regex


async def _load_content_for_user(content_id: str, current_user: dict) -> tuple[dict, dict]:
    """Fetch an aeo_content row + verify it belongs to the calling user's
    business. Returns (content_row, business_row). Raises HTTPException
    on miss / access denied."""
    business = await get_business_by_user(current_user["id"])
    if not business:
        raise HTTPException(status_code=404, detail="Business profile not found")

    res = supabase_admin.table("aeo_content") \
        .select("*").eq("id", content_id).limit(1).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Content not found")
    content = res.data[0]

    if str(content.get("business_id")) != str(business["id"]):
        raise HTTPException(status_code=403, detail="Access denied")

    return content, business


# ─── Endpoints ────────────────────────────────────────────────────────────

@router.post("/generate-content")
async def generate_content(
    request: GenerateContentRequest,
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

    language = "fr" if request.language == "fr" else "en"

    latest_audit = supabase_admin.table("aeo_audits") \
        .select("*").eq("business_id", business["id"]) \
        .order("created_at", desc=True).limit(1).execute()
    audit = latest_audit.data[0] if latest_audit.data else None

    name     = business["name"]
    btype    = business["type"]
    city     = business["city"]
    province = business.get("province") or ""
    services = business.get("services") or ""
    website  = business.get("website") or ""
    country  = business.get("country") or "Canada"

    audit_context = ""
    if audit:
        gaps = []
        if not audit.get("perplexity_mentioned"): gaps.append("Perplexity")
        if not audit.get("google_ai_mentioned"):  gaps.append("Google AI Overview")
        if not audit.get("chatgpt_mentioned"):    gaps.append("ChatGPT")
        if gaps:
            audit_context = f"The business is NOT currently cited by: {', '.join(gaps)}. "

    base_context = (
        f"Business name: {name}\n"
        f"Business type: {btype}\n"
        f"City: {city}{', ' + province if province else ''}\n"
        f"Services: {services}\n"
        f"Website: {website}\n"
        f"{audit_context}"
    )

    # People-Also-Ask seeds for FAQ grounding (best-effort)
    paa_questions = await _fetch_people_also_ask(btype, city, country, language)

    # Phase 2: owner's custom seed questions. Sanitize: cap length per item
    # and total count, drop empties.
    custom_faq_seeds = [
        s.strip()[:200] for s in (request.custom_faq_seeds or [])
        if s and s.strip()
    ][:10]

    # Phase 4: owner's existing Q+A pairs from their site. Sanitize:
    # cap count + lengths, drop empties or malformed pairs.
    existing_faqs = []
    for f in (request.existing_faqs or [])[:50]:
        q = (f.question or "").strip()[:200]
        a = (f.answer   or "").strip()[:1000]
        if q and a:
            existing_faqs.append({"question": q, "answer": a})

    prompts = build_content_prompts(language, base_context, services,
                                    paa_questions, custom_faq_seeds,
                                    existing_faqs)

    # System prompts enforce output format at the model level (more reliable
    # than user-prompt instructions). Particularly important for the bio,
    # which the LLM otherwise treats as a creative-writing assignment and
    # responds with markdown headers + alternatives + character-count notes.
    desc_system = (
        "You produce only the description text in plain prose. "
        "No markdown headers, no bold/italic, no preamble, no alternatives, "
        "no character counts, no labels. Output starts with the first word "
        "of the description itself."
    )
    bio_system = (
        "You produce only the bio text — a single short sentence or phrase "
        "under 150 characters. No markdown, no headers, no quotation marks, "
        "no labels, no alternatives, no character counts. Output starts and "
        "ends with the bio words themselves."
    )

    # Run all 5 LLM calls in parallel
    website_desc, gbp_desc, yelp_desc, social_bio_raw, faq_raw = await asyncio.gather(
        content_llm.generate(prompt=prompts["website_desc"], max_tokens=700, temperature=0.7,
                           system_prompt=desc_system),
        content_llm.generate(prompt=prompts["gbp_desc"],     max_tokens=350, temperature=0.7,
                           system_prompt=desc_system),
        content_llm.generate(prompt=prompts["yelp_desc"],    max_tokens=500, temperature=0.7,
                           system_prompt=desc_system),
        content_llm.generate(prompt=prompts["social_bio"],   max_tokens=120, temperature=0.5,
                           system_prompt=bio_system),
        content_llm.generate(prompt=prompts["faq"],          max_tokens=2500, temperature=0.5,
                           system_prompt="Return only valid JSON, no markdown."),
    )

    # Parse FAQ JSON, tolerant of fenced code blocks the LLM sometimes emits
    try:
        llm_faq = json.loads(re.sub(r'^```(?:json)?\s*|\s*```$', '', faq_raw.strip(),
                                     flags=re.MULTILINE))
        if not isinstance(llm_faq, list):
            llm_faq = []
    except Exception:
        llm_faq = []

    # Phase 4 — merge: owner's existing Q+A pairs come FIRST (verbatim),
    # then the LLM-generated new ones. Existing pairs preserve the owner's
    # exact wording for content already published on their website.
    faq: list[dict] = []
    for f in existing_faqs:
        faq.append({"question": f["question"], "answer": f["answer"]})
    for item in llm_faq:
        if isinstance(item, dict) and item.get("question") and item.get("answer"):
            faq.append({
                "question": str(item["question"]).strip(),
                "answer":   str(item["answer"]).strip(),
            })

    # Clean LLM output (strip markdown headers, "Alternative" sections,
    # bold-line wrappers, character-count meta) BEFORE applying char caps,
    # so we don't end up truncating 150 chars of markdown garbage.
    social_bio = truncate_at_word(clean_bio(social_bio_raw), 150)
    descriptions = {
        "website": clean_description(website_desc),
        "gbp":     truncate_at_word(clean_description(gbp_desc), 700),
        "yelp":    clean_description(yelp_desc),
    }

    # Server-side validation (warnings only -- still ship the content)
    validation_warnings = validate_content(descriptions, faq, social_bio)

    # Deterministic schema -- never LLM-generated
    schema_obj = build_schema(business, description=descriptions["website"], content_language=language)
    schema_raw = json.dumps(schema_obj, indent=2, ensure_ascii=False)
    schema_missing = find_missing_required_fields(business)

    # Deterministic FAQPage schema from the LLM-generated Q&A list
    faq_schema_obj = build_faq_schema(faq) if faq else None
    faq_schema_raw = (json.dumps(faq_schema_obj, indent=2, ensure_ascii=False)
                      if faq_schema_obj else None)

    insert_res = supabase_admin.table("aeo_content").insert({
        "business_id":   business["id"],
        "description":   descriptions["website"],   # legacy column for backward compat
        "descriptions":  descriptions,
        "faq":           faq,
        "faq_schema":    faq_schema_raw,
        "schema_markup": schema_raw,
        "social_bio":    social_bio,
        "language":      language,
        "paa_questions": paa_questions,
        "custom_faq_seeds": custom_faq_seeds,
        "existing_faqs": existing_faqs,
    }).execute()
    content_id = (insert_res.data[0]["id"]
                  if insert_res.data and insert_res.data[0].get("id") else None)

    return {
        "id":                    content_id,
        "language":              language,
        "descriptions":          descriptions,
        "social_bio":            social_bio,
        "faq":                   faq,
        "faq_schema":            faq_schema_raw,
        "schema_markup":         schema_raw,
        "schema_missing_fields": schema_missing,
        "paa_questions":         paa_questions,
        "custom_faq_seeds":      custom_faq_seeds,
        "existing_faqs":         existing_faqs,
        "validation_warnings":   validation_warnings,
        "verified":              {},
    }


# ─── Verify-and-edit endpoints (migration 017) ────────────────────────────
# Pattern: AI generates content -> owner reviews -> owner edits inline OR
# regenerates with notes -> owner verifies. Mirrors the reviews-module
# pattern. Three endpoints below: PATCH for edits, /verify for the
# verified-state toggle, /regenerate-item for "rewrite this with these
# notes." All scoped to the calling user's business via RLS + manual check.


@router.patch("/content/{content_id}")
async def patch_content(
    content_id: str,
    request: ContentPatchRequest,
    current_user: dict = Depends(get_current_user),
):
    """Apply inline edits to one aeo_content row. Body: { updates: {key: value, ...} }
    where keys are dotted paths (description.website, social_bio, faq.0.answer, etc).
    Multiple updates apply atomically (single supabase write).
    Also rebuilds the FAQ schema if any FAQ field changes (keeps JSON-LD in sync)."""
    content, _ = await _load_content_for_user(content_id, current_user)

    if not request.updates:
        raise HTTPException(status_code=422, detail="No updates provided")

    # Apply each update. Validation errors -> 422 with the offending key.
    faq_changed = False
    for key, value in request.updates.items():
        try:
            _apply_content_patch(content, key, value)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        if key.startswith("faq."):
            faq_changed = True

    # If any FAQ Q/A changed, rebuild the FAQPage JSON-LD so the schema
    # stays in sync with the human-readable Q&As.
    if faq_changed:
        faq_items = content.get("faq") or []
        if faq_items:
            schema_obj = build_faq_schema(faq_items)
            content["faq_schema"] = json.dumps(schema_obj, indent=2, ensure_ascii=False)
        else:
            content["faq_schema"] = None

    # Persist
    update_payload = {
        "descriptions":   content.get("descriptions"),
        "description":    content.get("description"),
        "social_bio":     content.get("social_bio"),
        "faq":            content.get("faq"),
        "faq_schema":     content.get("faq_schema"),
        "last_edited_at": "now()",
    }
    supabase_admin.table("aeo_content").update(update_payload).eq("id", content_id).execute()

    return {
        "id":          content_id,
        "descriptions": content.get("descriptions"),
        "social_bio":   content.get("social_bio"),
        "faq":          content.get("faq"),
        "faq_schema":   content.get("faq_schema"),
    }


@router.post("/content/{content_id}/verify")
async def verify_content_item(
    content_id: str,
    request: ContentVerifyRequest,
    current_user: dict = Depends(get_current_user),
):
    """Toggle the verified state for a single item key. Stored as JSONB map
    on aeo_content.verified. Used to track which items the owner has
    reviewed and approved before they're considered safe to publish."""
    content, _ = await _load_content_for_user(content_id, current_user)

    if not _VERIFY_KEY_RE.match(request.key):
        raise HTTPException(status_code=422, detail=f"Invalid verify key: {request.key}")

    verified = dict(content.get("verified") or {})
    if request.verified:
        verified[request.key] = True
    else:
        verified.pop(request.key, None)

    supabase_admin.table("aeo_content").update({"verified": verified}) \
        .eq("id", content_id).execute()
    return {"id": content_id, "verified": verified}


@router.post("/content/{content_id}/regenerate-item")
async def regenerate_content_item(
    content_id: str,
    request: ContentRegenerateItemRequest,
    current_user: dict = Depends(get_current_user),
):
    """Regenerate a single item with optional user notes ('make it shorter',
    'remove Invisalign — we don't do that'). Saves the new value AND clears
    that item's verified flag (it's a new value, owner needs to re-verify)."""
    content, business = await _load_content_for_user(content_id, current_user)

    if not _REGENERATE_KEY_RE.match(request.key):
        raise HTTPException(status_code=422,
            detail=f"Cannot regenerate item with key: {request.key}")

    if BILLING_ENABLED:
        sub = await get_active_subscription(str(business["id"]))
        if not sub:
            raise HTTPException(status_code=402, detail="Active subscription required")

    language = (content.get("language") == "fr" and "fr") or "en"
    services = business.get("services") or ""

    # ─── Description / social bio ─────────────────────────────────────────
    if request.key.startswith("description.") or request.key == "social_bio":
        prompts_map = build_regenerate_prompts(business, language, services, request.notes)
        prompt, max_tokens, temperature = prompts_map[request.key]

        if request.key == "social_bio":
            sys_prompt = (
                "You produce only the bio text — a single short sentence or phrase "
                "under 150 characters. No markdown, no headers, no quotation marks, "
                "no labels, no alternatives, no character counts."
            )
        else:
            sys_prompt = (
                "You produce only the description text in plain prose. "
                "No markdown, no preamble, no alternatives, no character counts, no labels."
            )

        raw = await content_llm.generate(
            prompt=prompt, max_tokens=max_tokens, temperature=temperature,
            system_prompt=sys_prompt,
        )

        if request.key == "social_bio":
            value = truncate_at_word(clean_bio(raw), 150)
        elif request.key == "description.gbp":
            value = truncate_at_word(clean_description(raw), 700)
        else:
            value = clean_description(raw)

        # Save + clear verified flag for this item (new value -> needs re-review)
        try:
            _apply_content_patch(content, request.key, value)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        verified = dict(content.get("verified") or {})
        verified.pop(request.key, None)

        supabase_admin.table("aeo_content").update({
            "descriptions":   content.get("descriptions"),
            "description":    content.get("description"),
            "social_bio":     content.get("social_bio"),
            "verified":       verified,
            "last_edited_at": "now()",
        }).eq("id", content_id).execute()

        return {"key": request.key, "value": value, "verified": verified}

    # ─── FAQ item ─────────────────────────────────────────────────────────
    # Regenerate one Q&A pair. Prompt asks for ONE question and answer in
    # JSON. Notes ("the answer is wrong about Invisalign") drive a rewrite.
    if request.key.startswith("faq."):
        idx = int(request.key.split(".", 1)[1])
        existing = (content.get("faq") or [])
        if not (0 <= idx < len(existing)):
            raise HTTPException(status_code=422, detail=f"FAQ index out of range")

        original = existing[idx]
        original_q = original.get("question", "")
        original_a = original.get("answer", "")

        notes_block = f"\nUser notes: {request.notes.strip()}\n" if request.notes.strip() else ""
        if language == "fr":
            faq_prompt = (
                f"Entreprise: {business['name']} ({business['type']}, {business['city']})\n"
                f"Question FAQ existante: {original_q}\n"
                f"Réponse existante: {original_a}\n"
                f"{notes_block}"
                f"Réécris cette FAQ. La réponse doit faire 40-80 mots, factuelle, "
                f"utile pour citation par les IA. Format JSON: "
                f"{{\"question\": \"...\", \"answer\": \"...\"}}. "
                f"Retourne uniquement du JSON valide."
            )
        else:
            faq_prompt = (
                f"Business: {business['name']} ({business['type']}, {business['city']})\n"
                f"Existing FAQ question: {original_q}\n"
                f"Existing answer: {original_a}\n"
                f"{notes_block}"
                f"Rewrite this Q&A. The answer should be 40-80 words, factual, "
                f"useful for AI to cite verbatim. Format as JSON: "
                f"{{\"question\": \"...\", \"answer\": \"...\"}}. "
                f"Return only valid JSON."
            )

        raw = await content_llm.generate(
            prompt=faq_prompt, max_tokens=400, temperature=0.5,
            system_prompt="Return only valid JSON, no markdown.",
        )
        try:
            new_item = json.loads(re.sub(r'^```(?:json)?\s*|\s*```$', '',
                                          raw.strip(), flags=re.MULTILINE))
            if not isinstance(new_item, dict) or "question" not in new_item or "answer" not in new_item:
                raise ValueError("Bad shape")
        except Exception:
            raise HTTPException(status_code=502, detail="Regenerate failed -- LLM returned invalid JSON")

        # Apply
        faq = list(content.get("faq") or [])
        faq[idx] = {"question": str(new_item["question"]), "answer": str(new_item["answer"])}
        content["faq"] = faq

        # Rebuild FAQ schema since the item changed
        schema_obj = build_faq_schema(faq)
        new_faq_schema = json.dumps(schema_obj, indent=2, ensure_ascii=False)

        # Clear verified flag for this item
        verified = dict(content.get("verified") or {})
        verified.pop(request.key, None)

        supabase_admin.table("aeo_content").update({
            "faq":            faq,
            "faq_schema":     new_faq_schema,
            "verified":       verified,
            "last_edited_at": "now()",
        }).eq("id", content_id).execute()

        return {"key": request.key, "value": faq[idx], "verified": verified}

    # Should be unreachable given the regex check above
    raise HTTPException(status_code=422, detail=f"Unsupported key: {request.key}")

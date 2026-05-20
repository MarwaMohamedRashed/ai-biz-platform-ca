"""AI execution coach endpoint.

Headline differentiation feature: a chat coach attached to each
recommendation. SMB owners get told what to do but rarely get walked
through how -- this fills that gap. Non-streaming for v1 (simpler).

The router is built locally in this module and included by api/aeo/router.py.
That keeps coach routing self-contained — adding new coach endpoints
doesn't touch the main router file. Tier gating (Pro-only) is enforced
here when BILLING_ENABLED.
"""
import logging
import os

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core.ai_engine import AIEngine
from core.auth import get_current_user
from core.database import get_business_by_user, get_active_subscription

from .prompts import CoachRecommendation, build_coach_system_prompt


logger = logging.getLogger(__name__)
router = APIRouter()

# ─── LLM client (env-configurable) ────────────────────────────────────────
# gemini-3.1-flash-lite is the cost-optimal default for chat-style
# coaching. If you notice the model dropping subtler instructions
# (Quebec French register, the 'offer to write the email' rule, etc.)
# in testing, override with COACH_MODEL=gemini-3.1-pro in .env.
coach_llm = AIEngine(
    provider=os.getenv("COACH_PROVIDER", "gemini"),
    model=os.getenv("COACH_MODEL", "gemini-3.1-flash-lite"),
)

BILLING_ENABLED = os.getenv("BILLING_ENABLED", "false").lower() == "true"

# Hard cap on conversation history sent to the LLM. Keeps cost bounded
# and prevents prompt-stuffing abuse. ~10 turns of normal chat.
_COACH_HISTORY_CAP = 20
# Hard cap on a single user message. Most coach questions are 1-3 sentences.
_COACH_MESSAGE_CAP = 2000


class CoachMessage(BaseModel):
    role: str           # 'user' | 'assistant'
    content: str


class CoachRequest(BaseModel):
    recommendation: CoachRecommendation
    messages: list[CoachMessage] = []  # full chat history (excluding the new message)
    new_message: str
    language: str = "en"               # 'en' | 'fr'


@router.post("/recommendation-help")
async def recommendation_help(
    request: CoachRequest,
    current_user: dict = Depends(get_current_user),
):
    """AI execution coach. Takes a recommendation context + conversation
    history + new user message, returns the next assistant reply.
    Non-streaming. Pro-tier only when BILLING_ENABLED."""
    # ─── Input validation ─────────────────────────────────────────────────
    if not request.new_message or not request.new_message.strip():
        raise HTTPException(status_code=422, detail="new_message is required")
    if len(request.new_message) > _COACH_MESSAGE_CAP:
        raise HTTPException(status_code=422,
            detail=f"new_message exceeds {_COACH_MESSAGE_CAP} chars")
    if not request.recommendation.title.strip():
        raise HTTPException(status_code=422, detail="recommendation.title is required")

    # Trim history to the most recent N turns to bound cost
    history = request.messages[-_COACH_HISTORY_CAP:]
    for m in history:
        if m.role not in ("user", "assistant"):
            raise HTTPException(status_code=422,
                detail=f"Invalid message role: {m.role}")

    # ─── Get business context ─────────────────────────────────────────────
    business = await get_business_by_user(current_user["id"])
    if not business:
        raise HTTPException(status_code=404, detail="Business profile not found")

    # ─── Tier gating: Pro only when billing is enabled ────────────────────
    # The coach is the headline differentiation feature for Pro. Starter
    # users see the upgrade CTA on the frontend instead of the chat input.
    if BILLING_ENABLED:
        sub = await get_active_subscription(str(business["id"]))
        if not sub or sub.get("plan_tier") != "pro":
            raise HTTPException(status_code=402, detail="pro_required")

    language = "fr" if request.language == "fr" else "en"
    system_prompt = build_coach_system_prompt(request.recommendation, business, language)

    # ─── Build the chat transcript ────────────────────────────────────────
    # Serialised inside the prompt so it works with any LLM provider.
    # Token budget is small because we trimmed history above.
    transcript = "\n".join(
        f"{'Owner' if m.role == 'user' else 'Coach'}: {m.content}"
        for m in history
    )
    if transcript:
        transcript += "\n"
    full_prompt = (
        f"{transcript}"
        f"Owner: {request.new_message.strip()}\n"
        f"Coach:"
    )

    # ─── Call the LLM ─────────────────────────────────────────────────────
    # Routes through `coach_llm` (configured via COACH_PROVIDER + COACH_MODEL).
    try:
        reply = await coach_llm.generate(
            prompt=full_prompt,
            system_prompt=system_prompt,
            max_tokens=600,
            temperature=0.5,
        )
    except Exception as e:
        logger.warning(f"[COACH] LLM call failed: {e}")
        raise HTTPException(status_code=502, detail="Coach is temporarily unavailable. Try again in a moment.")

    return {"reply": (reply or "").strip()}

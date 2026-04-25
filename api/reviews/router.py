"""
Reviews Router — Phase 1: AI Review Responder
==============================================
C#/.NET equivalent: ReviewsController.cs

FastAPI routers are like ASP.NET controllers.
Each function decorated with @router.get/post/put is a controller action.

Route prefix is set in main.py: prefix="/api/v1/reviews"
So @router.get("/") → GET /api/v1/reviews/
   @router.post("/responses/{review_id}/approve") → POST /api/v1/reviews/responses/{review_id}/approve
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from core.auth import get_current_user
from core.database import supabase_admin, get_business_by_user, get_active_subscription
from core.ai_engine import generate_review_response
import logging
logger = logging.getLogger(__name__)

# ─── Router (equivalent to [ApiController] + [Route("api/v1/reviews")] in C#) ─
router = APIRouter()


# ─── Request/Response models (equivalent to DTOs / ViewModels in C#) ──────────
class GenerateResponseRequest(BaseModel):
    review_id: str


class ApproveResponseRequest(BaseModel):
    review_id: str
    final_response: str   # Owner may have edited the AI draft


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/")
async def list_reviews(
    current_user: dict = Depends(get_current_user),   # 👈 [Authorize] equivalent
):
    """
    GET /api/v1/reviews/
    Returns all reviews for the current user's business.

    C#/.NET equivalent:
        [HttpGet]
        [Authorize]
        public async Task<IActionResult> GetReviews() { ... }
    """
    business = await get_business_by_user(current_user["id"])
    if not business:
        raise HTTPException(status_code=404, detail="Business profile not found")

    # Check subscription is active
    subscription = await get_active_subscription(business["id"])
    if not subscription:
        raise HTTPException(status_code=403, detail="No active review responder subscription")

    # Query reviews from database
    result = (
        supabase_admin.table("reviews")
        .select("*, review_responses(*)")
        .eq("business_id", business["id"])
        .order("review_date", desc=True)
        .execute()
    )
    return {"reviews": result.data}


@router.post("/generate-response")
async def generate_response(
    request: GenerateResponseRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    POST /api/v1/reviews/generate-response
    Calls the AI engine to generate a draft response for a review.
    Saves the draft to the database. Owner then approves or edits.
    """
    business = await get_business_by_user(current_user["id"])
    if not business:
        raise HTTPException(status_code=404, detail="Business profile not found")

    # Fetch the review
    review_result = (
        supabase_admin.table("reviews")
        .select("*")
        .eq("id", request.review_id)
        .eq("business_id", business["id"])   # Security: ensure this review belongs to this business
        .single()
        .execute()
    )
    if not review_result.data:
        raise HTTPException(status_code=404, detail="Review not found")

    review = review_result.data

      # Fetch business settings (falls back to defaults if no row exists)
    settings_result = (
        supabase_admin.table("business_settings")
        .select("*")
        .eq("business_id", business["id"])
        .limit(1)
        .execute()
    )
    settings = settings_result.data[0] if settings_result.data else {}

    # Call AI engine with full context
    ai_draft = await generate_review_response(
        review_text=review["text"],
        reviewer_name=review["author"],
        rating=review["rating"],
        business_name=business["name"],
        business_type=business["type"],
        business_settings=settings,
        review_date=review.get("review_date"),
    )

    # Save the draft to the database
    supabase_admin.table("review_responses").upsert({
        "review_id":  request.review_id,
        "ai_draft":   ai_draft,
        "status":     "draft",
    }, on_conflict="review_id").execute()

    return {"ai_draft": ai_draft, "review_id": request.review_id}

class RegenerateRequest(BaseModel):
    review_id: str
    instructions: str  # e.g. "Make it shorter", "Be more apologetic"


@router.post("/regenerate-response")
async def regenerate_response(
    request: RegenerateRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    POST /api/v1/reviews/regenerate-response
    Re-generates the AI draft using additional instructions from the owner.
    """
    business = await get_business_by_user(current_user["id"])
    if not business:
        raise HTTPException(status_code=404, detail="Business profile not found")

    review_result = (
        supabase_admin.table("reviews")
        .select("*")
        .eq("id", request.review_id)
        .eq("business_id", business["id"])
        .single()
        .execute()
    )
    if not review_result.data:
        raise HTTPException(status_code=404, detail="Review not found")

    review = review_result.data

    settings_result = (
        supabase_admin.table("business_settings")
        .select("*")
        .eq("business_id", business["id"])
        .limit(1)
        .execute()
    )
    settings = settings_result.data[0] if settings_result.data else {}

    # Append owner instructions to the review text context
    enriched_text = f"{review['text']}\n\nOwner instruction: {request.instructions}"

    ai_draft = await generate_review_response(
        review_text=enriched_text,
        reviewer_name=review["author"],
        rating=review["rating"],
        business_name=business["name"],
        business_type=business["type"],
        business_settings=settings,
        review_date=review.get("review_date"),
    )

    supabase_admin.table("review_responses").upsert({
        "review_id": request.review_id,
        "ai_draft":  ai_draft,
        "status":    "draft",
    }, on_conflict="review_id").execute()

    return {"ai_draft": ai_draft, "review_id": request.review_id}

@router.post("/auto-draft-all")
async def auto_draft_all(
    current_user: dict = Depends(get_current_user),
):
    """
    POST /api/v1/reviews/auto-draft-all
    Generates AI drafts for all pending reviews that don't have one yet.
    Called on app load or on a schedule — owner then approves from the queue.
    """
    business = await get_business_by_user(current_user["id"])
    if not business:
        raise HTTPException(status_code=404, detail="Business profile not found")

    subscription = await get_active_subscription(business["id"])
    if not subscription:
        raise HTTPException(status_code=403, detail="No active subscription")

    settings_result = (
        supabase_admin.table("business_settings")
        .select("*")
        .eq("business_id", business["id"])
        .limit(1)
        .execute()
    )
    settings = settings_result.data[0] if settings_result.data else {}

    if not settings.get("auto_draft_enabled", True):
        return {"message": "Auto-draft is disabled for this business", "drafted": 0}

    # Fetch pending reviews that have no draft yet
    reviews_result = (
        supabase_admin.table("reviews")
        .select("*, review_responses(*)")
        .eq("business_id", business["id"])
        .eq("status", "pending")
        .execute()
    )

    pending = [
        r for r in (reviews_result.data or [])
        if not r.get("review_responses")
    ]

    drafted = 0
    for review in pending:
        try:
            ai_draft = await generate_review_response(
                review_text=review["text"],
                reviewer_name=review["author"],
                rating=review["rating"],
                business_name=business["name"],
                business_type=business["type"],
                business_settings=settings,
                review_date=review.get("review_date"),
            )
            supabase_admin.table("review_responses").upsert({
                "review_id": review["id"],
                "ai_draft":  ai_draft,
                "status":    "draft",
            }, on_conflict="review_id").execute()
            drafted += 1
        except Exception as e:
            logger.error(f"Failed to draft review {review['id']}: {e}")
            continue

    return {"message": f"Drafted {drafted} reviews", "drafted": drafted}

@router.post("/responses/{review_id}/approve")
async def approve_response(
    review_id: str,
    request: ApproveResponseRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    POST /api/v1/reviews/responses/{review_id}/approve
    Owner approves (and optionally edits) the AI draft.
    TODO Phase 1 Week 2: Actually post to Google Business Profile API.
    """
    business = await get_business_by_user(current_user["id"])
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    # Update the response record
    from datetime import datetime, timezone
    supabase_admin.table("review_responses").update({
        "final_response": request.final_response,
        "status":         "approved",
        "posted_at":      datetime.now(timezone.utc).isoformat(),
    }).eq("review_id", review_id).execute()

    # TODO: Post to Google Business Profile API
    # google_api.post_review_response(review_id, request.final_response)

    return {"message": "Response approved", "review_id": review_id}

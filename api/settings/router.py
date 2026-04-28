"""
Setting Router — Phase 1: Get Business Settings
==============================================


FastAPI routers are like ASP.NET controllers.
Each function decorated with @router.get/post/put is a controller action.

Route prefix is set in main.py: prefix="/api/v1/reviews"
So @router.get("/") → GET /api/v1/BusinessSetting/
  GET / — fetch current settings for the business. Query business_settings where business_id matches. 
  If no row exists yet, return the defaults 
  (you can see the defaults in the migration: tone_preference='casual', response_language='match_reviewer', response_length='medium', auto_draft_enabled=True, cta_enabled=True, delay_acknowledgment=False).

PUT / — save settings. The request body should accept all the configurable fields. Use upsert with on_conflict="business_id" — same pattern as the reviews router.

For the request model, the fields are:

tone_preference: str
response_language: str
response_length: str
business_description: Optional[str]
auto_draft_enabled: bool
cta_enabled: bool
cta_custom_text: Optional[str]
delay_acknowledgment: bool
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from core.auth import get_current_user
from core.database import supabase_admin, get_business_by_user
import logging
logger = logging.getLogger(__name__)

# ─── Router (equivalent to [ApiController] + [Route("api/v1/reviews")] in C#) ─
router = APIRouter()

# ─── Request/Response models (equivalent to DTOs / ViewModels in C#) ──────────
class BusinessSettingRequest(BaseModel):
    tone_preference: str
    response_language: str
    response_length: str
    business_description: Optional[str]
    auto_draft_enabled: bool
    cta_enabled: bool
    cta_custom_text: Optional[str]
    delay_acknowledgment: bool


@router.get("/")
async def business_settings(
    current_user: dict = Depends(get_current_user),   # 👈 [Authorize] equivalent
):
    """
    GET /api/v1/business_settings/
    Returns all business_settings for the current user's business.

    """
    business = await get_business_by_user(current_user["id"])
    if not business:
        raise HTTPException(status_code=404, detail="Business profile not found")


    # Query reviews from database
    result = (
        supabase_admin.table("business_settings")
        .select("*")
        .eq("business_id", business["id"])
        .execute()
    )
    # If no row exists yet, return the defaults 
    #  (you can see the defaults in the migration: tone_preference='casual', response_language='match_reviewer', response_length='medium', auto_draft_enabled=True, cta_enabled=True, delay_acknowledgment=False).
    if not result.data:
        default_settings = {
            "tone_preference": 'casual',
            "response_language": 'match_reviewer',
            "response_length": 'medium',
            "business_description": '',
            "auto_draft_enabled": True,
            "cta_enabled": True,
            "cta_custom_text": '',
            "delay_acknowledgment": False,
            "business_id": business["id"]
        }
        return {"business_settings": default_settings}
    return  {"business_settings": result.data[0]}


@router.put("/")
async def update_business_settings(
    request: BusinessSettingRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    PUT / — save settings. The request body should accept all the configurable fields. 
    Use upsert with on_conflict="business_id" — same pattern as the reviews router.

    """
    business = await get_business_by_user(current_user["id"])
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    # Upsert the business settings
    
    supabase_admin.table("business_settings").upsert({
       "tone_preference": request.tone_preference,
       "response_language": request.response_language,
       "response_length": request.response_length,
       "business_description": request.business_description,
       "auto_draft_enabled": request.auto_draft_enabled,
       "cta_enabled": request.cta_enabled,
       "delay_acknowledgment": request.delay_acknowledgment,
       "cta_custom_text": request.cta_custom_text,
       "business_id": business["id"]
    }, on_conflict="business_id").execute()

    return {"message": "Settings updated", "business_id": business["id"]}

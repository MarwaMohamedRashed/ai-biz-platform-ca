from fastapi import APIRouter, Depends, HTTPException
from core.ai_engine import generate_insights
from pydantic import BaseModel
from typing import Literal
from core.auth import get_current_user
from core.database import supabase_admin, get_business_by_user
import logging
logger = logging.getLogger(__name__)

# ─── Router (equivalent to [ApiController] + [Route("api/v1/reviews")] in C#) ─
router = APIRouter()

class GenerateInsightsRequest (BaseModel):
    period: Literal['30d', '90d', '6m', 'all']
    language: str = 'en'

@router.post("/generate-insights")
async def generate_insights_endpoint(
    request: GenerateInsightsRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    POST /api/v1/insights/generate-insights
    Calls the AI engine to generate insights for specific persion's reviews.
    """
    #Get the current user's business (use get_business_by_user from core.database)
    business = await get_business_by_user(current_user["id"])
    if not business:
        raise HTTPException(status_code=404, detail="Business profile not found")


    #Map the period to a start date (30d → today minus 30 days, 90d → minus 90, 6m → minus 180, all → no filter)
    period_mapping = {
        '30d': 30,
        '90d': 90,
        '6m': 180,
        'all': None
    }
    days = period_mapping.get(request.period)
    if days:
        from datetime import datetime, timedelta
        start_date = datetime.utcnow() - timedelta(days=days)   
   
     #Fetch reviews for that business in that date range from the reviews table — you only need rating, text, and status columns
    query = supabase_admin.table("reviews").select("rating, text, status").eq("business_id", business["id"])
    if days:
        query = query.gte("review_date", start_date.isoformat())
    result = query.execute()
    if not result.data:
            return {"insights": {}, "review_count": 0, "avg_rating": None}
    
    review = result.data
    #Compute avg_rating, review_count yourself (simple Python math)
    ratings = [r["rating"] for r in review if r.get("rating")]
    avg_rating = avg_rating = round(sum(ratings) / len(ratings), 1) if ratings else None
    review_count = len(review)
    #Call generate_insights() from core.ai_engine
    ai_result  = await generate_insights(
        reviews=review,
        business_name=business["name"],
        business_type=business["type"],
        language = request.language,
      
    )
    #Return the result
    return {"insights": ai_result , "review_count": review_count, "avg_rating": avg_rating}




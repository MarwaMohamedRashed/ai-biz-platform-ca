from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from core.ai_engine import ai_engine  # ✅
from core.auth import get_current_user
from core.database import supabase_admin, get_business_by_user
import httpx
import os
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")
SERPAPI_KEY = os.getenv("SERPAPI_KEY")
KNOWN_TYPES = {"restaurant", "salon", "retail", "plumber", "cafe"}

async def normalize_business_type(raw_type: str) -> str:
    if raw_type.lower() in KNOWN_TYPES:
        return raw_type
    result = await ai_engine.generate(
        prompt=f'Translate this business type to a short English phrase suitable for a search query: "{raw_type}". Reply with only the translated phrase, nothing else.',
        max_tokens=20,
        temperature=0.0,
    )
    return result.strip()

async def query_perplexity(business_name: str, business_type_en: str, city: str) -> dict:
    query = f"best {business_type_en} in {city}"
    
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
    mentioned = business_name.lower() in answer.lower()
    snippet = answer[:500] if mentioned else None

    return {"mentioned": mentioned, "snippet": snippet, "query": query}

async def query_google_ai_overview(business_name: str, business_type_en: str, city: str) -> dict:
    query = f"best {business_type_en} in {city}"

    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://serpapi.com/search",
            params={
                "api_key": SERPAPI_KEY,
                "engine": "google",
                "q": query,
                "location": city,
                "gl": "ca",
                "hl": "en",
            },
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()

    ai_overview = data.get("ai_overview", {})
    answer = ai_overview.get("text_blocks", [{}])[0].get("snippet", "") if ai_overview else ""
    mentioned = business_name.lower() in answer.lower() if answer else False
    snippet = answer[:500] if mentioned else None

    return {"mentioned": mentioned, "snippet": snippet, "query": query}

class AuditRequest(BaseModel):
    business_id: str

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

    business_name = business["name"]
    city = business["city"]
    business_type_en = await normalize_business_type(business["type"])

    perplexity_result = await query_perplexity(business_name, business_type_en, city)
    google_result = await query_google_ai_overview(business_name, business_type_en, city)

    score = 0
    if perplexity_result["mentioned"]:
        score += 50
    if google_result["mentioned"]:
        score += 50

    supabase_admin.table("aeo_audits").insert({
        "business_id":          business["id"],
        "score":                score,
        "perplexity_mentioned": perplexity_result["mentioned"],
        "perplexity_snippet":   perplexity_result["snippet"],
        "google_ai_mentioned":  google_result["mentioned"],
        "google_ai_snippet":    google_result["snippet"],
        "raw_results": {
            "perplexity": perplexity_result,
            "google_ai":  google_result,
        },
    }).execute()

    return {
        "score":      score,
        "perplexity": perplexity_result,
        "google_ai":  google_result,
    }
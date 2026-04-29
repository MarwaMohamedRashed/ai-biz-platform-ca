from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from core.auth import get_current_user
from core.database import supabase_admin, get_business_by_user
import httpx
import os
from urllib.parse import quote

router = APIRouter()

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
SCOPES = "https://www.googleapis.com/auth/business.manage"

BASE_API_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
BASE_WEB_URL = os.getenv("WEB_BASE_URL", "http://localhost:3000")

REDIRECT_URI = f"{BASE_API_URL}/api/v1/google-auth/callback"

@router.get("/connect")
async def connect_google(current_user: dict = Depends(get_current_user)):
    # Build the Google OAuth URL and redirect the owner to it
    # Include state=current_user["id"] so the callback knows which user this is
    auth_url = (
        f"https://accounts.google.com/o/oauth2/v2/auth"
        f"?client_id={GOOGLE_CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&response_type=code"
        f"&scope={quote(SCOPES)}"
        f"&access_type=offline"
        f"&prompt=consent"
        f"&state={current_user['id']}"
    )

   
    return RedirectResponse(url=auth_url)


@router.get("/callback")
async def google_callback(code: str, state: str):
    # 1. Exchange code for tokens using httpx POST to Google token endpoint
    # 2. Fetch account ID from mybusinessaccountmanagement API
    # 3. Fetch location ID from mybusinessbusinessinformation API
    # 4. Save tokens + IDs to businesses table where user_id = state
    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri": REDIRECT_URI,
                "grant_type": "authorization_code",
            }
        )
        tokens = token_response.json()
        if "access_token" not in tokens:
            raise HTTPException(status_code=400, detail="Failed to get access token from Google")
        access_token = tokens["access_token"]
        refresh_token = tokens.get("refresh_token")
        accounts_response = await client.get(
            "https://mybusinessaccountmanagement.googleapis.com/v1/accounts",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        accounts = accounts_response.json()
        if not accounts.get("accounts"):
            raise HTTPException(status_code=400, detail="No Google Business account found")
        
        account_id = accounts["accounts"][0]["name"]  # looks like "accounts/123456789"

        locations_response = await client.get(
            f"https://mybusinessbusinessinformation.googleapis.com/v1/{account_id}/locations",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"readMask": "name"}
        )
        locations = locations_response.json()
        if not locations.get("locations"):
            raise HTTPException(status_code=400, detail="No Google Business location found")
        location_id = locations["locations"][0]["name"]  # looks like "locations/123456789"
        business = await get_business_by_user(state)
        if not business:
            raise HTTPException(status_code=404, detail="Business not found")

        supabase_admin.table("businesses").update({
            "google_access_token": access_token,
            "google_refresh_token": refresh_token,
            "google_account_id": account_id,
            "google_location_id": location_id,
        }).eq("id", business["id"]).execute()

        return RedirectResponse(url=f"{BASE_WEB_URL}/en/dashboard/settings?google=connected")

    
  
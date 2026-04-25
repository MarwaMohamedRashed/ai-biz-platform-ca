"""
Auth — JWT Middleware & Dependencies
======================================
FastAPI uses "dependency injection" for auth — similar to [Authorize] in ASP.NET,
but declared per-route using Depends() instead of attributes.

C#/.NET equivalent:
    [Authorize]                  → Depends(get_current_user)
    [Authorize(Roles="Admin")]   → Depends(require_admin)
    HttpContext.User.FindFirst() → current_user["id"]

How it works:
    1. Frontend sends JWT in Authorization: Bearer <token> header
    2. get_current_user() validates the token with Supabase
    3. Returns the user dict — available in any route that declares it
    4. Raises 401 automatically if token is missing or invalid
"""

import os
import logging
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from supabase import create_client

logger = logging.getLogger(__name__)

SUPABASE_URL      = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

# Tells FastAPI to look for a Bearer token in the Authorization header
bearer_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    """
    Validates the JWT token from the request header.
    Use as a dependency in any route that requires authentication.
    """
    token = credentials.credentials

    try:
        client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
        user_response = client.auth.get_user(token)

        if not user_response or not user_response.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            )

        return {
            "id":    user_response.user.id,
            "email": user_response.user.email,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Auth validation error: {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer(auto_error=False)),
) -> dict | None:
    """
    Same as get_current_user but doesn't raise if no token present.
    Useful for routes that work for both logged-in and anonymous users.
    """
    if not credentials:
        return None
    try:
        return await get_current_user(credentials)
    except HTTPException:
        return None

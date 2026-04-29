"""
AI Business Platform — FastAPI Backend
Entry point: uvicorn main:app --reload
Auto-generated docs: http://localhost:8000/docs  (like Swagger in ASP.NET)
"""
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Product routers — each product has its own route namespace
from reviews.router import router as reviews_router
from bookings.router import router as bookings_router
from startup.router import router as startup_router
from insights.router import router as insights_router
from settings.router import router as settings_router
from google_auth.router import router as google_auth_router

app = FastAPI(
    title="AI Business Platform API",
    description="Backend for Canadian small business AI tools",
    version="1.0.0",
)

# ─── CORS (equivalent to app.UseCors() in ASP.NET) ───────────────────────────
import os
WEB_BASE_URL = os.getenv("WEB_BASE_URL", "http://localhost:3000")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        WEB_BASE_URL,
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Route registration (equivalent to MapControllers in ASP.NET) ─────────────
# Each product has its own prefix — they share auth + DB middleware
app.include_router(reviews_router,  prefix="/api/v1/reviews",  tags=["reviews"])
app.include_router(bookings_router, prefix="/api/v1/bookings", tags=["bookings"])
app.include_router(startup_router,  prefix="/api/v1/startup",  tags=["startup"])
app.include_router(insights_router,  prefix="/api/v1/insights",  tags=["insights"])
app.include_router(settings_router,  prefix="/api/v1/settings",  tags=["settings"])
app.include_router(google_auth_router, prefix="/api/v1/google-auth", tags=["google-auth"])


# ─── Health check ─────────────────────────────────────────────────────────────
@app.get("/health")
async def health_check():
    """Railway and Vercel use this to confirm the service is running."""
    return {"status": "ok", "service": "ai-biz-platform-api"}

# ─── Run directly (development only) ─────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

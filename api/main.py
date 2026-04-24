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


app = FastAPI(
    title="AI Business Platform API",
    description="Backend for Canadian small business AI tools",
    version="1.0.0",
)

# ─── CORS (equivalent to app.UseCors() in ASP.NET) ───────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",        # Local Next.js dev
        "https://your-domain.vercel.app",  # Production frontend
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


# ─── Health check ─────────────────────────────────────────────────────────────
@app.get("/health")
async def health_check():
    """Railway and Vercel use this to confirm the service is running."""
    return {"status": "ok", "service": "ai-biz-platform-api"}

# ─── Run directly (development only) ─────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

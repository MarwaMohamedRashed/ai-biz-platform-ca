# FastAPI & Async Python for LeapOne
**Time:** ~3 hours | **Goal:** Build and understand the LeapOne backend API

---

## 1. What FastAPI Is

FastAPI is a Python framework for building REST APIs. It handles:
- Routing (which URL calls which function)
- Request/response parsing
- Input validation
- Auto-generated API docs (free, at `/docs`)
- Authentication middleware

Your frontend (Next.js) calls these endpoints. Your background jobs (syncing reviews) also run here.

---

## 2. Your First FastAPI App

```python
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def root():
    return {"message": "LeapOne API is running"}

@app.get("/health")
def health():
    return {"status": "ok"}
```

Run it:
```bash
uvicorn main:app --reload
```

Visit `http://localhost:8000/docs` — FastAPI generates interactive API docs automatically.

---

## 3. Routes and Path Parameters

```python
# GET /businesses/123/reviews
@app.get("/businesses/{business_id}/reviews")
def get_reviews(business_id: str):
    return {"business_id": business_id, "reviews": []}

# GET /reviews/456
@app.get("/reviews/{review_id}")
def get_review(review_id: str):
    return {"review_id": review_id}
```

---

## 4. Query Parameters

```python
# GET /reviews?status=pending&limit=10
@app.get("/reviews")
def list_reviews(status: str = "pending", limit: int = 20):
    return {"status": status, "limit": limit}
```

FastAPI reads these from the URL automatically. The `= "pending"` is the default value.

---

## 5. Request Body with Pydantic

Pydantic validates incoming data automatically. If the request doesn't match, FastAPI returns a 422 error with a clear message.

```python
from pydantic import BaseModel
from typing import Optional

class ApproveReviewRequest(BaseModel):
    review_id: str
    final_response: str
    edited: bool = False   # optional, defaults to False

@app.post("/reviews/approve")
def approve_review(body: ApproveReviewRequest):
    # body.review_id, body.final_response, body.edited are all validated
    return {"approved": True, "review_id": body.review_id}
```

---

## 6. Response Models

```python
from pydantic import BaseModel
from datetime import datetime

class ReviewResponse(BaseModel):
    id: str
    author: str
    rating: int
    text: str
    status: str
    created_at: datetime

@app.get("/reviews/{review_id}", response_model=ReviewResponse)
def get_review(review_id: str):
    # FastAPI validates the return value matches ReviewResponse
    return {
        "id": review_id,
        "author": "John Smith",
        "rating": 2,
        "text": "Waited 45 minutes",
        "status": "pending",
        "created_at": datetime.now()
    }
```

---

## 7. Async Python

Some operations take time — calling Google's API, querying the database, calling OpenAI. While waiting, Python can handle other requests. That's what `async/await` does.

### The pattern:
```python
# Regular function — blocks while waiting
def get_reviews_sync():
    result = database.query(...)   # waits here, nothing else can run
    return result

# Async function — yields control while waiting
async def get_reviews_async():
    result = await database.query(...)   # waits but other requests can run
    return result
```

### In FastAPI — use `async def` for anything that calls external services:

```python
import httpx   # async HTTP client

@app.get("/sync-reviews/{business_id}")
async def sync_reviews(business_id: str):
    # Call Google API asynchronously
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://mybusiness.googleapis.com/v4/accounts/{business_id}/locations",
            headers={"Authorization": f"Bearer {token}"}
        )
    
    reviews = response.json()
    return {"synced": len(reviews)}
```

### Calling OpenAI asynchronously:
```python
from openai import AsyncOpenAI

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

async def generate_review_response(review_text: str, business_name: str) -> str:
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": f"You help {business_name} respond to Google reviews professionally."},
            {"role": "user", "content": f"Write a response to: {review_text}"}
        ]
    )
    return response.choices[0].message.content
```

**Rule of thumb:** Use `async def` when the function calls an external service (database, API, file). Use regular `def` for pure logic.

---

## 8. Dependency Injection

FastAPI has a powerful system to share logic across routes — authentication, database connections, etc.

```python
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer

security = HTTPBearer()

async def get_current_user(token = Depends(security)):
    # Verify the JWT token from Supabase
    try:
        user = verify_supabase_jwt(token.credentials)
        return user
    except:
        raise HTTPException(status_code=401, detail="Invalid token")

# Now protect any route by adding it as a dependency
@app.get("/reviews")
async def get_reviews(user = Depends(get_current_user)):
    # user is available here, already verified
    return fetch_reviews_for_user(user.id)
```

---

## 9. Error Handling

```python
from fastapi import HTTPException

@app.get("/reviews/{review_id}")
async def get_review(review_id: str):
    review = await db.get_review(review_id)
    
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    
    return review
```

Common HTTP status codes:
| Code | Meaning | When to use |
|---|---|---|
| 200 | OK | Successful GET |
| 201 | Created | Successful POST that creates something |
| 400 | Bad Request | Invalid input |
| 401 | Unauthorized | Not logged in |
| 403 | Forbidden | Logged in but no permission |
| 404 | Not Found | Resource doesn't exist |
| 500 | Server Error | Unexpected error |

---

## 10. Project Structure for LeapOne

```
api/
├── main.py              ← FastAPI app, all routes registered here
├── routers/
│   ├── reviews.py       ← /reviews endpoints
│   ├── businesses.py    ← /businesses endpoints
│   └── auth.py          ← /auth endpoints
├── services/
│   ├── ai_engine.py     ← OpenAI calls
│   ├── google_api.py    ← Google Business Profile calls
│   └── supabase.py      ← Supabase client + helper functions
├── models/
│   └── schemas.py       ← Pydantic request/response models
└── .env                 ← Environment variables (never commit)
```

### `main.py` — how routers connect:
```python
from fastapi import FastAPI
from routers import reviews, businesses, auth

app = FastAPI(title="LeapOne API")

app.include_router(auth.router,       prefix="/auth")
app.include_router(businesses.router, prefix="/businesses")
app.include_router(reviews.router,    prefix="/reviews")
```

### A complete router example — `routers/reviews.py`:
```python
from fastapi import APIRouter, Depends
from services.supabase import get_supabase
from services.ai_engine import generate_review_response

router = APIRouter()

@router.get("/")
async def list_reviews(status: str = "pending", supabase = Depends(get_supabase)):
    result = supabase.table("reviews") \
        .select("*") \
        .eq("status", status) \
        .execute()
    return result.data

@router.post("/{review_id}/approve")
async def approve_review(review_id: str, supabase = Depends(get_supabase)):
    supabase.table("reviews") \
        .update({"status": "responded"}) \
        .eq("id", review_id) \
        .execute()
    return {"approved": True}
```

---

## 11. Running and Installing

**Install dependencies:**
```bash
pip install fastapi uvicorn[standard] supabase openai httpx python-dotenv pydantic
```

Or using a `requirements.txt`:
```
fastapi==0.111.0
uvicorn[standard]==0.29.0
supabase==2.4.0
openai==1.30.0
httpx==0.27.0
python-dotenv==1.0.1
pydantic==2.7.0
```

**Run locally:**
```bash
uvicorn main:app --reload --port 8000
```

**Auto-generated docs:** `http://localhost:8000/docs`

---

## Quick Reference

| Concept | Syntax |
|---|---|
| GET route | `@app.get("/path")` |
| POST route | `@app.post("/path")` |
| Path param | `def fn(id: str):` in route `/path/{id}` |
| Query param | `def fn(status: str = "pending"):` |
| Request body | `class Body(BaseModel):` + `def fn(body: Body):` |
| Async route | `async def fn():` + `await` inside |
| Auth guard | `Depends(get_current_user)` |
| Error | `raise HTTPException(status_code=404, detail="...")` |

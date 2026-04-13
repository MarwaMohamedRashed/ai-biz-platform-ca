# Python Essentials for LeapOne
**Time:** ~2 hours | **Goal:** Write real Python code for this project

---

## 1. Variables and Types

Python infers the type — you never declare it.

```python
name = "LeapOne"
rating = 5
price = 29.99
is_active = True
nothing = None
```

---

## 2. Strings

```python
business = "Salon"
city = "Milton"

# Combine with f-strings (use these everywhere)
message = f"Welcome to {business} in {city}"

# Multi-line string
prompt = """
You are an AI assistant helping a small business owner
respond to Google reviews professionally.
"""

# Common string methods
text = "  hello world  "
text.strip()        # "hello world"
text.upper()        # "  HELLO WORLD  "
text.replace("hello", "hi")  # "  hi world  "
```

---

## 3. Lists

Ordered, changeable collection.

```python
reviews = ["Great service!", "Too slow", "Amazing"]

# Access
reviews[0]      # "Great service!"
reviews[-1]     # "Amazing" (last item)

# Add / remove
reviews.append("Very clean")
reviews.remove("Too slow")

# Loop
for review in reviews:
    print(review)

# Length
len(reviews)    # 3
```

---

## 4. Dictionaries

Key-value pairs — you'll use these constantly.

```python
business = {
    "name": "Main St Salon",
    "city": "Milton",
    "rating": 4.8,
    "is_active": True
}

# Access
business["name"]            # "Main St Salon"
business.get("phone", "")   # "" if key doesn't exist (safe access)

# Add / update
business["province"] = "ON"
business["rating"] = 4.9

# Loop
for key, value in business.items():
    print(f"{key}: {value}")
```

---

## 5. Functions

```python
def generate_response(review_text: str, business_name: str) -> str:
    return f"Thank you for your review of {business_name}. {review_text}"

# Call it
response = generate_response("Great service!", "Main St Salon")
```

**Type hints** (`str`, `int`, `bool`) are optional but recommended — they make your code clearer and help your editor catch mistakes.

```python
def calculate_response_rate(responded: int, total: int) -> float:
    if total == 0:
        return 0.0
    return responded / total * 100
```

---

## 6. Classes

A class is a blueprint for an object.

```python
class Review:
    def __init__(self, author: str, rating: int, text: str):
        self.author = author
        self.rating = rating
        self.text = text
        self.status = "pending"

    def is_negative(self) -> bool:
        return self.rating <= 2

    def __repr__(self):
        return f"Review({self.author}, {self.rating} stars)"


# Create instances
review = Review("John Smith", 2, "Waited 45 minutes")
review.is_negative()    # True
review.status           # "pending"
```

---

## 7. Conditionals

```python
rating = 2

if rating <= 2:
    priority = "urgent"
elif rating == 3:
    priority = "normal"
else:
    priority = "low"

# One-liner (ternary)
label = "negative" if rating <= 2 else "positive"
```

---

## 8. Error Handling

```python
try:
    result = call_google_api(business_id)
except Exception as e:
    print(f"API call failed: {e}")
    result = None
finally:
    # Always runs
    log_attempt(business_id)
```

---

## 9. Imports and Modules

```python
# Built-in
import os
import json
from datetime import datetime

# Third-party (installed via pip)
from fastapi import FastAPI
from supabase import create_client

# Your own files
from app.services.ai_engine import generate_response
```

---

## 10. List Comprehensions

A concise way to build lists — used everywhere in Python.

```python
reviews = [
    {"rating": 5, "text": "Great"},
    {"rating": 2, "text": "Bad"},
    {"rating": 4, "text": "Good"},
]

# Get only negative reviews
negative = [r for r in reviews if r["rating"] <= 2]

# Get all ratings as a list
ratings = [r["rating"] for r in reviews]   # [5, 2, 4]

# Average rating
avg = sum(ratings) / len(ratings)           # 3.67
```

---

## 11. Working with JSON

FastAPI and Supabase both use JSON. Python handles it natively.

```python
import json

# Python dict → JSON string
data = {"name": "LeapOne", "rating": 4.8}
json_string = json.dumps(data)

# JSON string → Python dict
parsed = json.loads('{"name": "LeapOne"}')
parsed["name"]   # "LeapOne"
```

In FastAPI you rarely call `json.dumps` directly — it handles it automatically.

---

## 12. Environment Variables

Never hardcode secrets. Use environment variables.

```python
import os

supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SERVICE_KEY")
openai_key   = os.getenv("OPENAI_API_KEY")
```

These come from a `.env` file (never committed to GitHub):
```
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_KEY=eyJ...
OPENAI_API_KEY=sk-...
```

---

## Quick Reference Card

| Concept | Syntax |
|---|---|
| Variable | `x = 5` |
| f-string | `f"Hello {name}"` |
| List | `items = [1, 2, 3]` |
| Dict | `d = {"key": "value"}` |
| Function | `def name(param: type) -> return_type:` |
| If/else | `if x > 0:` / `elif` / `else:` |
| For loop | `for item in list:` |
| Try/catch | `try:` / `except Exception as e:` |
| Import | `from module import thing` |
| Env var | `os.getenv("KEY")` |

# Supabase & RLS for LeapOne
**Time:** ~1 hour | **Goal:** Understand how to use Supabase in code and how RLS protects data

---

## 1. What Supabase Gives You

One Supabase project gives you:
- **PostgreSQL database** — all your tables
- **Auth** — handles signup, login, Google OAuth, sessions, JWTs
- **Auto-generated REST API** — query your tables without writing SQL endpoints
- **Realtime** — live updates (useful later for notifications)
- **Vault** — encrypted secret storage (used for Google OAuth tokens)
- **Storage** — file uploads (not needed in Phase 1)

---

## 2. Two Supabase Clients

You will use two different clients depending on where the code runs:

### Frontend (Next.js) — `anon` key
```javascript
import { createClient } from '@supabase/supabase-js'

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
)
```
- Uses the `anon` (public) key
- **RLS is enforced** — user can only see their own data
- Safe to expose in the browser

### Backend (FastAPI) — `service_role` key
```python
from supabase import create_client

supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_KEY")   # service_role key
)
```
- Uses the `service_role` key
- **RLS is bypassed** — can read/write any row
- **Never expose this key in the frontend**
- Used for: syncing reviews from Google, writing AI drafts, sending notifications

---

## 3. Querying Data

### Select
```python
# Get all reviews for a business
result = supabase.table("reviews") \
    .select("*") \
    .eq("business_id", business_id) \
    .eq("status", "pending") \
    .execute()

reviews = result.data   # list of dicts
```

### Insert
```python
result = supabase.table("reviews").insert({
    "business_id": business_id,
    "google_review_id": "ChIJ...",
    "author": "John Smith",
    "rating": 2,
    "text": "Waited 45 minutes",
    "status": "pending"
}).execute()

new_review = result.data[0]
```

### Update
```python
result = supabase.table("reviews") \
    .update({"status": "responded"}) \
    .eq("id", review_id) \
    .execute()
```

### Delete
```python
supabase.table("reviews") \
    .delete() \
    .eq("id", review_id) \
    .execute()
```

---

## 4. Auth in the Frontend

### Sign in with Google
```javascript
const { data, error } = await supabase.auth.signInWithOAuth({
  provider: 'google',
  options: {
    redirectTo: 'https://leapone.ca/auth/callback'
  }
})
```
Google opens → user approves → Supabase creates/updates the user → redirects back.

### Sign out
```javascript
await supabase.auth.signOut()
```

### Get current user
```javascript
const { data: { user } } = await supabase.auth.getUser()
// user.id  → the UUID that matches profiles.id
// user.email
```

### Listen for auth state changes
```javascript
supabase.auth.onAuthStateChange((event, session) => {
  if (event === 'SIGNED_IN') {
    // redirect to dashboard
  }
  if (event === 'SIGNED_OUT') {
    // redirect to login
  }
})
```

---

## 5. How RLS Works in Practice

Every query from the frontend automatically filters by the logged-in user.

```javascript
// This returns ONLY reviews belonging to the logged-in user's business
// RLS policy handles the filtering — you write no WHERE clause for ownership
const { data: reviews } = await supabase
  .from('reviews')
  .select('*')
  .eq('status', 'pending')
```

If the user is not logged in → returns empty array (not an error).
If the user tries to access another business's data → returns empty array.

**You never need to add `WHERE user_id = current_user` in frontend queries.**

---

## 6. The `profiles` Table Pattern

Supabase Auth manages `auth.users`. When a user signs up, your trigger automatically creates a row in `profiles`. To get the current user's profile:

```javascript
const { data: profile } = await supabase
  .from('profiles')
  .select('*')
  .single()   // returns one row, not an array
```

To get the business:
```javascript
const { data: business } = await supabase
  .from('businesses')
  .select('*')
  .single()
```

RLS ensures `.single()` returns only their own business.

---

## 7. Supabase Vault (for Google tokens)

OAuth tokens are sensitive. You store them in Vault, not as plain text.

**Store a token (backend only):**
```python
# Store the token in vault, get back a secret ID (UUID)
result = supabase.rpc('vault.create_secret', {
    'secret': access_token,
    'name': f'google_access_token_{business_id}'
}).execute()

secret_id = result.data   # UUID — store this in review_connections
```

**Read a token (backend only):**
```python
result = supabase.table('vault.decrypted_secrets') \
    .select('decrypted_secret') \
    .eq('id', secret_id) \
    .single() \
    .execute()

token = result.data['decrypted_secret']
```

---

## 8. Environment Variables for Supabase

You need these in both frontend and backend:

**Frontend `.env.local`:**
```
NEXT_PUBLIC_SUPABASE_URL=https://qxoyrrmmmozjzddpyhvt.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJ...
```

**Backend `.env`:**
```
SUPABASE_URL=https://qxoyrrmmmozjzddpyhvt.supabase.co
SUPABASE_SERVICE_KEY=eyJ...   ← different from anon key, never expose
```

Find both keys in Supabase dashboard → **Settings → API**.

---

## Quick Reference

| Task | Method |
|---|---|
| Select rows | `.table("x").select("*").eq("col", val).execute()` |
| Insert row | `.table("x").insert({...}).execute()` |
| Update row | `.table("x").update({...}).eq("id", id).execute()` |
| Delete row | `.table("x").delete().eq("id", id).execute()` |
| Get one row | add `.single()` before `.execute()` |
| Sign in Google | `supabase.auth.signInWithOAuth({ provider: 'google' })` |
| Get user | `supabase.auth.getUser()` |
| Sign out | `supabase.auth.signOut()` |

# Path A — Content Feature Rebuild Plan

**Goal:** Bring the Content tab to a quality level where we are not embarrassed if a developer customer or a journalist looks closely. No beta labels, no caveats — it just works and competes.

**Estimated effort:** 2 sprints (~2 weeks of focused work).

**Mode:** Learning. The plan defines what to build and the acceptance criteria. You write the code; I review.

---

## Why this order

1. **Schema and FAQ are dangerous as-is.** Wrong schema can trigger Google penalties; FAQ without `FAQPage` JSON-LD does almost nothing for AEO. Fix the dangerous + low-value-as-shipped pieces first.
2. **Profile fields are the dependency.** The deterministic schema builder needs real address, phone, hours, image. We can't build the schema generator until the form collects these.
3. **Description quality and bilingual come after correctness.** They make the feature competitive; they don't fix the reputation risk.

---

## Sprint A1 — Correctness (≈1 week)

The "do not embarrass us" sprint. After this, the schema and FAQ outputs are correct and validated.

### Step 1 — Extend the `businesses` table
Migration 015 adds the fields the schema generator needs.

| Column | Type | Required for | Notes |
|---|---|---|---|
| `street_address` | text | Schema, GBP audit | Free text, e.g. "123 Bank St" |
| `postal_code` | text | Schema, GBP audit | Canadian format `K1P 5N7` |
| `phone` | text | Schema, GBP audit | E.164 ideally, but accept human format and normalize |
| `hours` | jsonb | Schema | `{ "monday": "09:00-17:00", ... }` shape |
| `image_url` | text | Schema | Logo or building photo |
| `price_range` | text | Schema | `$`, `$$`, `$$$`, `$$$$` |
| `country` | text default `'CA'` | Schema | Already implied; make explicit |

**Acceptance:** Migration applied. New columns nullable so existing rows don't break.

### Step 2 — Update the business profile form
Add inputs for the new fields in `apps/web/components/dashboard/SettingsPage.tsx` and onboarding wizard.

- Street address: text input
- Postal code: text input with regex hint for Canadian postal code
- Phone: text input with format placeholder
- Hours: 7 day-of-week rows, each with open/close time pickers (or "Closed" toggle)
- Image URL: text input (later we can add upload, not now)
- Price range: dropdown `$ / $$ / $$$ / $$$$`

**Acceptance:** Existing users can fill these in; new users see them in onboarding. Form saves to the new columns.

### Step 3 — Build the deterministic schema generator (the critical one)
Replace the LLM call in `generate-content` for `schema_markup` with a Python function `build_schema(business: dict) -> dict`.

Two parts:

**Part 3a — Business-type → Schema.org subtype mapping**
Add a dict in `api/aeo/schema_builder.py` mapping our business-type values to specific Schema.org `@type` strings.

```python
BUSINESS_TYPE_TO_SCHEMA = {
    "dentist": "Dentist",
    "restaurant": "Restaurant",
    "bakery": "Bakery",
    "beauty_salon": "BeautySalon",
    "physiotherapy": "Physiotherapy",
    # ... cover all values from our onboarding business-type list
    # fallback: "LocalBusiness"
}
```

**Part 3b — Deterministic builder**
A pure function that takes business data and returns a validated dict (no LLM):

```python
def build_schema(b: dict) -> dict:
    return {
        "@context": "https://schema.org",
        "@type": BUSINESS_TYPE_TO_SCHEMA.get(b["type"], "LocalBusiness"),
        "name": b["name"],
        "image": b["image_url"],
        "telephone": b["phone"],
        "priceRange": b["price_range"],
        "address": {
            "@type": "PostalAddress",
            "streetAddress": b["street_address"],
            "addressLocality": b["city"],
            "addressRegion": b["province"],
            "postalCode": b["postal_code"],
            "addressCountry": b.get("country", "CA"),
        },
        "geo": {...} if has_lat_lng else None,
        "openingHoursSpecification": _hours_to_schema(b["hours"]),
        "url": b["website"],
        "description": b.get("description"),  # the AI-generated description
    }
```

**Validation:** Strip nulls, validate keys against a Pydantic model, run `extruct` round-trip parse to confirm the output is valid JSON-LD.

**Acceptance:**
- Output passes Google's Rich Results Test for the business types we care about (test 3–5 manually).
- No hallucinated values — every field traces back to the DB.
- Missing required fields → clear error to the user telling them which profile fields to fill in (not a half-broken schema).

### Step 4 — Frontend schema block improvements
In `ContentPage.tsx`:

- Wrap copied output in `<script type="application/ld+json">...</script>` — the customer pastes a complete script tag, not loose JSON.
- Add a "Test in Google Rich Results" button that opens `https://search.google.com/test/rich-results?code=<urlencoded JSON-LD>` in a new tab.
- If the user is missing required profile fields, show a clear "Complete your profile to generate schema" CTA linking to settings, instead of generating a broken schema.

**Acceptance:** Pasting the copy output directly into a `<head>` works. Rich Results Test passes.

### Step 5 — FAQ → `FAQPage` JSON-LD
Two changes:

**5a — Generate 10 Q&As, not 5.** Update the prompt to ask for 10. Tell the LLM the answers should be 40–80 words each (Google's sweet spot for FAQ rich results).

**5b — Wrap output in `FAQPage` JSON-LD** server-side, return alongside the human-readable Q&A list:

```python
{
  "faq": [{"question": "...", "answer": "..."}, ...],
  "faq_schema": {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    "mainEntity": [
      {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}}
      for each
    ]
  }
}
```

Frontend: show the Q&A list as we do now, plus a second "FAQ Schema (JSON-LD)" copy block (with `<script>` wrapper) below it.

**Acceptance:** FAQ schema passes Rich Results Test. Customer can paste it on a `/faq` page and get rich results.

### Step 6 — Pass `services` into the description prompt
Currently we fetch `services` from the DB but the prompt doesn't get it specifically called out. Quick win: include "Mention these services specifically: {services}" in the prompt. ~10 lines.

**Acceptance:** Description outputs name the actual services for businesses that filled them in.

---

## Sprint A2 — Quality + bilingual (≈1 week)

After A1, the feature is correct. After A2, it's competitive.

### Step 7 — "People Also Ask" grounding for FAQ
Before generating the FAQ, query SerpApi (we already pay for it) with `"<business_type> in <city>"` and pull the `related_questions` field. Pass these real questions to the LLM with the prompt: "Answer these questions for this business: [list]. If a question doesn't apply, write your own variant."

**Acceptance:** FAQ questions match real user queries (verifiable by re-running the SerpApi query and seeing overlap).

### Step 8 — Per-platform descriptions
Generate 4 description variants instead of 1:

| Variant | Length | Tone | Notes |
|---|---|---|---|
| Website | 300–400 words | Detailed, third person | For the homepage / About page |
| Google Business Profile | 600–750 chars (hard cap) | Direct, benefit-focused | GBP description field |
| Yelp / directories | 200–250 words | Concise, mentions services | Yelp-style |
| Social bio | 150 chars | Punchy | Already exists, keep |

UI: tabs or an accordion above the description block. Each variant has its own copy button.

**Acceptance:** All 4 variants generated in one API call. No platform variant exceeds its character cap.

### Step 9 — French variants
For users with `locale = "fr"` (or a "Generate French version" toggle):
- Run all generators in French — description (4 variants), FAQ (10 Q&As), social bio
- Schema generator already language-agnostic; the `description` field embedded in schema should match the locale
- French `FAQPage` works the same — French questions, French answers

UI: language toggle on the Content tab. Default to user locale.

**Acceptance:** Quebec SMB user sees French content by default. Toggle works both ways.

### Step 10 — Server-side validation pass
Before returning any generated content, validate:
- Description: word counts within target range per variant
- FAQ: exactly 10 items, each `question` non-empty, each `answer` 40–80 words
- Schema: passes Pydantic + `extruct` round-trip
- Social bio: ≤ 150 chars

If validation fails, retry the LLM call once. If it fails twice, return what we have with a flag — don't ship malformed output to the user.

**Acceptance:** Customer never sees malformed JSON or out-of-spec content.

---

## Out of scope for Path A (deferred to F10–F12)

Not because they're unimportant — because shipping them now delays launch without removing reputation risk:

- Free public AEO grader at `leapone.ca/grade` (F10 — top-of-funnel vs HubSpot)
- Competitor benchmarking (F11 — the audit-side moat)
- Competitor weak-point mining (F12)
- AI-crawler analytics (F13)
- PDF export (F10 if quick)

---

## Acceptance for the launch gate

Before we flip `BILLING_ENABLED=true` and announce:

1. ✅ Schema passes Google Rich Results Test for at least 5 different business types
2. ✅ FAQ schema passes Rich Results Test
3. ✅ Description respects per-platform character limits
4. ✅ FR variants render correctly for a test FR business
5. ✅ Profile form has all schema-required fields, with validation
6. ✅ Missing profile fields → clear "complete your profile" UX, not broken output
7. ✅ End-to-end manual test: new user signs up → fills profile → runs audit → generates content → pastes schema on a real test page → Rich Results Test passes

---

## Suggested starting point

**Step 1 (migration 015)** is the right place to start. It's small, it's the dependency for everything else, and it's the kind of thing where I can review your migration SQL quickly.

Want me to walk you through Step 1 first — what columns to add, types, defaults, the migration file structure? Or do you want to look at the whole sprint first and pick a different starting point?

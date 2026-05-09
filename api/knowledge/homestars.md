---
key: homestars
applies_to: recommendation
match_titles:
  - Claim your HomeStars profile
last_updated: 2026-05-09
---

# HomeStars — what to know when guiding the owner

## What it is, briefly
HomeStars is Canada's largest residential trades directory. Owned by
Angi (formerly HomeAdvisor) but operates under the HomeStars brand in
Canada. Free contractor signup; reviews are the primary ranking factor.

## The signup form — what each field actually means

When the owner is on the form at homestars.com/create-account, they
hit these fields:

- **Business name**: must match the legal business name (matters if
  they're applying for the verified badge later)
- **Service area**: HomeStars asks for cities, but internally indexes
  by Forward Sortation Area (FSA — first 3 chars of postal code).
  Owners often type their city; that works. Power-users add multiple
  FSAs to expand coverage (e.g., a Toronto plumber serving K1P, K2A,
  M5V, etc.)
- **Trade categories**: pick **1 primary + up to 3 secondary**. The
  primary affects ranking heavily; secondary categories drive long-tail
  search matches. Example for a plumber: primary "Plumber"; secondary
  "Drain Services", "Water Heater Installation", "Emergency Plumbing"
- **Business license number**: this is the field that confuses people
  most. For solo proprietors / sole proprietorships in Canada, the
  business license number is usually the **HST/GST number** (format:
  `12345 6789 RT0001`). Incorporated businesses use their **CRA
  Business Number (BN)** — same first 9 digits as HST/GST but without
  the RT0001 suffix. If the owner is a hobby-business or under the
  $30k HST/GST threshold and not registered, they can leave this
  blank — HomeStars allows it but the verified badge takes longer.

## Verified badge — what it requires
- 3+ Canadian customer reviews (HomeStars-verified, not pasted)
- Valid business license OR proof of insurance (commercial liability)
- 1-2 weeks of HomeStars manual review

The badge is worth pursuing — verified contractors get cited more often
in AI engine answers and rank higher in HomeStars's own search.

## Common stuck points (volunteer if owner gets stuck)

| Stuck point | What to say |
|---|---|
| "Reviews from outside HomeStars" | Existing customers must each create a HomeStars account and submit. Owner can email a HomeStars-provided link. They can't paste in Google or Facebook reviews. |
| Phone verification fails | Must be a Canadian phone number (no toll-free, no US numbers, no VoIP — HomeStars filters those). |
| "How do I import existing customers?" | Free tier: nope, manually email each customer the review-request link. Paid tier: bulk-import contacts feature. |
| "Why is my profile not showing in search?" | Initial profiles take 24-48 hours to index. After that, ranking depends on review count + recency. |

## When to write the email to a developer
HomeStars signup is owner-friendly — no technical setup, no schema, no
HTML. The owner can do this themselves in 15-20 minutes. Don't offer to
write a developer email unless they're stuck on something else (like
their HST/GST registration, which is a CRA matter, not a technical one).

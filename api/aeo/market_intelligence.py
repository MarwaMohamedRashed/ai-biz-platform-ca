"""Market-intelligence domain layer — cache lookup + vertical canonicalization.

Phase 1 surface (see docs/market-intelligence-architecture.md):

  - `canonical_vertical(business_type)` — map a stored business type
    (businesses.type holds the natural phrase, e.g. "physiotherapy clinic")
    to the canonical vertical key the cache + BASELINE_SEEDS use
    (e.g. "physiotherapist"). Falls back to "other".
  - `normalize_city(city)` — consistent casing so the (vertical, city,
    country) cache key doesn't fragment on "oakville" vs "Oakville".
  - `get_or_create(vertical, city, province, country)` — read the shared
    market_intelligence row, or insert an empty one flagged `stale` so the
    Phase 2 refresh worker picks it up. Does NOT refresh — Phase 1 is
    read/establish only.

Also parks the mention-weight constants + helper here so Phase 2's refresh
worker and ROI v2 share one definition (tunable without a migration).

All DB access uses the service-role client (supabase_admin); these tables
are shared resources written only by the backend.
"""
import logging

from core.database import supabase_admin


logger = logging.getLogger(__name__)


# businesses.type stores the natural phrase chosen at onboarding; the canonical
# key is what BASELINE_SEEDS and the vertical detectors use. Mirror of
# apps/web/components/onboarding/StepBusinessInfo.tsx TYPES (phrase -> key).
# Keep in sync if the onboarding type list changes.
_PHRASE_TO_VERTICAL: dict[str, str] = {
    "restaurant":           "restaurant",
    "cafe":                 "cafe",
    "salon":                "salon",
    "retail":               "retail",
    "dentist":              "dentist",
    "physiotherapy clinic": "physiotherapist",
    "family doctor":        "family_doctor",
    "chiropractor":         "chiropractor",
    "optometrist":          "optometrist",
    "veterinarian":         "veterinarian",
    "lawyer":               "lawyer",
    "accountant":           "accountant",
    "realtor":              "realtor",
    "plumber":              "plumber",
    "auto repair":          "auto_repair",
    "cleaning service":     "cleaning_service",
    "personal trainer":     "personal_trainer",
    "other":                "other",
}

# Loose token fallbacks for free-form types that don't exactly match a phrase
# above (the owner can type a custom type when they pick "Other"). Checked only
# when the exact-phrase lookup misses. First substring hit wins.
_VERTICAL_KEYWORDS: list[tuple[str, str]] = [
    ("physio",       "physiotherapist"),
    ("dental",       "dentist"),
    ("dentist",      "dentist"),
    ("chiro",        "chiropractor"),
    ("optom",        "optometrist"),
    ("eye",          "optometrist"),
    ("vet",          "veterinarian"),
    ("restaurant",   "restaurant"),
    ("cafe",         "cafe"),
    ("coffee",       "cafe"),
    ("salon",        "salon"),
    ("spa",          "salon"),
    ("lawyer",       "lawyer"),
    ("law",          "lawyer"),
    ("legal",        "lawyer"),
    ("account",      "accountant"),
    ("tax",          "accountant"),
    ("realtor",      "realtor"),
    ("real estate",  "realtor"),
    ("plumb",        "plumber"),
    ("auto",         "auto_repair"),
    ("mechanic",     "auto_repair"),
    ("clean",        "cleaning_service"),
    ("trainer",      "personal_trainer"),
    ("fitness",      "personal_trainer"),
    ("gym",          "personal_trainer"),
    ("doctor",       "family_doctor"),
    ("clinic",       "family_doctor"),
]


# ── Mention weighting (used from Phase 2 onward; defined here so the refresh
# worker and ROI v2 share one source of truth — tune without a migration) ──
POSITION_WEIGHT: dict[int, float] = {1: 1.0, 2: 0.6, 3: 0.4}
POSITION_WEIGHT_DEFAULT = 0.2          # 4th position and beyond
STRENGTH_WEIGHT: dict[str, float] = {"strong": 1.0, "moderate": 0.6, "weak": 0.3}


def mention_weight(position: int, strength: str, sentiment: float) -> float:
    """weight = position_weight x strength_weight x (0.5 + 0.5 x sentiment).
    A first-position strong recommendation outweighs a third-position weak one."""
    pos = POSITION_WEIGHT.get(position, POSITION_WEIGHT_DEFAULT)
    strg = STRENGTH_WEIGHT.get((strength or "").lower(), STRENGTH_WEIGHT["weak"])
    sent = max(0.0, min(1.0, sentiment if sentiment is not None else 0.5))
    return pos * strg * (0.5 + 0.5 * sent)


def canonical_vertical(business_type: str | None) -> str:
    """Map a businesses.type value to a canonical vertical key.
    Exact phrase match first, then loose keyword match, else 'other'."""
    if not business_type:
        return "other"
    t = business_type.strip().lower()
    if t in _PHRASE_TO_VERTICAL:
        return _PHRASE_TO_VERTICAL[t]
    for needle, vertical in _VERTICAL_KEYWORDS:
        if needle in t:
            return vertical
    return "other"


def normalize_city(city: str | None) -> str:
    """Consistent casing for the cache key so 'oakville' and 'Oakville' don't
    create two rows. Light touch: trim, collapse internal whitespace, title-case."""
    if not city:
        return ""
    return " ".join(city.split()).title()


async def get_or_create(
    vertical: str,
    city: str,
    province: str,
    country: str = "Canada",
) -> dict | None:
    """Return the shared market_intelligence row for this market, creating an
    empty one (refresh_status='stale') if none exists yet so the Phase 2
    refresh worker knows to populate it.

    Phase 1 only reads/establishes the row — it does NOT trigger a refresh.
    Returns None only on an unexpected DB error (caller degrades to the
    non-cached audit path)."""
    city_norm = normalize_city(city)
    if not vertical or not city_norm:
        return None

    try:
        existing = (
            supabase_admin.table("market_intelligence")
            .select("*")
            .eq("vertical", vertical)
            .eq("city", city_norm)
            .eq("country", country)
            .limit(1)
            .execute()
        )
        if existing.data:
            return existing.data[0]

        inserted = (
            supabase_admin.table("market_intelligence")
            .insert({
                "vertical": vertical,
                "city": city_norm,
                "province": province,
                "country": country,
                "refresh_status": "stale",  # never refreshed yet — worker picks it up
            })
            .execute()
        )
        if inserted.data:
            logger.info(f"[MI] created market row ({vertical}, {city_norm}, {country})")
            return inserted.data[0]
        return None
    except Exception as e:
        # Most likely a unique-constraint race (two signups, same new market).
        # Re-select so the caller still gets the row.
        logger.warning(f"[MI] get_or_create fell back to re-select for ({vertical}, {city_norm}): {e}")
        try:
            again = (
                supabase_admin.table("market_intelligence")
                .select("*")
                .eq("vertical", vertical)
                .eq("city", city_norm)
                .eq("country", country)
                .limit(1)
                .execute()
            )
            return again.data[0] if again.data else None
        except Exception as e2:
            logger.error(f"[MI] get_or_create failed for ({vertical}, {city_norm}): {e2}")
            return None

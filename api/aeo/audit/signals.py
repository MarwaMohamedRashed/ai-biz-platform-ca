"""Text-signal extraction from business names, type strings, and website HTML.

Pure regex/text-processing. No HTTP, no LLM, no DB.

Three signal categories:

1. **Cuisine detection** — pulls the specific cuisine (Italian, Egyptian,
   etc.) plus parent category (Middle Eastern, Asian) from a name+type
   string. Used to enrich audit queries for restaurants.

2. **Dietary tags** — halal / vegetarian / vegan / kosher / jain. Scanned
   from the business name, type, and website. Drives dedicated audit
   queries ("halal restaurant {city}").

3. **Clinic service tags** — physiotherapy / chiropractic / acupuncture /
   massage_therapy / etc. Scanned from healthcare-business websites only,
   used to broaden the audit-query set for multi-disciplinary clinics
   beyond the owner's declared primary type.

Originally lived in `api/aeo/router.py` lines 64-76, 234-302, 308-408,
503-517. Moved here so build_queries (next extraction) and the audit
engine can import directly without going through router.py.
"""
import re


# Types we recognize directly from the onboarding chip set — for these,
# normalize_business_type() returns the raw phrase without an LLM call.
# The chip phrases in apps/web/components/onboarding/StepBusinessInfo.tsx
# (TYPES[].phrase) must all appear here, otherwise every audit pays for a
# normalize_business_type LLM round-trip even though the owner picked a
# specific category.
#
# NOTE: "restaurant" and "cafe" are still allowed here even though the
# LLM previously enriched them with cuisine context — the dedicated
# website + services cuisine scanner now handles that signal directly.
KNOWN_TYPES = {
    # Consumer services
    "restaurant", "cafe", "salon", "retail",
    # Healthcare specifics
    "dentist", "physiotherapy clinic", "family doctor",
    "chiropractor", "optometrist", "veterinarian",
    # Professional services
    "lawyer", "accountant", "realtor",
    # Trades / home services
    "plumber", "auto repair", "cleaning service",
    # Wellness
    "personal trainer",
}


# ─── Cuisine detection ────────────────────────────────────────────────────
# Each entry: (compiled_pattern, cuisine_label, parent_category).
# parent_category=None means the cuisine IS already the broadest useful category.
_CUISINE_DETECTORS: list[tuple[re.Pattern, str | None, str | None]] = [
    (re.compile(r"\begyptian\b",             re.IGNORECASE), "Egyptian",       "Middle Eastern"),
    (re.compile(r"\blebanese\b",             re.IGNORECASE), "Lebanese",       "Middle Eastern"),
    (re.compile(r"\bsyrian\b",               re.IGNORECASE), "Syrian",         "Middle Eastern"),
    (re.compile(r"\bturkish\b",              re.IGNORECASE), "Turkish",        "Middle Eastern"),
    (re.compile(r"\bmoroc\w*\b",             re.IGNORECASE), "Moroccan",       "Middle Eastern"),
    (re.compile(r"\bpersian\b|\biranian\b",  re.IGNORECASE), "Persian",        "Middle Eastern"),
    (re.compile(r"\bafghan\w*",              re.IGNORECASE), "Afghan",         "Middle Eastern"),
    (re.compile(r"\barab\w*\b",              re.IGNORECASE), "Arabic",         "Middle Eastern"),
    (re.compile(r"\bmiddle.?east\w*",        re.IGNORECASE), "Middle Eastern",  None),
    (re.compile(r"\bindian\b",               re.IGNORECASE), "Indian",         "South Asian"),
    (re.compile(r"\bpakistan\w*",            re.IGNORECASE), "Pakistani",      "South Asian"),
    (re.compile(r"\bbangladesh\w*",          re.IGNORECASE), "Bangladeshi",    "South Asian"),
    (re.compile(r"\bsouth.?asian\b",         re.IGNORECASE), "South Asian",     None),
    (re.compile(r"\bitalian\b",              re.IGNORECASE), "Italian",         None),
    (re.compile(r"\bgreek\b",                re.IGNORECASE), "Greek",          "Mediterranean"),
    (re.compile(r"\bmediterranean\b",        re.IGNORECASE), "Mediterranean",   None),
    (re.compile(r"\bchinese\b",              re.IGNORECASE), "Chinese",        "Asian"),
    (re.compile(r"\bjapanese\b|\bsushi\b|\bramen\b", re.IGNORECASE), "Japanese", "Asian"),
    (re.compile(r"\bkorean\b",               re.IGNORECASE), "Korean",         "Asian"),
    (re.compile(r"\bvietnam\w*|\bpho\b",     re.IGNORECASE), "Vietnamese",     "Asian"),
    (re.compile(r"\bthai\b",                 re.IGNORECASE), "Thai",           "Asian"),
    (re.compile(r"\bmexican\b|\btaquer\w*",  re.IGNORECASE), "Mexican",        "Latin"),
    (re.compile(r"\bcaribbean\b|\bjamaican\b", re.IGNORECASE), "Caribbean",    None),
    (re.compile(r"\bethiopian\b",            re.IGNORECASE), "Ethiopian",      "African"),
    (re.compile(r"\bsomali\w*",              re.IGNORECASE), "Somali",         "African"),
]

RESTAURANT_RE = re.compile(
    r"\brestaurant\b|\bcaf[eé]\b|\bdiner\b|\bkitchen\b|\bbistro\b"
    r"|\beatery\b|\bbakery\b|\bpizzeria\b|\btakeout\b|\bfood\b",
    re.IGNORECASE,
)


# ─── Dietary / religious food restrictions ────────────────────────────────
# Each entry: (tag_key, compiled_pattern, query_template).
# Scanned against business name, user-entered type, AND website homepage text.
# tag_key is stored in raw_results so future audits can reuse it without
# re-fetching the homepage.
DIETARY_PATTERNS: list[tuple[str, re.Pattern, str]] = [
    ("halal",       re.compile(r"\bhalal\b",                  re.IGNORECASE), "halal restaurant near {city}"),
    ("vegetarian",  re.compile(r"\bvegetarian\b",              re.IGNORECASE), "vegetarian restaurant {city}"),
    ("vegan",       re.compile(r"\bvegan\b|\bplant.based\b",   re.IGNORECASE), "vegan restaurant {city}"),
    ("kosher",      re.compile(r"\bkosher\b",                  re.IGNORECASE), "kosher restaurant {city}"),
    ("jain",        re.compile(r"\bjain\b",                    re.IGNORECASE), "jain vegetarian restaurant {city}"),
]


# ─── Healthcare clinic service signals ────────────────────────────────────
# Each entry: (tag_key, compiled_pattern, query_template).
# tag_key is the slug used internally; query_template must contain {city}.
# Only triggered when is_healthcare=True so a plumber whose site mentions
# 'sports medicine' coverage in a testimonial doesn't get stray queries.
CLINIC_SERVICE_PATTERNS: list[tuple[str, re.Pattern, str]] = [
    ("massage_therapy",      re.compile(r"\bmassage\s+therap\w*|\bRMT\b|\bregistered\s+massage\b", re.IGNORECASE), "massage therapy near {city}"),
    ("physiotherapy",        re.compile(r"\bphysiother\w+|\bphysical\s+therap\w*",                 re.IGNORECASE), "physiotherapy clinic {city}"),
    ("chiropractic",         re.compile(r"\bchiropract\w+",                                        re.IGNORECASE), "chiropractor near {city}"),
    ("acupuncture",          re.compile(r"\bacupuncture\b|\bacupuncturist\b",                      re.IGNORECASE), "acupuncture clinic {city}"),
    ("naturopath",           re.compile(r"\bnaturopath\w*",                                        re.IGNORECASE), "naturopath {city}"),
    ("dietitian",            re.compile(r"\bdietitian\b|\bnutritionist\b|\bnutrition\s+counsel\w+", re.IGNORECASE), "dietitian {city}"),
    ("psychology",           re.compile(r"\bpsycholog\w+|\bmental\s+health\b|\bcounsell?\w+",       re.IGNORECASE), "psychologist {city}"),
    ("optometry",            re.compile(r"\boptometr\w+|\beye\s+care\b|\beye\s+exam\b",             re.IGNORECASE), "optometrist {city}"),
    ("podiatry",             re.compile(r"\bpodiatr\w+|\bfoot\s+care\b|\bchiropod\w+",              re.IGNORECASE), "podiatrist {city}"),
    ("speech_therapy",       re.compile(r"\bspeech\s+therap\w+|\bspeech.language\s+path\w+",        re.IGNORECASE), "speech therapy {city}"),
    ("occupational_therapy", re.compile(r"\boccupational\s+therap\w+",                              re.IGNORECASE), "occupational therapy {city}"),
    ("walk_in",              re.compile(r"\bwalk.in\b|\burgent\s+care\b|\bno\s+appointment\b",      re.IGNORECASE), "walk in clinic {city}"),
    ("dermatology",          re.compile(r"\bdermatolog\w+|\bskin\s+clinic\b",                       re.IGNORECASE), "dermatologist {city}"),
    ("sports_medicine",      re.compile(r"\bsports\s+medicine\b|\bsports\s+injur\w+",               re.IGNORECASE), "sports medicine clinic {city}"),
    ("pediatric",            re.compile(r"\bpediatric\w*|\bchildren.s\s+clinic\b|\bkids\s+clinic\b", re.IGNORECASE), "pediatric clinic {city}"),
]


# ─── Title-tag + sub-specialty guardrails ─────────────────────────────────
_TITLE_TAG_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)

# Business types that already convey a specific primary identity — for
# these, we DON'T emit a sub-specialty service tag from body content.
# Surfacing "pediatric" on a "Burlington Family Dentists" site (because
# the homepage lists pediatric dentistry as one of many services they
# offer) labels the entire practice incorrectly. Title-tag matches still
# count for these types — e.g. "Pediatric Dental Group of Toronto" with
# "pediatric" in <title> WILL emit pediatric, since the practice is
# self-identifying that way.
#
# Generic types (family doctor, walk-in clinic, medical clinic, "other")
# stay outside this set and continue to fire sub-specialty tags from
# body content via the min_matches rule.
_SPECIFIC_TYPES_BODY_TAGS_SKIPPED = {
    "dentist", "dental office", "dental clinic", "orthodontist",
    "physiotherapy clinic", "physiotherapist", "physical therapy", "physical therapist",
    "chiropractor", "chiropractic clinic",
    "optometrist", "optometry clinic",
    "veterinarian", "veterinary clinic", "animal hospital",
    "podiatrist", "podiatry clinic",
    "dermatologist", "dermatology clinic",
}


def is_specific_type_for_subspecialty(business_type: str | None) -> bool:
    if not business_type:
        return False
    return business_type.lower().strip() in _SPECIFIC_TYPES_BODY_TAGS_SKIPPED


# ─── Public API ───────────────────────────────────────────────────────────

def extract_text_signals(
    text: str,
    service_min_matches: int = 1,
    business_type: str | None = None,
) -> dict:
    """Run the cuisine, dietary, and clinic-service regex banks over arbitrary text.

    Used for two inputs that benefit from identical scanning logic:
      * website homepage HTML  (in check_website, with service_min_matches=2)
      * the user's free-form `services` field from onboarding (in _run_audit_core,
        with service_min_matches=1 since the input is already short and curated)

    `service_min_matches` exists because long-form HTML often contains a single
    passing mention of a non-primary specialty (e.g. "pediatric dentistry"
    listed among 12 services on a family-dentist site). We don't want that to
    label the entire practice as a pediatric clinic. Title-tag matches are
    treated as a primary-identity signal and always count regardless of the
    frequency threshold.

    `business_type` (optional) further constrains body-content tagging: when
    the owner has selected a specific specialty in onboarding (dentist,
    physiotherapist, etc. — see _SPECIFIC_TYPES_BODY_TAGS_SKIPPED above), we
    only emit sub-specialty tags that match in <title>. Body content alone
    can't override the owner-declared primary identity.

    Returning a dict (not a tuple) so callers can ignore fields they don't need.
    """
    if not text:
        return {"cuisine": None, "cuisine_parent": None, "dietary_tags": [], "service_tags": []}

    title_match = _TITLE_TAG_RE.search(text)
    title_text = title_match.group(1) if title_match else ""

    dietary_tags = [tag for tag, pattern, _ in DIETARY_PATTERNS if pattern.search(text)]

    type_is_specific = is_specific_type_for_subspecialty(business_type)
    service_tags: list[str] = []
    for tag, pattern, _ in CLINIC_SERVICE_PATTERNS:
        # A match in <title> is a strong primary-identity signal — accept on 1.
        if title_text and pattern.search(title_text):
            service_tags.append(tag)
            continue
        # When the owner already picked a specific specialty, body matches
        # alone can't override that identity. Title-tag matches above still
        # fire (e.g. a specialised pediatric dental practice).
        if type_is_specific:
            continue
        # Otherwise require at least service_min_matches occurrences.
        if service_min_matches <= 1:
            if pattern.search(text):
                service_tags.append(tag)
        else:
            hits = pattern.findall(text)
            if len(hits) >= service_min_matches:
                service_tags.append(tag)

    cuisine: str | None = None
    cuisine_parent: str | None = None
    for pattern, label, parent in _CUISINE_DETECTORS:
        if pattern.search(text):
            cuisine = label
            cuisine_parent = parent
            break

    return {
        "cuisine":        cuisine,
        "cuisine_parent": cuisine_parent,
        "dietary_tags":   dietary_tags,
        "service_tags":   service_tags,
    }


def detect_cuisine(business_name: str, business_type_en: str) -> tuple[str | None, str | None, bool]:
    """Detect cuisine, parent category, and halal status from name + type.

    Returns:
        cuisine_label  -- specific cuisine (e.g. 'Egyptian'), or None
        parent_category -- broader category (e.g. 'Middle Eastern'), or None when
                           cuisine is already the broadest useful level
        is_halal       -- True only when 'halal' appears explicitly in name or type
    """
    combined = f"{business_name} {business_type_en}"
    is_halal = bool(re.search(r"\bhalal\b", combined, re.IGNORECASE))
    for pattern, cuisine, parent in _CUISINE_DETECTORS:
        if pattern.search(combined):
            return cuisine, parent, is_halal
    return None, None, is_halal

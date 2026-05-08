"""
Deterministic Schema.org JSON-LD builder for LocalBusiness audits.

Replaces the previous LLM-based schema generation. Every field traces
directly to the user's stored business profile -- no hallucinated values.
"""
from __future__ import annotations

import re

# ─── Business type → Schema.org @type ─────────────────────────────────────
# Two-stage resolution:
#   1. Exact match against the small set of onboarding TYPES values
#   2. Keyword/regex match against free-form `customType` strings
#   3. Fallback: LocalBusiness

EXACT_TYPE_MAP: dict[str, str] = {
    "restaurant": "Restaurant",
    "cafe":       "CafeOrCoffeeShop",
    "salon":      "BeautySalon",
    "retail":     "Store",
    "plumber":    "Plumber",
    # "other" deliberately falls through to keyword matching
}

# Order matters -- more specific patterns first.
KEYWORD_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # Medical / health
    (re.compile(r"\bdentist|\bdental\b",                                re.I), "Dentist"),
    (re.compile(r"\bphysiotherap\w*|\bphysical\s+therap\w*",            re.I), "Physiotherapy"),
    (re.compile(r"\bchiropract\w+",                                     re.I), "Chiropractor"),
    (re.compile(r"\boptometr\w+|\beye\s+care",                          re.I), "Optometric"),
    (re.compile(r"\bvet(erinary)?\b|\banimal\s+hospital",               re.I), "VeterinaryCare"),
    (re.compile(r"\bpharm\w+",                                          re.I), "Pharmacy"),
    (re.compile(r"\bclinic\b|\bmedical\b|\bfamily\s+doctor|\bgp\b",     re.I), "MedicalClinic"),

    # Food / drink
    (re.compile(r"\bbakery|\bbaker\b|\bp[âa]tisserie",                  re.I), "Bakery"),
    (re.compile(r"\bcaf[eé]\b|\bcoffee\s+shop",                         re.I), "CafeOrCoffeeShop"),
    (re.compile(r"\bbar\b|\bpub\b",                                     re.I), "BarOrPub"),
    (re.compile(r"\bbrewery",                                           re.I), "Brewery"),
    (re.compile(r"\brestaurant|\bdiner\b|\bsteakhouse|\bsushi|\bpizza", re.I), "Restaurant"),

    # Beauty / wellness
    (re.compile(r"\bhair\s+salon|\bbarber\b|\bhaircut",                 re.I), "HairSalon"),
    (re.compile(r"\bnail\s+salon|\bmanicure",                           re.I), "NailSalon"),
    (re.compile(r"\bbeauty\s+salon|\baesthetic",                        re.I), "BeautySalon"),
    (re.compile(r"\bday\s*spa|\bspa\b",                                 re.I), "DaySpa"),
    (re.compile(r"\bsalon\b",                                           re.I), "BeautySalon"),
    (re.compile(r"\btattoo\b",                                          re.I), "TattooParlor"),

    # Fitness
    (re.compile(r"\bgym\b|\bfitness\b|\bcrossfit",                      re.I), "ExerciseGym"),
    (re.compile(r"\byoga\b|\bpilates",                                  re.I), "HealthClub"),

    # Trades / construction
    (re.compile(r"\bplumb\w+",                                          re.I), "Plumber"),
    (re.compile(r"\belectric(ian|al)\b",                                re.I), "Electrician"),
    (re.compile(r"\bhvac\b|\bheating\b|\bcooling\b|\bair\s+conditioning", re.I), "HVACBusiness"),
    (re.compile(r"\bhouse\s*painter|\bpainting\s+contractor",           re.I), "HousePainter"),
    (re.compile(r"\bgeneral\s+contractor|\bcontractor\b|\bconstruction", re.I), "GeneralContractor"),
    (re.compile(r"\broof\w+",                                           re.I), "RoofingContractor"),
    (re.compile(r"\blocksmith",                                         re.I), "Locksmith"),
    (re.compile(r"\bmoving\s+(company|service)|\bmovers",               re.I), "MovingCompany"),

    # Auto
    (re.compile(r"\bauto\s+repair|\bmechanic|\bcar\s+repair",           re.I), "AutoRepair"),
    (re.compile(r"\bauto\s+body|\bcollision",                           re.I), "AutoBodyShop"),
    (re.compile(r"\bcar\s+wash|\bauto\s+wash",                          re.I), "AutoWash"),
    (re.compile(r"\bauto(motive)?\s+dealer|\bcar\s+dealer",             re.I), "AutoDealer"),

    # Professional services
    (re.compile(r"\blawyer|\battorney|\blegal\s+service|\blaw\s+(firm|office)", re.I), "Attorney"),
    (re.compile(r"\baccount\w+|\bbookkeep\w+|\bcpa\b",                  re.I), "AccountingService"),
    (re.compile(r"\breal\s+estate",                                     re.I), "RealEstateAgent"),
    (re.compile(r"\binsurance\s+(agent|agency|broker)",                 re.I), "InsuranceAgency"),
    (re.compile(r"\bbank\b|\bcredit\s+union",                           re.I), "BankOrCreditUnion"),

    # Retail
    (re.compile(r"\bclothing\s+(store|shop)|\bboutique\b",              re.I), "ClothingStore"),
    (re.compile(r"\bgrocery\b|\bsupermarket\b",                         re.I), "GroceryStore"),
    (re.compile(r"\bflorist\b|\bflower\s+shop",                         re.I), "Florist"),
    (re.compile(r"\bbook\s*store",                                      re.I), "BookStore"),
    (re.compile(r"\bjewelr\w+",                                         re.I), "JewelryStore"),
    (re.compile(r"\bpet\s+(store|shop)",                                re.I), "PetStore"),
    (re.compile(r"\bhardware\s+store",                                  re.I), "HardwareStore"),
    (re.compile(r"\bfurniture\s+store",                                 re.I), "FurnitureStore"),
    (re.compile(r"\belectronics\s+store",                               re.I), "ElectronicsStore"),

    # Hospitality / travel
    (re.compile(r"\bhotel\b|\bresort\b|\binn\b",                        re.I), "Hotel"),
    (re.compile(r"\bmotel\b",                                           re.I), "Motel"),
    (re.compile(r"\bbed\s*&?\s*breakfast|\bb&b\b",                      re.I), "BedAndBreakfast"),
    (re.compile(r"\btravel\s+agen\w+",                                  re.I), "TravelAgency"),

    # Other
    (re.compile(r"\bdaycare\b|\bchild\s*care",                          re.I), "ChildCare"),
    (re.compile(r"\bdry\s+clean",                                       re.I), "DryCleaningOrLaundry"),
    (re.compile(r"\bself\s+storage|\bstorage\s+(unit|facility)",        re.I), "SelfStorage"),
    (re.compile(r"\bgolf\s+course",                                     re.I), "GolfCourse"),
]


def resolve_schema_type(business_type: str | None) -> str:
    """Map a business-type string to the most specific Schema.org @type."""
    if not business_type:
        return "LocalBusiness"

    bt = business_type.strip().lower()
    if bt in EXACT_TYPE_MAP:
        return EXACT_TYPE_MAP[bt]

    for pattern, schema_type in KEYWORD_PATTERNS:
        if pattern.search(business_type):
            return schema_type

    return "LocalBusiness"


# ─── Hours conversion ─────────────────────────────────────────────────────
_DAY_NAME = {
    "monday":    "Monday",
    "tuesday":   "Tuesday",
    "wednesday": "Wednesday",
    "thursday":  "Thursday",
    "friday":    "Friday",
    "saturday":  "Saturday",
    "sunday":    "Sunday",
}
_HOURS_RANGE = re.compile(r"^(\d{2}:\d{2})-(\d{2}:\d{2})$")


def _hours_to_schema(hours: dict | None) -> list[dict] | None:
    """Convert {"monday": "09:00-17:00", "tuesday": "closed", ...}
       to a list of Schema.org OpeningHoursSpecification objects.
       Closed days are omitted (Schema.org convention)."""
    if not hours or not isinstance(hours, dict):
        return None

    out: list[dict] = []
    for day_key, val in hours.items():
        d = str(day_key).lower().strip()
        if d not in _DAY_NAME:
            continue
        if val is None or str(val).strip().lower() in ("", "closed"):
            continue
        m = _HOURS_RANGE.match(str(val).strip())
        if not m:
            continue
        out.append({
            "@type":     "OpeningHoursSpecification",
            "dayOfWeek": f"https://schema.org/{_DAY_NAME[d]}",
            "opens":     m.group(1),
            "closes":    m.group(2),
        })
    return out or None


# ─── Required-fields tracker (drives the "complete your profile" UX) ──────
# These are Google's required+strongly-recommended fields for LocalBusiness
# rich results. Missing any of them produces a valid schema that won't
# qualify for enhanced presentation.
REQUIRED_FIELDS_FOR_RICH_RESULTS = [
    "name",
    "image_url",
    "street_address",
    "city",
    "phone",
]


def find_missing_required_fields(business: dict) -> list[str]:
    """Return the list of profile fields a user still needs to fill in
    for the schema to qualify for Google rich results."""
    missing: list[str] = []
    for field in REQUIRED_FIELDS_FOR_RICH_RESULTS:
        v = business.get(field)
        if v is None or (isinstance(v, str) and not v.strip()):
            missing.append(field)
    return missing


# ─── Builder ──────────────────────────────────────────────────────────────
def build_schema(
    business: dict,
    description: str | None = None,
    content_language: str | None = None,
) -> dict:
    """
    Build a Schema.org JSON-LD object from a business profile dict.
    Pure / deterministic -- no LLM, no network calls, no hallucination.
    Fields with no data are omitted (not emitted as null).

    `content_language` is the language the description+FAQ were generated in
    (`'en'` or `'fr'`) — used to gate the Quebec bilingual `inLanguage`
    declaration. If the business is in QC AND content has been generated in
    French, we declare the entity as bilingual to Google Knowledge Graph.
    Without this gate we'd be claiming bilingual on English-only content,
    which Google can penalise.
    """
    obj: dict = {
        "@context": "https://schema.org",
        "@type":    resolve_schema_type(business.get("type")),
        "name":     business.get("name"),
    }

    # Quebec bilingual signal — only when business is in QC AND we know
    # French content exists (or the user explicitly opted in).
    province = (business.get("province") or "").strip().upper()
    if province == "QC" and (content_language == "fr" or business.get("bilingual_opt_in")):
        obj["inLanguage"] = ["fr-CA", "en-CA"]

    if business.get("image_url"):
        obj["image"] = business["image_url"]

    if business.get("phone"):
        obj["telephone"] = business["phone"]

    if business.get("price_range"):
        obj["priceRange"] = business["price_range"]

    if business.get("website"):
        obj["url"] = business["website"]

    # Address — include if at least one address field is present (other than
    # the always-present default country)
    addr_parts = {
        "streetAddress":    business.get("street_address"),
        "addressLocality":  business.get("city"),
        "addressRegion":    business.get("province"),
        "postalCode":       business.get("postal_code"),
        "addressCountry":   business.get("country") or "Canada",
    }
    if any(v for k, v in addr_parts.items() if k != "addressCountry"):
        obj["address"] = {
            "@type": "PostalAddress",
            **{k: v for k, v in addr_parts.items() if v},
        }

    hours_spec = _hours_to_schema(business.get("hours"))
    if hours_spec:
        obj["openingHoursSpecification"] = hours_spec

    if description and description.strip():
        obj["description"] = description.strip()

    return obj


# ─── FAQPage builder ──────────────────────────────────────────────────────
def build_faq_schema(faq_items: list[dict]) -> dict:
    """
    Build a Schema.org FAQPage JSON-LD object from a list of {question, answer}
    dicts. Items missing either field are silently dropped.
    """
    main_entity = []
    for item in faq_items or []:
        q = (item.get("question") or "").strip()
        a = (item.get("answer") or "").strip()
        if not q or not a:
            continue
        main_entity.append({
            "@type": "Question",
            "name":  q,
            "acceptedAnswer": {
                "@type": "Answer",
                "text":  a,
            },
        })

    return {
        "@context":   "https://schema.org",
        "@type":      "FAQPage",
        "mainEntity": main_entity,
    }

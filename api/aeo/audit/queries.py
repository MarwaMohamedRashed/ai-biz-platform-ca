"""Audit query builder.

`build_queries` decides which Google / Perplexity / ChatGPT search
queries to issue for a given business. Result is a deduplicated list of
query strings; the caller feeds each into every AI engine.

Strategy:
- Three baseline templates per audit (universal — see QUERY_TEMPLATES).
- Conditional add-ons gated by detected signals so query count stays
  predictable per audit cost (Canadian FSA query, emergency/weekend for
  trades + healthcare, cuisine + dietary for restaurants, service-
  specific for multi-disciplinary clinics).

Originally lived in `api/aeo/router.py` lines 215-219 (QUERY_TEMPLATES)
and 317-426 (build_queries). Moved here so the future audit engine
module can import directly.
"""
from .signals import (
    CLINIC_SERVICE_PATTERNS,
    DIETARY_PATTERNS,
    RESTAURANT_RE,
    detect_cuisine,
)


QUERY_TEMPLATES = [
    "best {type} in {city}, {province}",
    "{type} near {city}",
    "top {type} {city} {province}",
]


def build_queries(
    business_type_en: str,
    city: str,
    province: str,
    postal_code: str | None = None,
    is_trades: bool = False,
    is_healthcare: bool = False,
    business_name: str = "",
    dietary_tags: list[str] | None = None,
    service_tags: list[str] | None = None,
    cuisine_hint: str | None = None,
    cuisine_hint_parent: str | None = None,
) -> list[str]:
    """
    Returns the list of search-query strings to run against each AI engine.

    Base set: 3 templates (Best/near/Top) — runs for every audit.

    Conditional additions (only added when the gating condition is true,
    keeping cost predictable):
      * FSA-prefix query when postal_code is set — uniquely Canadian
        search pattern, ~20% of locals search by FSA prefix
      * Emergency / 24-7 query for trades + healthcare — high-intent
        urgency searches
      * Weekend-availability query for trades + healthcare — common
        intent for after-hours services
      * Cuisine-specific + parent-category queries for food businesses —
        e.g. 'best Egyptian restaurant Mississauga' + 'Middle Eastern food
        Mississauga'. Capped at 2 extras to keep API cost predictable.
      * Dietary queries from verified website/name signals — halal,
        vegetarian, vegan, kosher — only when explicitly detected, never
        assumed from cuisine origin alone.
      * Healthcare service queries from website signals — e.g. a clinic
        whose homepage mentions massage therapy and dietitian gets targeted
        queries like 'massage therapy Toronto' alongside the generic clinic
        query. Capped at 2 extras, skipped if the service is already
        captured in the normalized business type.
    """
    dietary_tags = dietary_tags or []
    service_tags = service_tags or []
    queries = [t.format(type=business_type_en, city=city, province=province)
               for t in QUERY_TEMPLATES]

    if postal_code and len(postal_code.strip()) >= 3:
        fsa = postal_code.strip()[:3].upper()
        queries.append(f"{business_type_en} near {fsa}")

    if is_trades or is_healthcare:
        queries.append(f"Emergency {business_type_en} {city} 24/7")
        queries.append(f"{business_type_en} open weekends {city}")

    # Restaurant vertical: add cuisine-specific and parent-category queries.
    # Match gate also accepts the business_type_en alone (handles `cafe`/`bakery`
    # where the business_name has no food-related token), and the cuisine_hint
    # (so a website-only signal like "Arabic food on the homepage" still flips
    # this branch on).
    restaurant_gate = (
        RESTAURANT_RE.search(f"{business_name} {business_type_en}")
        or (cuisine_hint and RESTAURANT_RE.search(business_type_en))
    )
    if restaurant_gate:
        cuisine, parent, is_halal_name = detect_cuisine(business_name, business_type_en)
        # Gap 1 fix: when name+type detection finds nothing, fall back to the
        # cuisine_hint extracted from the website/services scan. The user's
        # "Mandi Afandi" was the exact case this guards against — no cuisine token
        # in the name, "Arabic" only visible on the homepage.
        if not cuisine and cuisine_hint:
            cuisine = cuisine_hint
            parent = cuisine_hint_parent
        extras: list[str] = []
        if cuisine and cuisine.lower() not in business_type_en.lower():
            extras.append(f"best {cuisine.lower()} restaurant {city}")
        if parent and parent.lower() not in business_type_en.lower():
            extras.append(f"{parent.lower()} food {city}")
        queries.extend(extras[:2])

        # Dietary queries: combine name-based flag with website signals.
        effective_tags = set(dietary_tags)
        if is_halal_name:
            effective_tags.add("halal")
        for tag, _pat, tmpl in DIETARY_PATTERNS:
            if tag in effective_tags:
                dq = tmpl.format(city=city)
                if dq not in queries:
                    queries.append(dq)
                break  # one dietary query max

    # Healthcare vertical: inject service-specific queries from website signals.
    # Example: a clinic whose homepage lists massage therapy + dietitian gets
    # 'massage therapy Toronto' and 'dietitian Toronto' added so AI engines can
    # cite it for those specific service searches, not just the generic clinic query.
    if is_healthcare and service_tags:
        added = 0
        for tag, _pat, tmpl in CLINIC_SERVICE_PATTERNS:
            if tag not in service_tags:
                continue
            # Skip if this service is already captured in the normalized type
            # e.g. don't add 'physiotherapy clinic Toronto' when the type is
            # already 'physiotherapy clinic' (base queries cover it).
            keyword = tag.replace("_", " ")
            if keyword in business_type_en.lower():
                continue
            sq = tmpl.format(city=city)
            if sq not in queries:
                queries.append(sq)
                added += 1
            if added >= 2:
                break  # cap at 2 service queries to control API cost

    return queries

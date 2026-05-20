"""Vertical detection + directory-presence helpers.

Two related concerns live here:

1. **Vertical detectors** (`is_trades_business`, `is_healthcare_business`,
   etc.) — pure regex checks against the business-type string. Used by
   recommendations.py to gate Canadian-specific directory recs, and by
   engine.py to choose the right audit-query templates.

2. **Directory presence** — given the SerpApi organic-results blob from
   an audit, determine which known directories the business (and its
   competitors) already appear on. Drives the "citation gap" suggestions.

Pure functions only. No HTTP, no DB, no LLM calls.

Originally lived in `api/aeo/router.py` lines 2336-2629. Moved here so
both `recommendations.py` and the (future) `engine.py` can import them
without going through router.py's namespace.
"""
import re


# ─── Known directory / citation domains ───────────────────────────────────
# Mix of US + Canadian + international + niche health/professional sites.
DIRECTORY_DOMAINS: dict[str, str] = {
    "yelp.com":             "Yelp",
    "yelp.ca":              "Yelp",
    "yellowpages.com":      "Yellow Pages",
    "yellowpages.ca":       "Yellow Pages",
    "ypg.com":              "Yellow Pages",
    "bbb.org":              "BBB",
    "tripadvisor.com":      "TripAdvisor",
    "tripadvisor.ca":       "TripAdvisor",
    "facebook.com":         "Facebook",
    "instagram.com":        "Instagram",
    "linkedin.com":         "LinkedIn",
    "foursquare.com":       "Foursquare",
    "nextdoor.com":         "Nextdoor",
    "ratemds.com":          "RateMDs",
    "healthgrades.com":     "Healthgrades",
    "411.ca":               "411.ca",
    "canada411.ca":         "Canada411",
    "mapquest.com":         "MapQuest",
    "opencare.com":         "Opencare",
    "zocdoc.com":           "Zocdoc",
    "wellness.com":         "Wellness.com",
    "houzz.com":            "Houzz",
    "homestars.com":        "HomeStars",
    "trustedpros.ca":       "TrustedPros",
    "angi.com":             "Angi",
    "thumbtack.com":        "Thumbtack",
    # Canadian general directories (added 2026-05-08)
    "n49.com":              "n49",
    "cylex-canada.ca":      "Cylex Canada",
    # Canadian vertical-specific directories
    "realtor.ca":           "Realtor.ca",
    "lawyerlocate.ca":      "LawyerLocate",
    "opentable.com":        "OpenTable",
    "opentable.ca":         "OpenTable",
    # Community / UGC citation surfaces (added 2026-05-08)
    # Reddit is a top-3 AI citation domain since Google's $60M Reddit data
    # licensing deal. Detection works the same as for directories, but the
    # frontend treats it specially -- you don't "claim" a Reddit listing.
    "reddit.com":           "Reddit",
}


# ─── City -> subreddit name mapping ───────────────────────────────────────
# Used by the Reddit recommendation to send users to the most relevant
# local subreddit. Falls back to a Reddit search when city isn't mapped.
CITY_SUBREDDITS: dict[str, str] = {
    "toronto":         "toronto",
    "ottawa":          "ottawa",
    "vancouver":       "vancouver",
    "montreal":        "montreal",
    "montréal":        "montreal",
    "calgary":         "Calgary",
    "edmonton":        "Edmonton",
    "halifax":         "halifax",
    "winnipeg":        "Winnipeg",
    "quebec city":     "quebeccity",
    "québec":          "quebeccity",
    "quebec":          "quebeccity",
    "mississauga":     "mississauga",
    "brampton":        "brampton",
    "hamilton":        "Hamilton",
    "london":          "londonontario",
    "kitchener":       "waterloo",
    "waterloo":        "waterloo",
    "saskatoon":       "saskatoon",
    "regina":          "Regina",
    "victoria":        "VictoriaBC",
    "windsor":         "windsorontario",
    "burnaby":         "burnaby",
    "richmond":        "richmondbc",
    "surrey":          "surreybc",
    "markham":         "markham",
    "vaughan":         "Vaughan",
    "oakville":        "oakville",
    "burlington":      "burlingtonontario",
    "guelph":          "Guelph",
    "barrie":          "Barrie",
    "kelowna":         "kelowna",
}


def city_to_subreddit_url(city: str | None) -> str:
    """Returns a Reddit URL pointing at the city's subreddit if known,
    otherwise a Reddit search for the city name."""
    if not city:
        return "https://www.reddit.com/r/canada"
    sub = CITY_SUBREDDITS.get(city.strip().lower())
    if sub:
        return f"https://www.reddit.com/r/{sub}"
    return f"https://www.reddit.com/search/?q={city.replace(' ', '+')}"


# ─── Vertical detectors ───────────────────────────────────────────────────
# Each pattern is intentionally narrow — false positives mean the wrong rec
# fires for the wrong business, which is more damaging than a missed rec.

# Canadian trades-business detector — used by recommendations engine
# to suggest HomeStars/TrustedPros listings for plumbers, electricians, etc.
_TRADES_PATTERN = re.compile(
    r"\bplumb\w+|\belectric(ian|al)\b|\bhvac\b|\bheating\b|\bcooling\b|"
    r"\bair\s+conditioning|\broof\w+|\bcontractor\b|\bgeneral\s+contractor|"
    r"\bconstruction|\bhouse\s*painter|\bpainting\s+contractor|\blocksmith|"
    r"\bhandyman|\blandscap\w+|\bcarpent\w+|\bflooring\b|\brenovat\w+",
    re.IGNORECASE,
)

_HEALTHCARE_PATTERN = re.compile(
    r"\bdentist|\bdental\b|\bdoctor\b|\bphysician\b|\bphysiotherap\w*|"
    r"\bphysical\s+therap\w*|\bchiropract\w+|\boptometr\w+|\beye\s+care|"
    r"\bvet(erinary)?\b|\banimal\s+hospital|\bpharm\w+|\bmedical\s+clinic|"
    r"\bclinic\b|\bnaturopath\w*|\bmassage\s+therap\w*|\baudiologist|"
    r"\bpsychologist|\bcounsell?ing|\btherapist",
    re.IGNORECASE,
)

_DENTIST_PATTERN = re.compile(r"\bdentist|\bdental\b|\borthodont\w+", re.IGNORECASE)

_FOOD_PATTERN = re.compile(
    r"\brestaurant|\bdiner\b|\bsteakhouse|\bsushi|\bpizza|\bcaf[eé]\b|"
    r"\bcoffee\s+shop|\bbakery|\bbar\b|\bpub\b|\bbrewery|\bbistro|\beatery",
    re.IGNORECASE,
)

_LEGAL_PATTERN = re.compile(
    r"\blawyer|\battorney|\blegal\s+service|\blaw\s+(firm|office)|"
    r"\bparalegal|\bnotary\s+public",
    re.IGNORECASE,
)

_REALTOR_PATTERN = re.compile(
    r"\breal\s+estate|\brealtor\b|\brealty\b",
    re.IGNORECASE,
)

# B2B / professional services detector — gates the LinkedIn Company Page
# recommendation. Intentionally broad: covers services where LinkedIn
# presence is a real AI citation signal beyond just consumer-facing reviews.
_B2B_PATTERN = re.compile(
    r"\blawyer|\battorney|\blegal\s+service|\blaw\s+(firm|office)|\bparalegal|\bnotary"
    r"|\baccount\w+|\bbookkeep\w+|\bcpa\b|\bauditor"
    r"|\bconsult\w+|\badvisor\b|\badvisory"
    r"|\bIT\s+services|\bmanaged\s+services|\bIT\s+consulting|\btech\s+consult"
    r"|\bmarketing\s+agency|\badvertising\s+agency|\bdigital\s+agency|\bweb\s+design"
    r"|\bfinancial\s+(advisor|planner)|\bwealth\s+management"
    r"|\bbusiness\s+coach|\bexecutive\s+coach"
    r"|\brecruit\w+|\bstaffing"
    r"|\breal\s+estate|\brealtor\b"
    r"|\barchitect|\bengineering\s+firm|\bsoftware\s+(company|consult)|\bSaaS",
    re.IGNORECASE,
)


def is_trades_business(business_type: str | None) -> bool:
    """True if the business looks like a Canadian trades business — used to
    gate HomeStars/TrustedPros recommendations."""
    if not business_type:
        return False
    return bool(_TRADES_PATTERN.search(business_type))


def is_healthcare_business(business_type: str | None) -> bool:
    return bool(business_type and _HEALTHCARE_PATTERN.search(business_type))


def is_dentist_business(business_type: str | None) -> bool:
    return bool(business_type and _DENTIST_PATTERN.search(business_type))


def is_food_business(business_type: str | None) -> bool:
    return bool(business_type and _FOOD_PATTERN.search(business_type))


def is_legal_business(business_type: str | None) -> bool:
    return bool(business_type and _LEGAL_PATTERN.search(business_type))


def is_realtor_business(business_type: str | None) -> bool:
    return bool(business_type and _REALTOR_PATTERN.search(business_type))


def is_b2b_business(business_type: str | None) -> bool:
    """True for professional services / B2B verticals where a LinkedIn
    Company Page is a meaningful AI citation signal. Intentionally
    overlaps with is_legal_business and is_realtor_business -- a lawyer
    benefits from BOTH the LawyerLocate rec AND the LinkedIn rec; they
    serve different surfaces."""
    return bool(business_type and _B2B_PATTERN.search(business_type))


# ─── Directory presence detection ─────────────────────────────────────────

def domain_from_url(url: str) -> str:
    """Strip scheme/path/www; return bare domain in lowercase."""
    if not url:
        return ""
    u = url.lower()
    u = re.sub(r"^https?://", "", u)
    u = u.split("/", 1)[0]
    u = re.sub(r"^www\.", "", u)
    return u


def name_short(name: str | None) -> str:
    """First 3 words of a business name, lowercased — used as a lenient
    substring match against organic-result snippets."""
    if not name:
        return ""
    return " ".join(name.lower().strip().split()[:3])


def user_directories_only(per_query_results: list[dict], business_name: str) -> set[str]:
    """Lightweight helper: which directories does the user appear on?
    Used by generate_recommendations() — same matching logic as
    detect_directory_presence() but skips the competitor side."""
    user_dirs: set[str] = set()
    user_short = name_short(business_name)
    if not user_short:
        return user_dirs

    for q in per_query_results or []:
        for r in q.get("organic_results_raw", []) or []:
            link = r.get("link") or ""
            domain = domain_from_url(link)
            label = None
            for d_domain, d_label in DIRECTORY_DOMAINS.items():
                if domain == d_domain or domain.endswith("." + d_domain):
                    label = d_label
                    break
            if not label:
                continue
            haystack = ((r.get("title") or "") + " " + (r.get("snippet") or "")).lower()
            if user_short in haystack:
                user_dirs.add(label)
    return user_dirs


def detect_directory_presence(
    per_query_results: list[dict],
    business_name: str,
    competitor_names: list[str],
) -> dict:
    """
    Walk organic_results across all queries and determine which directories
    the user and each competitor appear on.
    Heuristic: a business is "on" a directory if its first three name words
    appear in the title or snippet of an organic result whose URL is on that
    directory's domain. Approximate but practical given SerpApi data.

    Returns:
      {
        "user":        ["Yelp", "BBB"],
        "competitors": {<comp_name>: ["Yelp", ...]},
        "gaps":        ["TripAdvisor", "Yellow Pages"]
      }
    """
    user_dirs: set[str] = set()
    competitor_dirs: dict[str, set[str]] = {n: set() for n in competitor_names if n}

    user_short = name_short(business_name)
    competitor_shorts = {n: name_short(n) for n in competitor_dirs}

    for q in per_query_results or []:
        for r in q.get("organic_results_raw", []) or []:
            link = r.get("link") or ""
            domain = domain_from_url(link)
            label = None
            for d_domain, d_label in DIRECTORY_DOMAINS.items():
                if domain == d_domain or domain.endswith("." + d_domain):
                    label = d_label
                    break
            if not label:
                continue
            haystack = ((r.get("title") or "") + " " + (r.get("snippet") or "")).lower()

            if user_short and user_short in haystack:
                user_dirs.add(label)
            for cname, n_short in competitor_shorts.items():
                if n_short and n_short in haystack:
                    competitor_dirs[cname].add(label)

    all_competitor_dirs: set[str] = set()
    for s in competitor_dirs.values():
        all_competitor_dirs |= s

    gaps = sorted(all_competitor_dirs - user_dirs)

    return {
        "user":        sorted(user_dirs),
        "competitors": {n: sorted(s) for n, s in competitor_dirs.items()},
        "gaps":        gaps,
    }

"""Country / province / address geocoding helpers.

Everything in this module is pure-function lookup data + small helpers
used by the audit pipeline to map between:

- Country name (as stored on businesses.country)  →  SerpApi `gl` code
- ISO-2 country code  →  SerpApi `gl` code
- Province / state abbreviation  →  full name SerpApi's geocoder accepts
- Free-form address string  →  SerpApi `gl` code (used to drop
  cross-border competitors when scope=local|country)

Originally lived in `api/aeo/router.py` lines 68-212. Moved here so the
content module (which currently duplicates the country->gl mapping
locally) can import from a single source of truth.
"""
import re


# Map full country names (as stored on businesses.country, set in onboarding) to
# Google's ISO 3166-1 alpha-2 region codes used by the SerpApi `gl` parameter.
# Keys must match the values in apps/web/components/onboarding/StepBusinessInfo.tsx COUNTRIES.
COUNTRY_TO_GL: dict[str, str] = {
    "Canada":         "ca",
    "United States":  "us",
    "United Kingdom": "gb",
    "Australia":      "au",
    "France":         "fr",
    "Germany":        "de",
    "Spain":          "es",
    "Italy":          "it",
    "Netherlands":    "nl",
    "Belgium":        "be",
    "Switzerland":    "ch",
    "New Zealand":    "nz",
    "Ireland":        "ie",
    "Portugal":       "pt",
    "Mexico":         "mx",
    "Brazil":         "br",
    "India":          "in",
    "Japan":          "jp",
    "South Korea":    "kr",
    "Singapore":      "sg",
    "South Africa":   "za",
}


# ISO 2-letter country codes → gl (handles databases that store "CA" instead of "Canada")
COUNTRY_ISO_TO_GL: dict[str, str] = {
    "CA": "ca", "US": "us", "GB": "gb", "UK": "gb", "AU": "au",
    "FR": "fr", "DE": "de", "ES": "es", "IT": "it", "NL": "nl",
    "BE": "be", "CH": "ch", "NZ": "nz", "IE": "ie", "PT": "pt",
    "MX": "mx", "BR": "br", "IN": "in", "JP": "jp", "KR": "kr",
    "SG": "sg", "ZA": "za",
}

# Canadian province/territory codes — any of these implies gl="ca"
CA_PROVINCE_CODES: frozenset[str] = frozenset(
    {"AB", "BC", "MB", "NB", "NL", "NS", "NT", "NU", "ON", "PE", "QC", "SK", "YT"}
)


# Maps a gl code to regex patterns that strongly indicate that country in a SerpApi
# address string. Word-boundaries (\b) prevent false positives like "uk" matching
# inside "Lukas Avenue". Every gl code in COUNTRY_TO_GL must have an entry here.
COUNTRY_ADDRESS_MARKERS: dict[str, list[str]] = {
    "ca": [r"\bcanada\b", r"\b[A-Z]\d[A-Z][\s\-]?\d[A-Z]\d\b"],  # Canadian postal: A1A 1A1
    "us": [r"\bunited states\b", r"\busa\b", r"\bu\.s\.a?\.?\b",
           r"\b[A-Z]{2}\s+\d{5}(?:-\d{4})?\b"],  # US state + ZIP: "NJ 08060", "WA 98101-1234"
    "gb": [r"\bunited kingdom\b", r"\bu\.?k\.?\b", r"\bengland\b", r"\bscotland\b", r"\bwales\b",
           r"\bmilton keynes\b", r"\bbirmingham\b uk", r"\bsouth london\b", r"\bnorth london\b",
           r"\b[A-Z]{1,2}\d{1,2}[A-Z]?\s\d[A-Z]{2}\b"],  # UK postal: MK2 2EE, SW1A 1AA
    "au": [r"\baustralia\b"],
    "fr": [r"\bfrance\b"],
    "de": [r"\bgermany\b", r"\bdeutschland\b"],
    "es": [r"\bspain\b", r"\bespaña\b"],
    "it": [r"\bitaly\b", r"\bitalia\b"],
    "nl": [r"\bnetherlands\b", r"\bholland\b", r"\bnederland\b"],
    "be": [r"\bbelgium\b", r"\bbelgique\b", r"\bbelgië\b"],
    "ch": [r"\bswitzerland\b", r"\bsuisse\b", r"\bschweiz\b"],
    "nz": [r"\bnew zealand\b"],
    "ie": [r"\bireland\b", r"\béire\b"],
    "pt": [r"\bportugal\b"],
    "mx": [r"\bmexico\b", r"\bméxico\b"],
    "br": [r"\bbrazil\b", r"\bbrasil\b"],
    "in": [r"\bindia\b"],
    "jp": [r"\bjapan\b"],
    "kr": [r"\bsouth korea\b", r"\bkorea\b"],
    "sg": [r"\bsingapore\b"],
    "za": [r"\bsouth africa\b"],
}

# Sanity-check: every supported country must have an entry in both maps.
assert set(COUNTRY_TO_GL.values()) == set(COUNTRY_ADDRESS_MARKERS.keys()), \
    "COUNTRY_TO_GL and COUNTRY_ADDRESS_MARKERS must cover the same gl codes"


# Maps common province/state abbreviations to full names recognised by SerpApi's geocoder.
# "City, ON" returns 0 results; "City, Ontario" returns correct Canadian local pack.
PROVINCE_ABBR_TO_FULL: dict[str, str] = {
    # Canadian provinces & territories
    "AB": "Alberta", "BC": "British Columbia", "MB": "Manitoba",
    "NB": "New Brunswick", "NL": "Newfoundland and Labrador",
    "NS": "Nova Scotia", "NT": "Northwest Territories",
    "NU": "Nunavut", "ON": "Ontario", "PE": "Prince Edward Island",
    "QC": "Quebec", "SK": "Saskatchewan", "YT": "Yukon",
    # US states (common ones — SerpApi handles the rest)
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
    "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
    "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming", "DC": "District of Columbia",
}


def country_to_gl(country: str | None) -> str | None:
    """Maps a country name or ISO-2 code to a SerpApi `gl` code.
    Returns None if unknown — caller should omit the gl param."""
    if not country:
        return None
    c = country.strip()
    return COUNTRY_TO_GL.get(c) or COUNTRY_ISO_TO_GL.get(c.upper())


def province_to_gl(province: str | None) -> str | None:
    """Infer gl from province abbreviation when country field is absent or unrecognised.
    Currently handles Canadian provinces (→ 'ca'). Returns None if unclear."""
    if not province:
        return None
    if province.strip().upper() in CA_PROVINCE_CODES:
        return "ca"
    return None


def address_country_gl(address: str | None) -> str | None:
    """Identify which country an address is in. Returns gl code, or None if no
    clear country marker found (in which case the address is given the benefit
    of the doubt — kept rather than dropped)."""
    if not address:
        return None
    a = address.lower()
    for gl, patterns in COUNTRY_ADDRESS_MARKERS.items():
        for p in patterns:
            # Postal code patterns use uppercase [A-Z] — match against original address.
            # All other text patterns match against lowercased address.
            if re.search(p, address if "[A-Z]" in p else a):
                return gl
    return None


def expand_province(province: str | None) -> str | None:
    """Return the full province/state name for SerpApi's geocoder.
    If already a full name or unknown, returns as-is."""
    if not province:
        return None
    upper = province.strip().upper()
    return PROVINCE_ABBR_TO_FULL.get(upper, province.strip())


def extract_search_name(business_name: str, city: str) -> str:
    """Drop ', in {city}' suffix from a business name so SerpApi queries
    don't double up the location."""
    return re.sub(rf'\s+in\s+{re.escape(city)}\s*$', '', business_name, flags=re.IGNORECASE).strip()

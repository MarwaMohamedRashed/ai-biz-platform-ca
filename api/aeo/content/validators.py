"""Output post-processing + validation for content generation.

LLMs producing descriptions / FAQ / bios often add markdown headers,
character counts, alternative versions, and "Here is the description:"
preambles. These helpers strip the noise and return the bare content.

`_validate_content` runs after generation to flag obvious issues (too
short, too long, missing pieces). The frontend uses the returned warning
codes to highlight items that need owner attention.
"""
import re


def truncate_at_word(text: str, limit: int) -> str:
    """Hard-cap a string at `limit` chars without splitting a word."""
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit - 1].rsplit(' ', 1)[0] + "…"


# Markers we consider end-of-bio when the LLM tries to add commentary or
# alternatives below the actual bio text. Order doesn't matter -- we cut at
# the earliest match. Case-insensitive substring match.
_BIO_END_MARKERS = (
    "\n---", "\n***",
    "\nalternative", "\nalt:", "\nalt.",
    "\n*character count", "\n(character count",
    "\n*note:", "\n_(",
    "\n# ", "\n## ",
    "\n**bio", "\n**social",
    "\nbio:", "\nsocial bio:",
    "\nversion 2", "\nversion 1",
    "\nor:", "\nor,",
    "\nhere is", "\nhere's",
    "\nlet me know",
)

_BIO_LABEL_PREFIX = re.compile(
    r"^(?:bio|social\s+bio|instagram\s+bio|facebook\s+bio|caption|tagline)\s*:\s*",
    re.IGNORECASE,
)
_BIO_HEADING_LINE = re.compile(r"^#+\s+.*?\n+", re.MULTILINE)
_BIO_BOLD_WRAPPER = re.compile(r"^\*\*(.+?)\*\*\s*$")


def clean_bio(raw: str) -> str:
    """Extract clean bio text from an LLM response.

    Defends against the LLM producing:
      - markdown headers ("# LeapOne Bio")
      - bold wrappers ("**actual bio**")
      - character-count meta ("*Character count: 50*")
      - "Alternative if..." sections
      - leading "Bio:" / "Social Bio:" labels
      - surrounding quotes
    Returns the first clean bio sentence/line.
    """
    if not raw:
        return ""
    s = raw.strip()

    # Cut at the first end-marker (case-insensitive)
    s_lower = s.lower()
    cut = len(s)
    for marker in _BIO_END_MARKERS:
        idx = s_lower.find(marker)
        if 0 < idx < cut:
            cut = idx
    s = s[:cut].strip()

    # Strip leading markdown heading line
    s = _BIO_HEADING_LINE.sub("", s, count=1).strip()
    # Strip leading "Bio:" / "Social Bio:" / etc.
    s = _BIO_LABEL_PREFIX.sub("", s).strip()
    # Take first non-empty line (bios are one line)
    lines = [line.strip() for line in s.split("\n") if line.strip()]
    if lines:
        s = lines[0]
    # Strip **bold** wrapper if the whole line is wrapped in it
    m = _BIO_BOLD_WRAPPER.match(s)
    if m:
        s = m.group(1).strip()
    # Strip surrounding quotes
    s = s.strip("\"'").strip()
    return s


def clean_description(raw: str) -> str:
    """Light cleanup for descriptions.

    Less aggressive than clean_bio because descriptions are paragraph-form
    and we want to preserve content. Only strips leading markdown headers
    and obvious meta-prefixes ("Description:", "Here is the description:").
    """
    if not raw:
        return ""
    s = raw.strip()
    # Strip leading "Here is..." / "Here's..." preambles
    s = re.sub(r"^(here is|here's|here are)\s+(the\s+)?(\w+\s+){0,4}description:?\s*\n*",
               "", s, count=1, flags=re.IGNORECASE).strip()
    # Strip a leading markdown heading
    s = _BIO_HEADING_LINE.sub("", s, count=1).strip()
    # Strip a leading "Description:" / "Website Description:" label
    s = re.sub(
        r"^(?:description|website\s+description|google\s+description|gbp\s+description|"
        r"google\s+business\s+profile\s+description|yelp\s+description)\s*:\s*",
        "", s, flags=re.IGNORECASE,
    ).strip()
    return s


def validate_content(descriptions: dict, faq: list, social_bio: str) -> list[str]:
    """Return a list of validation warning codes (empty list = clean)."""
    warnings: list[str] = []
    if not descriptions.get("website") or len(descriptions["website"].split()) < 100:
        warnings.append("website_description_too_short")
    if not descriptions.get("gbp"):
        warnings.append("gbp_description_missing")
    elif len(descriptions["gbp"]) > 750:
        warnings.append("gbp_description_too_long")
    if not faq or len(faq) < 8:
        warnings.append("faq_too_few_items")
    if not social_bio or len(social_bio) > 150:
        warnings.append("social_bio_invalid_length")
    return warnings

"""Website probe — schema detection + signal extraction from homepage HTML.

One async function, `check_website(url, business_type)`, that:

  * Fetches the URL with a 10s timeout (follow redirects, browser UA)
  * Scans the lowercased HTML for LocalBusiness / FAQ schema (JSON-LD,
    HTML-escaped JSON-LD, and microdata fallback)
  * Runs `extract_text_signals` over the body to pick up dietary,
    service-tag, and cuisine signals (with sub-specialty guardrails)

Returns a dict the audit pipeline + competitor scoring + content
generation all consume. Schema/signal failures degrade to `reachable:
False` with empty signal lists — never raises.

KNOWN LIMITATION: static HTML scan only. Schema injected at runtime by
JavaScript (Yoast SEO on some configs, Webflow's CMS, Wix's structured-
data plugin, etc.) is invisible. The audit recommendation copy says
"we couldn't detect" rather than "you're missing" to avoid accusing
owners of a fault that doesn't exist.

Originally lived in api/aeo/router.py lines 557-654. Moved here during
Tier 6 so the audit engine + competitor module can import without
needing the router back-reference. `check_competitor_websites` in
competitors.py hoists its lazy import to a top-level one as a result.
"""
import httpx

from .signals import extract_text_signals


# LocalBusiness JSON-LD subtypes recognised by Google's structured data
# crawler. Keeping the full list here (rather than in signals.py) since
# it's specifically about *schema* detection, not text signals.
_LB_SUBTYPES = {
    "restaurant", "foodestablishment", "cafeorcoffeeshop", "fastfoodrestaurant",
    "barorpub", "bakery", "icecreamshop", "winery", "distillery",
    "dentist", "physician", "medicalbusiness", "healthandbeautybusiness",
    "medicalclinic", "optician", "pharmacy", "physiotherapist",
    "homeandconstructionbusiness", "electrician", "generalcontractor",
    "hvacbusiness", "housepainter", "locksmith", "movingcompany",
    "plumber", "roofingcontractor",
    "autodealer", "autorepair", "autobodyshop",
    "legalservice", "accountingservice", "financialservice",
    "insuranceagency", "realestateagent",
    "hairsalon", "beautysalon", "nailsalon", "dayspa", "tattooparlor",
    "store", "sportinggoods", "clothingstore", "electronicsstore",
    "lodging", "hotel", "motel", "bedandbreakfast",
    "veterinarycare", "animalshelter",
}


async def check_website(website: str | None, business_type: str | None = None) -> dict:
    if not website:
        return {"reachable": False, "has_local_business_schema": False, "has_faq_schema": False}

    url = website if website.startswith("http") else f"https://{website}"
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=10.0) as client:
            response = await client.get(url, headers={"User-Agent": "Mozilla/5.0 (LeapOne AEO Audit Bot)"})
            response.raise_for_status()
            html = response.text.lower()
    except Exception as e:
        print(f"[AEO] Website fetch failed for {url}: {e}")
        return {"reachable": False, "has_local_business_schema": False, "has_faq_schema": False}

    # Schema detection — we look for three different surface forms:
    #   1. JSON-LD ("@type":"LocalBusiness")  — the modern standard
    #   2. HTML-escaped JSON-LD (&quot;@type&quot;:&quot;LocalBusiness&quot;)
    #      — happens when a CMS exports the schema via a template that
    #      escapes the JSON before insertion
    #   3. Microdata (itemtype="https://schema.org/LocalBusiness") — older
    #      format still valid per Google
    html_nospace = html.replace(" ", "")
    # html_nospace_unesc — also collapse HTML-escaped quotes so the escaped
    # JSON-LD pattern (`&quot;@type&quot;:&quot;LocalBusiness&quot;`)
    # collapses to the same shape as the unescaped one.
    html_nospace_unesc = html_nospace.replace("&quot;", '"').replace("&#34;", '"')

    _all_lb_keys = {"localbusiness"} | _LB_SUBTYPES
    has_local_business = any(
        f'"@type":"{t}"' in html_nospace_unesc for t in _all_lb_keys
    )
    # Microdata fallback — older sites use itemtype="schema.org/LocalBusiness"
    if not has_local_business:
        has_local_business = any(
            f'schema.org/{t}' in html_nospace.replace("https://", "").replace("http://", "")
            for t in {"LocalBusiness"} | {s[0].upper() + s[1:] for s in _LB_SUBTYPES}
        )
    has_faq = (
        '"@type":"faqpage"' in html_nospace_unesc
        or 'schema.org/faqpage' in html_nospace.replace("https://", "").replace("http://", "")
    )

    # Dietary / cuisine / clinic-service signal extraction from homepage text.
    # Shared with _run_audit_core which runs the same scan over the user's
    # free-form `services` field so signals declared in onboarding (but not yet
    # on the website) still drive query enrichment.
    #
    # service_min_matches=2 because long-form HTML contains many one-off
    # mentions of specialties that aren't the practice's primary identity.
    # E.g. Burlington Family Dentists' page listed "pediatric dentistry" once
    # in a services grid and the detector labelled the whole practice as
    # pediatric. A title-tag match always counts regardless (see helper).
    # business_type adds a second guardrail: when the owner selected a
    # specific specialty in onboarding (dentist, physiotherapist, etc.),
    # body-content sub-specialty matches are suppressed entirely.
    signals = extract_text_signals(
        html,
        service_min_matches=2,
        business_type=business_type,
    )
    dietary_tags = signals["dietary_tags"]
    service_tags = signals["service_tags"]
    cuisine_hint = signals["cuisine"]
    cuisine_hint_parent = signals["cuisine_parent"]

    print(f"[AEO] Website: reachable=True local_schema={has_local_business} faq_schema={has_faq} dietary={dietary_tags} services={service_tags} cuisine_hint={cuisine_hint}")
    return {
        "reachable": True,
        "has_local_business_schema": has_local_business,
        "has_faq_schema": has_faq,
        "dietary_tags": dietary_tags,
        "service_tags": service_tags,
        "cuisine_hint": cuisine_hint,
        "cuisine_hint_parent": cuisine_hint_parent,
    }

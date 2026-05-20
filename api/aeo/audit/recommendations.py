"""Rule-based recommendations engine.

Takes a completed audit result (the per-pillar data + breakdown + recency
check) and emits an ordered list of recommendations, each tied to a
specific pillar and weighted by impact.

Originally lived in `api/aeo/router.py` between the scoring function and
`_run_audit_core`. Moved here so the routes file stops being a 4,800-line
god module.
"""
from .verticals import (
    CITY_SUBREDDITS,
    city_to_subreddit_url,
    is_b2b_business,
    is_dentist_business,
    is_food_business,
    is_healthcare_business,
    is_legal_business,
    is_realtor_business,
    is_trades_business,
    user_directories_only,
)


def generate_recommendations(
    business: dict,
    perplexity: dict,
    google: dict,
    website_check: dict,
    breakdown: dict,
    recency: dict,
    chatgpt: dict | None = None,
) -> list[dict]:
    """
    Maps each pillar gap to a specific, actionable recommendation.
    Returns a list sorted by impact (highest points first).
    """
    recs = []
    kg = google["knowledge_graph"]
    lp = google["local_pack"]
    has_gbp = kg["found"] or lp["present"]
    rating = kg.get("rating") or lp.get("rating") or 0
    reviews_count = kg.get("reviews_count") or lp.get("reviews") or 0

    # When we have BOTH a Knowledge Graph card and a Local Pack entry, we
    # have full visibility into the owner's GBP and can definitively call
    # out missing fields. When we only have LP (no KG, common for category
    # searches like "dentist Burlington"), we DON'T know if category/phone/
    # website are missing on the actual profile — Google just chose not to
    # render the KG for this query. We must NOT recommend "add your
    # category" if the owner can look at their real GBP and see it's there.
    #
    # NOTE: when B (branded SerpApi call) lands, kg["found"] will be True
    # whenever Google has any KG for this business — so these guards
    # naturally adapt. Until then, they prevent misleading recs.
    have_full_gbp_visibility = kg["found"]

    # ─── GBP pillar ──────────────────────────────────────────
    if not has_gbp:
        recs.append({
            "pillar": "gbp",
            "title": "Claim your Google Business Profile",
            "description": "Your business doesn't appear in Google's local listings. A claimed GBP is the single most important signal for local AI search.",
            "action": "Visit business.google.com and claim or create your listing for this business.",
            "difficulty": "easy",
            "impact": 15,
            "url": "https://business.google.com",
        })
    elif have_full_gbp_visibility:
        # Only emit "missing field" recs when we can SEE the owner's KG data
        # — otherwise we'd be making accusations we can't back up.
        if not kg.get("type") and breakdown["gbp"] < 25:
            recs.append({
                "pillar": "gbp",
                "title": "Set your primary GBP category",
                "description": "Your Google Business Profile doesn't have a primary category set. Categories are the #1 local pack ranking factor.",
                "action": "In your GBP dashboard, set your primary business category (e.g. 'Physiotherapy clinic'). Add 2-3 secondary categories.",
                "difficulty": "easy",
                "impact": 5,
                "url": "https://business.google.com",
            })
        if not (kg.get("website") or kg.get("phone")) and not business.get("website"):
            recs.append({
                "pillar": "gbp",
                "title": "Add a phone number and website to your GBP",
                "description": "Customers need a way to contact you directly from Google.",
                "action": "Add your business phone and website URL in your GBP profile.",
                "difficulty": "easy",
                "impact": 5,
                "url": "https://business.google.com",
            })
    else:
        # LP-present + KG-empty path: we know they're on Google but can't
        # see their KG details. Don't accuse — invite a verification check.
        # This rec applies whether or not the branded search (Part B) found
        # a KG, since LP-only visibility still suggests the profile could
        # be more discoverable.
        recs.append({
            "pillar": "gbp",
            "title": "Review your Google Business Profile",
            "description": "Your business appears in Google's local results but we couldn't see the full Knowledge Panel details on category searches. A complete GBP (description, photos, posts) makes AI engines more likely to cite you.",
            "action": "Open business.google.com and check that your category, description, hours, photos, and contact info are all complete and current.",
            "difficulty": "easy",
            "impact": 5,
            "url": "https://business.google.com",
        })

    # ─── Reviews pillar ──────────────────────────────────────
    count_label = str(reviews_count) if reviews_count else "unknown"
    if not reviews_count or reviews_count < 10:
        recs.append({
            "pillar": "reviews",
            "title": f"Get to 10+ Google reviews (current: {count_label})",
            "description": "AI search engines use review count as a strong trust signal. Below 10 reviews, your business looks new or unestablished.",
            "action": "Send a review request link to your last 10 customers. Use Google's free 'Get more reviews' QR code generator in your GBP dashboard.",
            "difficulty": "medium",
            "impact": 6,
        })
    elif reviews_count < 50:
        recs.append({
            "pillar": "reviews",
            "title": f"Get to 50+ Google reviews (current: {reviews_count})",
            "description": "50+ reviews puts you in the top tier for review volume in your category.",
            "action": "Set up a recurring system: ask every customer for a review at the moment of service completion.",
            "difficulty": "medium",
            "impact": 6,
        })

    if rating > 0 and rating < 4.0:
        recs.append({
            "pillar": "reviews",
            "title": f"Improve your rating above 4.0 (current: {rating})",
            "description": "Ratings below 4.0 actively hurt AI citations. AI engines avoid recommending businesses with mixed reputations.",
            "action": "Respond to every negative review professionally. Identify the top complaint pattern and address it operationally.",
            "difficulty": "hard",
            "impact": 10,
        })
    elif rating > 0 and rating < 4.5:
        recs.append({
            "pillar": "reviews",
            "title": f"Push your rating above 4.5 (current: {rating})",
            "description": "4.5+ is the threshold for 'highly rated' in most AI engines.",
            "action": "Respond to every review. Encourage your most satisfied customers to leave 5-star feedback.",
            "difficulty": "medium",
            "impact": 5,
        })

    # Recency check — only shown when we successfully checked and the business is stale
    if recency.get("checked") and recency.get("recent") is False:
        days = recency.get("days_since_last")
        last = recency.get("last_review_date") or "more than 3 months ago"
        days_label = f"{days} days ago" if days else last
        recs.append({
            "pillar": "reviews",
            "title": f"You haven't received new reviews in 3+ months (last: {days_label})",
            "description": "Review recency is a trust signal for AI engines. A business with stale reviews looks inactive, even with a high total count.",
            "action": "Re-activate your review request process. Text or email your last 20 customers a direct link to your Google review page. Consider adding a QR code at your front desk.",
            "difficulty": "medium",
            "impact": 7,
        })

    # ─── Website & Schema pillar ─────────────────────────────
    if not business.get("website"):
        recs.append({
            "pillar": "website",
            "title": "Add your website URL to your profile",
            "description": "Without a website, AI engines have no authoritative source to cite about your business.",
            "action": "Add your website URL in the LeapOne profile settings. If you don't have one, free options include Google Sites or a one-page Carrd.",
            "difficulty": "medium",
            "impact": 8,
        })
    elif not website_check["reachable"]:
        recs.append({
            "pillar": "website",
            "title": "Your website is unreachable",
            "description": "Our crawler couldn't reach your website. AI engines can't cite content they can't access.",
            "action": "Test your site in an incognito browser. If it's down, contact your hosting provider. If it returns errors, check for SSL or redirect issues.",
            "difficulty": "medium",
            "impact": 8,
        })
    else:
        if not website_check["has_local_business_schema"]:
            recs.append({
                "pillar": "website",
                "title": "Check for LocalBusiness schema on your homepage",
                # Honest framing — our HTML scan can't see schema injected by
                # JavaScript at runtime (Yoast, Webflow CMS, Wix plugins, etc.).
                # The owner might already have it via a plugin; we say "couldn't
                # detect" rather than "is missing" so we don't accuse a fault
                # that may not exist. Same trust principle as the GBP fix.
                "description": "We couldn't detect LocalBusiness JSON-LD on your homepage. If you use a CMS plugin that adds schema (Yoast SEO, Rank Math, Webflow), it may be injected via JavaScript — verify in Google's Rich Results Test. If it's missing, the Content tab has a copy-paste schema you can add.",
                "action": "Run your homepage through Google's Rich Results Test (search.google.com/test/rich-results). If LocalBusiness isn't listed, paste the schema from the Content tab into your <head> tag.",
                "difficulty": "medium",
                "impact": 6,
                "url": "https://search.google.com/test/rich-results",
            })
        if not website_check["has_faq_schema"]:
            recs.append({
                "pillar": "website",
                "title": "Check for FAQ schema on your homepage",
                "description": "We couldn't detect FAQ schema on your homepage. FAQ schema is the most-cited structured-data type by AI engines like ChatGPT and Perplexity. If your CMS plugin injects schema via JavaScript it won't show on our scan — verify in Google's Rich Results Test before adding new schema.",
                "action": "Run your homepage through Google's Rich Results Test. If FAQ schema isn't there, use the Content tab to generate Q&A pairs + JSON-LD you can paste into your <head>.",
                "difficulty": "medium",
                "impact": 6,
                "url": "https://search.google.com/test/rich-results",
            })

    # ─── Local Search Presence pillar ────────────────────────
    if not google["local_pack"]["present"]:
        recs.append({
            "pillar": "local_search",
            "title": "Get into Google's local 'map pack'",
            "description": "You're not appearing in Google's top-3 local results for your category. The local pack is where most customers click first.",
            "action": "Optimize your GBP: complete every field, upload 10+ photos, post weekly updates, get reviews. Make sure your address is verified and your service area is set correctly.",
            "difficulty": "hard",
            "impact": 10,
        })
    if not google["organic"]["present"]:
        recs.append({
            "pillar": "local_search",
            "title": "Get listed in local directories",
            "description": "Your business doesn't appear in regular Google search results for your category. Citations from local directories build the authority that fixes this.",
            "action": "List your business on Yelp, Yellow Pages Canada, BBB, and 2-3 industry-specific directories. Use identical NAP (name, address, phone) on every listing.",
            "difficulty": "medium",
            "impact": 5,
        })

    # ─── AI Citation pillar ──────────────────────────────────
    if chatgpt and not chatgpt["mentioned"]:
        recs.append({
            "pillar": "ai_citation",
            "title": "Build your presence in ChatGPT's training data",
            "description": (
                "ChatGPT answers from its training knowledge, not live search. "
                "Your business isn't prominent enough yet to appear in its responses. "
                "These actions build the web footprint that gets picked up in future AI model updates (typically 6–12 months)."
            ),
            "action": (
                "1. Claim and fully complete your Yelp, TripAdvisor, and Yellow Pages profiles — "
                "these platforms are heavily indexed in AI training data. "
                "2. Get listed in your local Chamber of Commerce and BBB. "
                "3. Seek a mention in a local news article or industry publication. "
                "4. Add a detailed FAQ page to your website — Q&A content is exactly what LLMs train on."
            ),
            "difficulty": "hard",
            "impact": 6,
        })
    if not perplexity["mentioned"]:
        recs.append({
            "pillar": "ai_citation",
            "title": "Get cited by Perplexity",
            "description": "Perplexity searches the web in real time. It favors authoritative sources like Yelp, Reddit, news sites, and well-structured business listings.",
            "action": "Create or update your business listing on directories Perplexity crawls: Yelp, BBB, Yellow Pages, Foursquare. Ensure your website has clear, factual content about your services.",
            "difficulty": "hard",
            "impact": 6,
        })
    if not google["ai_overview"]["mentioned"]:
        recs.append({
            "pillar": "ai_citation",
            "title": "Optimize for Google AI Overview",
            "description": "Google AI Overview cites businesses with strong GBP + content + schema together. It's the hardest AI engine to influence but rewards a complete profile.",
            "action": "Add a 150-200 word business description on your homepage that directly answers 'what do you do, where, and for whom'. Use the description we generated for you in the Content tab.",
            "difficulty": "hard",
            "impact": 6,
        })

    # ─── Canadian vertical-specific directory recommendations ─────
    # Each block is gated by a vertical detector AND by whether the user
    # is already detected on that directory in their organic results.
    # We always compute user_dirs because Reddit detection is universal
    # (fires for every business) so we always need the directory presence
    # data anyway.
    btype = business.get("type")
    user_dirs = user_directories_only(
        google.get("per_query", []),
        business.get("name", ""),
    )

    # Trades — HomeStars + TrustedPros
    if is_trades_business(btype):
        if "HomeStars" not in user_dirs:
            recs.append({
                "pillar": "ai_citation",
                "title": "Claim your HomeStars profile",
                "description": "HomeStars is Canada's largest trades directory and one of the most-cited sources by AI engines (ChatGPT, Perplexity, Google AI Overview) when answering 'best contractor in <city>' questions. Trades businesses without a HomeStars profile are dramatically less likely to be cited.",
                "action": "Create a free contractor profile at homestars.com/create-account. Complete your services, service area, and request reviews from your last 5 satisfied customers.",
                "difficulty": "easy",
                "impact": 4,
                "url": "https://homestars.com/create-account",
            })
        if "TrustedPros" not in user_dirs:
            recs.append({
                "pillar": "ai_citation",
                "title": "Claim your TrustedPros profile",
                "description": "TrustedPros is the second-largest Canadian trades directory and a trusted citation source for AI engines. Combined with a HomeStars listing, it materially boosts your chance of being cited in AI answers about local trades.",
                "action": "Sign up as a contractor at trustedpros.ca. Verify your business details and request a few customer reviews to bootstrap your rating.",
                "difficulty": "easy",
                "impact": 3,
                "url": "https://www.trustedpros.ca/contractor",
            })

    # Healthcare — RateMDs (any healthcare) + Opencare (dentists specifically)
    if is_healthcare_business(btype):
        if "RateMDs" not in user_dirs:
            recs.append({
                "pillar": "ai_citation",
                "title": "Claim your RateMDs profile",
                "description": "RateMDs is Canada's largest healthcare-provider rating site. AI engines cite it heavily when patients search 'best dentist/doctor/physiotherapist near me'. Healthcare businesses without a RateMDs profile are routinely missed in AI answers about local care.",
                "action": "Find your existing RateMDs listing (created automatically from public records) at ratemds.com and claim it, or create a new profile. Verify your credentials, hours, and services.",
                "difficulty": "easy",
                "impact": 4,
                "url": "https://www.ratemds.com",
            })
        if is_dentist_business(btype) and "Opencare" not in user_dirs:
            recs.append({
                "pillar": "ai_citation",
                "title": "Claim your Opencare profile",
                "description": "Opencare is the dominant Canadian directory for dental practices and is regularly cited by ChatGPT and Perplexity for 'best dentist in <city>' queries. Dentists not on Opencare miss a category-specific citation source.",
                "action": "Sign up as a dental practice at opencare.com/dentists/join. Complete your services, accepted insurance, and office hours.",
                "difficulty": "easy",
                "impact": 3,
                "url": "https://www.opencare.com/dentists/join/",
            })

    # Food — OpenTable + TripAdvisor
    if is_food_business(btype):
        if "OpenTable" not in user_dirs:
            recs.append({
                "pillar": "ai_citation",
                "title": "Claim your OpenTable listing",
                "description": "OpenTable is the most-cited restaurant-discovery source for AI engines in Canada. Even if you don't take reservations through them, the directory presence alone boosts visibility in AI search answers about local dining.",
                "action": "Sign up at restaurant.opentable.com. You can list your restaurant for discovery without enabling reservations.",
                "difficulty": "easy",
                "impact": 4,
                "url": "https://restaurant.opentable.com",
            })
        if "TripAdvisor" not in user_dirs:
            recs.append({
                "pillar": "ai_citation",
                "title": "Claim your TripAdvisor business listing",
                "description": "TripAdvisor is widely cited by Perplexity and Google AI Overview for restaurant queries — especially when the searcher includes 'best' or 'top'. A complete TripAdvisor profile is one of the highest-ROI citations for restaurants in Canada.",
                "action": "Claim your business at tripadvisor.com/Owners. Add photos, menu, and respond to recent reviews.",
                "difficulty": "easy",
                "impact": 3,
                "url": "https://www.tripadvisor.com/Owners",
            })

    # Legal — LawyerLocate
    if is_legal_business(btype) and "LawyerLocate" not in user_dirs:
        recs.append({
            "pillar": "ai_citation",
            "title": "Claim your LawyerLocate profile",
            "description": "LawyerLocate is a Canadian-specific lawyer directory that ranks well in AI engine answers about legal services. Combined with a LinkedIn presence, it materially boosts AI citation rates for solo practitioners and small firms.",
            "action": "Register at lawyerlocate.ca/lawyers/register. List your practice areas, jurisdictions, and contact details.",
            "difficulty": "easy",
            "impact": 3,
            "url": "https://www.lawyerlocate.ca/lawyers/register",
        })

    # Realtor — Realtor.ca (CREA-national)
    if is_realtor_business(btype) and "Realtor.ca" not in user_dirs:
        recs.append({
            "pillar": "ai_citation",
            "title": "Ensure you appear on Realtor.ca",
            "description": "Realtor.ca is the national directory operated by the Canadian Real Estate Association (CREA). It is the single most-cited source by AI engines for Canadian real estate queries. Active CREA membership puts you on Realtor.ca automatically — verify your listing is complete and current.",
            "action": "Confirm your CREA membership is active via your provincial real estate board, then verify your Realtor.ca profile shows current listings, photo, contact details, and specializations.",
            "difficulty": "easy",
            "impact": 4,
            "url": "https://www.crea.ca/membership/",
        })

    # B2B / professional services — LinkedIn Company Page
    # AI engines (especially Perplexity and Google AI Overview) cite
    # LinkedIn pages heavily when answering questions about professional
    # services, B2B vendors, lawyers, accountants, etc.
    if is_b2b_business(btype) and "LinkedIn" not in user_dirs:
        recs.append({
            "pillar": "ai_citation",
            "title": "Activate your LinkedIn Company Page",
            "description": "For B2B and professional services, LinkedIn is one of the highest-leverage AI citation surfaces. AI engines weight LinkedIn pages heavily when answering 'find me a <profession> in <city>' queries. Static profiles are ignored — pages with weekly posting and active engagement get cited far more often.",
            "action": "Create or activate your LinkedIn Company Page. Commit to one industry-relevant post per week. Have employees and clients follow the page. Pin a clear value-proposition post at the top.",
            "difficulty": "medium",
            "impact": 3,
            "url": "https://www.linkedin.com/company/setup/new/",
        })

    # ─── Reddit (community citation surface, every vertical) ──────
    # Reddit is a top-3 AI citation domain after Google's $60M Reddit data
    # licensing deal. Citations come from organic discussion (you can't
    # claim a Reddit listing the way you do Yelp), so the action is
    # community engagement — explicitly framed as long-term, not a quick
    # win. We surface this for every vertical because it applies broadly.
    if "Reddit" not in user_dirs:
        city = business.get("city") or ""
        subreddit_url = city_to_subreddit_url(city)
        recs.append({
            "pillar": "ai_citation",
            "title": "Build authentic Reddit presence",
            "description": "Reddit is one of the most-cited AI citation sources in 2026 — Google licensed Reddit data for $60M and AI Overview / Perplexity / ChatGPT all weight Reddit threads heavily for 'best X in <city>' queries. Reddit citations come from real community discussion, not paid listings. This is a long-term play, not a quick win.",
            "action": (
                f"Engage authentically in r/{CITY_SUBREDDITS.get(city.strip().lower(), 'your city subreddit')} "
                "and industry-relevant subreddits. Answer questions in your area of expertise without "
                "self-promoting. Ask satisfied customers to share their experience when relevant threads "
                "come up. Avoid astroturfing — Reddit detects and bans it fast, and the public shaming "
                "is worse than no presence."
            ),
            "difficulty": "hard",
            "impact": 3,
            "url": subreddit_url,
        })

    # ─── Universal AI-engine listings (any vertical) ──────────────
    # Apple Business Connect feeds Apple Maps + Apple Intelligence.
    # Bing Places feeds Microsoft Copilot. Both are growing AI citation
    # sources; both are free and under-claimed by Canadian SMBs.
    # We can't easily detect presence from SerpApi (Apple Maps + Bing Places
    # don't surface in Google's index) so we fire for all businesses at
    # low impact — the cost of ignoring is much higher than the noise of
    # showing one extra rec.
    recs.append({
        "pillar": "ai_citation",
        "title": "Claim your Apple Business Connect listing",
        "description": "Apple Business Connect (free) controls how your business shows up in Apple Maps and is increasingly cited by Apple Intelligence on iPhone/iPad. Most Canadian SMBs have not claimed their listing — this is one of the lowest-effort, highest-incremental-reach citations available right now.",
        "action": "Visit businessconnect.apple.com, sign in with your Apple ID, find your business, and verify ownership. Takes 5–10 minutes.",
        "difficulty": "easy",
        "impact": 2,
        "url": "https://businessconnect.apple.com",
    })
    recs.append({
        "pillar": "ai_citation",
        "title": "Claim your Bing Places listing",
        "description": "Bing Places feeds Microsoft Copilot's local search answers. With Copilot integrated into Windows 11 and Microsoft 365, Bing Places presence is a growing AI citation factor. Bing Places will auto-import your Google Business Profile data — you just need to verify ownership.",
        "action": "Visit bingplaces.com, import from Google, verify ownership, and confirm your details. Takes 5 minutes.",
        "difficulty": "easy",
        "impact": 2,
        "url": "https://www.bingplaces.com",
    })

    # Sort by impact (highest first)
    recs.sort(key=lambda r: r["impact"], reverse=True)
    return recs

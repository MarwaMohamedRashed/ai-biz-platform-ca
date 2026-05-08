"""
Tests for Reddit + LinkedIn citation extensions (Phase 5, 2026-05-08):
  - Reddit in DIRECTORY_DOMAINS + detection
  - city -> subreddit URL helper
  - Reddit rec (universal, conditional on not-on-Reddit)
  - _is_b2b_business detector
  - LinkedIn Company Page rec (B2B-only, conditional on not-on-LinkedIn)
"""
from aeo.router import (
    _is_b2b_business,
    _city_to_subreddit_url,
    _user_directories_only,
    generate_recommendations,
    CITY_SUBREDDITS,
)


# ─── _city_to_subreddit_url ───────────────────────────────────────────────
class TestCityToSubredditUrl:
    def test_known_canadian_city(self):
        assert _city_to_subreddit_url("Toronto")  == "https://www.reddit.com/r/toronto"
        assert _city_to_subreddit_url("Ottawa")   == "https://www.reddit.com/r/ottawa"
        assert _city_to_subreddit_url("Vancouver") == "https://www.reddit.com/r/vancouver"

    def test_case_insensitive(self):
        assert _city_to_subreddit_url("TORONTO") == "https://www.reddit.com/r/toronto"
        assert _city_to_subreddit_url("toronto") == "https://www.reddit.com/r/toronto"

    def test_montreal_french_accent(self):
        # Montréal with accent should still resolve
        assert _city_to_subreddit_url("Montréal") == "https://www.reddit.com/r/montreal"

    def test_unknown_city_falls_back_to_search(self):
        url = _city_to_subreddit_url("Smallville")
        assert "reddit.com/search" in url
        assert "Smallville" in url

    def test_empty_returns_canada_subreddit(self):
        assert _city_to_subreddit_url(None) == "https://www.reddit.com/r/canada"
        assert _city_to_subreddit_url("")   == "https://www.reddit.com/r/canada"

    def test_city_with_spaces_in_search_fallback(self):
        # Quebec City IS in the map
        assert _city_to_subreddit_url("Quebec City") == "https://www.reddit.com/r/quebeccity"
        # But unknown multi-word city falls back, with + encoding
        url = _city_to_subreddit_url("Some Unknown Town")
        assert "Some+Unknown+Town" in url

    def test_canadian_subreddits_present_for_top_cities(self):
        # Sanity — confirm the top-15 Canadian cities by population are mapped
        for city in ["toronto", "ottawa", "vancouver", "montreal", "calgary",
                     "edmonton", "winnipeg", "halifax", "victoria",
                     "mississauga", "brampton", "hamilton", "saskatoon"]:
            assert city in CITY_SUBREDDITS, f"missing: {city}"


# ─── _is_b2b_business ─────────────────────────────────────────────────────
class TestIsB2bBusiness:
    def test_legal_verticals(self):
        for v in ["lawyer", "attorney", "law firm", "law office", "paralegal"]:
            assert _is_b2b_business(v), f"missed {v!r}"

    def test_accounting_verticals(self):
        for v in ["accountant", "accounting service", "bookkeeper", "CPA"]:
            assert _is_b2b_business(v), f"missed {v!r}"

    def test_consulting_verticals(self):
        for v in ["consultant", "management consultant", "consulting firm",
                  "business advisor", "advisory firm"]:
            assert _is_b2b_business(v), f"missed {v!r}"

    def test_agency_verticals(self):
        for v in ["marketing agency", "advertising agency", "digital agency",
                  "web design"]:
            assert _is_b2b_business(v), f"missed {v!r}"

    def test_financial_verticals(self):
        for v in ["financial advisor", "financial planner", "wealth management"]:
            assert _is_b2b_business(v), f"missed {v!r}"

    def test_real_estate_overlaps_intentionally(self):
        # Realtors are also B2B — they get BOTH Realtor.ca rec AND LinkedIn rec
        assert _is_b2b_business("real estate agent")
        assert _is_b2b_business("realtor")

    def test_recruiting_and_staffing(self):
        for v in ["recruiter", "staffing agency", "recruitment firm"]:
            assert _is_b2b_business(v), f"missed {v!r}"

    def test_consumer_verticals_rejected(self):
        for v in ["restaurant", "hair salon", "dentist", "plumber",
                  "bakery", "café", "physiotherapy clinic", "retail store"]:
            assert not _is_b2b_business(v), f"false positive on {v!r}"

    def test_empty_returns_false(self):
        assert not _is_b2b_business(None)
        assert not _is_b2b_business("")


# ─── Reddit detection ────────────────────────────────────────────────────
class TestRedditDetection:
    def _q(self, organic):
        return {"organic_results_raw": organic}

    def test_reddit_thread_about_user_detected(self):
        per_query = [self._q([
            {
                "link": "https://www.reddit.com/r/toronto/comments/abc/best_dentist/",
                "title": "Best dentist in Toronto? - r/toronto",
                "snippet": "I really recommend Smile Dental, they were great with my kids.",
            },
        ])]
        out = _user_directories_only(per_query, "Smile Dental")
        assert "Reddit" in out

    def test_reddit_subdomain_recognised(self):
        # old.reddit.com should still match
        per_query = [self._q([
            {
                "link": "https://old.reddit.com/r/toronto/comments/abc/",
                "title": "Smile Dental - reddit",
                "snippet": "",
            },
        ])]
        out = _user_directories_only(per_query, "Smile Dental")
        assert "Reddit" in out

    def test_reddit_thread_about_competitor_not_user(self):
        per_query = [self._q([
            {
                "link": "https://www.reddit.com/r/toronto/comments/abc/",
                "title": "Bright Smile Clinic was awful - reddit",
                "snippet": "",
            },
        ])]
        out = _user_directories_only(per_query, "Smile Dental")
        # User name not in title/snippet → not detected
        assert "Reddit" not in out


# ─── End-to-end recommendations ──────────────────────────────────────────
def _make_args(business_type, business_name="Test Biz", city="Toronto",
               province="ON", on_dirs=None):
    """Build minimum-viable audit context for generate_recommendations()."""
    on_dirs = on_dirs or []
    organic = []
    for d in on_dirs:
        domain_for_label = {
            "Yelp":         "yelp.com",
            "TripAdvisor":  "tripadvisor.com",
            "BBB":          "bbb.org",
            "HomeStars":    "homestars.com",
            "TrustedPros":  "trustedpros.ca",
            "RateMDs":      "ratemds.com",
            "Opencare":     "opencare.com",
            "OpenTable":    "opentable.com",
            "LawyerLocate": "lawyerlocate.ca",
            "Realtor.ca":   "realtor.ca",
            "n49":          "n49.com",
            "LinkedIn":     "linkedin.com",
            "Reddit":       "reddit.com",
        }.get(d, "example.com")
        organic.append({
            "link":    f"https://{domain_for_label}/profile/x",
            "title":   f"{business_name} - {d}",
            "snippet": "",
        })

    business = {
        "name": business_name, "type": business_type,
        "city": city, "province": province,
        "country": "Canada", "website": "https://example.com",
    }
    perplexity = {"mentioned": True, "snippet": None}
    google = {
        "ai_overview":     {"mentioned": True, "snippet": None},
        "knowledge_graph": {"found": True, "rating": 4.8, "reviews_count": 50,
                            "type": business_type, "website": "https://example.com",
                            "phone": "555-0123"},
        "local_pack":      {"present": True, "position": 1, "rating": 4.8, "reviews": 50},
        "organic":         {"present": True, "position": 1},
        "per_query":       [{"organic_results_raw": organic}],
    }
    website_check = {"reachable": True, "has_local_business_schema": True, "has_faq_schema": True}
    breakdown = {"gbp": 25, "reviews": 22, "website": 20, "local_search": 15, "ai_citation": 18}
    recency = {"checked": True, "recent": True, "days_since_last": 5, "last_review_date": None}
    chatgpt = {"mentioned": True, "snippet": None}
    return business, perplexity, google, website_check, breakdown, recency, chatgpt


class TestRedditRecommendation:
    def test_reddit_rec_fires_when_not_detected(self):
        # Universal: any business not on Reddit gets the rec
        recs = generate_recommendations(*_make_args("dentist", "Smile Dental"))
        titles = [r["title"] for r in recs]
        assert any("Reddit" in t for t in titles)

    def test_reddit_rec_does_not_fire_when_already_on_reddit(self):
        recs = generate_recommendations(*_make_args(
            "dentist", "Smile Dental", on_dirs=["Reddit"]))
        titles = [r["title"] for r in recs]
        assert not any("Reddit" in t for t in titles)

    def test_reddit_rec_uses_city_subreddit_when_known(self):
        recs = generate_recommendations(*_make_args(
            "plumber", "Joe's Plumbing", city="Ottawa"))
        reddit_recs = [r for r in recs if "Reddit" in r["title"]]
        assert len(reddit_recs) == 1
        assert "ottawa" in reddit_recs[0]["url"]

    def test_reddit_rec_falls_back_when_city_unknown(self):
        recs = generate_recommendations(*_make_args(
            "plumber", "Joe's Plumbing", city="Smallville"))
        reddit_recs = [r for r in recs if "Reddit" in r["title"]]
        assert len(reddit_recs) == 1
        # Should be a search URL, not r/smallville
        assert "search" in reddit_recs[0]["url"]

    def test_reddit_rec_difficulty_is_hard(self):
        # Reddit engagement is genuinely hard / long-term — frame honestly
        recs = generate_recommendations(*_make_args("dentist", "X"))
        reddit_recs = [r for r in recs if "Reddit" in r["title"]]
        assert reddit_recs[0]["difficulty"] == "hard"

    def test_reddit_rec_warns_against_astroturfing(self):
        recs = generate_recommendations(*_make_args("dentist", "X"))
        reddit_recs = [r for r in recs if "Reddit" in r["title"]]
        # Honest framing — must include the astroturfing warning so we
        # don't lead customers into a self-promotional ban
        assert "astroturf" in reddit_recs[0]["action"].lower()


class TestLinkedInRecommendation:
    def test_lawyer_gets_linkedin_rec(self):
        recs = generate_recommendations(*_make_args("law firm", "Smith Law"))
        titles = [r["title"] for r in recs]
        assert any("LinkedIn" in t for t in titles)

    def test_accountant_gets_linkedin_rec(self):
        recs = generate_recommendations(*_make_args("accountant", "ACME CPA"))
        titles = [r["title"] for r in recs]
        assert any("LinkedIn" in t for t in titles)

    def test_consultant_gets_linkedin_rec(self):
        recs = generate_recommendations(*_make_args("management consultant", "X"))
        titles = [r["title"] for r in recs]
        assert any("LinkedIn" in t for t in titles)

    def test_marketing_agency_gets_linkedin_rec(self):
        recs = generate_recommendations(*_make_args("digital marketing agency", "X"))
        titles = [r["title"] for r in recs]
        assert any("LinkedIn" in t for t in titles)

    def test_realtor_gets_linkedin_and_realtor_ca(self):
        # Overlap is intentional — realtor benefits from both
        recs = generate_recommendations(*_make_args("real estate agent", "Jane Realty"))
        titles = [r["title"] for r in recs]
        assert any("LinkedIn"   in t for t in titles)
        assert any("Realtor.ca" in t for t in titles)

    def test_lawyer_gets_linkedin_and_lawyerlocate(self):
        # Overlap is intentional — lawyer benefits from both
        recs = generate_recommendations(*_make_args("law firm", "Smith Law"))
        titles = [r["title"] for r in recs]
        assert any("LinkedIn"     in t for t in titles)
        assert any("LawyerLocate" in t for t in titles)

    def test_lawyer_already_on_linkedin_no_rec(self):
        recs = generate_recommendations(*_make_args(
            "law firm", "Smith Law", on_dirs=["LinkedIn"]))
        titles = [r["title"] for r in recs]
        assert not any("LinkedIn" in t for t in titles)

    def test_dentist_does_not_get_linkedin_rec(self):
        # Healthcare is not B2B for LinkedIn purposes
        recs = generate_recommendations(*_make_args("dentist", "X"))
        titles = [r["title"] for r in recs]
        assert not any("LinkedIn" in t for t in titles)

    def test_restaurant_does_not_get_linkedin_rec(self):
        recs = generate_recommendations(*_make_args("restaurant", "X"))
        titles = [r["title"] for r in recs]
        assert not any("LinkedIn" in t for t in titles)

    def test_plumber_does_not_get_linkedin_rec(self):
        # Trades is not B2B for LinkedIn purposes
        recs = generate_recommendations(*_make_args("plumber", "X"))
        titles = [r["title"] for r in recs]
        assert not any("LinkedIn" in t for t in titles)

    def test_hair_salon_does_not_get_linkedin_rec(self):
        recs = generate_recommendations(*_make_args("hair salon", "X"))
        titles = [r["title"] for r in recs]
        assert not any("LinkedIn" in t for t in titles)

    def test_linkedin_difficulty_is_medium(self):
        # LinkedIn is an ongoing commitment, not a one-time claim
        recs = generate_recommendations(*_make_args("law firm", "X"))
        linkedin_recs = [r for r in recs if "LinkedIn" in r["title"]]
        assert linkedin_recs[0]["difficulty"] == "medium"

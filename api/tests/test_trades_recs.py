"""
Tests for the Canadian-trades-directory recommendation logic.
Covers HomeStars + TrustedPros gap detection in generate_recommendations().
"""
from aeo.router import (
    _is_trades_business,
    _user_directories_only,
    generate_recommendations,
)


# ─── _is_trades_business ──────────────────────────────────────────────────
class TestIsTradesBusiness:
    def test_plumber_variants(self):
        assert _is_trades_business("plumber")
        assert _is_trades_business("plumbing services")
        assert _is_trades_business("residential plumber")

    def test_electrician_variants(self):
        assert _is_trades_business("electrician")
        assert _is_trades_business("electrical contractor")

    def test_hvac_variants(self):
        assert _is_trades_business("HVAC")
        assert _is_trades_business("heating and cooling")
        assert _is_trades_business("air conditioning specialist")

    def test_roofing_and_construction(self):
        assert _is_trades_business("roofer")
        assert _is_trades_business("roofing contractor")
        assert _is_trades_business("general contractor")
        assert _is_trades_business("construction company")

    def test_specialty_trades(self):
        assert _is_trades_business("locksmith")
        assert _is_trades_business("handyman")
        assert _is_trades_business("landscaper")
        assert _is_trades_business("carpenter")
        assert _is_trades_business("flooring installation")
        assert _is_trades_business("home renovations")
        assert _is_trades_business("house painter")

    def test_non_trades_rejected(self):
        assert not _is_trades_business("dentist")
        assert not _is_trades_business("hair salon")
        assert not _is_trades_business("restaurant")
        assert not _is_trades_business("law firm")
        assert not _is_trades_business("physiotherapy clinic")

    def test_empty_returns_false(self):
        assert not _is_trades_business(None)
        assert not _is_trades_business("")
        assert not _is_trades_business("   ")


# ─── _user_directories_only ───────────────────────────────────────────────
class TestUserDirectoriesOnly:
    def _q(self, organic):
        return {"organic_results_raw": organic}

    def test_detects_homestars(self):
        per_query = [self._q([
            {"link": "https://homestars.com/companies/joes-plumbing",
             "title": "Joe's Plumbing - HomeStars",
             "snippet": "Top plumber in Toronto."},
        ])]
        out = _user_directories_only(per_query, "Joe's Plumbing")
        assert "HomeStars" in out

    def test_detects_trustedpros(self):
        per_query = [self._q([
            {"link": "https://www.trustedpros.ca/profile/joes-plumbing",
             "title": "Joe's Plumbing - TrustedPros",
             "snippet": "Verified contractor in Toronto."},
        ])]
        out = _user_directories_only(per_query, "Joe's Plumbing")
        assert "TrustedPros" in out

    def test_does_not_match_competitor_on_same_directory(self):
        # User is "Joe's Plumbing" but result is about "Mario's Plumbing"
        per_query = [self._q([
            {"link": "https://homestars.com/companies/marios-plumbing",
             "title": "Mario's Plumbing - HomeStars",
             "snippet": "Local Toronto plumber."},
        ])]
        out = _user_directories_only(per_query, "Joe's Plumbing")
        assert "HomeStars" not in out

    def test_empty_input(self):
        assert _user_directories_only([], "Joe's") == set()
        assert _user_directories_only(None, "Joe's") == set()


# ─── Trades recommendations (end-to-end) ──────────────────────────────────
def _make_audit_data(business_type, business_name, on_homestars=False, on_trustedpros=False):
    """Build a minimum-viable audit context for generate_recommendations()."""
    organic = []
    if on_homestars:
        organic.append({
            "link": "https://homestars.com/companies/x",
            "title": f"{business_name} - HomeStars",
            "snippet": "",
        })
    if on_trustedpros:
        organic.append({
            "link": "https://www.trustedpros.ca/profile/x",
            "title": f"{business_name} - TrustedPros",
            "snippet": "",
        })

    business = {"name": business_name, "type": business_type, "city": "Toronto",
                "website": "https://example.com"}
    perplexity = {"mentioned": True, "snippet": None}
    google = {
        "ai_overview":     {"mentioned": True, "snippet": None},
        "knowledge_graph": {"found": True, "rating": 4.8, "reviews_count": 50,
                            "type": "Plumber", "website": "https://example.com",
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


class TestTradesRecommendations:
    def test_plumber_not_on_homestars_gets_rec(self):
        args = _make_audit_data("plumber", "Joe's Plumbing", on_homestars=False, on_trustedpros=True)
        recs = generate_recommendations(*args)
        homestars_recs = [r for r in recs if "HomeStars" in r["title"]]
        assert len(homestars_recs) == 1
        assert homestars_recs[0]["url"] == "https://homestars.com/create-account"
        assert homestars_recs[0]["difficulty"] == "easy"
        assert homestars_recs[0]["pillar"] == "ai_citation"

    def test_plumber_not_on_trustedpros_gets_rec(self):
        args = _make_audit_data("plumber", "Joe's Plumbing", on_homestars=True, on_trustedpros=False)
        recs = generate_recommendations(*args)
        tp_recs = [r for r in recs if "TrustedPros" in r["title"]]
        assert len(tp_recs) == 1
        assert tp_recs[0]["url"] == "https://www.trustedpros.ca/contractor"

    def test_plumber_on_both_gets_neither_rec(self):
        args = _make_audit_data("plumber", "Joe's Plumbing", on_homestars=True, on_trustedpros=True)
        recs = generate_recommendations(*args)
        titles = [r["title"] for r in recs]
        assert not any("HomeStars" in t for t in titles)
        assert not any("TrustedPros" in t for t in titles)

    def test_plumber_on_neither_gets_both_recs(self):
        args = _make_audit_data("plumber", "Joe's Plumbing", on_homestars=False, on_trustedpros=False)
        recs = generate_recommendations(*args)
        titles = [r["title"] for r in recs]
        assert any("HomeStars" in t for t in titles)
        assert any("TrustedPros" in t for t in titles)

    def test_dentist_does_not_get_trades_recs(self):
        # Non-trades business should never get HomeStars/TrustedPros recs
        args = _make_audit_data("dentist", "Smile Dental", on_homestars=False, on_trustedpros=False)
        recs = generate_recommendations(*args)
        titles = [r["title"] for r in recs]
        assert not any("HomeStars" in t for t in titles)
        assert not any("TrustedPros" in t for t in titles)

    def test_restaurant_does_not_get_trades_recs(self):
        args = _make_audit_data("italian restaurant", "Mario's", on_homestars=False, on_trustedpros=False)
        recs = generate_recommendations(*args)
        titles = [r["title"] for r in recs]
        assert not any("HomeStars" in t for t in titles)
        assert not any("TrustedPros" in t for t in titles)

    def test_other_trades_verticals_get_recs(self):
        for vertical in ["electrician", "HVAC contractor", "roofing company",
                         "general contractor", "landscaper", "handyman service"]:
            args = _make_audit_data(vertical, "ACME Co", on_homestars=False, on_trustedpros=False)
            recs = generate_recommendations(*args)
            titles = [r["title"] for r in recs]
            assert any("HomeStars" in t for t in titles), f"HomeStars rec missing for {vertical}"
            assert any("TrustedPros" in t for t in titles), f"TrustedPros rec missing for {vertical}"

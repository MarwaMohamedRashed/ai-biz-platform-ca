"""
Tests for the Canadian vertical expansion (Phase 1+2+3, 2026-05-08):
  - 5 vertical detector helpers
  - 6 conditional vertical recommendations
  - 2 universal recommendations (Apple Business Connect + Bing Places)
  - Conditional query templates (FSA / emergency / weekend)
  - Quebec inLanguage schema
"""
from aeo.router import (
    _is_healthcare_business,
    _is_dentist_business,
    _is_food_business,
    _is_legal_business,
    _is_realtor_business,
    build_queries,
    generate_recommendations,
)
from aeo.schema_builder import build_schema


# ─── Vertical detectors ───────────────────────────────────────────────────
class TestHealthcareDetector:
    def test_positives(self):
        for v in ["dentist", "dental clinic", "doctor", "physician",
                  "physiotherapy", "physical therapist", "chiropractor",
                  "optometrist", "veterinary clinic", "pharmacy",
                  "medical clinic", "naturopath", "massage therapist",
                  "audiologist", "psychologist", "counselling service"]:
            assert _is_healthcare_business(v), f"missed {v!r}"

    def test_negatives(self):
        for v in ["plumber", "restaurant", "hair salon", "lawyer",
                  "real estate agent", "bakery"]:
            assert not _is_healthcare_business(v), f"false positive on {v!r}"


class TestDentistDetector:
    def test_positives(self):
        for v in ["dentist", "dental clinic", "orthodontist"]:
            assert _is_dentist_business(v)

    def test_negatives(self):
        # Other healthcare verticals should NOT trigger dentist-specific recs
        for v in ["physiotherapy", "doctor", "chiropractor"]:
            assert not _is_dentist_business(v)


class TestFoodDetector:
    def test_positives(self):
        for v in ["restaurant", "italian restaurant", "café", "coffee shop",
                  "bakery", "bar", "pub", "brewery", "bistro", "diner",
                  "steakhouse", "sushi bar", "pizza place"]:
            assert _is_food_business(v), f"missed {v!r}"

    def test_negatives(self):
        for v in ["plumber", "dentist", "real estate agent"]:
            assert not _is_food_business(v)


class TestLegalDetector:
    def test_positives(self):
        for v in ["lawyer", "attorney", "law firm", "law office",
                  "legal service", "paralegal", "notary public"]:
            assert _is_legal_business(v), f"missed {v!r}"

    def test_negatives(self):
        for v in ["plumber", "restaurant", "dentist"]:
            assert not _is_legal_business(v)


class TestRealtorDetector:
    def test_positives(self):
        for v in ["real estate agent", "realtor", "real estate brokerage",
                  "realty"]:
            assert _is_realtor_business(v), f"missed {v!r}"

    def test_negatives(self):
        for v in ["plumber", "restaurant", "lawyer"]:
            assert not _is_realtor_business(v)


# ─── build_queries — conditional templates ────────────────────────────────
class TestBuildQueriesConditional:
    def test_base_three_for_generic_business(self):
        # No postal_code, not trades, not healthcare → just the 3 base queries
        q = build_queries("hair salon", "Ottawa", "ON")
        assert len(q) == 3

    def test_fsa_added_when_postal_code_set(self):
        q = build_queries("hair salon", "Ottawa", "ON", postal_code="K1P 5N7")
        assert len(q) == 4
        assert any("K1P" in s for s in q)

    def test_fsa_uppercased(self):
        q = build_queries("hair salon", "Ottawa", "ON", postal_code="k1p5n7")
        assert any("K1P" in s for s in q)

    def test_fsa_skipped_for_short_postal_code(self):
        q = build_queries("hair salon", "Ottawa", "ON", postal_code="K1")
        assert len(q) == 3   # too short, no FSA query added

    def test_emergency_and_weekend_for_trades(self):
        q = build_queries("plumber", "Ottawa", "ON", is_trades=True)
        assert len(q) == 5   # 3 base + emergency + weekend
        assert any("Emergency" in s for s in q)
        assert any("open weekends" in s for s in q)

    def test_emergency_and_weekend_for_healthcare(self):
        q = build_queries("dentist", "Ottawa", "ON", is_healthcare=True)
        assert len(q) == 5
        assert any("Emergency" in s for s in q)

    def test_max_six_when_all_conditions_true(self):
        q = build_queries("plumber", "Ottawa", "ON",
                          postal_code="K1P 5N7", is_trades=True)
        assert len(q) == 6   # 3 base + FSA + emergency + weekend

    def test_no_emergency_for_non_trades_non_healthcare(self):
        q = build_queries("hair salon", "Ottawa", "ON",
                          postal_code="K1P 5N7", is_trades=False, is_healthcare=False)
        assert len(q) == 4   # 3 base + FSA only
        assert not any("Emergency" in s for s in q)


# ─── End-to-end recommendations — vertical recs + universals ──────────────
def _make_args(business_type, business_name="Test Biz", province="ON",
               on_dirs=None):
    """Build minimum-viable audit context for generate_recommendations()."""
    on_dirs = on_dirs or []
    organic = []
    for d in on_dirs:
        # Use canonical domain for each label so the URL → label match works
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
        }.get(d, "example.com")
        organic.append({
            "link":    f"https://{domain_for_label}/profile/x",
            "title":   f"{business_name} - {d}",
            "snippet": "",
        })

    business = {
        "name": business_name, "type": business_type,
        "city": "Toronto", "province": province,
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


class TestVerticalRecommendations:
    # ─── Healthcare → RateMDs + Opencare (dentist only) ───
    def test_dentist_not_on_anything_gets_ratemds_and_opencare(self):
        recs = generate_recommendations(*_make_args("dentist", "Smile Dental"))
        titles = [r["title"] for r in recs]
        assert any("RateMDs" in t for t in titles)
        assert any("Opencare" in t for t in titles)

    def test_physio_gets_ratemds_but_not_opencare(self):
        recs = generate_recommendations(*_make_args("physiotherapy clinic", "PhysioHub"))
        titles = [r["title"] for r in recs]
        assert any("RateMDs" in t for t in titles)
        assert not any("Opencare" in t for t in titles)

    def test_dentist_already_on_ratemds_no_rec(self):
        recs = generate_recommendations(*_make_args(
            "dentist", "Smile Dental", on_dirs=["RateMDs"]))
        titles = [r["title"] for r in recs]
        assert not any("RateMDs" in t for t in titles)

    # ─── Food → OpenTable + TripAdvisor ───
    def test_restaurant_gets_both_food_recs(self):
        recs = generate_recommendations(*_make_args("italian restaurant", "Mario's"))
        titles = [r["title"] for r in recs]
        assert any("OpenTable" in t for t in titles)
        assert any("TripAdvisor" in t for t in titles)

    def test_restaurant_already_on_opentable_no_rec(self):
        recs = generate_recommendations(*_make_args(
            "italian restaurant", "Mario's", on_dirs=["OpenTable"]))
        titles = [r["title"] for r in recs]
        assert not any("OpenTable" in t for t in titles)

    # ─── Legal → LawyerLocate ───
    def test_lawyer_gets_lawyerlocate(self):
        recs = generate_recommendations(*_make_args("law firm", "Smith Law"))
        titles = [r["title"] for r in recs]
        assert any("LawyerLocate" in t for t in titles)

    # ─── Realtor → Realtor.ca ───
    def test_realtor_gets_realtor_ca(self):
        recs = generate_recommendations(*_make_args("real estate agent", "Jane Realty"))
        titles = [r["title"] for r in recs]
        assert any("Realtor.ca" in t for t in titles)

    # ─── Cross-contamination guards ───
    def test_dentist_does_not_get_food_or_legal_recs(self):
        recs = generate_recommendations(*_make_args("dentist", "Smile Dental"))
        titles = [r["title"] for r in recs]
        assert not any("OpenTable"    in t for t in titles)
        assert not any("LawyerLocate" in t for t in titles)
        assert not any("Realtor.ca"   in t for t in titles)
        assert not any("HomeStars"    in t for t in titles)

    def test_plumber_does_not_get_health_or_food_recs(self):
        recs = generate_recommendations(*_make_args("plumber", "Joe's Plumbing"))
        titles = [r["title"] for r in recs]
        assert not any("RateMDs"   in t for t in titles)
        assert not any("Opencare"  in t for t in titles)
        assert not any("OpenTable" in t for t in titles)


class TestUniversalRecommendations:
    def test_apple_business_connect_fires_for_everyone(self):
        for vertical in ["dentist", "plumber", "italian restaurant",
                         "hair salon", "lawyer", "real estate agent"]:
            recs = generate_recommendations(*_make_args(vertical, "X"))
            titles = [r["title"] for r in recs]
            assert any("Apple Business Connect" in t for t in titles), \
                f"Apple rec missing for {vertical}"

    def test_bing_places_fires_for_everyone(self):
        for vertical in ["dentist", "plumber", "italian restaurant",
                         "hair salon", "lawyer", "real estate agent"]:
            recs = generate_recommendations(*_make_args(vertical, "X"))
            titles = [r["title"] for r in recs]
            assert any("Bing Places" in t for t in titles), \
                f"Bing Places rec missing for {vertical}"


# ─── Quebec inLanguage schema ─────────────────────────────────────────────
class TestQuebecBilingualSchema:
    def _qc_business(self):
        return {
            "name": "Boulangerie Quebec", "type": "bakery",
            "city": "Montréal", "province": "QC", "country": "Canada",
        }

    def test_qc_with_french_content_gets_inlanguage(self):
        s = build_schema(self._qc_business(), content_language="fr")
        assert s["inLanguage"] == ["fr-CA", "en-CA"]

    def test_qc_with_english_only_does_not_claim_bilingual(self):
        s = build_schema(self._qc_business(), content_language="en")
        assert "inLanguage" not in s

    def test_qc_with_no_content_language_does_not_claim_bilingual(self):
        s = build_schema(self._qc_business())
        assert "inLanguage" not in s

    def test_qc_with_explicit_opt_in_gets_inlanguage(self):
        biz = self._qc_business()
        biz["bilingual_opt_in"] = True
        s = build_schema(biz, content_language="en")
        assert s["inLanguage"] == ["fr-CA", "en-CA"]

    def test_ontario_with_french_content_does_not_claim_bilingual(self):
        # Province gate: only QC gets the inLanguage signal
        biz = self._qc_business()
        biz["province"] = "ON"
        s = build_schema(biz, content_language="fr")
        assert "inLanguage" not in s

    def test_lowercase_qc_still_recognized(self):
        biz = self._qc_business()
        biz["province"] = "qc"
        s = build_schema(biz, content_language="fr")
        assert s["inLanguage"] == ["fr-CA", "en-CA"]

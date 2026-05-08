"""
Tests for the deterministic schema builder.
Covers QA test plan sections 6.7 (LocalBusiness regression), 6.6 (FAQPage validity),
2.5–2.7 (validators).
"""
import pytest
from aeo.schema_builder import (
    resolve_schema_type,
    build_schema,
    build_faq_schema,
    find_missing_required_fields,
)


# ─── resolve_schema_type ──────────────────────────────────────────────────
class TestResolveSchemaType:
    def test_exact_onboarding_values(self):
        assert resolve_schema_type("restaurant") == "Restaurant"
        assert resolve_schema_type("cafe")       == "CafeOrCoffeeShop"
        assert resolve_schema_type("salon")      == "BeautySalon"
        assert resolve_schema_type("retail")     == "Store"
        assert resolve_schema_type("plumber")    == "Plumber"

    def test_keyword_match_health_verticals(self):
        assert resolve_schema_type("dental clinic")             == "Dentist"
        assert resolve_schema_type("physiotherapy & rehab")     == "Physiotherapy"
        assert resolve_schema_type("chiropractor in ottawa")    == "Chiropractor"
        assert resolve_schema_type("veterinary clinic")         == "VeterinaryCare"
        assert resolve_schema_type("pharmacy")                  == "Pharmacy"

    def test_keyword_match_food_verticals(self):
        assert resolve_schema_type("italian pizza")             == "Restaurant"
        assert resolve_schema_type("local bakery")              == "Bakery"
        assert resolve_schema_type("coffee shop")               == "CafeOrCoffeeShop"
        assert resolve_schema_type("craft brewery")             == "Brewery"
        assert resolve_schema_type("sports bar")                == "BarOrPub"

    def test_keyword_match_trades(self):
        assert resolve_schema_type("plumbing services")         == "Plumber"
        assert resolve_schema_type("electrician")               == "Electrician"
        assert resolve_schema_type("hvac contractor")           == "HVACBusiness"
        assert resolve_schema_type("roofing company")           == "RoofingContractor"
        assert resolve_schema_type("auto repair shop")          == "AutoRepair"

    def test_keyword_match_professional_services(self):
        assert resolve_schema_type("law firm")                  == "Attorney"
        assert resolve_schema_type("attorney at law")           == "Attorney"
        assert resolve_schema_type("accounting service")        == "AccountingService"
        assert resolve_schema_type("real estate agent")         == "RealEstateAgent"

    def test_specific_pattern_wins_over_general(self):
        # 'physiotherapy clinic' contains 'clinic' (MedicalClinic) but should win as Physiotherapy
        assert resolve_schema_type("physiotherapy clinic") == "Physiotherapy"
        # 'dental clinic' should be Dentist, not MedicalClinic
        assert resolve_schema_type("dental clinic") == "Dentist"

    def test_case_insensitive(self):
        assert resolve_schema_type("PHYSIOTHERAPY CLINIC") == "Physiotherapy"
        assert resolve_schema_type("Dental")               == "Dentist"

    def test_unknown_falls_back_to_localbusiness(self):
        assert resolve_schema_type("flux capacitor consultancy") == "LocalBusiness"
        assert resolve_schema_type("")                            == "LocalBusiness"
        assert resolve_schema_type(None)                          == "LocalBusiness"


# ─── build_schema ─────────────────────────────────────────────────────────
class TestBuildSchema:
    @pytest.fixture
    def full_business(self):
        return {
            "name":           "James Snow Physiotherapy",
            "type":           "physiotherapy clinic",
            "city":           "Milton",
            "province":       "ON",
            "country":        "Canada",
            "website":        "https://example.com",
            "phone":          "+1 905-555-0123",
            "street_address": "100 King St",
            "postal_code":    "L9T 1A1",
            "image_url":      "https://example.com/logo.png",
            "price_range":    "$$",
            "hours": {
                "monday":  "09:00-17:00",
                "tuesday": "09:00-17:00",
                "sunday":  "closed",
            },
        }

    def test_full_business_produces_complete_schema(self, full_business):
        s = build_schema(full_business, description="Best clinic in Milton.")
        assert s["@context"] == "https://schema.org"
        assert s["@type"] == "Physiotherapy"
        assert s["name"] == "James Snow Physiotherapy"
        assert s["image"] == "https://example.com/logo.png"
        assert s["telephone"] == "+1 905-555-0123"
        assert s["priceRange"] == "$$"
        assert s["url"] == "https://example.com"
        assert s["description"] == "Best clinic in Milton."

    def test_address_is_postaladdress_type(self, full_business):
        s = build_schema(full_business)
        assert s["address"]["@type"]           == "PostalAddress"
        assert s["address"]["streetAddress"]   == "100 King St"
        assert s["address"]["addressLocality"] == "Milton"
        assert s["address"]["addressRegion"]   == "ON"
        assert s["address"]["postalCode"]      == "L9T 1A1"
        assert s["address"]["addressCountry"]  == "Canada"

    def test_country_defaults_to_canada(self):
        s = build_schema({"name": "X", "type": "salon", "city": "Ottawa"})
        # No country in business dict → builder defaults to Canada in addressCountry
        # but the address block only renders if at least one address field present
        assert s["address"]["addressCountry"] == "Canada"
        assert s["address"]["addressLocality"] == "Ottawa"

    def test_omits_missing_fields(self):
        s = build_schema({"name": "X", "type": "salon", "city": "Ottawa"})
        # No phone, image, price_range → those keys must be ABSENT (not None)
        assert "telephone" not in s
        assert "image" not in s
        assert "priceRange" not in s
        # No website provided → no `url`
        assert "url" not in s

    def test_omits_address_block_when_no_address_fields(self):
        s = build_schema({"name": "X", "type": "salon"})  # no city, postal, street, region
        assert "address" not in s

    def test_hallucination_guard_country_is_canada_not_CA(self, full_business):
        s = build_schema(full_business)
        # Regression: prior LLM output emitted "CA" — deterministic builder must use full name
        assert s["address"]["addressCountry"] == "Canada"

    def test_no_invented_fields(self, full_business):
        s = build_schema(full_business)
        # Regression: prior LLM output had `servesCuisine`, `areaServed`, `service[]` for non-restaurants
        assert "servesCuisine" not in s
        assert "areaServed"    not in s
        assert "service"       not in s

    def test_hours_become_opening_hours_specification(self, full_business):
        s = build_schema(full_business)
        spec = s["openingHoursSpecification"]
        assert isinstance(spec, list)
        # Closed days should be omitted (Schema.org convention)
        days = [item["dayOfWeek"] for item in spec]
        assert "https://schema.org/Sunday" not in days
        # Open days should be present
        mondays = [s for s in spec if s["dayOfWeek"] == "https://schema.org/Monday"]
        assert len(mondays) == 1
        assert mondays[0]["opens"]  == "09:00"
        assert mondays[0]["closes"] == "17:00"

    def test_empty_hours_does_not_emit_key(self):
        s = build_schema({"name": "X", "type": "salon", "city": "Ottawa", "hours": {}})
        assert "openingHoursSpecification" not in s

    def test_invalid_hours_format_skipped(self):
        # Malformed hours value — should be silently dropped, not raise
        s = build_schema({"name": "X", "type": "salon", "city": "Ottawa",
                          "hours": {"monday": "garbage"}})
        assert "openingHoursSpecification" not in s


# ─── build_faq_schema ─────────────────────────────────────────────────────
class TestBuildFaqSchema:
    def test_valid_faq_produces_faqpage(self):
        items = [
            {"question": "Do you accept insurance?", "answer": "Yes, most major plans."},
            {"question": "Do you have parking?",      "answer": "Free on-site lot."},
        ]
        s = build_faq_schema(items)
        assert s["@context"] == "https://schema.org"
        assert s["@type"]    == "FAQPage"
        assert len(s["mainEntity"]) == 2
        assert s["mainEntity"][0]["@type"] == "Question"
        assert s["mainEntity"][0]["name"]  == "Do you accept insurance?"
        assert s["mainEntity"][0]["acceptedAnswer"]["@type"] == "Answer"
        assert s["mainEntity"][0]["acceptedAnswer"]["text"]  == "Yes, most major plans."

    def test_drops_items_with_missing_question_or_answer(self):
        items = [
            {"question": "Q1", "answer": "A1"},
            {"question": "",    "answer": "A2"},      # empty Q
            {"question": "Q3", "answer": ""},          # empty A
            {"question": "Q4"},                         # no A key
        ]
        s = build_faq_schema(items)
        assert len(s["mainEntity"]) == 1
        assert s["mainEntity"][0]["name"] == "Q1"

    def test_empty_input_returns_empty_mainentity(self):
        s = build_faq_schema([])
        assert s["mainEntity"] == []

    def test_none_input_returns_empty_mainentity(self):
        s = build_faq_schema(None)
        assert s["mainEntity"] == []


# ─── find_missing_required_fields ─────────────────────────────────────────
class TestFindMissingRequiredFields:
    def test_complete_profile_has_no_missing(self):
        biz = {
            "name":           "X",
            "image_url":      "https://example.com/logo.png",
            "street_address": "1 Main St",
            "city":           "Milton",
            "phone":          "555-0123",
        }
        assert find_missing_required_fields(biz) == []

    def test_blank_image_is_flagged(self):
        biz = {
            "name":           "X",
            "image_url":      "",
            "street_address": "1 Main St",
            "city":           "Milton",
            "phone":          "555-0123",
        }
        assert "image_url" in find_missing_required_fields(biz)

    def test_whitespace_only_is_flagged(self):
        biz = {"name": "X", "city": "Milton", "image_url": "   ",
               "street_address": "1 Main St", "phone": "555-0123"}
        assert "image_url" in find_missing_required_fields(biz)

    def test_missing_keys_are_flagged(self):
        biz = {"name": "X"}
        missing = find_missing_required_fields(biz)
        assert set(missing) == {"image_url", "street_address", "city", "phone"}

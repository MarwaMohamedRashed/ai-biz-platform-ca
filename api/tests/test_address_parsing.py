"""
Tests for the postal-code-shape country inference (cross-border filter fix).

The bug we're locking in: SerpApi's local pack sometimes returns competitors
from another country with the SAME city name (e.g., "Milton Keynes, MK9 1AB"
slipping into a search for Milton, Ontario). The address has no country
WORD — only a postal code. We need to infer the country from postal-code
shape so the cross-border filter works.

These tests do NOT cover the full address parser — only the country-
inference logic added on 2026-05-09 to fix the regression.
"""
from aeo.router import _extract_location_from_address


class TestPostalCodeCountryInference:
    """Locks in the cross-border filter fix: country inferred from postal-code
    shape when no country word is present in the address."""

    def test_uk_postal_no_country_word_inferred(self):
        # The exact case from the bug report — UK Milton Keynes leaking
        # into a Canadian Milton search
        _, _, country = _extract_location_from_address("Milton Keynes, MK9 1AB")
        assert country == "United Kingdom"

    def test_uk_short_postal_no_country_word(self):
        _, _, country = _extract_location_from_address("Westminster, SW1A 1AA")
        assert country == "United Kingdom"

    def test_uk_postal_with_full_address(self):
        # Realistic SerpApi-style address with street, city, UK postal
        _, _, country = _extract_location_from_address(
            "10 Downing St, Westminster, London, SW1A 2AA"
        )
        assert country == "United Kingdom"

    def test_canadian_postal_no_country_word(self):
        # Canadian postal codes (A9A 9A9) should be detected as Canada even
        # without "Canada" in the address
        _, _, country = _extract_location_from_address(
            "1 Main St, Milton, ON L9T 0A1"
        )
        assert country == "Canada"

    def test_canadian_postal_no_space(self):
        # Canadian postal codes can appear without the space too
        _, _, country = _extract_location_from_address(
            "100 King St, Toronto, ON M5J2N1"
        )
        assert country == "Canada"

    def test_us_zip_with_state_no_country_word(self):
        _, region, country = _extract_location_from_address(
            "123 Main Ave, Burlington, VT 05401"
        )
        assert region == "VT"
        assert country == "United States"

    def test_us_zip_plus_4(self):
        _, region, country = _extract_location_from_address(
            "1 Pennsylvania Plaza, New York, NY 10119-0001"
        )
        assert region == "NY"
        assert country == "United States"


class TestNoOverInference:
    """Defensive — don't infer a country when we don't have evidence."""

    def test_short_address_returns_none_country(self):
        _, _, country = _extract_location_from_address("Just a name")
        assert country is None

    def test_empty_address(self):
        city, _, country = _extract_location_from_address("")
        assert city is None
        assert country is None

"""
Tests for the profile-field validators in api/aeo/router.py.
Covers QA test plan sections 2.5–2.7 (postal code, image URL, price range, hours).
"""
import pytest
from fastapi import HTTPException
from aeo.router import (
    _clean_postal,
    _clean_image_url,
    _clean_price_range,
    _clean_hours,
)


# ─── Postal code ──────────────────────────────────────────────────────────
class TestCleanPostal:
    def test_valid_canadian_postal(self):
        assert _clean_postal("K1P 5N7", "Canada") == "K1P 5N7"
        assert _clean_postal("k1p 5n7", "Canada") == "K1P 5N7"   # uppercased
        assert _clean_postal("K1P5N7",  "Canada") == "K1P5N7"    # no space accepted
        assert _clean_postal("L9T 1A1", "Canada") == "L9T 1A1"

    def test_us_zip_rejected_when_country_canada(self):
        with pytest.raises(HTTPException) as exc:
            _clean_postal("12345", "Canada")
        assert exc.value.status_code == 422

    def test_garbage_rejected_when_country_canada(self):
        with pytest.raises(HTTPException):
            _clean_postal("ABCDEF",   "Canada")
        with pytest.raises(HTTPException):
            _clean_postal("KKK 5N7",  "Canada")

    def test_us_postal_passthrough_when_country_us(self):
        # When country is not Canada, the validator just normalises whitespace + case
        assert _clean_postal("90210",      "United States") == "90210"
        assert _clean_postal("12345-6789", "United States") == "12345-6789"

    def test_empty_returns_none(self):
        assert _clean_postal(None,  "Canada") is None
        assert _clean_postal("",    "Canada") is None
        assert _clean_postal("   ", "Canada") is None


# ─── Image URL ────────────────────────────────────────────────────────────
class TestCleanImageUrl:
    def test_https_accepted(self):
        assert _clean_image_url("https://example.com/logo.png") == "https://example.com/logo.png"

    def test_http_accepted(self):
        assert _clean_image_url("http://example.com/logo.png") == "http://example.com/logo.png"

    def test_no_scheme_rejected(self):
        with pytest.raises(HTTPException) as exc:
            _clean_image_url("logo.png")
        assert exc.value.status_code == 422

    def test_relative_url_rejected(self):
        with pytest.raises(HTTPException):
            _clean_image_url("/static/logo.png")

    def test_data_uri_rejected(self):
        with pytest.raises(HTTPException):
            _clean_image_url("data:image/png;base64,iVBORw0KGgo=")

    def test_empty_returns_none(self):
        assert _clean_image_url(None) is None
        assert _clean_image_url("")   is None
        assert _clean_image_url(" ")  is None


# ─── Price range ──────────────────────────────────────────────────────────
class TestCleanPriceRange:
    def test_all_four_valid_values(self):
        for v in ["$", "$$", "$$$", "$$$$"]:
            assert _clean_price_range(v) == v

    def test_invalid_rejected(self):
        with pytest.raises(HTTPException) as exc:
            _clean_price_range("medium")
        assert exc.value.status_code == 422

    def test_too_many_dollars_rejected(self):
        with pytest.raises(HTTPException):
            _clean_price_range("$$$$$")

    def test_empty_returns_none(self):
        assert _clean_price_range(None) is None
        assert _clean_price_range("")   is None
        assert _clean_price_range("  ") is None


# ─── Hours ────────────────────────────────────────────────────────────────
class TestCleanHours:
    def test_valid_full_week(self):
        h = {
            "monday":    "09:00-17:00",
            "tuesday":   "09:00-17:00",
            "wednesday": "09:00-17:00",
            "thursday":  "09:00-17:00",
            "friday":    "09:00-17:00",
            "saturday":  "10:00-14:00",
            "sunday":    "closed",
        }
        out = _clean_hours(h)
        assert out["monday"]   == "09:00-17:00"
        assert out["sunday"]   == "closed"
        assert out["saturday"] == "10:00-14:00"

    def test_case_insensitive_day_keys(self):
        out = _clean_hours({"Monday": "09:00-17:00"})
        assert out == {"monday": "09:00-17:00"}

    def test_closed_case_insensitive(self):
        out = _clean_hours({"monday": "CLOSED"})
        assert out == {"monday": "closed"}

    def test_invalid_day_rejected(self):
        with pytest.raises(HTTPException):
            _clean_hours({"funday": "09:00-17:00"})

    def test_invalid_format_rejected(self):
        with pytest.raises(HTTPException):
            _clean_hours({"monday": "9-5"})

    def test_invalid_time_rejected(self):
        with pytest.raises(HTTPException):
            _clean_hours({"monday": "25:00-17:00"})  # hour > 23

    def test_blank_values_dropped(self):
        out = _clean_hours({"monday": "", "tuesday": "09:00-17:00"})
        assert out == {"tuesday": "09:00-17:00"}

    def test_all_empty_returns_none(self):
        # Entire-empty hours dict → None (so DB stores NULL, not empty {})
        assert _clean_hours({}) is None

    def test_none_returns_none(self):
        assert _clean_hours(None) is None

    def test_non_dict_rejected(self):
        with pytest.raises(HTTPException):
            _clean_hours("monday 9-5")

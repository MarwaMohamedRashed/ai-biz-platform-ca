"""
Tests for the citation-gap detector and supporting helpers.
Covers QA test plan section 7.6 (citation gap analysis).
"""
from aeo.router import (
    _domain_from_url,
    _name_short,
    _detect_directory_presence,
    DIRECTORY_DOMAINS,
)


# ─── _domain_from_url ─────────────────────────────────────────────────────
class TestDomainFromUrl:
    def test_strips_scheme(self):
        assert _domain_from_url("https://yelp.com/biz/foo") == "yelp.com"

    def test_strips_www(self):
        assert _domain_from_url("https://www.yelp.com/biz/foo") == "yelp.com"

    def test_strips_path(self):
        assert _domain_from_url("https://yelp.com/biz/foo/bar?q=1") == "yelp.com"

    def test_lowercases(self):
        assert _domain_from_url("https://Yelp.COM/biz/foo") == "yelp.com"

    def test_handles_subdomains(self):
        # Subdomains preserved — caller can match with endswith("." + d)
        assert _domain_from_url("https://m.yelp.com/biz/foo") == "m.yelp.com"

    def test_empty_returns_empty(self):
        assert _domain_from_url("") == ""
        assert _domain_from_url(None) == ""


# ─── _name_short ──────────────────────────────────────────────────────────
class TestNameShort:
    def test_takes_first_three_words(self):
        assert _name_short("James Snow Physiotherapy & Rehabilitation Centre") == "james snow physiotherapy"

    def test_lowercases(self):
        assert _name_short("ACME PLUMBING") == "acme plumbing"

    def test_short_name_passthrough(self):
        assert _name_short("Joe's Pizza") == "joe's pizza"

    def test_empty(self):
        assert _name_short(None) == ""
        assert _name_short("") == ""


# ─── _detect_directory_presence ───────────────────────────────────────────
class TestDetectDirectoryPresence:
    def _make_query(self, organic):
        """Helper: mimic the per_query dict shape with an organic_results_raw key."""
        return {"organic_results_raw": organic}

    def test_user_detected_on_yelp(self):
        per_query = [
            self._make_query([
                {
                    "link": "https://yelp.com/biz/joes-pizza-ottawa",
                    "title": "Joe's Pizza in Ottawa - Yelp",
                    "snippet": "Best pizza spot.",
                },
            ]),
        ]
        out = _detect_directory_presence(per_query, "Joe's Pizza", [])
        assert "Yelp" in out["user"]
        assert out["competitors"] == {}
        assert out["gaps"] == []

    def test_competitor_detected_on_yelp(self):
        per_query = [
            self._make_query([
                {
                    "link": "https://yelp.com/biz/marios-pizza-ottawa",
                    "title": "Mario's Pizza in Ottawa - Yelp",
                    "snippet": "Family-run.",
                },
            ]),
        ]
        out = _detect_directory_presence(per_query, "Joe's Pizza", ["Mario's Pizza"])
        assert out["user"] == []
        assert "Yelp" in out["competitors"]["Mario's Pizza"]
        assert "Yelp" in out["gaps"]   # competitor on, user not → gap

    def test_no_gap_when_user_also_on_directory(self):
        per_query = [
            self._make_query([
                {"link": "https://yelp.com/biz/joes-pizza",  "title": "Joe's Pizza - Yelp",
                 "snippet": ""},
                {"link": "https://yelp.com/biz/marios",      "title": "Mario's Pizza - Yelp",
                 "snippet": ""},
            ]),
        ]
        out = _detect_directory_presence(per_query, "Joe's Pizza", ["Mario's Pizza"])
        assert "Yelp" in out["user"]
        assert "Yelp" in out["competitors"]["Mario's Pizza"]
        assert out["gaps"] == []   # both on Yelp → no gap

    def test_non_directory_domains_ignored(self):
        per_query = [
            self._make_query([
                {"link": "https://example.com/about", "title": "Joe's Pizza", "snippet": ""},
                {"link": "https://random-blog.com/",   "title": "Mario's Pizza review", "snippet": ""},
            ]),
        ]
        out = _detect_directory_presence(per_query, "Joe's Pizza", ["Mario's Pizza"])
        assert out["user"] == []
        assert out["competitors"]["Mario's Pizza"] == []

    def test_aggregates_across_queries(self):
        per_query = [
            self._make_query([
                {"link": "https://yelp.com/biz/joes",  "title": "Joe's Pizza on Yelp", "snippet": ""},
            ]),
            self._make_query([
                {"link": "https://bbb.org/listing",     "title": "Joe's Pizza - BBB", "snippet": ""},
            ]),
        ]
        out = _detect_directory_presence(per_query, "Joe's Pizza", [])
        assert set(out["user"]) == {"Yelp", "BBB"}

    def test_subdomain_directory_recognized(self):
        per_query = [
            self._make_query([
                {"link": "https://m.yelp.com/biz/joes", "title": "Joe's Pizza Yelp", "snippet": ""},
            ]),
        ]
        out = _detect_directory_presence(per_query, "Joe's Pizza", [])
        # Should match yelp.com via the endswith(".yelp.com") branch
        assert "Yelp" in out["user"]

    def test_returns_sorted_lists(self):
        per_query = [
            self._make_query([
                {"link": "https://yelp.com/biz/x",   "title": "Joe's Pizza Yelp", "snippet": ""},
                {"link": "https://bbb.org/x",        "title": "Joe's Pizza BBB",   "snippet": ""},
                {"link": "https://411.ca/biz/x",     "title": "Joe's Pizza 411",   "snippet": ""},
            ]),
        ]
        out = _detect_directory_presence(per_query, "Joe's Pizza", [])
        assert out["user"] == sorted(out["user"])  # sorted

    def test_empty_input_returns_empty_shape(self):
        out = _detect_directory_presence([], "Joe's", [])
        assert out == {"user": [], "competitors": {}, "gaps": []}


# ─── DIRECTORY_DOMAINS sanity ─────────────────────────────────────────────
class TestDirectoryDomainsConst:
    def test_has_canadian_directories(self):
        # We're a Canadian product — must cover CA-specific directories
        assert "yelp.ca" in DIRECTORY_DOMAINS
        assert "yellowpages.ca" in DIRECTORY_DOMAINS
        assert "411.ca" in DIRECTORY_DOMAINS
        assert "canada411.ca" in DIRECTORY_DOMAINS

    def test_has_canadian_trades_directories(self):
        # The two most important Canadian-specific trades directories
        assert "homestars.com" in DIRECTORY_DOMAINS
        assert "trustedpros.ca" in DIRECTORY_DOMAINS
        assert DIRECTORY_DOMAINS["homestars.com"]  == "HomeStars"
        assert DIRECTORY_DOMAINS["trustedpros.ca"] == "TrustedPros"

    def test_has_canadian_general_directories(self):
        # n49 + Cylex Canada — added 2026-05-08
        assert DIRECTORY_DOMAINS["n49.com"]         == "n49"
        assert DIRECTORY_DOMAINS["cylex-canada.ca"] == "Cylex Canada"

    def test_has_canadian_vertical_directories(self):
        # Vertical-specific Canadian directories
        assert DIRECTORY_DOMAINS["realtor.ca"]      == "Realtor.ca"
        assert DIRECTORY_DOMAINS["lawyerlocate.ca"] == "LawyerLocate"
        assert DIRECTORY_DOMAINS["opentable.com"]   == "OpenTable"
        assert DIRECTORY_DOMAINS["opentable.ca"]    == "OpenTable"

    def test_has_reddit_as_community_citation_source(self):
        assert DIRECTORY_DOMAINS["reddit.com"] == "Reddit"

    def test_has_global_majors(self):
        for d in ["yelp.com", "tripadvisor.com", "bbb.org", "facebook.com",
                  "linkedin.com", "instagram.com", "foursquare.com"]:
            assert d in DIRECTORY_DOMAINS

    def test_labels_are_consistent(self):
        # Both yelp.com and yelp.ca should label as "Yelp"
        assert DIRECTORY_DOMAINS["yelp.com"] == DIRECTORY_DOMAINS["yelp.ca"]
        assert DIRECTORY_DOMAINS["yellowpages.com"] == DIRECTORY_DOMAINS["yellowpages.ca"]
        assert DIRECTORY_DOMAINS["tripadvisor.com"] == DIRECTORY_DOMAINS["tripadvisor.ca"]

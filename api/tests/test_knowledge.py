"""
Tests for the knowledge-base loader (api/aeo/knowledge.py).

Verifies that:
  - Frontmatter parses correctly (inline list, multi-line list, scalars)
  - Files in api/knowledge/ load successfully at module init
  - for_faq() returns the FAQ best-practices entry
  - for_recommendation() matches by title (case-insensitive exact match)
"""
from aeo import knowledge as kb


# ─── Frontmatter parser ──────────────────────────────────────────────────
class TestParseFrontmatter:
    def test_inline_list(self):
        raw = (
            "---\n"
            "key: foo\n"
            "match_titles: [\"A\", \"B\"]\n"
            "---\n"
            "body content"
        )
        meta, body = kb._parse_frontmatter(raw)
        assert meta["key"] == "foo"
        assert meta["match_titles"] == ["A", "B"]
        assert body.strip() == "body content"

    def test_multiline_list(self):
        raw = (
            "---\n"
            "key: foo\n"
            "match_titles:\n"
            "  - First Title\n"
            "  - Second Title\n"
            "applies_to: recommendation\n"
            "---\n"
            "body"
        )
        meta, _ = kb._parse_frontmatter(raw)
        assert meta["match_titles"] == ["First Title", "Second Title"]
        assert meta["applies_to"] == "recommendation"

    def test_scalar_with_quotes(self):
        raw = "---\nkey: \"foo\"\napplies_to: 'faq'\n---\nbody"
        meta, _ = kb._parse_frontmatter(raw)
        assert meta["key"] == "foo"
        assert meta["applies_to"] == "faq"

    def test_no_frontmatter_returns_empty_meta(self):
        meta, body = kb._parse_frontmatter("just a body, no frontmatter")
        assert meta == {}
        assert "just a body" in body


# ─── KnowledgeEntry.matches_title ────────────────────────────────────────
class TestMatchesTitle:
    def test_case_insensitive_exact(self):
        e = kb.KnowledgeEntry(key="x", applies_to="recommendation",
                              match_titles=["Claim your HomeStars profile"])
        assert e.matches_title("Claim your HomeStars profile")
        assert e.matches_title("claim your homestars profile")
        assert e.matches_title("CLAIM YOUR HOMESTARS PROFILE")

    def test_no_match(self):
        e = kb.KnowledgeEntry(key="x", applies_to="recommendation",
                              match_titles=["Foo"])
        assert not e.matches_title("Bar")
        assert not e.matches_title("")
        assert not e.matches_title(None)

    def test_no_titles_never_matches(self):
        e = kb.KnowledgeEntry(key="x", applies_to="faq")
        assert not e.matches_title("anything")


# ─── Real-file integration (loaded at module init) ───────────────────────
class TestLoadedEntries:
    def test_faq_aeo_entry_loaded(self):
        """The FAQ best-practices entry must exist (it's the Phase 1 win)."""
        body = kb.for_faq()
        assert body is not None
        assert "AEO best practices" in body or "long-tail" in body.lower()

    def test_homestars_entry_loaded(self):
        """HomeStars knowledge should match the trades rec title."""
        body = kb.for_recommendation("Claim your HomeStars profile")
        assert body is not None
        assert "HST" in body or "GST" in body
        # Should mention common stuck points
        assert "stuck" in body.lower() or "common" in body.lower()

    def test_trustedpros_entry_loaded(self):
        body = kb.for_recommendation("Claim your TrustedPros profile")
        assert body is not None

    def test_ratemds_entry_loaded(self):
        body = kb.for_recommendation("Claim your RateMDs profile")
        assert body is not None
        # Key Canadian-specific insight: profiles auto-created from public records
        assert "claim" in body.lower()

    def test_opencare_entry_loaded(self):
        body = kb.for_recommendation("Claim your Opencare profile")
        assert body is not None

    def test_opentable_entry_loaded(self):
        body = kb.for_recommendation("Claim your OpenTable listing")
        assert body is not None
        # Key tradeoff: free directory tier vs paid reservations
        assert "free" in body.lower() and "paid" in body.lower()

    def test_apple_business_connect_entry_loaded(self):
        body = kb.for_recommendation("Claim your Apple Business Connect listing")
        assert body is not None
        # Common stuck point we explicitly call out
        assert "Apple ID" in body

    def test_unmatched_title_returns_none(self):
        assert kb.for_recommendation("Claim your made-up directory profile") is None
        assert kb.for_recommendation("") is None
        assert kb.for_recommendation(None) is None

    def test_all_keys_includes_expected(self):
        keys = kb.all_keys()
        assert "faq_generation_aeo" in keys
        assert "homestars" in keys
        assert "trustedpros" in keys
        assert "ratemds" in keys
        assert "opencare" in keys
        assert "opentable" in keys
        assert "apple_business_connect" in keys

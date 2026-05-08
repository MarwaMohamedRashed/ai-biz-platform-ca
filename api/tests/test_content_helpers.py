"""
Tests for content-generation helpers in api/aeo/router.py.
Covers QA test plan sections 6.3 (per-platform caps), 6.9 (FR variant),
6.12 (validation warnings).
"""
from aeo.router import (
    _truncate_at_word,
    _validate_content,
    _build_content_prompts,
)


# ─── _truncate_at_word ────────────────────────────────────────────────────
class TestTruncateAtWord:
    def test_short_string_unchanged(self):
        assert _truncate_at_word("hello world", 100) == "hello world"

    def test_exact_length_unchanged(self):
        s = "a" * 100
        assert _truncate_at_word(s, 100) == s

    def test_long_string_truncated_with_ellipsis(self):
        s = "lorem ipsum dolor sit amet consectetur adipiscing elit"
        out = _truncate_at_word(s, 30)
        assert len(out) <= 30
        assert out.endswith("…")

    def test_does_not_split_words(self):
        s = "lorem ipsum dolor sit amet"
        out = _truncate_at_word(s, 12)
        # Output must end at a word boundary, then "…"
        assert out.endswith("…")
        assert " ipsum…" in out or " lorem…" in out or out == "lorem…"
        # No half-word like "ipsu" should appear
        assert "ipsu…" not in out

    def test_strips_input_whitespace(self):
        assert _truncate_at_word("  hello  ", 100) == "hello"

    def test_empty_returns_empty(self):
        assert _truncate_at_word(None, 100) == ""
        assert _truncate_at_word("", 100) == ""


# ─── _validate_content ────────────────────────────────────────────────────
class TestValidateContent:
    def test_clean_input_no_warnings(self):
        descriptions = {
            "website": " ".join(["lorem"] * 150),  # 150 words
            "gbp":     "Short clean GBP description.",
            "yelp":    "Yelp description.",
        }
        faq = [{"question": f"Q{i}", "answer": f"A{i}"} for i in range(10)]
        social_bio = "Punchy bio under 150 chars."
        warnings = _validate_content(descriptions, faq, social_bio)
        assert warnings == []

    def test_short_website_flagged(self):
        descriptions = {"website": "too short", "gbp": "ok", "yelp": "ok"}
        faq = [{"question": f"Q{i}", "answer": f"A{i}"} for i in range(10)]
        warnings = _validate_content(descriptions, faq, "bio")
        assert "website_description_too_short" in warnings

    def test_missing_gbp_flagged(self):
        descriptions = {"website": " ".join(["w"] * 200), "gbp": "", "yelp": "ok"}
        warnings = _validate_content(descriptions,
                                      [{"question": f"Q{i}", "answer": f"A{i}"} for i in range(10)],
                                      "bio")
        assert "gbp_description_missing" in warnings

    def test_long_gbp_flagged(self):
        descriptions = {"website": " ".join(["w"] * 200),
                        "gbp": "x" * 800,    # > 750
                        "yelp": "ok"}
        warnings = _validate_content(descriptions,
                                      [{"question": f"Q{i}", "answer": f"A{i}"} for i in range(10)],
                                      "bio")
        assert "gbp_description_too_long" in warnings

    def test_few_faqs_flagged(self):
        descriptions = {"website": " ".join(["w"] * 200), "gbp": "ok", "yelp": "ok"}
        faq = [{"question": "Q", "answer": "A"}]   # only 1
        warnings = _validate_content(descriptions, faq, "bio")
        assert "faq_too_few_items" in warnings

    def test_long_social_bio_flagged(self):
        descriptions = {"website": " ".join(["w"] * 200), "gbp": "ok", "yelp": "ok"}
        faq = [{"question": f"Q{i}", "answer": f"A{i}"} for i in range(10)]
        warnings = _validate_content(descriptions, faq, "x" * 200)
        assert "social_bio_invalid_length" in warnings


# ─── _build_content_prompts ───────────────────────────────────────────────
class TestBuildContentPrompts:
    @staticmethod
    def _has_keys(d):
        assert set(d.keys()) == {"website_desc", "gbp_desc", "yelp_desc", "social_bio", "faq"}

    def test_english_prompts_have_all_keys(self):
        p = _build_content_prompts("en", "ctx", "service1", [])
        self._has_keys(p)

    def test_french_prompts_have_all_keys(self):
        p = _build_content_prompts("fr", "ctx", "service1", [])
        self._has_keys(p)

    def test_french_prompts_are_in_french(self):
        # If FR prompts are built, they should contain French words/phrases
        p = _build_content_prompts("fr", "ctx", "service1", [])
        # Basic French markers in any of the description prompts
        joined = " ".join(p.values()).lower()
        assert any(word in joined for word in ["entreprise", "écris", "français", "mots"])

    def test_english_prompts_are_in_english(self):
        p = _build_content_prompts("en", "ctx", "service1", [])
        joined = " ".join(p.values()).lower()
        assert any(word in joined for word in ["business", "write", "words", "description"])

    def test_services_appear_in_description_prompts(self):
        p = _build_content_prompts("en", "ctx", "physiotherapy, massage, sports", [])
        # Services line should be in website + gbp + yelp prompts (not in social/faq)
        for k in ["website_desc", "gbp_desc", "yelp_desc"]:
            assert "physiotherapy, massage, sports" in p[k]

    def test_paa_questions_appear_in_faq_prompt(self):
        paa = ["What insurance do you accept?", "Do you have parking?"]
        p = _build_content_prompts("en", "ctx", "", paa)
        assert "What insurance do you accept?" in p["faq"]
        assert "Do you have parking?" in p["faq"]

    def test_paa_block_omitted_when_empty(self):
        p = _build_content_prompts("en", "ctx", "", [])
        # Should NOT have the "real customer questions" prefix
        assert "real customer questions" not in p["faq"]

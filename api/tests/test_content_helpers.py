"""
Tests for content-generation helpers in api/aeo/router.py.
Covers QA test plan sections 6.3 (per-platform caps), 6.9 (FR variant),
6.12 (validation warnings).
"""
from aeo.router import (
    _truncate_at_word,
    _validate_content,
    _build_content_prompts,
    _clean_bio,
    _clean_description,
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

    # ─── Phase 2: custom seed questions ───────────────────────────────
    def test_custom_seeds_included_verbatim_in_faq_prompt_en(self):
        seeds = ["Can I bring my dog?", "Do you accept Sunlife insurance?"]
        p = _build_content_prompts("en", "ctx", "", [], seeds)
        assert "Can I bring my dog?" in p["faq"]
        assert "Do you accept Sunlife insurance?" in p["faq"]
        # Asks LLM to use them verbatim, not rephrase
        assert "verbatim" in p["faq"].lower() or "exactly" in p["faq"].lower()

    def test_custom_seeds_included_verbatim_in_faq_prompt_fr(self):
        seeds = ["Puis-je amener mon chien ?", "Acceptez-vous Sunlife ?"]
        p = _build_content_prompts("fr", "ctx", "", [], seeds)
        assert "Puis-je amener mon chien" in p["faq"]
        assert "telles quelles" in p["faq"].lower() or "exactement" in p["faq"].lower()

    def test_custom_seeds_block_omitted_when_empty(self):
        p = _build_content_prompts("en", "ctx", "", [], [])
        assert "OWNER'S CUSTOM QUESTIONS" not in p["faq"]
        p2 = _build_content_prompts("en", "ctx", "", [])  # arg omitted
        assert "OWNER'S CUSTOM QUESTIONS" not in p2["faq"]

    def test_custom_seeds_capped_at_10(self):
        seeds = [f"Question {i}?" for i in range(15)]
        p = _build_content_prompts("en", "ctx", "", [], seeds)
        # First 10 should be present
        assert "Question 0?" in p["faq"]
        assert "Question 9?" in p["faq"]
        # 11+ should NOT be in the prompt
        assert "Question 10?" not in p["faq"]
        assert "Question 14?" not in p["faq"]

    def test_custom_seeds_empty_strings_dropped(self):
        seeds = ["", "  ", "Real question?", ""]
        p = _build_content_prompts("en", "ctx", "", [], seeds)
        assert "Real question?" in p["faq"]
        # Block should reference 1 question (not 4)
        assert "first 1 question" in p["faq"]

    def test_custom_seeds_remaining_count_in_prompt(self):
        # 3 seeds -> LLM asked to generate 7 more
        p = _build_content_prompts("en", "ctx", "", [], ["Q1?", "Q2?", "Q3?"])
        assert "generate 7 additional" in p["faq"].lower()

    def test_custom_seeds_only_affects_faq_not_other_prompts(self):
        seeds = ["Custom seed question 1?"]
        p = _build_content_prompts("en", "ctx", "", [], seeds)
        # Seeds must appear in the FAQ prompt
        assert "Custom seed question 1?" in p["faq"]
        # But NOT in description / bio prompts (defensive — wrong wiring would leak)
        for key in ("website_desc", "gbp_desc", "yelp_desc", "social_bio"):
            assert "Custom seed question 1?" not in p[key], f"leaked into {key}"

    def test_bio_prompt_includes_format_constraint(self):
        # Regression for the "markdown header + alternatives" bug —
        # the bio prompt must explicitly forbid the bad output patterns
        p = _build_content_prompts("en", "ctx", "", [])
        bio = p["social_bio"].lower()
        assert "no markdown" in bio
        assert "no alternative" in bio or "no alternatives" in bio

    def test_description_prompts_include_format_constraint(self):
        p = _build_content_prompts("en", "ctx", "", [])
        for k in ["website_desc", "gbp_desc", "yelp_desc"]:
            assert "no markdown" in p[k].lower(), f"{k} missing format constraint"


# ─── _clean_bio (regression for markdown + meta-commentary bug) ───────────
class TestCleanBio:
    def test_strips_markdown_header(self):
        raw = "# LeapOne Bio\n\nAI Visibility for Tech Companies | Milton, ON"
        assert _clean_bio(raw) == "AI Visibility for Tech Companies | Milton, ON"

    def test_strips_bold_wrapper(self):
        raw = "**AI Visibility for Tech Companies | Milton, ON**"
        assert _clean_bio(raw) == "AI Visibility for Tech Companies | Milton, ON"

    def test_strips_bold_after_header(self):
        raw = "# LeapOne Bio\n\n**AI Visibility for Tech Companies | Milton, ON**"
        assert _clean_bio(raw) == "AI Visibility for Tech Companies | Milton, ON"

    def test_cuts_at_horizontal_rule(self):
        raw = (
            "Best plumber in Toronto, 24/7 emergency service.\n"
            "---\n"
            "*Character count: 50 characters*"
        )
        assert _clean_bio(raw) == "Best plumber in Toronto, 24/7 emergency service."

    def test_cuts_at_alternative_section(self):
        raw = (
            "Best plumber in Toronto.\n\n"
            "Alternative if you want shorter: GTA's emergency plumber."
        )
        assert _clean_bio(raw) == "Best plumber in Toronto."

    def test_cuts_at_character_count_note(self):
        raw = "Best plumber in Toronto.\n\n*Character count: 24 characters*"
        assert _clean_bio(raw) == "Best plumber in Toronto."

    def test_strips_label_prefix(self):
        for prefix in ["Bio: ", "Social Bio: ", "Instagram Bio: ", "Caption: "]:
            assert _clean_bio(prefix + "Best plumber in Toronto.") == "Best plumber in Toronto."

    def test_strips_quotes(self):
        assert _clean_bio('"Best plumber in Toronto."') == "Best plumber in Toronto."
        assert _clean_bio("'Best plumber in Toronto.'") == "Best plumber in Toronto."

    def test_real_world_example_from_screenshot(self):
        # The exact pattern from the user's screenshot bug report
        raw = (
            "# LeapOne Bio\n\n"
            "**AI Visibility for Tech Companies | Milton, ON**\n\n"
            "---\n\n"
            "*Character count: 50 characters (well under the 150 limit)*\n\n"
            "**Alternative if..."
        )
        cleaned = _clean_bio(raw)
        assert cleaned == "AI Visibility for Tech Companies | Milton, ON"
        assert "#" not in cleaned
        assert "**" not in cleaned
        assert "Character count" not in cleaned
        assert "Alternative" not in cleaned

    def test_clean_bio_then_truncate_works_correctly(self):
        # Defense-in-depth: clean first, then truncate. The original bug was
        # that we truncated 150 chars of "# LeapOne Bio\n\n**actual bio**" —
        # so the truncated output was mostly garbage.
        raw = (
            "# LeapOne Bio\n\n"
            "**This is a long bio that goes way past one hundred and fifty "
            "characters so it will be truncated by the next step in the pipeline.**"
        )
        cleaned = _clean_bio(raw)
        truncated = _truncate_at_word(cleaned, 150)
        assert "#" not in truncated and "**" not in truncated
        assert truncated.startswith("This is a long bio")

    def test_empty_returns_empty(self):
        assert _clean_bio("") == ""
        assert _clean_bio(None) == ""

    def test_already_clean_passthrough(self):
        assert _clean_bio("Best plumber in Toronto.") == "Best plumber in Toronto."


# ─── _clean_description ──────────────────────────────────────────────────
class TestCleanDescription:
    def test_strips_here_is_preamble(self):
        raw = "Here is the website description:\n\nAcme Plumbing serves Toronto..."
        assert _clean_description(raw).startswith("Acme Plumbing")

    def test_strips_label(self):
        for prefix in ["Description: ", "Website Description: ", "Google Description: "]:
            assert _clean_description(prefix + "Acme Plumbing serves...").startswith("Acme Plumbing")

    def test_strips_markdown_header(self):
        raw = "# Acme Plumbing\n\nServes Toronto and the GTA..."
        assert _clean_description(raw).startswith("Serves Toronto")

    def test_preserves_paragraph_content(self):
        # Light cleanup — must NOT strip paragraph content
        raw = (
            "Acme Plumbing is a Toronto-based plumbing service serving the GTA.\n\n"
            "We specialize in emergency repairs, drain cleaning, and water heater "
            "installation. Available 24/7 with same-day appointments."
        )
        out = _clean_description(raw)
        assert "Acme Plumbing" in out
        assert "GTA" in out
        assert "emergency repairs" in out

    def test_empty_returns_empty(self):
        assert _clean_description("") == ""
        assert _clean_description(None) == ""

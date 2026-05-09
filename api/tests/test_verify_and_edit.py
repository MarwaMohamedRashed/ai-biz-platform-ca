"""
Tests for the verify-and-edit flow on aeo_content.

Covers the deterministic helpers that drive PATCH /content/{id},
POST /content/{id}/verify, and POST /content/{id}/regenerate-item:
  - dotted-path patcher (_apply_content_patch)
  - key validation regexes
  - auth-gate / shape constraints (via curl-style HTTP tests below)

The actual endpoints + LLM regeneration paths are tested via integration
tests when we add a test-mode supabase fixture; for now we lock in the
pure-function behaviour the endpoints depend on.
"""
import pytest
from aeo.router import (
    _apply_content_patch,
    _VERIFY_KEY_RE,
    _PATCH_KEY_RE,
    _REGENERATE_KEY_RE,
)


# ─── _apply_content_patch ────────────────────────────────────────────────
class TestApplyContentPatch:
    def _row(self):
        return {
            "descriptions": {"website": "old web", "gbp": "old gbp", "yelp": "old yelp"},
            "description":  "old web",  # legacy column
            "social_bio":   "old bio",
            "faq": [
                {"question": "Q1?", "answer": "A1"},
                {"question": "Q2?", "answer": "A2"},
                {"question": "Q3?", "answer": "A3"},
            ],
        }

    def test_update_description_website_also_syncs_legacy_column(self):
        row = self._row()
        _apply_content_patch(row, "description.website", "new web")
        assert row["descriptions"]["website"] == "new web"
        assert row["description"] == "new web"   # legacy column kept in sync

    def test_update_description_gbp_does_not_touch_legacy_column(self):
        row = self._row()
        _apply_content_patch(row, "description.gbp", "new gbp")
        assert row["descriptions"]["gbp"] == "new gbp"
        assert row["description"] == "old web"   # legacy untouched

    def test_update_description_yelp(self):
        row = self._row()
        _apply_content_patch(row, "description.yelp", "new yelp")
        assert row["descriptions"]["yelp"] == "new yelp"

    def test_update_social_bio(self):
        row = self._row()
        _apply_content_patch(row, "social_bio", "new bio")
        assert row["social_bio"] == "new bio"

    def test_update_faq_question(self):
        row = self._row()
        _apply_content_patch(row, "faq.1.question", "new Q2?")
        assert row["faq"][1]["question"] == "new Q2?"
        assert row["faq"][1]["answer"]   == "A2"   # answer preserved

    def test_update_faq_answer(self):
        row = self._row()
        _apply_content_patch(row, "faq.0.answer", "new A1")
        assert row["faq"][0]["question"] == "Q1?"  # question preserved
        assert row["faq"][0]["answer"]   == "new A1"

    def test_other_descriptions_unchanged_on_partial_update(self):
        row = self._row()
        _apply_content_patch(row, "description.website", "new web")
        assert row["descriptions"]["gbp"]  == "old gbp"
        assert row["descriptions"]["yelp"] == "old yelp"

    def test_other_faq_items_unchanged_on_partial_update(self):
        row = self._row()
        _apply_content_patch(row, "faq.1.answer", "new A2")
        assert row["faq"][0] == {"question": "Q1?", "answer": "A1"}
        assert row["faq"][2] == {"question": "Q3?", "answer": "A3"}

    def test_invalid_key_raises(self):
        row = self._row()
        with pytest.raises(ValueError):
            _apply_content_patch(row, "schema_markup", "fake")

    def test_invalid_description_subkey_raises(self):
        row = self._row()
        with pytest.raises(ValueError):
            _apply_content_patch(row, "description.snapchat", "x")

    def test_faq_index_out_of_range_raises(self):
        row = self._row()
        with pytest.raises(ValueError):
            _apply_content_patch(row, "faq.99.answer", "x")

    def test_negative_faq_index_raises(self):
        row = self._row()
        with pytest.raises(ValueError):
            _apply_content_patch(row, "faq.-1.answer", "x")

    def test_invalid_faq_field_raises(self):
        row = self._row()
        with pytest.raises(ValueError):
            _apply_content_patch(row, "faq.0.snippet", "x")


# ─── Key regex constraints ───────────────────────────────────────────────
class TestVerifyKeyRegex:
    def test_accepts_valid_keys(self):
        for k in ["description.website", "description.gbp", "description.yelp",
                  "social_bio", "faq.0", "faq.7", "faq.99"]:
            assert _VERIFY_KEY_RE.match(k), f"rejected: {k}"

    def test_rejects_invalid_keys(self):
        for k in ["description.snapchat", "description", "social", "faq",
                  "faq.foo", "faq.0.question", "schema_markup", "..", ""]:
            assert not _VERIFY_KEY_RE.match(k), f"accepted: {k}"


class TestPatchKeyRegex:
    def test_accepts_valid_keys(self):
        for k in ["description.website", "social_bio",
                  "faq.0.question", "faq.5.answer"]:
            assert _PATCH_KEY_RE.match(k), f"rejected: {k}"

    def test_requires_qa_field_for_faq(self):
        # faq.0 alone is for verify, not patch
        assert not _PATCH_KEY_RE.match("faq.0")

    def test_rejects_unknown_faq_field(self):
        assert not _PATCH_KEY_RE.match("faq.0.metadata")

    def test_rejects_schema_markup(self):
        # Schema is deterministic -- not editable
        assert not _PATCH_KEY_RE.match("schema_markup")
        assert not _PATCH_KEY_RE.match("faq_schema")


class TestRegenerateKeyRegex:
    def test_accepts_valid_keys(self):
        for k in ["description.website", "description.gbp", "description.yelp",
                  "social_bio", "faq.0", "faq.4"]:
            assert _REGENERATE_KEY_RE.match(k), f"rejected: {k}"

    def test_rejects_individual_faq_fields(self):
        # Regenerate works at the FAQ-item level, not Q/A field level
        # (rewriting just the question without the answer would break coherence)
        assert not _REGENERATE_KEY_RE.match("faq.0.question")
        assert not _REGENERATE_KEY_RE.match("faq.0.answer")

    def test_rejects_schemas(self):
        # Schemas regenerate via the deterministic builder -- no LLM call,
        # so there's nothing meaningful for "regenerate with notes" to do
        assert not _REGENERATE_KEY_RE.match("schema_markup")
        assert not _REGENERATE_KEY_RE.match("faq_schema")

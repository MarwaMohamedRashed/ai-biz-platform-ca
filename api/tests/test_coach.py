"""
Tests for the AI execution coach (POST /recommendation-help).

The endpoint itself depends on the LLM + auth + DB so we test it via curl
in CI; here we cover the deterministic helpers:
  - _build_coach_system_prompt: includes recommendation context + business
    context + behaviour rules; FR variant returns French.
  - Constants: history cap, message cap.
"""
from aeo.router import (
    _build_coach_system_prompt,
    _COACH_HISTORY_CAP,
    _COACH_MESSAGE_CAP,
    CoachRecommendation,
)


def _rec(**overrides) -> CoachRecommendation:
    base = {
        "title":       "Claim your HomeStars profile",
        "description": "HomeStars is Canada's largest trades directory.",
        "action":      "Create a free contractor profile at homestars.com/create-account.",
        "pillar":      "ai_citation",
        "url":         "https://homestars.com/create-account",
        "impact":      4,
    }
    base.update(overrides)
    return CoachRecommendation(**base)


def _biz(**overrides) -> dict:
    base = {
        "name":     "Joe's Plumbing",
        "type":     "plumber",
        "city":     "Toronto",
        "province": "ON",
        "country":  "Canada",
        "website":  "https://joesplumbing.ca",
    }
    base.update(overrides)
    return base


# ─── _build_coach_system_prompt — English ─────────────────────────────────
class TestBuildCoachSystemPromptEnglish:
    def test_includes_recommendation_title(self):
        p = _build_coach_system_prompt(_rec(), _biz(), "en")
        assert "Claim your HomeStars profile" in p

    def test_includes_recommendation_action(self):
        p = _build_coach_system_prompt(_rec(), _biz(), "en")
        assert "homestars.com/create-account" in p

    def test_includes_business_name_and_city(self):
        p = _build_coach_system_prompt(_rec(), _biz(), "en")
        assert "Joe's Plumbing" in p
        assert "Toronto" in p
        assert "ON" in p

    def test_handles_missing_url(self):
        p = _build_coach_system_prompt(_rec(url=None), _biz(), "en")
        assert "Link: none" in p

    def test_handles_missing_website(self):
        p = _build_coach_system_prompt(_rec(), _biz(website=None), "en")
        assert "not provided" in p

    def test_includes_behaviour_rules(self):
        p = _build_coach_system_prompt(_rec(), _biz(), "en")
        # Rule 1: keep replies short
        assert "SHORT" in p or "short" in p
        # Rule 2: ask clarifying questions
        assert "clarif" in p.lower()
        # Rule 5: offer to write an email for a developer
        assert "email" in p.lower() and ("administrator" in p.lower() or "developer" in p.lower())
        # Rule 7: never invent
        assert "invent" in p.lower() or "not sure" in p.lower() or "honest" in p.lower()

    def test_includes_non_technical_warning(self):
        p = _build_coach_system_prompt(_rec(), _biz(), "en")
        assert "NOT technical" in p or "not technical" in p

    def test_canadian_context_preserved(self):
        p = _build_coach_system_prompt(_rec(), _biz(), "en")
        # The system prompt should be specifically about Canadian SMBs,
        # not generic worldwide
        assert "Canadian" in p


# ─── _build_coach_system_prompt — French ──────────────────────────────────
class TestBuildCoachSystemPromptFrench:
    def test_returns_french_when_locale_fr(self):
        p = _build_coach_system_prompt(_rec(), _biz(), "fr")
        # French markers in the system prompt
        assert any(word in p.lower() for word in ["coach ia", "propriétaire", "pme canadienne"])

    def test_includes_recommendation_in_french_prompt(self):
        p = _build_coach_system_prompt(_rec(title="Réclamez votre profil"), _biz(), "fr")
        assert "Réclamez votre profil" in p

    def test_includes_business_context_in_french_prompt(self):
        p = _build_coach_system_prompt(_rec(), _biz(city="Montréal"), "fr")
        assert "Montréal" in p

    def test_french_prompt_includes_quebec_french_directive(self):
        p = _build_coach_system_prompt(_rec(), _biz(), "fr")
        # Asking for Quebec French specifically (not metropolitan French)
        assert "français du Québec" in p or "Québec" in p


# ─── Constants ───────────────────────────────────────────────────────────
class TestCoachConstants:
    def test_history_cap_is_reasonable(self):
        # 20 messages = ~10 conversational turns. Bounds cost without
        # cutting off normal coaching sessions.
        assert 10 <= _COACH_HISTORY_CAP <= 50

    def test_message_cap_allows_full_questions(self):
        # 2000 chars is plenty for a long question + context paste-in
        # but blocks paragraph-stuffing attacks.
        assert 500 <= _COACH_MESSAGE_CAP <= 5000

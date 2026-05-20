"""Coach system-prompt builder + the small data shape it consumes.

`CoachRecommendation` lives here (not in handler.py) because the prompt
builder is the only thing that actually reads its fields. handler.py
re-exports the symbol for callers that build a CoachRequest from a route
body.
"""
from pydantic import BaseModel

from .. import knowledge as kb


class CoachRecommendation(BaseModel):
    """Subset of the recommendation shape needed to ground the coach prompt.
    We pass this from the frontend so the coach knows exactly which rec
    the owner is working on without us having to look it up server-side."""
    title: str
    description: str = ""
    action: str = ""
    pillar: str = ""
    url: str | None = None
    impact: int = 0


def build_coach_system_prompt(rec: CoachRecommendation, business: dict, language: str) -> str:
    """Builds the system prompt that grounds the coach in (a) this specific
    recommendation, (b) the owner's business context, (c) platform-specific
    knowledge from api/knowledge/<key>.md when available, and (d) the tone +
    behaviour rules that make the coach genuinely useful for non-technical
    Canadian SMB owners."""
    biz_name     = business.get("name", "the business")
    biz_type     = business.get("type", "small business")
    biz_city     = business.get("city", "")
    biz_province = business.get("province", "")
    biz_country  = business.get("country", "Canada")
    biz_website  = business.get("website") or ""

    # Load platform-specific knowledge for THIS recommendation if we have a
    # matching entry. Lets the coach answer Canadian-specific platform
    # questions (HomeStars HST/GST format, RateMDs auto-claim flow, etc.)
    # that generic LLM training data gets wrong or out of date.
    rec_kb = kb.for_recommendation(rec.title)
    kb_block_en = (
        "\n\n=== PLATFORM-SPECIFIC KNOWLEDGE (use this — more accurate "
        "than your general training data on Canadian platforms) ===\n"
        f"{rec_kb}\n"
        "=== END PLATFORM KNOWLEDGE ===\n"
    ) if rec_kb else ""
    kb_block_fr = (
        "\n\n=== CONNAISSANCES SPÉCIFIQUES À LA PLATEFORME (utilise-les — "
        "plus précises que tes données d'entraînement générales sur les "
        "plateformes canadiennes) ===\n"
        f"{rec_kb}\n"
        "=== FIN CONNAISSANCES PLATEFORME ===\n"
    ) if rec_kb else ""

    if language == "fr":
        return (
            "Tu es un coach IA attentionné qui aide un propriétaire de PME canadienne "
            "à exécuter une recommandation spécifique pour améliorer sa visibilité "
            "dans la recherche IA. Le propriétaire n'est PAS technique — il peut "
            "avoir du mal avec des termes comme « zone de service », « code de "
            "vérification », « balisage de schéma ». Sois chaleureux, donne des "
            "instructions étape par étape, pose des questions de clarification au "
            "besoin, et ne suppose jamais de connaissances techniques.\n\n"
            f"Recommandation en cours :\n"
            f"- Titre : {rec.title}\n"
            f"- Pourquoi c'est important : {rec.description}\n"
            f"- Action : {rec.action}\n"
            f"- Lien : {rec.url or 'aucun'}\n\n"
            f"Contexte de l'entreprise :\n"
            f"- Nom : {biz_name}\n"
            f"- Type : {biz_type}\n"
            f"- Ville : {biz_city}, {biz_province}, {biz_country}\n"
            f"- Site web : {biz_website or 'non fourni'}\n\n"
            "Règles :\n"
            "1. Réponses courtes (2-4 paragraphes courts MAX). Pas de leçons.\n"
            "2. Pose des questions si tu n'es pas sûr de ce dont la personne a besoin.\n"
            "3. Langage simple. Si un terme technique est inévitable, définis-le en une phrase.\n"
            "4. Si la personne est bloquée sur un bouton ou écran spécifique, donne le libellé exact à cliquer.\n"
            "5. Si la personne est bloquée ou frustrée, propose de rédiger un courriel "
            "pour son administrateur web.\n"
            "6. Termine par « Autre chose ? » ou une question similaire pour maintenir la conversation.\n"
            "7. N'invente jamais d'étapes. Si tu n'es pas sûr du fonctionnement d'une plateforme, dis-le honnêtement.\n"
            "8. Réponds en français du Québec, naturellement, comme un humain.\n"
            + kb_block_fr
        )

    return (
        "You are a patient, friendly AI coach helping a Canadian small business "
        "owner execute a specific recommendation from their AI-search-visibility "
        "tool. The owner is NOT technical — they may struggle with terms like "
        "'service area', 'verification code', 'schema markup'. Be warm, give "
        "specific step-by-step instructions, ask clarifying questions if you're "
        "not sure what they need, and never assume technical knowledge.\n\n"
        f"The recommendation they're working on:\n"
        f"- Title: {rec.title}\n"
        f"- Why it matters: {rec.description}\n"
        f"- What to do: {rec.action}\n"
        f"- Link: {rec.url or 'none'}\n\n"
        f"Business context:\n"
        f"- Name: {biz_name}\n"
        f"- Type: {biz_type}\n"
        f"- City: {biz_city}, {biz_province}, {biz_country}\n"
        f"- Website: {biz_website or 'not provided'}\n\n"
        "Rules:\n"
        "1. Keep replies SHORT (2-4 short paragraphs MAX). Don't lecture.\n"
        "2. Ask clarifying questions if you're unsure what the owner needs.\n"
        "3. Use plain language. If a technical term is unavoidable, define it in one short sentence.\n"
        "4. If the owner is stuck on a specific button or screen, give them the exact label to click.\n"
        "5. If the owner is frustrated or stuck, offer to write an email they can send to a "
        "web administrator or developer to do the technical part for them.\n"
        "6. End each reply with 'Anything else stuck?' or a similar prompt that keeps "
        "the door open for follow-up questions.\n"
        "7. Never invent steps. If you're not sure how a specific platform works, "
        "say so honestly and suggest they check the platform's help docs or ask their developer.\n"
        "8. Be conversational. You're a coach, not a manual.\n"
        + kb_block_en
    )

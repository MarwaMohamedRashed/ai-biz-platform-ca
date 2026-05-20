"""Content-generation prompt builders.

Two entry points:

- `build_content_prompts` — initial generation. Returns the EN/FR prompt
  set for the website / GBP / Yelp descriptions, social bio, and FAQ.
  Caller passes through PAA seeds (from SerpApi), owner-supplied custom
  FAQ seeds, and existing on-site FAQs to avoid duplication.

- `build_regenerate_prompts` — per-item regeneration. Reuses the
  content prompts internally and adds the owner's free-text notes as a
  rewrite signal.

Both append "no markdown / no preamble" hard-format rules so the LLM
doesn't decorate its output with character-count meta, alternative
versions, or section headers.
"""
from .. import knowledge as kb


# 2026 sweet spot per AEO research (10 was low-end).
FAQ_TARGET_COUNT = 15


def build_content_prompts(language: str, base_context: str, services: str,
                          paa_questions: list[str],
                          custom_faq_seeds: list[str] | None = None,
                          existing_faqs: list[dict] | None = None) -> dict[str, str]:
    """Localized prompt templates for the four LLM calls.

    `custom_faq_seeds` (Phase 2): owner-provided questions they hear from
    real customers. Used verbatim as the first N items in the generated FAQ.

    `existing_faqs` (Phase 4): owner-supplied Q+A pairs already on their
    website. Passed to the LLM as 'topics already covered — generate NEW
    questions that don't duplicate these'. The LLM only writes new Qs+As;
    the owner's existing pairs are merged back verbatim by the caller.

    The LLM is told to generate enough new Qs+As to bring the TOTAL
    (existing + custom seeds + new) to FAQ_TARGET_COUNT (15)."""
    services_line_en = f"\nServices to highlight: {services}" if services else ""
    services_line_fr = f"\nServices à mettre en avant : {services}" if services else ""

    # AEO best-practices knowledge appended to the FAQ prompt so the LLM
    # produces citation-optimized Q&As. Loaded from
    # api/knowledge/faq_generation_aeo.md at module import time.
    faq_aeo_kb = kb.for_faq()
    faq_kb_block = f"\n\n=== AEO BEST PRACTICES — APPLY EVERY ONE ===\n{faq_aeo_kb}\n=== END BEST PRACTICES ===\n" if faq_aeo_kb else ""

    # Phase 2 — owner's custom seed questions (verbatim Qs the LLM answers).
    seeds = [s.strip() for s in (custom_faq_seeds or []) if s and s.strip()][:10]

    # Phase 4 — owner's existing Q+A pairs from their website. The LLM is
    # told these topics are ALREADY COVERED — write NEW questions. Existing
    # pairs are merged back into the final FAQ list by the caller (verbatim).
    existing = []
    for f in (existing_faqs or [])[:50]:
        q = (f.get("question") or "").strip()[:200] if isinstance(f, dict) else ""
        a = (f.get("answer")   or "").strip()[:1000] if isinstance(f, dict) else ""
        if q and a:
            existing.append({"question": q, "answer": a})

    # How many NEW Q+As (LLM picks both Q and A on a topic NOT already
    # covered by existing or seeds). Total target (existing + seeds + new)
    # = FAQ_TARGET_COUNT, but never less than 5 new ones — even an owner
    # with 20 existing FAQs still gets fresh AEO-optimized content from us.
    new_target = max(5, FAQ_TARGET_COUNT - len(existing) - len(seeds))
    # llm_output_count = what the LLM writes in its JSON array. This includes
    # the seed Qs (LLM writes their answers) PLUS the new_target new Q+A pairs.
    # Existing pairs are NOT in this count -- they're merged in by the caller
    # after the LLM call.
    llm_output_count = len(seeds) + new_target

    # Build the existing-FAQs block — what the LLM should NOT duplicate.
    # Note: existing pairs are NOT in the LLM's output array; they're merged
    # back by the caller after the LLM call.
    existing_block_en = ""
    existing_block_fr = ""
    if existing:
        existing_listing = "\n".join(
            f"  {i+1}. Q: {f['question']}\n     A: {f['answer']}"
            for i, f in enumerate(existing)
        )
        existing_block_en = (
            f"\n\n=== TOPICS ALREADY COVERED ON OWNER'S WEBSITE — DO NOT DUPLICATE ===\n"
            f"The owner already has {len(existing)} Q+A pair(s) on their site. "
            f"DO NOT write questions that cover the same topics. None of your "
            f"{llm_output_count} output items should duplicate any of these. "
            f"The owner's existing FAQs are merged back automatically.\n"
            f"{existing_listing}\n=== END EXISTING TOPICS ===\n"
        )
        existing_block_fr = (
            f"\n\n=== SUJETS DÉJÀ COUVERTS SUR LE SITE DU PROPRIÉTAIRE — NE PAS DUPLIQUER ===\n"
            f"Le propriétaire a déjà {len(existing)} paire(s) Q+R sur son site. NE PAS "
            f"écrire de questions sur les mêmes sujets. Aucun de tes {llm_output_count} "
            f"éléments de sortie ne doit dupliquer ceux-ci. Les FAQ existantes "
            f"sont fusionnées automatiquement.\n{existing_listing}\n"
            f"=== FIN SUJETS EXISTANTS ===\n"
        )

    # Custom seed questions block — owner's verbatim Qs, LLM writes answers.
    # These count toward llm_output_count.
    custom_seed_block_en = ""
    custom_seed_block_fr = ""
    if seeds:
        joined = "\n".join(f'  {i+1}. "{s}"' for i, s in enumerate(seeds))
        remaining_after_seeds = llm_output_count - len(seeds)
        custom_seed_block_en = (
            f"\n\n=== OWNER'S CUSTOM QUESTIONS — USE VERBATIM ===\n"
            f"The owner says these are real questions they hear from customers. "
            f"Use them EXACTLY as the first {len(seeds)} questions in your output "
            f"(do not rephrase or rewrite). Write high-quality answers for each "
            f"that follow the best practices below. Then generate "
            f"{remaining_after_seeds} additional NEW Q+A pairs to complete your "
            f"set of {llm_output_count}.\n{joined}\n=== END CUSTOM QUESTIONS ===\n"
        )
        custom_seed_block_fr = (
            f"\n\n=== QUESTIONS PERSONNALISÉES DU PROPRIÉTAIRE — UTILISE TELLES QUELLES ===\n"
            f"Le propriétaire dit que ce sont de vraies questions qu'il entend des "
            f"clients. Utilise-les EXACTEMENT comme les {len(seeds)} premières "
            f"questions de ta sortie (ne reformule pas). Écris des réponses de "
            f"qualité pour chacune. Génère ensuite {remaining_after_seeds} paires "
            f"Q+R additionnelles pour compléter ton ensemble de {llm_output_count}.\n"
            f"{joined}\n=== FIN QUESTIONS PERSONNALISÉES ===\n"
        )

    # Total count instruction — what the LLM puts in its JSON array.
    faq_count_instruction_en = (
        f"\nOutput {llm_output_count} Q+A pairs in a single JSON array."
    )
    faq_count_instruction_fr = (
        f"\nProduis {llm_output_count} paires Q+R dans un seul tableau JSON."
    )
    paa_block_en = ""
    paa_block_fr = ""
    if paa_questions:
        joined = "\n- ".join(paa_questions[:8])
        paa_block_en = (
            "\nUse these real customer questions as inspiration (rewrite to fit "
            "this business; if one doesn't apply, write a relevant variant):\n- "
            + joined
        )
        paa_block_fr = (
            "\nUtilise ces vraies questions de clients comme inspiration (réécris pour "
            "cadrer avec l'entreprise; si une ne s'applique pas, écris une variante pertinente):\n- "
            + joined
        )

    # Hard format rule appended to every prose-content prompt to prevent
    # the LLM from emitting markdown headers, alternative versions, or
    # character-count commentary on top of the actual content.
    no_markdown_en = (
        "\n\nIMPORTANT: Output only the description text in plain prose. "
        "No markdown headers (# ##). No bold/italic markers. No 'Here is...' "
        "preamble. No 'Alternative version' sections. No character-count "
        "notes. No labels like 'Description:'. Just the prose itself."
    )
    no_markdown_fr = (
        "\n\nIMPORTANT : Retourne uniquement le texte de description en prose. "
        "Pas de titres markdown (# ##). Pas de gras/italique. Pas de préambule "
        "« Voici... ». Pas de sections « Version alternative ». Pas de notes "
        "sur le nombre de caractères. Pas d'étiquettes comme « Description : ». "
        "Juste la prose."
    )
    bio_format_en = (
        "\n\nIMPORTANT: Output ONLY the bio text — a single sentence or short "
        "phrase under 150 characters. No markdown. No headers. No quotation "
        "marks around the bio. No 'Bio:' label. No alternatives. No character-"
        "count notes. No commentary. Just the bio words."
    )
    bio_format_fr = (
        "\n\nIMPORTANT : Retourne UNIQUEMENT le texte de la biographie — une "
        "seule phrase ou courte expression de moins de 150 caractères. Pas "
        "de markdown. Pas de titres. Pas de guillemets. Pas d'étiquette « Bio : ». "
        "Pas d'alternatives. Pas de notes sur le nombre de caractères. Juste "
        "les mots de la biographie."
    )

    if language == "fr":
        return {
            "website_desc": (
                f"{base_context}\nÉcris une description d'entreprise de 300-400 mots optimisée pour les "
                "moteurs de recherche IA (ChatGPT, Perplexity, Google AI Overview). Sois précis, mentionne "
                "la ville et les principaux services. Ton professionnel à la troisième personne."
                + services_line_fr
                + no_markdown_fr
            ),
            "gbp_desc": (
                f"{base_context}\nÉcris une description Google Business Profile, MAXIMUM 700 caractères. "
                "Va droit au but, mentionne la ville et les services, orientée bénéfices client."
                + services_line_fr
                + no_markdown_fr
            ),
            "yelp_desc": (
                f"{base_context}\nÉcris une description style Yelp de 200-250 mots, ton concis, "
                "troisième personne, mentionne les services."
                + services_line_fr
                + no_markdown_fr
            ),
            "social_bio": (
                f"{base_context}\nÉcris une biographie de 150 caractères MAXIMUM pour Instagram/Facebook. "
                "Style punchy, mentionne la ville et le service principal."
                + bio_format_fr
            ),
            "faq": (
                f"{base_context}{faq_count_instruction_fr}\n"
                "Chaque réponse doit faire 40-60 mots, être factuelle et utile pour citation par les IA.\n"
                "Format: tableau JSON [{\"question\": \"...\", \"answer\": \"...\"}]. "
                "Retourne uniquement du JSON valide."
                + existing_block_fr
                + custom_seed_block_fr
                + paa_block_fr
                + faq_kb_block
            ),
        }

    return {
        "website_desc": (
            f"{base_context}\nWrite a 300-400 word business description optimized to appear in AI search "
            "engine answers (ChatGPT, Perplexity, Google AI Overview). Be specific, mention the city and "
            "key services. Write in third person, professional tone."
            + services_line_en
            + no_markdown_en
        ),
        "gbp_desc": (
            f"{base_context}\nWrite a Google Business Profile description, MAX 700 characters. "
            "Direct, benefit-focused, mention the city and main services."
            + services_line_en
            + no_markdown_en
        ),
        "yelp_desc": (
            f"{base_context}\nWrite a Yelp-style description, 200-250 words, concise tone, third person, "
            "mention services."
            + services_line_en
            + no_markdown_en
        ),
        "social_bio": (
            f"{base_context}\nWrite a 150-character MAX social bio for Instagram/Facebook. Punchy, "
            "include city and main service."
            + bio_format_en
        ),
        "faq": (
            f"{base_context}{faq_count_instruction_en}\n"
            "Each answer should be 40-60 words, factual, and useful for AI to cite verbatim.\n"
            "Format as JSON array: [{\"question\": \"...\", \"answer\": \"...\"}]. "
            "Return only valid JSON."
            + existing_block_en
            + custom_seed_block_en
            + paa_block_en
            + faq_kb_block
        ),
    }


def build_regenerate_prompts(
    business: dict, language: str, services: str, notes: str,
) -> dict[str, tuple[str, int, float]]:
    """Map regenerate keys -> (prompt, max_tokens, temperature) tuples.
    Notes are appended as 'User notes:' to whichever base prompt is used."""
    btype    = business["type"]
    name     = business["name"]
    city     = business["city"]
    province = business.get("province") or ""
    website  = business.get("website") or ""

    base_context = (
        f"Business name: {name}\n"
        f"Business type: {btype}\n"
        f"City: {city}{', ' + province if province else ''}\n"
        f"Services: {services}\n"
        f"Website: {website}\n"
    )

    # Re-use the same prompt builder that generate_content uses, with empty
    # paa_questions (we don't re-fetch PAA on per-item regenerate -- it's
    # already in the DB and the user's notes are the new signal).
    prompts = build_content_prompts(language, base_context, services, [])
    notes_block = f"\n\nUser notes for this regenerate: {notes.strip()}\n" if notes.strip() else ""

    out: dict[str, tuple[str, int, float]] = {
        "description.website": (prompts["website_desc"] + notes_block, 700, 0.7),
        "description.gbp":     (prompts["gbp_desc"]     + notes_block, 350, 0.7),
        "description.yelp":    (prompts["yelp_desc"]    + notes_block, 500, 0.7),
        "social_bio":          (prompts["social_bio"]   + notes_block, 120, 0.5),
    }
    return out

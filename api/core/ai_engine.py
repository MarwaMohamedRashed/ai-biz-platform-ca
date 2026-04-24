"""
AI Engine — Provider Abstraction Layer
======================================
NEVER call OpenAI or Gemini SDKs directly from product code.
Always use this module. This lets you swap providers with one config change.

Usage:
    from core.ai_engine import ai_engine
    response = await ai_engine.generate(prompt="...", context={...})

C#/.NET equivalent thinking:
    This is like an IEmailService interface with concrete implementations
    (SmtpEmailService, SendGridEmailService). Your product code depends on
    the interface, not the concrete class. Switch providers = swap one line.
"""

import os
import logging
from typing import Optional
from openai import AsyncOpenAI
import google.generativeai as genai
import anthropic

logger = logging.getLogger(__name__)

# ─── Provider config ──────────────────────────────────────────────────────────
# Set AI_PROVIDER=openai or AI_PROVIDER=gemini in your .env file
AI_PROVIDER = os.getenv("AI_PROVIDER", "claude")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-haiku-4-5-20251001")


class AIEngine:
    """
    Single interface for all AI calls across all three products.

    C#/.NET equivalent: a generic service registered in DI container
        services.AddSingleton<IAIEngine, AIEngine>();
    """

    def __init__(self):
        self.provider = AI_PROVIDER

        if self.provider == "openai":
            self._openai = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        elif self.provider == "gemini":
            genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
            self._gemini = genai.GenerativeModel(GEMINI_MODEL)
        elif self.provider == "claude":
            self._claude = anthropic.AsyncAnthropic(
                api_key=os.getenv("ANTHROPIC_API_KEY")
            )
        else:
            raise ValueError(f"Unknown AI_PROVIDER: {self.provider}. Use 'openai', 'gemini', or 'claude'.")

        logger.info(f"AI engine initialised — provider: {self.provider}")

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 500,
        temperature: float = 0.7,
    ) -> str:
        """
        Generate text from a prompt. Works the same regardless of provider.

        Args:
            prompt:        The user message / task description
            system_prompt: Role/context for the AI (e.g. "You are a helpful
                           assistant for a Canadian hair salon...")
            max_tokens:    Maximum response length
            temperature:   0.0 = deterministic, 1.0 = creative

        Returns:
            The generated text as a plain string
        """
        try:
            if self.provider == "openai":
                return await self._generate_openai(prompt, system_prompt, max_tokens, temperature)
            elif self.provider == "gemini":
                return await self._generate_gemini(prompt, system_prompt, max_tokens, temperature)
            elif self.provider == "claude":
                return await self._generate_claude(prompt, system_prompt, max_tokens, temperature)
        except Exception as e:
            logger.error(f"AI generation failed [{self.provider}]: {e}")
            raise

    # ─── OpenAI implementation ─────────────────────────────────────────────────
    async def _generate_openai(
        self, prompt: str, system_prompt: Optional[str], max_tokens: int, temperature: float
    ) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = await self._openai.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return response.choices[0].message.content.strip()

    # ─── Gemini implementation ─────────────────────────────────────────────────
    async def _generate_gemini(
        self, prompt: str, system_prompt: Optional[str], max_tokens: int, temperature: float
    ) -> str:
        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
        response = self._gemini.generate_content(
            full_prompt,
            generation_config=genai.GenerationConfig(
                max_output_tokens=max_tokens,
                temperature=temperature,
            ),
        )
        return response.text.strip()
    # ─── Claude implementation ─────────────────────────────────────────────────
    async def _generate_claude(
        self, prompt: str, system_prompt: Optional[str], max_tokens: int, temperature: float
    ) -> str:
        messages = [{"role": "user", "content": prompt}]
        response = await self._claude.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=max_tokens,
            system=system_prompt or "",
            messages=messages,
        )
        return response.content[0].text.strip()

# ─── Singleton instance (like a registered DI service) ───────────────────────
# Import this in your route handlers: from core.ai_engine import ai_engine
ai_engine = AIEngine()


# ─── Pre-built prompts for each product ──────────────────────────────────────
# Keep prompts here so they're easy to tune without touching product code.

REVIEW_SYSTEM_PROMPT = """You are a professional customer service specialist 
for a Canadian small business. Write warm, genuine, and professional responses 
to Google reviews. Always thank the reviewer by name if provided. Keep responses 
under 150 words. Never be defensive about negative reviews — acknowledge concerns 
and offer to resolve offline."""

BOOKING_SYSTEM_PROMPT = """You are a friendly booking assistant for a Canadian 
small business. Help customers book appointments via SMS. Be conversational and 
brief — this is a text message conversation. Confirm the service, date, time, 
and customer name before finalizing. Use Canadian spelling (e.g. colour, centre)."""

STARTUP_SYSTEM_PROMPT = """You are a knowledgeable business advisor specializing 
in Ontario small business regulations. Help aspiring entrepreneurs understand 
what they need to do to start their business legally. Be accurate, cite government 
sources, and always recommend consulting a lawyer or accountant for complex situations."""


async def generate_review_response(
    review_text: str,
    reviewer_name: str,
    rating: int,
    business_name: str,
    business_type: str,
    business_settings: dict = None,
    review_date: str = None,
) -> str:
    """Generate a response to a Google review using business settings."""

    settings = business_settings or {}
    tone        = settings.get('tone_preference', 'casual')
    language    = settings.get('response_language', 'match_reviewer')
    length      = settings.get('response_length', 'medium')
    cta_on      = settings.get('cta_enabled', True)
    cta_custom  = settings.get('cta_custom_text', '')
    delay_on    = settings.get('delay_acknowledgment', False)
    description = settings.get('business_description', '')

    # ── Tone instruction ──────────────────────────────────────────────────────
    tone_map = {
        'casual':       'Write in a warm, friendly, conversational tone.',
        'professional': 'Write in a formal, polished, professional tone.',
        'playful':      'Write in a fun, energetic tone with light humour where appropriate.',
    }
    tone_instruction = tone_map.get(tone, tone_map['casual'])

    # ── Length instruction ────────────────────────────────────────────────────
    length_map = {
        'short':  'Keep the response under 75 words.',
        'medium': 'Keep the response between 75 and 150 words.',
        'long':   'Write a thorough response of 150 to 250 words.',
    }
    length_instruction = length_map.get(length, length_map['medium'])

    # ── Language instruction ──────────────────────────────────────────────────
    language_map = {
        'match_reviewer': 'Detect the language of the review and respond in the same language.',
        'english':        'Always respond in English.',
        'french':         'Always respond in French.',
        'both':           'Respond in both English and French, English first.',
    }
    language_instruction = language_map.get(language, language_map['match_reviewer'])

    # ── Delay acknowledgment ──────────────────────────────────────────────────
    delay_instruction = ''
    if delay_on and review_date:
        from datetime import datetime, timezone
        try:
            reviewed_at = datetime.fromisoformat(review_date.replace('Z', '+00:00'))
            days_old = (datetime.now(timezone.utc) - reviewed_at).days
            if days_old > 3:
                delay_instruction = f'This review is {days_old} days old. Begin with a brief, sincere apology for the delayed response.'
        except Exception:
            pass

    # ── CTA instruction ───────────────────────────────────────────────────────
    cta_instruction = ''
    if cta_on:
        if cta_custom:
            cta_instruction = f'End with this call to action: "{cta_custom}"'
        elif rating >= 4:
            cta_instruction = 'End with a warm invitation to return and a subtle suggestion to share the experience with friends or family.'
        elif rating == 3:
            cta_instruction = 'End with a genuine invitation to return, expressing that you would love the chance to earn their full satisfaction.'
        else:
            cta_instruction = 'End with a direct and sincere invitation to contact the business to resolve their concerns.'

    # ── Build system prompt ───────────────────────────────────────────────────
    system_prompt = f"""You are a customer service specialist writing Google review responses 
on behalf of {business_name}, a {business_type} in Canada.

{f'About the business: {description}' if description else ''}

Rules:
- {tone_instruction}
- {length_instruction}
- {language_instruction}
- Always thank the reviewer by name if provided.
- Never be defensive. Acknowledge concerns with empathy.
- Never make specific legal or financial promises.
- Use Canadian spelling (e.g. colour, centre, apologise).
{f'- {delay_instruction}' if delay_instruction else ''}
{f'- {cta_instruction}' if cta_instruction else ''}"""

    # ── Build prompt ──────────────────────────────────────────────────────────
    sentiment = 'positive' if rating >= 4 else 'negative' if rating <= 2 else 'mixed'
    prompt = f"""Reviewer: {reviewer_name or 'a customer'}
Rating: {rating}/5 stars ({sentiment})
Review: {review_text}

Write a response on behalf of {business_name}."""

    return await ai_engine.generate(
        prompt=prompt,
        system_prompt=system_prompt,
        max_tokens=300,
        temperature=0.7,
    )

async def generate_booking_reply(
    customer_message: str,
    conversation_history: list[dict],
    business_name: str,
    available_slots: list[str],
) -> str:
    """Phase 2: Generate next message in a booking conversation."""
    history_text = "\n".join(
        [f"{m['role'].upper()}: {m['content']}" for m in conversation_history[-6:]]
    )
    slots_text = "\n".join(available_slots[:5]) if available_slots else "No slots available today"
    prompt = f"""
Business: {business_name}
Available slots: {slots_text}

Conversation so far:
{history_text}

Customer just said: {customer_message}

Reply to continue booking the appointment.
"""
    return await ai_engine.generate(
        prompt=prompt,
        system_prompt=BOOKING_SYSTEM_PROMPT,
        max_tokens=120,
        temperature=0.5,
    )

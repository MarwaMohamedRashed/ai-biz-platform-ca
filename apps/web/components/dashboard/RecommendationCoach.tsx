'use client'

import { useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import { useLocale } from 'next-intl'
import { chatWithCoach, type CoachMessage, type CoachRecommendationContext } from '@/lib/coach-api'

interface Props {
  recommendation: CoachRecommendationContext
  /**
   * Stable identifier — when the parent collapses + re-expands a different
   * recommendation we want a fresh conversation, not the old one.
   */
  recommendationKey: string
  /**
   * Subscription tier of the current user. Coach is a Pro-only feature;
   * Starter users see an upgrade CTA in place of the chat input.
   */
  currentTier?: 'starter' | 'pro'
}

/**
 * Inline AI execution coach panel. Lives inside an expanded recommendation
 * row. Owner types a question -> we call POST /recommendation-help with the
 * full conversation history -> render the reply.
 *
 * Non-streaming for v1 (simpler). The coach typically replies in 5-10 sec
 * for `gpt-4o-mini`. We show a "Coach is thinking…" indicator while waiting.
 */
export default function RecommendationCoach({ recommendation, recommendationKey, currentTier = 'starter' }: Props) {
  const locale = useLocale()
  const language: 'en' | 'fr' = locale === 'fr' ? 'fr' : 'en'

  // ─── Tier gate: starter users see an upgrade CTA, not the chat input ──
  // The "Get step-by-step help" button stays visible for everyone (so
  // Starter sees what Pro unlocks). Clicking it opens this panel which
  // shows the upgrade pitch instead of the input. Conversion-positive UX.
  if (currentTier !== 'pro') {
    return (
      <div className="mt-3 bg-white border border-indigo-100 rounded-xl overflow-hidden">
        <div className="px-3 py-2 bg-indigo-50 border-b border-indigo-100 flex items-center gap-2">
          <span className="text-base">🤝</span>
          <p className="text-xs font-semibold text-[#1e293b]">
            {language === 'fr' ? 'Coach IA — fonctionnalité Pro' : 'AI coach — a Pro feature'}
          </p>
        </div>
        <div className="p-4">
          <p className="text-xs text-slate-700 leading-relaxed mb-3">
            {language === 'fr'
              ? "Le coach IA vous guide pas à pas dans chaque recommandation, comme un consultant marketing. Posez n'importe quelle question — il connaît votre entreprise et la recommandation, et peut même rédiger le courriel à envoyer à votre administrateur web si la partie technique est trop complexe."
              : "The AI coach walks you step-by-step through each recommendation, like having a marketing consultant on call. Ask any question — it knows your business and the recommendation, and can even write the email to send your web admin when the technical part feels overwhelming."}
          </p>
          <p className="text-[11px] text-slate-500 mb-3">
            {language === 'fr'
              ? "Inclus dans le plan Pro à 49 $/mois. Le coach n'est pas inclus dans Starter."
              : 'Included with the Pro plan at $49/mo. Not included with Starter.'}
          </p>
          <Link
            href={`/${locale}/dashboard/plan`}
            className="inline-flex items-center gap-1 text-xs font-semibold text-white
                       bg-[#4f46e5] hover:bg-indigo-700 px-3 py-2 rounded-lg transition-colors"
          >
            {language === 'fr' ? 'Passer à Pro' : 'Upgrade to Pro'} →
          </Link>
        </div>
      </div>
    )
  }

  const [messages, setMessages] = useState<CoachMessage[]>([])
  const [draft, setDraft] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const scrollRef = useRef<HTMLDivElement>(null)

  // Reset when the recommendation changes (different rec = different convo)
  useEffect(() => {
    setMessages([])
    setDraft('')
    setError('')
  }, [recommendationKey])

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages, busy])

  async function send(suggestedMessage?: string) {
    const text = (suggestedMessage ?? draft).trim()
    if (!text || busy) return

    const newUserMsg: CoachMessage = { role: 'user', content: text }
    const next = [...messages, newUserMsg]
    setMessages(next)
    setDraft('')
    setBusy(true)
    setError('')

    try {
      const { reply } = await chatWithCoach(recommendation, messages, text, language)
      setMessages([...next, { role: 'assistant', content: reply }])
    } catch (e) {
      // Roll back the user message that was added so they can retry from the input
      setMessages(messages)
      setDraft(text)
      const msg = e instanceof Error ? e.message : 'Coach is unavailable.'
      // Tier-required hint (when we add gating, this will fire)
      if (msg.includes('402')) {
        setError(language === 'fr'
          ? 'Le coach IA est disponible avec le plan Pro.'
          : 'The AI coach is available on the Pro plan.')
      } else {
        setError(language === 'fr'
          ? "Le coach n'a pas pu répondre. Réessayez dans un instant."
          : 'Coach failed to reply. Try again in a moment.')
      }
    } finally {
      setBusy(false)
    }
  }

  const SUGGESTED: { en: string[]; fr: string[] } = {
    en: [
      'Walk me through this step by step',
      "I don't have what they're asking for",
      'Write the email I should send to my web admin',
    ],
    fr: [
      'Guide-moi étape par étape',
      "Je n'ai pas ce qu'ils demandent",
      'Rédige le courriel à envoyer à mon admin web',
    ],
  }
  const suggestions = SUGGESTED[language]

  return (
    <div className="mt-3 bg-white border border-indigo-100 rounded-xl overflow-hidden">
      <div className="px-3 py-2 bg-indigo-50 border-b border-indigo-100 flex items-center gap-2">
        <span className="text-base">🤝</span>
        <p className="text-xs font-semibold text-[#1e293b]">
          {language === 'fr' ? 'Coach IA — guide pas à pas' : 'AI coach — step-by-step help'}
        </p>
      </div>

      <div ref={scrollRef} className="max-h-80 overflow-y-auto p-3 flex flex-col gap-2">
        {messages.length === 0 && (
          <div className="flex flex-col gap-2">
            <p className="text-[11px] text-slate-500">
              {language === 'fr'
                ? "Coincé? Décris ce qui te bloque et je te guide étape par étape. Tu peux aussi cliquer une suggestion ci-dessous."
                : 'Stuck on a step? Tell me what\'s blocking you and I\'ll walk you through it. Or pick a suggestion below.'}
            </p>
            <div className="flex flex-wrap gap-1.5">
              {suggestions.map(s => (
                <button key={s} onClick={() => send(s)} disabled={busy}
                        className="text-[10px] font-semibold text-indigo-700 bg-indigo-50 border border-indigo-100
                                   px-2 py-1 rounded-full hover:bg-indigo-100 transition-colors disabled:opacity-50">
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[85%] rounded-xl px-3 py-2 text-xs leading-relaxed
                            ${m.role === 'user'
                              ? 'bg-[#4f46e5] text-white'
                              : 'bg-slate-50 border border-slate-100 text-slate-700'}`}>
              <p className="whitespace-pre-wrap">{m.content}</p>
            </div>
          </div>
        ))}

        {busy && (
          <div className="flex justify-start">
            <div className="bg-slate-50 border border-slate-100 rounded-xl px-3 py-2 text-xs text-slate-400 italic">
              {language === 'fr' ? 'Le coach réfléchit…' : 'Coach is thinking…'}
            </div>
          </div>
        )}

        {error && (
          <p className="text-[11px] text-red-600">{error}</p>
        )}
      </div>

      <div className="border-t border-slate-100 p-2 flex gap-1.5">
        <input
          type="text"
          value={draft}
          onChange={e => setDraft(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() } }}
          placeholder={language === 'fr' ? 'Pose une question…' : 'Ask a question…'}
          disabled={busy}
          className="flex-1 text-xs text-slate-700 border border-slate-200 rounded-lg px-3 py-1.5
                     focus:outline-none focus:border-[#4f46e5] disabled:bg-slate-50"
        />
        <button onClick={() => send()} disabled={busy || !draft.trim()}
                className="text-xs font-semibold text-white bg-[#4f46e5] hover:bg-indigo-700
                           px-3 py-1.5 rounded-lg disabled:opacity-50">
          {language === 'fr' ? 'Envoyer' : 'Send'}
        </button>
      </div>
    </div>
  )
}

'use client'

import React, { useState } from 'react'
import Link from 'next/link'
import { useTranslations } from 'next-intl'
import type { Recommendation } from './RecommendationsList'
import OwnReputationCard from './OwnReputationCard'

interface Breakdown {
  gbp: number
  reviews: number
  website: number
  local_search: number
  ai_citation: number
}

interface AiPerQueryResult {
  mentioned: boolean
  snippet?: string | null
  answer?: string
  query?: string
}

interface RawResults {
  perplexity?: {
    mentioned: boolean
    snippet?: string | null
    per_query?: AiPerQueryResult[]
  }
  chatgpt?: {
    mentioned: boolean
    snippet?: string | null
    per_query?: AiPerQueryResult[]
  }
  google?: {
    ai_overview?: { mentioned: boolean; snippet?: string | null }
    // local_pack carries rating/reviews when Google's local pack returns
    // that data — used as a fallback for the GBP/Reviews breakdown when
    // the Knowledge Graph card is empty (real production case 2026-05-17).
    local_pack?: {
      present: boolean
      position: number | null
      rating?: number | null
      reviews?: number | null
    }
    organic?: { present: boolean; position?: number | null }
    knowledge_graph?: {
      found: boolean
      title?: string | null
      rating?: number | null
      reviews_count?: number | null
      type?: string | null
      website?: string | null
      phone?: string | null
    }
    per_query?: Array<{
      query?: string
      ai_overview?: { mentioned: boolean; snippet?: string | null; text?: string }
    }>
  }
  website?: { reachable: boolean; has_local_business_schema: boolean; has_faq_schema: boolean }
  competitors?: Array<{ name?: string | null }>
}

interface Audit {
  score: number
  score_breakdown: Breakdown | null
  raw_results: RawResults | null
  created_at: string
}

interface Props {
  businessId: string | null
  initialAudit: Audit | null
  initialRecommendations: Recommendation[]
  prevBreakdown: Breakdown | null
  locale: string
  currentTier?: 'starter' | 'pro'
}

export default function AeoAuditCard({ businessId, initialAudit, initialRecommendations, prevBreakdown, locale, currentTier = 'starter' }: Props) {
  const t = useTranslations('dashboard.aeo')

  const PILLARS: { key: keyof Breakdown; label: string; max: number }[] = [
    { key: 'gbp',          label: t('pillars.gbp'),         max: 25 },
    { key: 'reviews',      label: t('pillars.reviews'),     max: 22 },
    { key: 'website',      label: t('pillars.website'),     max: 20 },
    { key: 'local_search', label: t('pillars.localSearch'), max: 15 },
    { key: 'ai_citation',  label: t('pillars.aiCitation'),  max: 18 },
  ]

  function getPillarHint(key: keyof Breakdown, raw: RawResults | null): string | null {
    if (!raw) return null
    const kg  = raw.google?.knowledge_graph
    const ws  = raw.website
    const lp  = raw.google?.local_pack
    const mentioned = [
      raw.chatgpt?.mentioned,
      raw.perplexity?.mentioned,
      raw.google?.ai_overview?.mentioned,
    ].filter(v => v === true).length

    // Google renders findings inconsistently: sometimes a Knowledge Graph
    // card, sometimes only a Local Pack entry, sometimes both. The score
    // already considers both; the hints/breakdown must too. We treat a
    // present LP as evidence that the business IS found on Google even
    // when KG is empty, and use the LP rating/reviews_count as fallback.
    const businessFoundOnGoogle = (kg?.found === true) || (lp?.present === true)
    const effectiveReviewCount = kg?.reviews_count ?? lp?.reviews ?? null
    const effectiveRating      = kg?.rating       ?? lp?.rating  ?? null

    switch (key) {
      case 'gbp':
        if (!businessFoundOnGoogle)   return t('pillarHints.gbpNotFound')
        // Phone/website are only available on KG. If we only have LP data,
        // we can't tell if the listing is complete — show the "good" hint
        // rather than misleadingly claiming it's incomplete.
        if (kg?.found && (!kg.phone || !kg.website)) return t('pillarHints.gbpIncomplete')
        return t('pillarHints.gbpGood')

      case 'reviews':
        if (effectiveReviewCount != null && effectiveReviewCount < 30)
          return t('pillarHints.reviewsLow', { count: effectiveReviewCount })
        if (effectiveRating != null && effectiveRating < 4.0)
          return t('pillarHints.reviewsRating', { rating: effectiveRating.toFixed(1) })
        if (effectiveReviewCount != null) return t('pillarHints.reviewsGood')
        return null

      case 'website':
        if (ws?.reachable === false)          return t('pillarHints.websiteUnreachable')
        if (!ws?.has_local_business_schema)   return t('pillarHints.websiteNoSchema')
        if (!ws?.has_faq_schema)              return t('pillarHints.websiteNoFaq')
        return t('pillarHints.websiteGood')

      case 'local_search':
        if (!lp?.present)                          return t('pillarHints.localNotInPack')
        if (raw.google?.organic?.present === false) return t('pillarHints.localNotOrganic')
        return t('pillarHints.localGood')

      case 'ai_citation':
        if (mentioned === 0) return t('pillarHints.aiNone')
        if (mentioned === 3) return t('pillarHints.aiAll')
        return t('pillarHints.aiSome', { count: mentioned })

      default: return null
    }
  }

  // Display-only card now — the "Run audit / Re-run audit" action moved up
  // to the dashboard page header (RerunAuditButton.tsx) so it's reachable
  // without scrolling. After a fresh audit lands, the page's Server
  // Components re-render via router.refresh() and pass fresh props here.
  // The parent passes a `key` (latest audit's created_at) so this Client
  // Component remounts with the new data instead of clinging to stale state.
  const audit = initialAudit
  const recommendations = initialRecommendations
  const prevBreakdownState = prevBreakdown

  const scoreColor = !audit ? 'text-slate-300'
    : audit.score >= 70 ? 'text-green-600'
    : audit.score >= 40 ? 'text-amber-500'
    : 'text-red-500'

  // Tier label rendered under the big score. Plain-language interpretation
  // so the owner knows whether "55/100" is good or bad without clicking.
  function scoreTierKey(score: number): 'excellent' | 'good' | 'fair' | 'needsWork' {
    if (score >= 80) return 'excellent'
    if (score >= 60) return 'good'
    if (score >= 40) return 'fair'
    return 'needsWork'
  }

  // Per-pillar signals for the inline "What we checked" expand. Same raw
  // data as the legacy "Why this score?" drawer — surfaced inline so owners
  // don't have to click through to understand a score.
  function getPillarSignals(
    key: keyof Breakdown,
    raw: RawResults | null,
  ): { label: string; value: string | boolean | number | null | undefined }[] {
    if (!raw) return []
    const kg = raw.google?.knowledge_graph
    const ws = raw.website
    const lp = raw.google?.local_pack

    // Knowledge Graph and Local Pack are alternate Google surfaces for the
    // same business. Fall back to LP when KG is empty so we don't show
    // "Found in Google's business listings: No" for a business that's
    // clearly on Google (it's just rendered as LP-only this time). See
    // also getPillarHint above for the same reasoning.
    const foundOnGoogle = (kg?.found === true) || (lp?.present === true)
    const effRating      = kg?.rating       ?? lp?.rating  ?? null
    const effReviewCount = kg?.reviews_count ?? lp?.reviews ?? null

    switch (key) {
      case 'gbp':
        return [
          { label: t('drawer.gbpFound'),    value: foundOnGoogle },
          { label: t('drawer.gbpTitle'),    value: kg?.title ?? null },
          { label: t('drawer.gbpCategory'), value: kg?.type ?? null },
          { label: t('drawer.rating'),      value: effRating != null ? `${effRating}★` : null },
          { label: t('drawer.reviewCount'), value: effReviewCount ?? null },
          { label: t('drawer.gbpWebsite'),  value: kg?.website ?? null },
          { label: t('drawer.gbpPhone'),    value: kg?.phone ?? null },
        ]
      case 'reviews':
        return [
          { label: t('drawer.rating'),      value: effRating != null ? `${effRating}★` : null },
          { label: t('drawer.reviewCount'), value: effReviewCount ?? null },
        ]
      case 'website':
        return [
          { label: t('drawer.websiteReachable'),    value: ws?.reachable },
          { label: t('drawer.localBusinessSchema'), value: ws?.has_local_business_schema },
          { label: t('drawer.faqSchema'),           value: ws?.has_faq_schema },
        ]
      case 'local_search':
        return [
          { label: t('drawer.inLocalPack'),  value: lp?.present },
          { label: t('drawer.localPackPos'), value: lp?.position != null ? `#${lp.position}` : t('drawer.notInPack') },
          { label: t('drawer.inOrganic'),    value: raw.google?.organic?.present },
        ]
      case 'ai_citation':
        return [
          { label: t('drawer.mentionedChatgpt'),    value: raw.chatgpt?.mentioned },
          { label: t('drawer.mentionedPerplexity'), value: raw.perplexity?.mentioned },
          { label: t('drawer.mentionedGoogleAI'),   value: raw.google?.ai_overview?.mentioned },
        ]
      default:
        return []
    }
  }

  if (!businessId) {
    return (
      <div className="bg-white rounded-2xl border-l-[3px] border-l-[#4f46e5] shadow-sm border border-slate-100 p-4">
        <span className="text-[10px] font-bold text-[#4f46e5] uppercase tracking-wider">{t('label')}</span>
        <p className="text-sm font-semibold text-[#1e293b] mt-2 mb-1">{t('noBusinessTitle')}</p>
        <p className="text-xs text-slate-500 mb-3">{t('noBusinessDesc')}</p>
        <Link href={`/${locale}/dashboard/settings`}
          className="text-xs font-semibold bg-[#4f46e5] text-white px-3 py-1.5 rounded-lg hover:bg-indigo-700 transition-colors">
          {t('completeProfile')}
        </Link>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="bg-white rounded-2xl border-l-[3px] border-l-[#4f46e5] shadow-sm border border-slate-100 p-5">
        {audit && (
          <div className="mb-4">
            <div className="flex items-baseline gap-2">
              <p className={`text-4xl font-extrabold ${scoreColor}`}>
                {audit.score}<span className="text-base font-semibold text-slate-400">/100</span>
              </p>
              <Link
                href={`/${locale}/methodology`}
                title={t('howCalculated')}
                aria-label={t('howCalculated')}
                className="inline-flex items-center justify-center w-5 h-5 rounded-full
                           text-slate-400 hover:text-[#4f46e5] hover:bg-indigo-50
                           transition-colors">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                  <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2"/>
                  <line x1="12" y1="10" x2="12" y2="16" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                  <circle cx="12" cy="7" r="1" fill="currentColor"/>
                </svg>
              </Link>
            </div>
            <p className={`text-sm font-semibold mt-1 ${scoreColor}`}>
              {t(`scoreTier.${scoreTierKey(audit.score)}`)}
            </p>
            <p className="text-[11px] text-slate-400 mt-1">
              {new Date(audit.created_at).toLocaleDateString(
                locale === 'fr' ? 'fr-CA' : 'en-CA',
                { month: 'long', day: 'numeric', year: 'numeric' },
              )}
            </p>
          </div>
        )}

        {!audit && (
          <p className="text-sm font-semibold text-[#1e293b] mb-3">
            {t('findOutVisible')}
          </p>
        )}

        {audit && audit.score_breakdown && (
          <div className="flex flex-col gap-3 mb-4">
            {PILLARS.map(p => {
              const delta = prevBreakdownState
                ? audit.score_breakdown![p.key] - prevBreakdownState[p.key]
                : null
              // Pillar-specific CTAs surfaced inside the "What we checked"
              // expand. For GBP we always link to business.google.com so
              // owners can verify their profile themselves — especially
              // important when the audit took the LP-only path and we
              // can't see all KG fields (see project_gbp_trust_fix memory).
              const cta = p.key === 'gbp'
                ? { label: t('drawer.viewYourGbp'), href: 'https://business.google.com' }
                : null
              return (
                <PillarRow
                  key={p.key}
                  label={p.label}
                  points={audit.score_breakdown![p.key]}
                  max={p.max}
                  delta={delta}
                  hint={getPillarHint(p.key, audit.raw_results)}
                  signals={getPillarSignals(p.key, audit.raw_results)}
                  cta={cta}
                />
              )
            })}
          </div>
        )}

        {/* The "Re-run audit" button used to live here. It moved to the
            dashboard page header (RerunAuditButton.tsx) so the most
            important action on the page is reachable without scrolling. */}
      </div>

      {audit && <AISnapshotSection rawResults={audit.raw_results} />}

      {audit && <OwnReputationCard />}
    </div>
  )
}

function AISnapshotSection({ rawResults }: { rawResults: RawResults | null }) {
  const t = useTranslations('dashboard.aeo')
  if (!rawResults) return null

  // Competitor names for highlighting — sourced from the audit's local pack results
  const competitorNames: string[] = (rawResults.competitors ?? [])
    .map(c => c.name)
    .filter((n): n is string => Boolean(n && n.trim().length > 2))

  /** Truncate to ~400 chars at a word boundary. */
  function truncate(text: string): string {
    if (text.length <= 400) return text
    const cut = text.slice(0, 400)
    const lastSpace = cut.lastIndexOf(' ')
    return (lastSpace > 300 ? cut.slice(0, lastSpace) : cut) + '…'
  }

  /**
   * When not mentioned: use the first answer so we can show which competitors
   * appear instead. When mentioned: snippet is the sentence where the name appears.
   */
  function getSnippet(
    engine: { mentioned: boolean; snippet?: string | null; per_query?: AiPerQueryResult[] } | null | undefined
  ): string | null {
    if (!engine) return null
    if (engine.snippet) return truncate(engine.snippet)
    const answer = engine.per_query?.find(q => q.answer)?.answer
    return answer ? truncate(answer) : null
  }

  function getGoogleSnippet(): string | null {
    const ao = rawResults?.google?.ai_overview
    if (ao?.snippet) return truncate(ao.snippet)
    for (const q of rawResults?.google?.per_query ?? []) {
      const text = q.ai_overview?.text
      if (text) return truncate(text)
    }
    return null
  }

  /** Count how many known competitors appear in the text (match on first 2 words). */
  function countCompetitorsIn(text: string | null): number {
    if (!text || !competitorNames.length) return 0
    const lower = text.toLowerCase()
    return competitorNames.filter(name => {
      const short = name.toLowerCase().split(/\s+/).slice(0, 2).join(' ')
      return short.length >= 3 && lower.includes(short)
    }).length
  }

  /**
   * Split text around competitor name matches and return highlighted nodes.
   * Uses split() with a capturing group — odd indices are the captured matches.
   */
  function highlight(text: string): React.ReactNode[] {
    if (!competitorNames.length) return [text]
    const escaped = competitorNames
      .map(n => n.split(/\s+/).slice(0, 2).join('\\s+'))
      .map(s => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
    const pattern = new RegExp(`(${escaped.join('|')})`, 'gi')
    return text.split(pattern).map((part, i) =>
      i % 2 === 1
        ? <mark key={i} className="bg-orange-100 text-orange-800 not-italic font-semibold rounded px-0.5">{part}</mark>
        : part
    )
  }

  const engines = [
    {
      key: 'chatgpt',
      name: 'ChatGPT',
      mentioned: rawResults.chatgpt?.mentioned,
      snippet: getSnippet(rawResults.chatgpt),
      query: rawResults.chatgpt?.per_query?.[0]?.query ?? null,
    },
    {
      key: 'perplexity',
      name: 'Perplexity',
      mentioned: rawResults.perplexity?.mentioned,
      snippet: getSnippet(rawResults.perplexity),
      query: rawResults.perplexity?.per_query?.[0]?.query ?? null,
    },
    {
      key: 'google',
      name: 'Google AI Overview',
      mentioned: rawResults.google?.ai_overview?.mentioned,
      snippet: getGoogleSnippet(),
      query: rawResults.google?.per_query?.[0]?.query ?? null,
    },
  ]

  if (!engines.some(e => e.snippet !== null || e.mentioned !== undefined)) return null

  return (
    <div className="bg-white rounded-2xl shadow-sm border border-slate-100 p-5">
      <span className="text-[11px] font-bold text-[#4f46e5] uppercase tracking-wider">
        {t('aiSnapshot.label')}
      </span>
      <p className="text-xs text-slate-500 mt-0.5 mb-4">{t('aiSnapshot.subtitle')}</p>
      <div className="flex flex-col gap-3">
        {engines.map(engine => {
          const compCount = engine.mentioned === false ? countCompetitorsIn(engine.snippet) : 0
          const isIn = engine.mentioned === true
          const isOut = engine.mentioned === false
          return (
            <div
              key={engine.key}
              className={`rounded-xl p-4 border ${
                isIn ? 'bg-green-50 border-green-100' : 'bg-slate-50 border-slate-100'
              }`}
            >
              {/* Engine name + status badge */}
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-extrabold text-[#1e293b]">{engine.name}</span>
                {engine.mentioned !== undefined && (
                  <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${
                    isIn ? 'bg-green-100 text-green-700' : 'bg-slate-200 text-slate-500'
                  }`}>
                    {isIn ? t('aiSnapshot.youAppear') : t('aiSnapshot.notMentioned')}
                  </span>
                )}
              </div>

              {/* Query context */}
              {engine.query && (
                <p className="text-xs text-slate-400 mb-2">
                  {t('aiSnapshot.queryLabel')}: <span className="italic">&ldquo;{engine.query}&rdquo;</span>
                </p>
              )}

              {/* Snippet */}
              {engine.snippet ? (
                <p className="text-sm text-slate-600 italic leading-relaxed mb-2">
                  &ldquo;{highlight(engine.snippet)}&rdquo;
                </p>
              ) : (
                <p className="text-sm text-slate-400 mb-2">{t('aiSnapshot.noAnswer')}</p>
              )}

              {/* Plain-language verdict for not-mentioned engines */}
              {isOut && compCount > 0 && (
                <p className="text-xs font-semibold text-orange-600">
                  {compCount === 1
                    ? t('aiSnapshot.competitorSingular')
                    : t('aiSnapshot.competitorPlural', { count: compCount })}
                </p>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

function PillarRow({
  label, points, max, delta, hint, signals, cta,
}: {
  label: string
  points: number
  max: number
  delta: number | null
  hint?: string | null
  signals?: { label: string; value: string | boolean | number | null | undefined }[]
  /** Optional pillar-specific call-to-action shown inside the expanded
   *  "What we checked" panel. Used by the GBP pillar today to deep-link
   *  to business.google.com so owners can verify their profile. */
  cta?: { label: string; href: string } | null
}) {
  const t = useTranslations('dashboard.aeo')
  const [expanded, setExpanded] = useState(false)
  const pct = max === 0 ? 0 : (points / max) * 100
  const color = pct >= 75 ? 'bg-green-500' : pct >= 40 ? 'bg-amber-400' : 'bg-red-300'
  const deltaLabel = delta === null || delta === 0 ? null : delta > 0 ? `+${delta}` : `${delta}`
  const deltaColor = delta && delta > 0 ? 'text-green-600' : 'text-red-500'
  const hasSignals = (signals?.length ?? 0) > 0
  return (
    <div className="flex flex-col">
      <div className="flex items-center gap-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between mb-1">
            <p className="text-[13px] font-semibold text-[#1e293b] truncate">{label}</p>
            <div className="flex items-center gap-1.5 flex-shrink-0 ml-2">
              {deltaLabel && (
                <span className={`text-[10px] font-bold ${deltaColor}`}>{deltaLabel}</span>
              )}
              <p className="text-xs text-slate-500">{points}/{max}</p>
            </div>
          </div>
          <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
            <div className={`h-full ${color} rounded-full transition-all`} style={{ width: `${pct}%` }} />
          </div>
          {hint && (
            <p className="text-xs mt-1.5 leading-snug text-slate-600">{hint}</p>
          )}
          {hasSignals && (
            <button
              type="button"
              onClick={() => setExpanded(e => !e)}
              aria-expanded={expanded}
              className="text-xs font-medium text-[#4f46e5] hover:underline mt-1.5 inline-flex items-center gap-1 transition-colors">
              <span aria-hidden="true">{expanded ? '▴' : '▾'}</span>
              {expanded ? t('hideDetails') : t('whatWeChecked')}
            </button>
          )}
        </div>
      </div>
      {hasSignals && expanded && (
        <div className="mt-2 ml-1 pl-3 border-l-2 border-slate-100">
          {signals!.map((s, i) => (
            <Signal key={i} label={s.label} value={s.value} />
          ))}
          {cta && (
            <a
              href={cta.href}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-2 inline-flex items-center gap-1 text-xs font-semibold text-[#4f46e5] hover:underline">
              {cta.label}
              <span aria-hidden="true">→</span>
            </a>
          )}
        </div>
      )}
    </div>
  )
}

function Signal({ label, value }: { label: string; value: string | boolean | number | null | undefined }) {
  const displayValue = value === true ? '✅ Yes'
    : value === false ? '❌ No'
    : value == null ? '—'
    : String(value)
  const isPositive = value === true
  const isNegative = value === false
  return (
    <div className="flex items-start justify-between gap-2 py-1.5 border-b border-slate-50 last:border-0">
      <p className="text-xs text-slate-600">{label}</p>
      <p className={`text-xs font-semibold flex-shrink-0 ${isPositive ? 'text-green-600' : isNegative ? 'text-red-500' : 'text-slate-700'}`}>
        {displayValue}
      </p>
    </div>
  )
}


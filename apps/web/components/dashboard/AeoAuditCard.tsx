'use client'

import React, { useState } from 'react'
import { createClient } from '@/lib/supabase'
import Link from 'next/link'
import { useTranslations } from 'next-intl'
import RecommendationsList, { Recommendation } from './RecommendationsList'
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
    local_pack?: { present: boolean; position: number | null }
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

    switch (key) {
      case 'gbp':
        if (!kg?.found)            return t('pillarHints.gbpNotFound')
        if (!kg.phone || !kg.website) return t('pillarHints.gbpIncomplete')
        return t('pillarHints.gbpGood')

      case 'reviews':
        if (kg?.reviews_count != null && kg.reviews_count < 30)
          return t('pillarHints.reviewsLow', { count: kg.reviews_count })
        if (kg?.rating != null && kg.rating < 4.0)
          return t('pillarHints.reviewsRating', { rating: kg.rating.toFixed(1) })
        if (kg?.reviews_count != null) return t('pillarHints.reviewsGood')
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

  const [audit, setAudit] = useState<Audit | null>(initialAudit)
  const [recommendations, setRecommendations] = useState<Recommendation[]>(initialRecommendations)
  // After a fresh audit, prev becomes the initial audit's breakdown
  const [prevBreakdownState] = useState<Breakdown | null>(prevBreakdown)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [drawerOpen, setDrawerOpen] = useState(false)

  async function runAudit() {
    if (!businessId) return
    setLoading(true)
    setError('')
    try {
      const { data: { session } } = await createClient().auth.getSession()
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/v1/aeo/audit`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${session?.access_token}`,
        },
        body: JSON.stringify({ business_id: businessId, locale }),
      })
      if (res.status === 402) {
        setError('upgrade_required')
        return
      }
      if (!res.ok) throw new Error('Audit failed')
      const data = await res.json()
      setAudit({
        score: data.score,
        score_breakdown: data.breakdown,
        raw_results: data.raw_results ?? null,
        created_at: new Date().toISOString(),
      })
      setRecommendations(data.recommendations || [])
    } catch {
      setError(t('auditFailed'))
    } finally {
      setLoading(false)
    }
  }

  const scoreColor = !audit ? 'text-slate-300'
    : audit.score >= 70 ? 'text-green-600'
    : audit.score >= 40 ? 'text-amber-500'
    : 'text-red-500'

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
      <div className="bg-white rounded-2xl border-l-[3px] border-l-[#4f46e5] shadow-sm border border-slate-100 p-4">
        <div className="flex items-start justify-between mb-2">
          <span className="text-[10px] font-bold text-[#4f46e5] uppercase tracking-wider">{t('label')}</span>
          {audit && (
            <span className="text-[10px] text-slate-400">{new Date(audit.created_at).toLocaleDateString('en-CA')}</span>
          )}
        </div>

        {audit && (
          <div className="mb-3">
            <p className={`text-4xl font-extrabold ${scoreColor}`}>
              {audit.score}<span className="text-base font-semibold text-slate-400">/100</span>
            </p>
            <p className="text-xs text-slate-500 mt-0.5">{t('scoreLabel')}</p>
          </div>
        )}

        {!audit && !loading && (
          <p className="text-sm font-semibold text-[#1e293b] mb-3">
            {t('findOutVisible')}
          </p>
        )}

        {audit && audit.score_breakdown && (
          <div className="flex flex-col gap-2 mb-3">
            {PILLARS.map(p => {
              const delta = prevBreakdownState
                ? audit.score_breakdown![p.key] - prevBreakdownState[p.key]
                : null
              return (
                <PillarRow
                  key={p.key}
                  label={p.label}
                  points={audit.score_breakdown![p.key]}
                  max={p.max}
                  delta={delta}
                  hint={getPillarHint(p.key, audit.raw_results)}
                />
              )
            })}
          </div>
        )}

        {error === 'upgrade_required' ? (
          <div className="mb-3 p-3 bg-amber-50 border border-amber-100 rounded-xl">
            <p className="text-xs text-amber-700 font-semibold mb-1">{t('upgradeTitle')}</p>
            <p className="text-[11px] text-amber-600 mb-2">{t('upgradeBody')}</p>
            <a href={`/${locale}/dashboard/plan`}
              className="text-xs font-semibold text-[#4f46e5] hover:underline">
              {t('upgradeCta')}
            </a>
          </div>
        ) : error ? (
          <p className="text-xs text-red-500 mb-2">{error}</p>
        ) : null}

        <div className="flex items-center gap-2 flex-wrap">
          <button
            onClick={runAudit}
            disabled={loading}
            className="text-xs font-semibold bg-[#4f46e5] text-white px-3 py-1.5 rounded-lg hover:bg-indigo-700 transition-colors disabled:opacity-50">
            {loading ? t('running') : audit ? t('rerunAudit') : t('runAudit')}
          </button>
          {audit && (
            <button
              onClick={() => setDrawerOpen(true)}
              className="text-xs font-semibold text-[#4f46e5] hover:underline">
              {t('whyThisScore')}
            </button>
          )}
        </div>

        <div className="flex items-center gap-3 mt-3 border-t border-slate-50 pt-2">
          <Link
            href={`/${locale}/methodology`}
            className="text-[10px] text-slate-400 hover:text-[#4f46e5] hover:underline transition-colors">
            {t('howCalculated')}
          </Link>
        </div>
      </div>

      {audit && <AISnapshotSection rawResults={audit.raw_results} />}

      {audit && <OwnReputationCard />}

      {audit && drawerOpen && (
        <RawDataDrawer
          rawResults={audit.raw_results}
          breakdown={audit.score_breakdown}
          onClose={() => setDrawerOpen(false)}
        />
      )}
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

function PillarRow({ label, points, max, delta, hint }: { label: string; points: number; max: number; delta: number | null; hint?: string | null }) {
  const pct = max === 0 ? 0 : (points / max) * 100
  const color = pct >= 75 ? 'bg-green-500' : pct >= 40 ? 'bg-amber-400' : 'bg-red-300'
  const hintColor = pct >= 75 ? 'text-green-600' : pct >= 40 ? 'text-amber-600' : 'text-red-500'
  const deltaLabel = delta === null || delta === 0 ? null : delta > 0 ? `+${delta}` : `${delta}`
  const deltaColor = delta && delta > 0 ? 'text-green-600' : 'text-red-500'
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between mb-0.5">
          <p className="text-[11px] font-semibold text-[#1e293b] truncate">{label}</p>
          <div className="flex items-center gap-1.5 flex-shrink-0 ml-2">
            {deltaLabel && (
              <span className={`text-[9px] font-bold ${deltaColor}`}>{deltaLabel}</span>
            )}
            <p className="text-[10px] text-slate-500">{points}/{max}</p>
          </div>
        </div>
        <div className="h-1 bg-slate-100 rounded-full overflow-hidden">
          <div className={`h-full ${color} rounded-full transition-all`} style={{ width: `${pct}%` }} />
        </div>
        {hint && (
          <p className={`text-[10px] mt-1 leading-snug ${hintColor}`}>{hint}</p>
        )}
      </div>
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
      <p className="text-[11px] text-slate-600">{label}</p>
      <p className={`text-[11px] font-semibold flex-shrink-0 ${isPositive ? 'text-green-600' : isNegative ? 'text-red-500' : 'text-slate-700'}`}>
        {displayValue}
      </p>
    </div>
  )
}

function DrawerSection({ title, pts, max, children }: { title: string; pts: number; max: number; children: React.ReactNode }) {
  const pct = max === 0 ? 0 : (pts / max) * 100
  const color = pct >= 75 ? 'text-green-600' : pct >= 40 ? 'text-amber-500' : 'text-red-500'
  return (
    <div className="mb-5">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-xs font-extrabold text-[#1e293b]">{title}</h3>
        <span className={`text-xs font-bold ${color}`}>{pts}/{max}</span>
      </div>
      <div className="bg-slate-50 rounded-xl px-3 py-1">
        {children}
      </div>
    </div>
  )
}

function RawDataDrawer({
  rawResults,
  breakdown,
  onClose,
}: {
  rawResults: RawResults | null
  breakdown: Breakdown | null
  onClose: () => void
}) {
  const t = useTranslations('dashboard.aeo')
  const kg = rawResults?.google?.knowledge_graph
  const lp = rawResults?.google?.local_pack
  const ws = rawResults?.website
  const perplexity = rawResults?.perplexity
  const chatgpt    = rawResults?.chatgpt
  const aiOverview = rawResults?.google?.ai_overview?.snippet

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/30 z-40"
        onClick={onClose}
        aria-hidden="true"
      />
      {/* Drawer */}
      <div className="fixed inset-y-0 right-0 w-full max-w-sm bg-white z-50 shadow-2xl flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100">
          <div>
            <h2 className="text-sm font-extrabold text-[#1e293b]">{t('drawer.title')}</h2>
            <p className="text-[10px] text-slate-500">{t('drawer.subtitle')}</p>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600 text-lg leading-none"
            aria-label="Close">
            ✕
          </button>
        </div>

        {/* Scrollable body */}
        <div className="flex-1 overflow-y-auto px-5 py-4">
          {!rawResults ? (
            <p className="text-xs text-slate-500">{t('drawer.noData')}</p>
          ) : (
            <>
              <DrawerSection title={t('pillars.gbp')} pts={breakdown?.gbp ?? 0} max={25}>
                <Signal label={t('drawer.gbpFound')}    value={kg?.found} />
                <Signal label={t('drawer.gbpTitle')}    value={kg?.title} />
                <Signal label={t('drawer.gbpCategory')} value={kg?.type} />
                <Signal label={t('drawer.rating')}      value={kg?.rating != null ? `${kg.rating}★` : null} />
                <Signal label={t('drawer.reviewCount')} value={kg?.reviews_count} />
                <Signal label={t('drawer.gbpWebsite')}  value={kg?.website != null ? kg.website : null} />
                <Signal label={t('drawer.gbpPhone')}    value={kg?.phone != null ? kg.phone : null} />
              </DrawerSection>

              <DrawerSection title={t('pillars.reviews')} pts={breakdown?.reviews ?? 0} max={22}>
                <Signal label={t('drawer.rating')}       value={kg?.rating != null ? `${kg.rating}★` : null} />
                <Signal label={t('drawer.reviewCount')}  value={kg?.reviews_count} />
              </DrawerSection>

              <DrawerSection title={t('pillars.website')} pts={breakdown?.website ?? 0} max={20}>
                <Signal label={t('drawer.websiteReachable')}      value={ws?.reachable} />
                <Signal label={t('drawer.localBusinessSchema')}   value={ws?.has_local_business_schema} />
                <Signal label={t('drawer.faqSchema')}             value={ws?.has_faq_schema} />
              </DrawerSection>

              <DrawerSection title={t('pillars.localSearch')} pts={breakdown?.local_search ?? 0} max={15}>
                <Signal label={t('drawer.inLocalPack')}  value={lp?.present} />
                <Signal label={t('drawer.localPackPos')} value={lp?.position != null ? `#${lp.position}` : t('drawer.notInPack')} />
                <Signal label={t('drawer.inOrganic')}    value={rawResults?.google?.organic?.present} />
              </DrawerSection>

              <DrawerSection title={t('pillars.aiCitation')} pts={breakdown?.ai_citation ?? 0} max={18}>
                <Signal label={t('drawer.mentionedChatgpt')} value={chatgpt?.mentioned} />
                {chatgpt?.snippet && (
                  <p className="text-[10px] text-slate-500 italic mt-1 mb-2 leading-relaxed">
                    &quot;{chatgpt.snippet.slice(0, 200)}{chatgpt.snippet.length > 200 ? '…' : ''}&quot;
                  </p>
                )}
                {chatgpt !== undefined && !chatgpt?.mentioned && (
                  <p className="text-[10px] text-slate-400 mb-2">
                    {t('drawer.chatgptNote')}
                  </p>
                )}
                <Signal label={t('drawer.mentionedPerplexity')} value={perplexity?.mentioned} />
                {perplexity?.snippet && (
                  <p className="text-[10px] text-slate-500 italic mt-1 mb-2 leading-relaxed">
                    &quot;{perplexity.snippet.slice(0, 200)}{perplexity.snippet.length > 200 ? '…' : ''}&quot;
                  </p>
                )}
                <Signal label={t('drawer.mentionedGoogleAI')} value={rawResults?.google?.ai_overview?.mentioned} />
                {aiOverview && (
                  <p className="text-[10px] text-slate-500 italic mt-1 leading-relaxed">
                    &quot;{aiOverview.slice(0, 200)}{aiOverview.length > 200 ? '…' : ''}&quot;
                  </p>
                )}
              </DrawerSection>
            </>
          )}
        </div>
      </div>
    </>
  )
}

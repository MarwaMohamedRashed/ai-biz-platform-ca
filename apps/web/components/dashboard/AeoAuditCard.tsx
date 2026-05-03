'use client'

import React, { useState } from 'react'
import { createClient } from '@/lib/supabase'
import Link from 'next/link'
import RecommendationsList, { Recommendation } from './RecommendationsList'

interface Breakdown {
  gbp: number
  reviews: number
  website: number
  local_search: number
  ai_citation: number
}

interface RawResults {
  perplexity?: { mentioned: boolean; snippet?: string | null }
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
  }
  website?: { reachable: boolean; has_local_business_schema: boolean; has_faq_schema: boolean }
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
}

const PILLARS: { key: keyof Breakdown; label: string; max: number }[] = [
  { key: 'gbp',          label: 'Google Business Profile', max: 25 },
  { key: 'reviews',      label: 'Reviews & Reputation',    max: 22 },
  { key: 'website',      label: 'Website & Schema',        max: 20 },
  { key: 'local_search', label: 'Local Search Presence',   max: 15 },
  { key: 'ai_citation',  label: 'AI Citations',            max: 18 },
]

export default function AeoAuditCard({ businessId, initialAudit, initialRecommendations, prevBreakdown, locale }: Props) {
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
        body: JSON.stringify({ business_id: businessId }),
      })
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
      setError('Audit failed. Please try again.')
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
        <span className="text-[10px] font-bold text-[#4f46e5] uppercase tracking-wider">AI Visibility Audit</span>
        <p className="text-sm font-semibold text-[#1e293b] mt-2 mb-1">Set up your business profile first</p>
        <p className="text-xs text-slate-500 mb-3">We need your business name, type, and city to run the audit.</p>
        <Link href={`/${locale}/dashboard/settings`}
          className="text-xs font-semibold bg-[#4f46e5] text-white px-3 py-1.5 rounded-lg hover:bg-indigo-700 transition-colors">
          Complete your profile →
        </Link>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="bg-white rounded-2xl border-l-[3px] border-l-[#4f46e5] shadow-sm border border-slate-100 p-4">
        <div className="flex items-start justify-between mb-2">
          <span className="text-[10px] font-bold text-[#4f46e5] uppercase tracking-wider">AI Visibility Audit</span>
          {audit && (
            <span className="text-[10px] text-slate-400">{new Date(audit.created_at).toLocaleDateString('en-CA')}</span>
          )}
        </div>

        {audit && (
          <div className="mb-3">
            <p className={`text-4xl font-extrabold ${scoreColor}`}>
              {audit.score}<span className="text-base font-semibold text-slate-400">/100</span>
            </p>
            <p className="text-xs text-slate-500 mt-0.5">AEO Readiness Score</p>
          </div>
        )}

        {!audit && !loading && (
          <p className="text-sm font-semibold text-[#1e293b] mb-3">
            Find out how visible your business is to AI search engines
          </p>
        )}

        {audit && audit.score_breakdown && (
          <div className="flex flex-col gap-1.5 mb-3">
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
                />
              )
            })}
          </div>
        )}

        {error && <p className="text-xs text-red-500 mb-2">{error}</p>}

        <div className="flex items-center gap-2 flex-wrap">
          <button
            onClick={runAudit}
            disabled={loading}
            className="text-xs font-semibold bg-[#4f46e5] text-white px-3 py-1.5 rounded-lg hover:bg-indigo-700 transition-colors disabled:opacity-50">
            {loading ? 'Running audit… (30–60 seconds)' : audit ? 'Re-run audit' : 'Run AEO Readiness Audit →'}
          </button>
          {audit && (
            <button
              onClick={() => setDrawerOpen(true)}
              className="text-xs font-semibold text-[#4f46e5] hover:underline">
              Why this score? →
            </button>
          )}
        </div>

        <div className="flex items-center gap-3 mt-3 border-t border-slate-50 pt-2">
          <Link
            href={`/${locale}/methodology`}
            className="text-[10px] text-slate-400 hover:text-[#4f46e5] hover:underline transition-colors">
            How is the score calculated?
          </Link>
        </div>
      </div>

      {audit && <RecommendationsList recommendations={recommendations} />}

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

function PillarRow({ label, points, max, delta }: { label: string; points: number; max: number; delta: number | null }) {
  const pct = max === 0 ? 0 : (points / max) * 100
  const color = pct >= 75 ? 'bg-green-500' : pct >= 40 ? 'bg-amber-400' : 'bg-red-300'
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
  const kg = rawResults?.google?.knowledge_graph
  const lp = rawResults?.google?.local_pack
  const ws = rawResults?.website
  const perplexity = rawResults?.perplexity
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
            <h2 className="text-sm font-extrabold text-[#1e293b]">Why this score?</h2>
            <p className="text-[10px] text-slate-500">Raw signals from the last audit</p>
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
            <p className="text-xs text-slate-500">No raw data available for this audit.</p>
          ) : (
            <>
              <DrawerSection title="Google Business Profile" pts={breakdown?.gbp ?? 0} max={25}>
                <Signal label="Found in Knowledge Graph"    value={kg?.found} />
                <Signal label="Business title"             value={kg?.title} />
                <Signal label="Category"                   value={kg?.type} />
                <Signal label="Rating"                     value={kg?.rating != null ? `${kg.rating}★` : null} />
                <Signal label="Review count"               value={kg?.reviews_count} />
                <Signal label="Website on listing"         value={kg?.website != null ? kg.website : null} />
                <Signal label="Phone on listing"           value={kg?.phone != null ? kg.phone : null} />
              </DrawerSection>

              <DrawerSection title="Reviews & Reputation" pts={breakdown?.reviews ?? 0} max={22}>
                <Signal label="Rating"        value={kg?.rating != null ? `${kg.rating}★` : null} />
                <Signal label="Review count"  value={kg?.reviews_count} />
              </DrawerSection>

              <DrawerSection title="Website & Schema" pts={breakdown?.website ?? 0} max={20}>
                <Signal label="Website reachable"        value={ws?.reachable} />
                <Signal label="LocalBusiness schema"     value={ws?.has_local_business_schema} />
                <Signal label="FAQ / HowTo schema"       value={ws?.has_faq_schema} />
              </DrawerSection>

              <DrawerSection title="Local Search Presence" pts={breakdown?.local_search ?? 0} max={15}>
                <Signal label="In Google local pack"       value={lp?.present} />
                <Signal label="Local pack position"        value={lp?.position != null ? `#${lp.position}` : 'Not in pack'} />
                <Signal label="In organic results"         value={rawResults?.google?.organic?.present} />
              </DrawerSection>

              <DrawerSection title="AI Citations" pts={breakdown?.ai_citation ?? 0} max={18}>
                <Signal label="Mentioned by Perplexity"       value={perplexity?.mentioned} />
                {perplexity?.snippet && (
                  <p className="text-[10px] text-slate-500 italic mt-1 mb-2 leading-relaxed">
                    &quot;{perplexity.snippet.slice(0, 200)}{perplexity.snippet.length > 200 ? '…' : ''}&quot;
                  </p>
                )}
                <Signal label="Mentioned in Google AI Overview" value={rawResults?.google?.ai_overview?.mentioned} />
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

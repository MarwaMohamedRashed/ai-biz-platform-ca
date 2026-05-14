'use client'

import { useState, useEffect } from 'react'
import { useTranslations } from 'next-intl'
import { createClient } from '@/lib/supabase'

interface ReputationItem {
  theme: string
  detail?: string
  example?: string
  source?: string
}

// Backward-compat: older cached responses store plain strings
function normaliseItems(raw: unknown[]): ReputationItem[] {
  return raw.map(item =>
    typeof item === 'string' ? { theme: item } : (item as ReputationItem)
  )
}

interface OwnReputationData {
  strengths: unknown[]
  weaknesses: unknown[]
  summary: string
  review_count: number
  avg_rating: number | null
  cached: boolean
  error?: string
}

/**
 * Standalone card showing the own business's strengths and weaknesses derived
 * from their public Google Maps reviews (via SerpApi — same pipeline as competitor
 * analysis). Does NOT use the Phase 2 reviews table or review_insights table.
 *
 * Requires an AEO audit to have been run so we have a place_id. Shows nothing
 * if no audit exists or the place_id could not be resolved.
 */
export default function OwnReputationCard() {
  const t = useTranslations('dashboard.ownReputation')
  const [data, setData] = useState<OwnReputationData | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function load() {
      try {
        const { data: { session } } = await createClient().auth.getSession()
        const res = await fetch(
          `${process.env.NEXT_PUBLIC_API_URL}/api/v1/aeo/own-reputation`,
          { headers: { Authorization: `Bearer ${session?.access_token}` } },
        )
        if (!res.ok) return
        const json: OwnReputationData = await res.json()
        setData(json)
      } catch {
        // silently fail — card just won't render
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  if (loading) {
    return (
      <div className="bg-slate-50 rounded-2xl p-5 animate-pulse h-32" />
    )
  }

  // Show name-mismatch warning instead of hiding silently
  if (!data || data.error === 'no_place_id') {
    return (
      <div className="bg-amber-50 border border-amber-200 rounded-2xl p-4 flex gap-3">
        <span className="text-lg mt-0.5">⚠️</span>
        <div>
          <p className="text-xs font-bold text-amber-800 mb-0.5">{t('nameMismatchTitle')}</p>
          <p className="text-xs text-amber-700 leading-snug">{t('nameMismatchBody')}</p>
        </div>
      </div>
    )
  }

  if (data.review_count === 0) return null

  const strengths = normaliseItems(data.strengths ?? [])
  const weaknesses = normaliseItems(data.weaknesses ?? [])
  if (strengths.length === 0 && weaknesses.length === 0) return null

  return (
    <div className="bg-white border border-slate-100 rounded-2xl p-5">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-base">⭐</span>
          <h2 className="text-sm font-extrabold text-slate-800">{t('title')}</h2>
        </div>
        <div className="text-right">
          <p className="text-[10px] text-slate-400">
              {t('reviewsMeta', {
                count: data.review_count,
                reviews: data.review_count !== 1 ? t('reviewPlural') : t('reviewSingular'),
              })}
            {data.avg_rating != null && (
              <span className="ml-1 font-semibold text-amber-500">{data.avg_rating}★</span>
            )}
          </p>
          <p className="text-[9px] text-slate-300">{t('viaGoogle')}</p>
        </div>
      </div>

      <div className="flex flex-col gap-3">
        {/* Weaknesses first — actionable issues the owner should address */}
        {weaknesses.length > 0 && (
          <div>
            <p className="text-[10px] font-bold text-amber-700 mb-1.5">{t('weaknesses')}</p>
            <div className="flex flex-col gap-2">
              {weaknesses.map((w, i) => (
                <div
                  key={i}
                  className="bg-amber-50 border border-amber-100 rounded-xl px-3 py-2.5"
                >
                  <div className="flex items-center justify-between gap-2 mb-0.5">
                    <p className="text-[11px] font-semibold text-amber-800">{w.theme}</p>
                    {w.source && (
                      <span className="text-[9px] text-amber-600 bg-amber-100 px-1.5 py-0.5 rounded-full shrink-0">{w.source}</span>
                    )}
                  </div>
                  {w.detail && (
                    <p className="text-[10px] text-amber-700 leading-snug">{w.detail}</p>
                  )}
                  {w.example && (
                    <p className="text-[10px] text-slate-400 italic mt-0.5">&ldquo;{w.example}&rdquo;</p>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Strengths */}
        {strengths.length > 0 && (
          <div>
            <p className="text-[10px] font-bold text-green-700 mb-1.5">{t('strengths')}</p>
            <div className="flex flex-col gap-2">
              {strengths.map((s, i) => (
                <div
                  key={i}
                  className="bg-green-50 border border-green-100 rounded-xl px-3 py-2.5"
                >
                  <div className="flex items-center justify-between gap-2 mb-0.5">
                    <p className="text-[11px] font-semibold text-green-800">{s.theme}</p>
                    {s.source && (
                      <span className="text-[9px] text-green-600 bg-green-100 px-1.5 py-0.5 rounded-full shrink-0">{s.source}</span>
                    )}
                  </div>
                  {s.detail && (
                    <p className="text-[10px] text-green-700 leading-snug">{s.detail}</p>
                  )}
                  {s.example && (
                    <p className="text-[10px] text-slate-400 italic mt-0.5">&ldquo;{s.example}&rdquo;</p>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Summary */}
        {data.summary && (
          <div className="bg-slate-50 rounded-xl px-3 py-2.5">
            <p className="text-[11px] text-slate-600 leading-relaxed">{data.summary}</p>
          </div>
        )}
      </div>
    </div>
  )
}

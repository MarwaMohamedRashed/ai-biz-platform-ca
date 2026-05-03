'use client'

import { useState, useEffect } from 'react'
import { createClient } from '@/lib/supabase'

interface OwnReputationData {
  strengths: string[]
  weaknesses: string[]
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

  // Hide if no useful data
  if (!data || data.review_count === 0 || data.error === 'no_place_id') return null
  if (data.strengths.length === 0 && data.weaknesses.length === 0) return null

  return (
    <div className="bg-white border border-slate-100 rounded-2xl p-5">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-base">⭐</span>
          <h2 className="text-sm font-extrabold text-slate-800">Your Reputation</h2>
        </div>
        <div className="text-right">
          <p className="text-[10px] text-slate-400">
            {data.review_count} Google review{data.review_count !== 1 ? 's' : ''}
            {data.avg_rating != null && (
              <span className="ml-1 font-semibold text-amber-500">{data.avg_rating}★</span>
            )}
          </p>
          <p className="text-[9px] text-slate-300">via Google Maps</p>
        </div>
      </div>

      <div className="flex flex-col gap-3">
        {/* Strengths */}
        {data.strengths.length > 0 && (
          <div>
            <p className="text-[10px] font-bold text-green-700 mb-1.5">✅ What customers love</p>
            <div className="flex flex-wrap gap-1.5">
              {data.strengths.map((s, i) => (
                <span
                  key={i}
                  className="text-[11px] bg-green-50 text-green-800 border border-green-100 px-2.5 py-1 rounded-full font-medium"
                >
                  {s}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Weaknesses */}
        {data.weaknesses.length > 0 && (
          <div>
            <p className="text-[10px] font-bold text-amber-700 mb-1.5">⚠️ What needs attention</p>
            <div className="flex flex-wrap gap-1.5">
              {data.weaknesses.map((w, i) => (
                <span
                  key={i}
                  className="text-[11px] bg-amber-50 text-amber-800 border border-amber-100 px-2.5 py-1 rounded-full font-medium"
                >
                  {w}
                </span>
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

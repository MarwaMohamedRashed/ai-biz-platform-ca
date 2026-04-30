'use client'

import { useState } from 'react'
import { createClient } from '@/lib/supabase'
import Link from 'next/link'

interface Audit {
  score: number
  perplexity_mentioned: boolean
  perplexity_snippet: string | null
  google_ai_mentioned: boolean
  google_ai_snippet: string | null
  created_at: string
}

interface Props {
  businessId: string | null
  initialAudit: Audit | null
  locale: string
}

export default function AeoAuditCard({ businessId, initialAudit, locale }: Props) {
  const [audit, setAudit] = useState<Audit | null>(initialAudit)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

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
        perplexity_mentioned: data.perplexity.mentioned,
        perplexity_snippet: data.perplexity.snippet,
        google_ai_mentioned: data.google_ai.mentioned,
        google_ai_snippet: data.google_ai.snippet,
        created_at: new Date().toISOString(),
      })
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
    <div className="bg-white rounded-2xl border-l-[3px] border-l-[#4f46e5] shadow-sm border border-slate-100 p-4">
      <div className="flex items-start justify-between mb-2">
        <span className="text-[10px] font-bold text-[#4f46e5] uppercase tracking-wider">AI Visibility Audit</span>
        {audit && (
          <span className="text-[10px] text-slate-400">{new Date(audit.created_at).toLocaleDateString()}</span>
        )}
      </div>

      {audit && (
        <div className="mb-3">
          <p className={`text-4xl font-extrabold ${scoreColor}`}>
            {audit.score}<span className="text-base font-semibold text-slate-400">/100</span>
          </p>
          <p className="text-xs text-slate-500 mt-0.5">AI Visibility Score</p>
        </div>
      )}

      {!audit && !loading && (
        <p className="text-sm font-semibold text-[#1e293b] mb-3">
          Find out if AI search engines can find your business
        </p>
      )}

      {audit && (
        <div className="flex flex-col gap-2 mb-3">
          <EngineRow name="Perplexity" mentioned={audit.perplexity_mentioned} snippet={audit.perplexity_snippet} />
          <EngineRow name="Google AI" mentioned={audit.google_ai_mentioned} snippet={audit.google_ai_snippet} />
        </div>
      )}

      {error && <p className="text-xs text-red-500 mb-2">{error}</p>}

      <button
        onClick={runAudit}
        disabled={loading}
        className="text-xs font-semibold bg-[#4f46e5] text-white px-3 py-1.5 rounded-lg hover:bg-indigo-700 transition-colors disabled:opacity-50">
        {loading ? 'Running audit… (15–30 seconds)' : audit ? 'Re-run audit' : 'Run AI Visibility Audit →'}
      </button>
    </div>
  )
}

function EngineRow({ name, mentioned, snippet }: { name: string; mentioned: boolean; snippet: string | null }) {
  return (
    <div className="flex items-start gap-2">
      <span className={`mt-0.5 text-sm font-bold flex-shrink-0 ${mentioned ? 'text-green-500' : 'text-red-400'}`}>
        {mentioned ? '✓' : '✗'}
      </span>
      <div>
        <p className="text-xs font-semibold text-[#1e293b]">{name}</p>
        {mentioned && snippet
          ? <p className="text-[10px] text-slate-400 mt-0.5 line-clamp-2">{snippet}</p>
          : <p className="text-[10px] text-slate-400">Not mentioned</p>
        }
      </div>
    </div>
  )
}
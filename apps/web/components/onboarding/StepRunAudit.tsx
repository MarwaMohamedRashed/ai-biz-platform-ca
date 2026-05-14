'use client'

import { useEffect, useRef, useState } from 'react'
import { useTranslations } from 'next-intl'
import { createClient } from '@/lib/supabase'

interface Props {
  businessId: string | null
  locale: string
  onComplete: (auditResult: AuditResult | null) => void
}

export interface AuditResult {
  score: number
  recommendations: Recommendation[]
}

interface Recommendation {
  pillar: 'gbp' | 'reviews' | 'website' | 'local_search' | 'ai_citation'
  title: string
  description: string
  action: string
  difficulty: 'easy' | 'medium' | 'hard'
  impact: number
  url?: string
}

/** First-audit step. Kicks off the audit on mount, animates a progress
 *  message reel while it runs (typical audit = 30-60s), then advances
 *  to the next step with the result. Failure surfaces a 'skip to
 *  dashboard' escape hatch — never blocks completion. */
export default function StepRunAudit({ businessId, locale, onComplete }: Props) {
  const t = useTranslations('onboarding.stepAudit')
  const [msgIndex, setMsgIndex] = useState(0)
  const [failed, setFailed] = useState(false)
  // Ref guard so React 18 strict-mode double-mount doesn't fire two audits.
  const startedRef = useRef(false)

  // Rotating progress messages while the audit runs.
  useEffect(() => {
    const id = setInterval(() => setMsgIndex(i => (i + 1) % 5), 4500)
    return () => clearInterval(id)
  }, [])

  // Kick off the audit once on mount.
  useEffect(() => {
    if (startedRef.current) return
    startedRef.current = true
    if (!businessId) {
      setFailed(true)
      return
    }
    let cancelled = false
    ;(async () => {
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
        if (!res.ok) throw new Error('Audit failed')
        const data = await res.json()
        if (cancelled) return
        onComplete({
          score: data.score,
          recommendations: data.recommendations || [],
        })
      } catch {
        if (!cancelled) setFailed(true)
      }
    })()
    return () => { cancelled = true }
  }, [businessId, locale, onComplete])

  return (
    <div className="flex flex-col items-center gap-6 py-10 text-center">
      {!failed ? (
        <>
          {/* Spinner */}
          <div className="w-16 h-16 rounded-full border-4 border-indigo-100 border-t-[#4f46e5] animate-spin" />
          <div>
            <h1 className="text-2xl font-bold text-[#1e293b]">{t('heading')}</h1>
            <p className="text-sm text-slate-500 mt-2 max-w-md mx-auto leading-relaxed">{t('subtitle')}</p>
          </div>
          {/* Rotating status message */}
          <p key={msgIndex} className="text-sm font-medium text-[#4f46e5] animate-pulse">
            {t(`msg${msgIndex + 1}` as 'msg1' | 'msg2' | 'msg3' | 'msg4' | 'msg5')}
          </p>
        </>
      ) : (
        <>
          <div className="w-16 h-16 rounded-full bg-amber-50 flex items-center justify-center">
            <span className="text-amber-500 text-3xl" aria-hidden="true">⚠</span>
          </div>
          <div>
            <h1 className="text-xl font-bold text-[#1e293b]">{t('failed')}</h1>
          </div>
          <button
            type="button"
            onClick={() => onComplete(null)}
            className="w-full py-3 rounded-xl bg-[#4f46e5] text-white text-sm font-semibold hover:bg-indigo-700 transition-colors">
            {t('skip')}
          </button>
        </>
      )}
    </div>
  )
}

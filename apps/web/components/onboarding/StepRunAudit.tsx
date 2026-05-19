'use client'

import { useEffect, useRef, useState } from 'react'
import { useTranslations } from 'next-intl'
import { createClient } from '@/lib/supabase'

interface Props {
  businessId: string | null
  locale: string
  onComplete: (auditResult: AuditResult | null) => void
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

interface AuditCompetitor {
  place_id?: string | null
  name?: string | null
  rating?: number | null
  reviews?: number | null
  address?: string | null
}

export interface AuditResult {
  score: number
  recommendations: Recommendation[]
  competitors: AuditCompetitor[]
  raw_results?: unknown
}

/** First-audit step. Kicks off the audit on mount, animates a progress
 *  message reel while it runs (typical audit = 30-90s, can be longer for
 *  popular businesses with thousands of reviews). At 60s we surface a
 *  'Taking longer than expected' message + escape button so the owner is
 *  never stuck staring at a spinner. Failure surfaces the same escape. */
export default function StepRunAudit({ businessId, locale, onComplete }: Props) {
  const t = useTranslations('onboarding.stepAudit')
  const [msgIndex, setMsgIndex] = useState(0)
  const [failed, setFailed] = useState(false)
  const [slow, setSlow] = useState(false)
  // Ref guard so React 18 strict-mode double-mount doesn't fire two audits.
  const startedRef = useRef(false)
  // Ref-latest pattern for onComplete. The parent passes an inline arrow,
  // so onComplete is a new function on every parent render. Without this ref,
  // putting onComplete in the audit effect's deps would tear down + restart
  // (and abort the in-flight fetch) on every parent re-render. We keep the
  // effect dep-free of onComplete and read the latest version via the ref.
  const onCompleteRef = useRef(onComplete)
  useEffect(() => { onCompleteRef.current = onComplete }, [onComplete])

  // Rotating progress messages while the audit runs.
  useEffect(() => {
    const id = setInterval(() => setMsgIndex(i => (i + 1) % 5), 4500)
    return () => clearInterval(id)
  }, [])

  // After 60s, surface the "this is taking a while" CTA but keep waiting.
  useEffect(() => {
    const id = setTimeout(() => setSlow(true), 60_000)
    return () => clearTimeout(id)
  }, [])

  // Kick off the audit once on mount.
  //
  // Two-track strategy:
  //   Track A — POST /aeo/audit and read the JSON response (fast path, < 60 s).
  //   Track B — after a 30 s grace period, poll public.aeo_audits via the
  //             browser supabase client looking for a fresh row this audit
  //             saved before its response could reach us.
  //
  // We race both tracks (Promise.race); whichever finds the result first wins,
  // the other is aborted. This guarantees that even when the long-running POST
  // is killed by a proxy/Vercel/browser fetch timeout, the user still advances
  // to step 3 as soon as the backend persists the row. Without this, audits
  // that succeed server-side but lose the response leave the user staring at
  // an infinite spinner.
  useEffect(() => {
    if (startedRef.current) return
    startedRef.current = true
    if (!businessId) {
      setFailed(true)
      return
    }
    // NOTE: React 18 strict-mode (dev only) double-invokes effects:
    // mount → cleanup → remount. Earlier versions of this effect used
    //   (a) abort.abort() in cleanup → killed the fetch
    //   (b) a `cancelled` closure flag set by cleanup → discarded the result
    // Both, combined with the startedRef guard that blocks the remount from
    // starting a replacement audit, deadlocked the spinner forever.
    //
    // The fix: cleanup is intentionally a no-op. The startedRef prevents a
    // second concurrent audit; the fetch runs once to completion and calls
    // onCompleteRef.current(result) unconditionally. React 18 tolerates a
    // setState on an unmounted-then-remounted instance (same fiber, same
    // refs), and on a real unmount it's a silent no-op.
    const abort = new AbortController()

    const POLL_GRACE_MS    = 30_000   // don't bother polling before this
    const POLL_INTERVAL_MS = 5_000
    const TOTAL_DEADLINE_MS = 180_000  // 3 min hard cap on the whole step

    const apiUrl   = process.env.NEXT_PUBLIC_API_URL
    const supabase = createClient()

    function toAuditResult(score: number, raw: unknown): AuditResult {
      const r = (raw ?? {}) as Record<string, unknown>
      return {
        score,
        recommendations: (r.recommendations as Recommendation[] | undefined) ?? [],
        competitors:     (r.competitors as AuditCompetitor[] | undefined) ?? [],
        raw_results:     raw,
      }
    }

    async function trackA(): Promise<AuditResult | null> {
      try {
        const { data: { session } } = await supabase.auth.getSession()
        if (!session?.access_token) return null
        const res = await fetch(`${apiUrl}/api/v1/aeo/audit`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${session.access_token}`,
          },
          body: JSON.stringify({ business_id: businessId, locale }),
          signal: abort.signal,
        })
        if (!res.ok) return null
        const data = await res.json()
        return {
          score:           data.score,
          recommendations: data.recommendations || [],
          competitors:     data.competitors || [],
          raw_results:     data.raw_results,
        }
      } catch {
        return null
      }
    }

    async function trackB(): Promise<AuditResult | null> {
      // Initial grace period — fresh audits typically finish in 30-60 s, so
      // polling before that wastes Supabase reads.
      await new Promise(r => setTimeout(r, POLL_GRACE_MS))
      const deadline = Date.now() + (TOTAL_DEADLINE_MS - POLL_GRACE_MS)
      while (Date.now() < deadline && !abort.signal.aborted) {
        const { data, error } = await supabase
          .from('aeo_audits')
          .select('score, raw_results, created_at')
          .eq('business_id', businessId)
          .gte('created_at', new Date(Date.now() - 15 * 60_000).toISOString())
          .order('created_at', { ascending: false })
          .limit(1)
          .maybeSingle()
        if (!error && data && data.score != null) {
          return toAuditResult(data.score as number, data.raw_results)
        }
        await new Promise(r => setTimeout(r, POLL_INTERVAL_MS))
      }
      return null
    }

    ;(async () => {
      // Race them. The first non-null wins. If both eventually return null
      // (within the 3-min deadline), we surface the failed-state UI.
      const result = await Promise.race([trackA(), trackB()])
      if (result) {
        onCompleteRef.current(result)
      } else {
        setFailed(true)
      }
    })()

    // Cleanup is intentionally a no-op — see the long comment above.
  }, [businessId, locale])

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
          {/* Soft escape after 60s -- audit still running in background */}
          {slow && (
            <div className="mt-2 flex flex-col items-center gap-2">
              <p className="text-xs text-slate-500 max-w-sm">{t('slow')}</p>
              <button
                type="button"
                onClick={() => onCompleteRef.current(null)}
                className="text-xs font-semibold text-[#4f46e5] hover:underline">
                {t('skip')}
              </button>
            </div>
          )}
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
            onClick={() => onCompleteRef.current(null)}
            className="w-full py-3 rounded-xl bg-[#4f46e5] text-white text-sm font-semibold hover:bg-indigo-700 transition-colors">
            {t('skip')}
          </button>
        </>
      )}
    </div>
  )
}

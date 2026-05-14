'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { useLocale, useTranslations } from 'next-intl'
import { createClient } from '@/lib/supabase'
import type { AuditResult } from './StepRunAudit'

interface Props {
  businessName: string
  firstName: string
  auditResult: AuditResult | null
}

const TIME_PILL: Record<'easy' | 'medium' | 'hard', string> = {
  easy:   'bg-green-50 text-green-700',
  medium: 'bg-amber-50 text-amber-700',
  hard:   'bg-slate-100 text-slate-600',
}

/** Final onboarding step. Picks the top 3 highest-impact non-hard
 *  recommendations and shows them as a 'first wins' preview, so the
 *  owner leaves onboarding with a clear sense of what to do next.
 *  If the audit failed, falls back to a brief encouragement message. */
export default function StepQuickWins({ businessName, firstName, auditResult }: Props) {
  const t = useTranslations('onboarding.stepWins')
  const tRec = useTranslations('dashboard.recommendations')
  const router = useRouter()
  const locale = useLocale()
  const [going, setGoing] = useState(false)

  // Top 3 wins = highest impact, prefer non-hard difficulty.
  const wins = (auditResult?.recommendations || [])
    .filter(r => r.difficulty !== 'hard')
    .sort((a, b) => b.impact - a.impact)
    .slice(0, 3)
  const totalLift = wins.reduce((s, r) => s + r.impact, 0)

  async function handleGo() {
    setGoing(true)
    try {
      const supabase = createClient()
      const { data: businesses } = await supabase
        .from('businesses')
        .select('id')
        .limit(1)
      if (businesses?.[0]) {
        const businessId = businesses[0].id
        await supabase.from('businesses')
          .update({ onboarding_completed: true })
          .eq('id', businessId)
        const trialEnds = new Date()
        trialEnds.setDate(trialEnds.getDate() + 14)
        await supabase.from('subscriptions').insert({
          business_id: businessId,
          plan_tier: 'starter',
          status: 'trialing',
          trial_ends: trialEnds.toISOString(),
        })
      }
    } catch {
      // best-effort; we still navigate even if these writes fail
    }
    router.push(`/${locale}/dashboard`)
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold text-[#1e293b]">
          {t('heading', { firstName })}
        </h1>
        {businessName && (
          <p className="text-sm text-[#4f46e5] font-medium mt-1">{businessName}</p>
        )}
        <p className="text-sm text-slate-500 mt-2 leading-relaxed">{t('subtitle')}</p>
      </div>

      {!auditResult && (
        <div className="bg-amber-50 border border-amber-200 text-amber-700 text-sm rounded-xl px-4 py-3">
          {t('noAudit')}
        </div>
      )}

      {auditResult && wins.length === 0 && (
        <div className="bg-emerald-50 border border-emerald-200 text-emerald-800 text-sm rounded-xl px-4 py-3">
          🎉 {t('noWins')}
        </div>
      )}

      {wins.length > 0 && (
        <>
          <div className="flex items-baseline justify-between">
            <span className="text-xs font-semibold text-emerald-700">
              {tRec('progressLine', { done: 0, total: wins.length })}
            </span>
            <span className="text-xs font-semibold text-[#4f46e5]">
              {t('pointsLift', { points: totalLift })}
            </span>
          </div>
          <div className="flex flex-col gap-3">
            {wins.map((r, i) => (
              <div key={i} className="bg-white border border-slate-200 rounded-xl p-4 flex items-start gap-3">
                <div className="flex-shrink-0 w-9 h-9 rounded-full bg-amber-50 flex items-center justify-center mt-0.5">
                  <span className="text-xs font-bold text-amber-700">+{r.impact}</span>
                </div>
                <div className="flex-1 min-w-0">
                  <div className="mb-1.5">
                    <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${TIME_PILL[r.difficulty]}`}>
                      {tRec(`difficulty.${r.difficulty}`)}
                    </span>
                  </div>
                  <p className="text-sm font-semibold text-[#1e293b] mb-1">{r.title}</p>
                  <p className="text-xs text-slate-600 leading-relaxed">{r.description}</p>
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      <button
        type="button"
        onClick={handleGo}
        disabled={going}
        className="w-full py-3 rounded-xl bg-[#4f46e5] text-white text-sm font-semibold
                   hover:bg-indigo-700 transition-colors disabled:opacity-50">
        {t('ctaGo')}
      </button>
    </div>
  )
}

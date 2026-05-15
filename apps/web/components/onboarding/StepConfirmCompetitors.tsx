'use client'

import { useRef, useState } from 'react'
import { useTranslations } from 'next-intl'
import CompetitorPicker, { type CompetitorEntry } from '@/components/dashboard/CompetitorPicker'
import type { AuditResult } from './StepRunAudit'

interface Props {
  auditResult: AuditResult | null
  onComplete: () => void
}

interface AuditCompetitor {
  place_id?: string | null
  name?: string | null
}

/** Third onboarding step. Shows the audit's auto-detected competitors as
 *  the starting list, plus a search-and-pick to add up to 5 total. On
 *  Continue, saves the list through CompetitorPicker's imperative save
 *  handle (which scores any new entries in parallel before resolving). */
export default function StepConfirmCompetitors({ auditResult, onComplete }: Props) {
  const t = useTranslations('onboarding.stepConfirmCompetitors')
  const saveRef = useRef<(() => Promise<void>) | null>(null)
  const [continuing, setContinuing] = useState(false)

  // Seed the picker from the audit's competitors (auto-detected) so the owner
  // sees a starting list, not an empty editor.
  const rawCompetitors: AuditCompetitor[] = (
    (auditResult as unknown as { competitors?: AuditCompetitor[] } | null)?.competitors
    ?? []
  )
  const initialList: CompetitorEntry[] = rawCompetitors
    .filter((c): c is { place_id: string; name: string } =>
      Boolean(c?.place_id && c.name))
    .slice(0, 5)
    .map(c => ({
      place_id: c.place_id,
      name:     c.name,
      source:   'auto' as const,
    }))

  async function handleContinue() {
    setContinuing(true)
    try {
      if (saveRef.current) await saveRef.current()
    } finally {
      setContinuing(false)
      onComplete()
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <div>
        <h1 className="text-2xl font-bold text-[#1e293b]">{t('heading')}</h1>
        <p className="text-sm text-slate-500 mt-2 leading-relaxed">{t('subtitle')}</p>
      </div>

      <CompetitorPicker
        initialList={initialList}
        hideSave
        saveRef={saveRef}
      />

      <p className="text-xs text-slate-400">{t('scoringHint')}</p>

      <div className="flex items-center justify-between gap-3">
        <button
          type="button"
          onClick={onComplete}
          className="text-xs font-semibold text-slate-500 hover:text-[#4f46e5] hover:underline">
          {t('skip')}
        </button>
        <button
          type="button"
          onClick={handleContinue}
          disabled={continuing}
          className="px-5 py-2.5 rounded-xl bg-[#4f46e5] text-white text-sm font-semibold
                     hover:bg-indigo-700 transition-colors disabled:opacity-50">
          {t('continue')}
        </button>
      </div>
    </div>
  )
}

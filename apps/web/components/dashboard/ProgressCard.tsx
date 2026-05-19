'use client'

import { useEffect, useState } from 'react'
import { useTranslations } from 'next-intl'
import type { AuditDrift } from '@/lib/audit-drift'

// Dashboard Progress card — month-over-month drift between the latest two
// audits. The retention spine described in feedback_supabase_mutations
// memory: every month the owner gets a fresh answer to "is what I'm
// doing working?". For Phase 2 v1 we surface what we already measure
// (score, citations, local pack, reviews, competitors) without needing
// to persist completion records server-side.
//
// We also pull the localStorage completion set from RecommendationsList
// (`leapone:completed:<businessKey>`) so we can mention "X items completed
// since last audit" — best-effort, browser-local only. When the owner uses
// a different browser, this section just hides; the rest of the card is
// fully server-side.

interface Props {
  drift: AuditDrift | null
  /** Same key RecommendationsList uses for its localStorage completion set.
   *  Typically the business name. */
  businessKey?: string | null
  /** Date string for the next monthly cycle, shown when drift is null
   *  (only one audit run so far). Server-formatted to keep locale right. */
  nextReportDateLabel?: string
}

export default function ProgressCard({ drift, businessKey, nextReportDateLabel }: Props) {
  const t = useTranslations('dashboard.progress')
  const [completedSinceLast, setCompletedSinceLast] = useState<number | null>(null)

  // Read the localStorage completion set (Phase 2 best-effort). If the
  // owner just signed in on a different device, this will be 0 — UI hides
  // that line in that case instead of misrepresenting effort.
  useEffect(() => {
    if (!businessKey || !drift) return
    try {
      const raw = window.localStorage.getItem(`leapone:completed:${businessKey}`)
      if (!raw) return
      const arr = JSON.parse(raw) as string[]
      // We don't track WHEN each item was marked done, so we can only show
      // the total completed set right now. Calling it "items completed"
      // (not "since last audit") keeps the framing honest.
      if (Array.isArray(arr)) setCompletedSinceLast(arr.length)
    } catch { /* localStorage unavailable */ }
  }, [businessKey, drift])

  // Empty state: only one audit so far. Show the "unlocks on…" pre-promise.
  if (!drift) {
    return (
      <section className="rounded-2xl border border-slate-100 bg-white p-5 print-hide">
        <div className="flex items-start gap-3">
          <div className="w-9 h-9 rounded-full bg-indigo-50 flex items-center justify-center flex-shrink-0">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="M12 8v4l3 3" stroke="#4f46e5" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              <circle cx="12" cy="12" r="9" stroke="#4f46e5" strokeWidth="2"/>
            </svg>
          </div>
          <div className="flex-1 min-w-0">
            <h2 className="text-sm font-extrabold text-[#1e293b]">{t('lockedTitle')}</h2>
            <p className="text-xs text-slate-500 mt-1 leading-relaxed">
              {nextReportDateLabel
                ? t('lockedSubtitleWithDate', { date: nextReportDateLabel })
                : t('lockedSubtitle')}
            </p>
          </div>
        </div>
      </section>
    )
  }

  const scoreDir =
    drift.scoreDelta > 0 ? 'up' :
    drift.scoreDelta < 0 ? 'down' :
                           'flat'

  return (
    <section className="rounded-2xl border border-slate-100 bg-white p-5 print-hide">
      <div className="flex items-center justify-between gap-3 mb-3">
        <div>
          <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">{t('eyebrow')}</span>
          <h2 className="text-sm font-extrabold text-[#1e293b] mt-1">
            {t('title')}
          </h2>
        </div>
        <span className="text-[10px] text-slate-400">
          {t('comparedTo', { date: formatRelative(drift.previousAt) })}
        </span>
      </div>

      {/* Score delta — the headline drift signal. */}
      <div className="rounded-xl bg-slate-50 p-3 flex items-center justify-between gap-3 mb-3">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
            {t('scoreLabel')}
          </p>
          <p className="text-lg font-extrabold text-[#1e293b] tabular-nums">
            {drift.currentScore} <span className="text-slate-300 text-sm font-normal">/ 100</span>
          </p>
        </div>
        <DeltaBadge direction={scoreDir} value={drift.scoreDelta} suffix={t('points')} />
      </div>

      {/* Drift rows */}
      <ul className="flex flex-col gap-2">
        <DriftRow
          label={t('citations.chatgpt')}
          change={drift.chatgptChange}
          t={t}
        />
        <DriftRow
          label={t('citations.perplexity')}
          change={drift.perplexityChange}
          t={t}
        />
        <DriftRow
          label={t('citations.googleAi')}
          change={drift.googleAiChange}
          t={t}
        />
        <DriftRow
          label={t('localPack')}
          change={drift.localPackChange}
          t={t}
        />
        {drift.reviewCountDelta != null && drift.reviewCountDelta !== 0 && (
          <li className="flex items-center justify-between gap-2 px-1">
            <span className="text-xs text-[#1e293b]">{t('reviews')}</span>
            <span className={`text-xs font-bold tabular-nums ${drift.reviewCountDelta > 0 ? 'text-emerald-600' : 'text-rose-600'}`}>
              {drift.reviewCountDelta > 0 ? '+' : ''}{drift.reviewCountDelta}
            </span>
          </li>
        )}
      </ul>

      {/* Competitor movement */}
      {(drift.newCompetitors.length > 0 || drift.droppedCompetitors.length > 0) && (
        <div className="mt-4 pt-3 border-t border-slate-100">
          {drift.newCompetitors.length > 0 && (
            <CompetitorList
              label={t('newCompetitors', { count: drift.newCompetitors.length })}
              names={drift.newCompetitors}
              tone="warn"
            />
          )}
          {drift.droppedCompetitors.length > 0 && (
            <CompetitorList
              label={t('droppedCompetitors', { count: drift.droppedCompetitors.length })}
              names={drift.droppedCompetitors}
              tone="ok"
            />
          )}
        </div>
      )}

      {/* Owner-effort line (best-effort localStorage read). */}
      {completedSinceLast != null && completedSinceLast > 0 && (
        <p className="mt-4 pt-3 border-t border-slate-100 text-[11px] text-slate-500 italic">
          {t('completedNote', { count: completedSinceLast })}
        </p>
      )}

      <p className="mt-3 text-[10px] text-slate-400 leading-relaxed">
        {t('disclosure')}
      </p>
    </section>
  )
}

function DeltaBadge({ direction, value, suffix }: { direction: 'up' | 'down' | 'flat'; value: number; suffix: string }) {
  const tone =
    direction === 'up'   ? 'bg-emerald-50 text-emerald-700' :
    direction === 'down' ? 'bg-rose-50 text-rose-700' :
                           'bg-slate-100 text-slate-600'
  const sign = direction === 'up' ? '+' : direction === 'down' ? '' : '±'
  return (
    <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-bold tabular-nums ${tone}`}>
      {sign}{value} {suffix}
    </span>
  )
}

function DriftRow({
  label, change, t,
}: {
  label: string
  change: -1 | 0 | 1
  t: ReturnType<typeof useTranslations>
}) {
  const tone =
    change === 1  ? 'text-emerald-600' :
    change === -1 ? 'text-rose-600'   :
                    'text-slate-400'
  const labelKey =
    change === 1  ? 'changeUp' :
    change === -1 ? 'changeDown' :
                    'changeFlat'
  return (
    <li className="flex items-center justify-between gap-2 px-1">
      <span className="text-xs text-[#1e293b]">{label}</span>
      <span className={`text-[11px] font-bold uppercase ${tone}`}>{t(labelKey)}</span>
    </li>
  )
}

function CompetitorList({ label, names, tone }: { label: string; names: string[]; tone: 'ok' | 'warn' }) {
  const dotClass = tone === 'warn' ? 'bg-rose-400' : 'bg-emerald-400'
  return (
    <div className="flex flex-col gap-1.5 mb-2 last:mb-0">
      <p className="text-[11px] font-semibold text-slate-500">{label}</p>
      <ul className="flex flex-col gap-1">
        {names.map(name => (
          <li key={name} className="text-xs text-[#1e293b] flex items-center gap-2">
            <span className={`w-1.5 h-1.5 rounded-full ${dotClass} flex-shrink-0`} aria-hidden="true" />
            {name}
          </li>
        ))}
      </ul>
    </div>
  )
}

// Lightweight relative-date formatter so we don't pull in a heavy dep.
// Uses Intl.RelativeTimeFormat for proper locale handling.
function formatRelative(iso: string): string {
  const then = new Date(iso).getTime()
  const now  = Date.now()
  const diffSeconds = Math.round((then - now) / 1000)
  const abs = Math.abs(diffSeconds)
  const fmt = new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' })
  if (abs < 60)            return fmt.format(diffSeconds, 'second')
  if (abs < 60 * 60)       return fmt.format(Math.round(diffSeconds / 60), 'minute')
  if (abs < 60 * 60 * 24)  return fmt.format(Math.round(diffSeconds / 3600), 'hour')
  if (abs < 60 * 60 * 24 * 30) return fmt.format(Math.round(diffSeconds / 86400), 'day')
  return fmt.format(Math.round(diffSeconds / (86400 * 30)), 'month')
}

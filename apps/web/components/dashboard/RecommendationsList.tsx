'use client'

import { useState, useEffect, useCallback } from 'react'
import { useTranslations } from 'next-intl'
import RecommendationCoach from './RecommendationCoach'
import {
  recommendationImpactRange,
  formatCadRange,
  type RoiBreakdown,
} from '@/lib/roi'

export interface Recommendation {
  pillar: 'gbp' | 'reviews' | 'website' | 'local_search' | 'ai_citation'
  title: string
  description: string
  action: string
  difficulty: 'easy' | 'medium' | 'hard'
  impact: number
  url?: string
}

interface Props {
  recommendations: Recommendation[]
  currentTier?: 'starter' | 'pro'
  /** Stable per-business namespace for the localStorage completion set.
   *  Falls back to "default" if not provided. */
  businessKey?: string | null
  /** ROI breakdown for the current business. When provided, each card
   *  surfaces an estimated $-range impact tag — speaks the owner's
   *  language (revenue) instead of just "+N points". Computed server-
   *  side; safe to pass through as a serializable prop. */
  roi?: RoiBreakdown | null
  /** Locale for CAD formatting (en-CA vs fr-CA). */
  locale?: string
}

/** Stable key for a recommendation — pillar + title hash. Robust across
 *  re-renders and audit re-runs (title text rarely changes). */
function recKey(r: Recommendation): string {
  return `${r.pillar}::${r.title}`
}

/** localStorage-backed set of completed recommendation keys, scoped per
 *  business. Falls back gracefully if storage is unavailable. */
function useCompletedSet(businessKey: string): {
  set: Set<string>
  mark: (k: string) => void
  unmark: (k: string) => void
  ready: boolean
} {
  const storageKey = `leapone:completed:${businessKey || 'default'}`
  const [set, setSet] = useState<Set<string>>(() => new Set())
  // SSR-safe: hydrate from localStorage on the client after mount.
  // First paint will show items as not-done; flashes to done on next tick.
  const [ready, setReady] = useState(false)
  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(storageKey)
      if (raw) setSet(new Set(JSON.parse(raw)))
    } catch { /* localStorage unavailable / parse error -> empty set */ }
    setReady(true)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [storageKey])
  const persist = useCallback((next: Set<string>) => {
    try { window.localStorage.setItem(storageKey, JSON.stringify([...next])) } catch {}
    setSet(next)
  }, [storageKey])
  const mark = useCallback((k: string) => {
    setSet(prev => {
      const next = new Set(prev)
      next.add(k)
      persist(next)
      return next
    })
  }, [persist])
  const unmark = useCallback((k: string) => {
    setSet(prev => {
      const next = new Set(prev)
      next.delete(k)
      persist(next)
      return next
    })
  }, [persist])
  return { set, mark, unmark, ready }
}

const PILLAR_ORDER: Recommendation['pillar'][] = [
  'gbp', 'reviews', 'website', 'local_search', 'ai_citation',
]

// Difficulty -> time-pill colour. Green = quick win, amber = afternoon,
// slate = long-term. Stops Multi-week items from looking like emergencies.
const TIME_PILL: Record<Recommendation['difficulty'], string> = {
  easy:   'bg-green-50 text-green-700',
  medium: 'bg-amber-50 text-amber-700',
  hard:   'bg-slate-100 text-slate-600',
}

// Maps the recommendation pillar key (snake_case) to the
// dashboard.aeo.pillars i18n key (camelCase).
const PILLAR_LABEL_KEY: Record<Recommendation['pillar'], string> = {
  gbp:          'gbp',
  reviews:      'reviews',
  website:      'website',
  local_search: 'localSearch',
  ai_citation:  'aiCitation',
}

export default function RecommendationsList({
  recommendations, currentTier = 'starter', businessKey, roi, locale = 'en',
}: Props) {
  const t = useTranslations('dashboard.recommendations')
  const tPillars = useTranslations('dashboard.aeo.pillars')
  const completion = useCompletedSet(businessKey || 'default')

  if (!recommendations || recommendations.length === 0) {
    return (
      <div className="bg-white rounded-2xl border-l-[3px] border-l-emerald-500 shadow-sm border border-slate-100 p-4">
        <p className="text-sm font-semibold text-[#1e293b]">{t('optimizedTitle')}</p>
        <p className="text-xs text-slate-500 mt-1">{t('optimizedBody')}</p>
      </div>
    )
  }

  // Split into active (not yet marked done) and completed lists.
  const active   = recommendations.filter(r => !completion.set.has(recKey(r)))
  const completed = recommendations.filter(r =>  completion.set.has(recKey(r)))

  // Hero = highest-impact ACTIVE item that isn't a multi-week project.
  const heroCandidates = active.filter(r => r.difficulty !== 'hard')
  const hero = heroCandidates.length > 0
    ? [...heroCandidates].sort((a, b) => b.impact - a.impact)[0]
    : null

  // Rest of active items grouped by pillar in canonical pillar order.
  const rest = hero ? active.filter(r => r !== hero) : active
  const groups: Partial<Record<Recommendation['pillar'], Recommendation[]>> = {}
  for (const r of rest) {
    if (!groups[r.pillar]) groups[r.pillar] = []
    groups[r.pillar]!.push(r)
  }
  for (const k of Object.keys(groups) as Recommendation['pillar'][]) {
    groups[k]!.sort((a, b) => b.impact - a.impact)
  }

  const totalPoints    = recommendations.reduce((s, r) => s + r.impact, 0)
  const earnedPoints   = completed.reduce((s, r) => s + r.impact, 0)
  const progressPct    = recommendations.length > 0
    ? Math.round((completed.length / recommendations.length) * 100)
    : 0

  return (
    <div className="flex flex-col gap-5">
      {/* Progress + summary */}
      <div>
        <div className="flex items-baseline justify-between mb-1.5">
          <p className="text-sm font-semibold text-[#1e293b]">
            {t('progressLine', { done: completed.length, total: recommendations.length })}
          </p>
          <p className="text-xs text-slate-500">
            {t('progressPoints', { points: earnedPoints })}
            <span className="text-slate-300 mx-1.5">/</span>
            {t('totalPoints', { points: totalPoints })}
          </p>
        </div>
        <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
          <div className="h-full bg-emerald-500 rounded-full transition-all"
               style={{ width: `${progressPct}%` }} />
        </div>
      </div>

      {/* Hero "Start with this" card (only from active items) */}
      {hero && (
        <HeroRecCard
          rec={hero}
          recommendationKey="hero"
          currentTier={currentTier}
          completion={completion}
          roi={roi}
          locale={locale}
        />
      )}

      {/* Active pillar groups */}
      {PILLAR_ORDER.map(pillar => {
        const items = groups[pillar]
        if (!items || items.length === 0) return null
        const pillarPoints = items.reduce((s, r) => s + r.impact, 0)
        return (
          <div key={pillar}>
            <div className="flex items-baseline justify-between mb-2 px-1">
              <h3 className="text-sm font-extrabold text-[#1e293b]">
                {tPillars(PILLAR_LABEL_KEY[pillar])}
              </h3>
              <span className="text-xs text-slate-500">
                {t('itemsCount', { count: items.length })}
                <span className="text-slate-300 mx-1">·</span>
                {t('pillarPoints', { points: pillarPoints })}
              </span>
            </div>
            <div className="flex flex-col gap-2">
              {items.map((r, i) => (
                <RecCard
                  key={`${pillar}-${i}`}
                  rec={r}
                  recommendationKey={`${pillar}-${i}-${r.title}`}
                  currentTier={currentTier}
                  completion={completion}
                  roi={roi}
                  locale={locale}
                />
              ))}
            </div>
          </div>
        )
      })}

      {/* Completed section (collapsed by default) */}
      {completed.length > 0 && <CompletedSection items={completed} completion={completion} />}
    </div>
  )
}

/** Completed list — collapsed by default so the active items stay the focus. */
function CompletedSection({
  items, completion,
}: {
  items: Recommendation[]
  completion: ReturnType<typeof useCompletedSet>
}) {
  const t = useTranslations('dashboard.recommendations')
  const [open, setOpen] = useState(false)
  return (
    <div className="border-t border-slate-100 pt-4">
      <button type="button"
              onClick={() => setOpen(o => !o)}
              aria-expanded={open}
              className="w-full flex items-baseline justify-between mb-2 px-1 text-left hover:opacity-80 transition-opacity">
        <h3 className="text-sm font-extrabold text-emerald-700">
          {t('completedSection.title')} <span className="text-emerald-600">({items.length})</span>
        </h3>
        <span className="text-xs text-slate-400" aria-hidden="true">{open ? '−' : '+'}</span>
      </button>
      {open && (
        <>
          <p className="text-xs text-slate-500 mb-2 px-1">{t('completedSection.subtitle')}</p>
          <div className="flex flex-col gap-2">
            {items.map((r, i) => (
              <CompletedRow key={i} rec={r} onUndo={() => completion.unmark(recKey(r))} />
            ))}
          </div>
        </>
      )}
    </div>
  )
}

function CompletedRow({
  rec, onUndo,
}: {
  rec: Recommendation
  onUndo: () => void
}) {
  const t = useTranslations('dashboard.recommendations')
  return (
    <div className="bg-emerald-50/40 border border-emerald-100 rounded-xl px-4 py-3 flex items-center gap-3">
      <span className="flex-shrink-0 w-7 h-7 rounded-full bg-emerald-100 flex items-center justify-center text-emerald-700 text-sm font-bold">✓</span>
      <div className="flex-1 min-w-0">
        <p className="text-sm text-slate-600 line-through truncate">{rec.title}</p>
      </div>
      <button type="button" onClick={onUndo}
              className="text-xs font-medium text-slate-500 hover:text-[#4f46e5] hover:underline">
        {t('unmark')}
      </button>
    </div>
  )
}

// ─── Standard recommendation card ────────────────────────────────────────
function RecCard({
  rec, recommendationKey, currentTier, completion, roi, locale = 'en',
}: {
  rec: Recommendation
  recommendationKey: string
  currentTier: 'starter' | 'pro'
  completion: ReturnType<typeof useCompletedSet>
  roi?: RoiBreakdown | null
  locale?: string
}) {
  const t = useTranslations('dashboard.recommendations')
  const [expanded, setExpanded] = useState(false)
  const [coachOpen, setCoachOpen] = useState(false)
  const dollarRange = roi ? recommendationImpactRange(rec.pillar, rec.impact, roi) : null

  return (
    <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
      <button
        type="button"
        onClick={() => setExpanded(e => !e)}
        aria-expanded={expanded}
        className="w-full flex items-start gap-3 p-4 hover:bg-slate-50 transition-colors text-left">
        <div className="flex-shrink-0 w-9 h-9 rounded-full bg-amber-50 flex items-center justify-center mt-0.5">
          <span className="text-xs font-bold text-amber-700">+{rec.impact}</span>
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1.5 flex-wrap">
            <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${TIME_PILL[rec.difficulty]}`}>
              {t(`difficulty.${rec.difficulty}`)}
            </span>
            {dollarRange && (
              <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 tabular-nums"
                    title={t('dollarTagTooltip')}>
                ~{formatCadRange(dollarRange, locale)}{' '}{t('perMonthShort')}
              </span>
            )}
          </div>
          <p className="text-sm font-semibold text-[#1e293b] mb-1">{rec.title}</p>
          <p className="text-xs text-slate-600 leading-relaxed">{rec.description}</p>
        </div>
        <span className="text-slate-400 text-sm flex-shrink-0 mt-1" aria-hidden="true">
          {expanded ? '−' : '+'}
        </span>
      </button>

      {expanded && (
        <ExpandedActions
          rec={rec}
          recommendationKey={recommendationKey}
          currentTier={currentTier}
          coachOpen={coachOpen}
          onToggleCoach={() => setCoachOpen(o => !o)}
          onMarkDone={() => completion.mark(recKey(rec))}
        />
      )}
    </div>
  )
}

// ─── Hero recommendation card (featured "start with this") ───────────────
function HeroRecCard({
  rec, recommendationKey, currentTier, completion, roi, locale = 'en',
}: {
  rec: Recommendation
  recommendationKey: string
  currentTier: 'starter' | 'pro'
  completion: ReturnType<typeof useCompletedSet>
  roi?: RoiBreakdown | null
  locale?: string
}) {
  const t = useTranslations('dashboard.recommendations')
  const [expanded, setExpanded] = useState(true) // hero opens by default
  const [coachOpen, setCoachOpen] = useState(false)
  const dollarRange = roi ? recommendationImpactRange(rec.pillar, rec.impact, roi) : null

  return (
    <div className="bg-gradient-to-br from-indigo-50 to-white border border-indigo-200 rounded-2xl overflow-hidden shadow-sm">
      <div className="px-5 pt-4 pb-3 border-b border-indigo-100/60">
        <div className="flex items-center justify-between mb-1">
          <span className="text-[10px] font-bold text-[#4f46e5] tracking-wider">
            {t('startHere.label')}
          </span>
          <span className="text-[10px] text-slate-500">
            {t('startHere.subtitle')}
          </span>
        </div>
      </div>
      <button
        type="button"
        onClick={() => setExpanded(e => !e)}
        aria-expanded={expanded}
        className="w-full flex items-start gap-3 px-5 py-4 hover:bg-white/60 transition-colors text-left">
        <div className="flex-shrink-0 w-11 h-11 rounded-full bg-[#4f46e5] flex items-center justify-center mt-0.5">
          <span className="text-sm font-bold text-white">+{rec.impact}</span>
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-2 flex-wrap">
            <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${TIME_PILL[rec.difficulty]}`}>
              {t(`difficulty.${rec.difficulty}`)}
            </span>
            {dollarRange && (
              <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 tabular-nums"
                    title={t('dollarTagTooltip')}>
                ~{formatCadRange(dollarRange, locale)}{' '}{t('perMonthShort')}
              </span>
            )}
          </div>
          <p className="text-base font-extrabold text-[#1e293b] mb-1.5 leading-snug">{rec.title}</p>
          <p className="text-sm text-slate-700 leading-relaxed">{rec.description}</p>
        </div>
        <span className="text-slate-400 text-base flex-shrink-0 mt-1" aria-hidden="true">
          {expanded ? '−' : '+'}
        </span>
      </button>

      {expanded && (
        <ExpandedActions
          rec={rec}
          recommendationKey={recommendationKey}
          currentTier={currentTier}
          coachOpen={coachOpen}
          onToggleCoach={() => setCoachOpen(o => !o)}
          onMarkDone={() => completion.mark(recKey(rec))}
        />
      )}
    </div>
  )
}

// ─── Shared expanded body (action steps + link + coach + mark done) ──────
function ExpandedActions({
  rec, recommendationKey, currentTier, coachOpen, onToggleCoach, onMarkDone,
}: {
  rec: Recommendation
  recommendationKey: string
  currentTier: 'starter' | 'pro'
  coachOpen: boolean
  onToggleCoach: () => void
  onMarkDone: () => void
}) {
  const t = useTranslations('dashboard.recommendations')
  return (
    <div className="px-5 pb-4 pt-1 bg-white/60 border-t border-slate-100">
      <div className="bg-white border border-slate-200 rounded-lg p-3 mb-3">
        <p className="text-[10px] font-bold text-slate-500 uppercase tracking-wide mb-1.5">
          {t('whatToDo')}
        </p>
        <p className="text-sm text-[#1e293b] leading-relaxed">{rec.action}</p>
      </div>

      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div className="flex items-center gap-2 flex-wrap">
          {rec.url && (
            <a href={rec.url} target="_blank" rel="noopener noreferrer"
               className="inline-flex items-center gap-1 text-xs font-semibold text-[#4f46e5] hover:text-indigo-700 hover:underline">
              {t('openLink')}
            </a>
          )}
          <button
            type="button"
            onClick={onMarkDone}
            className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-700
                       bg-emerald-50 hover:bg-emerald-100 border border-emerald-200
                       px-3 py-1.5 rounded-lg transition-colors">
            ✓ {t('markDone')}
          </button>
        </div>
        <button
          type="button"
          onClick={onToggleCoach}
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-white
                     bg-[#4f46e5] hover:bg-indigo-700 px-3 py-1.5 rounded-lg transition-colors">
          🤝 {coachOpen ? t('hideHelp') : t('getHelp')}
        </button>
      </div>

      {coachOpen && (
        <div className="mt-3">
          <RecommendationCoach
            recommendation={{
              title:       rec.title,
              description: rec.description,
              action:      rec.action,
              pillar:      rec.pillar,
              url:         rec.url,
              impact:      rec.impact,
            }}
            recommendationKey={recommendationKey}
            currentTier={currentTier}
          />
        </div>
      )}
    </div>
  )
}

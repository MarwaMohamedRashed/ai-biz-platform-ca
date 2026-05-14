'use client'

import { useState } from 'react'
import { useTranslations } from 'next-intl'
import RecommendationCoach from './RecommendationCoach'

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

export default function RecommendationsList({ recommendations, currentTier = 'starter' }: Props) {
  const t = useTranslations('dashboard.recommendations')
  const tPillars = useTranslations('dashboard.aeo.pillars')

  if (!recommendations || recommendations.length === 0) {
    return (
      <div className="bg-white rounded-2xl border-l-[3px] border-l-emerald-500 shadow-sm border border-slate-100 p-4">
        <p className="text-sm font-semibold text-[#1e293b]">{t('optimizedTitle')}</p>
        <p className="text-xs text-slate-500 mt-1">{t('optimizedBody')}</p>
      </div>
    )
  }

  // Hero = highest-impact item that isn't a multi-week project. Owners get
  // a clear "do this first" without scrolling through long-term work.
  const heroCandidates = recommendations.filter(r => r.difficulty !== 'hard')
  const hero = heroCandidates.length > 0
    ? [...heroCandidates].sort((a, b) => b.impact - a.impact)[0]
    : null

  // Everything else grouped by pillar in the canonical pillar order.
  const rest = hero ? recommendations.filter(r => r !== hero) : recommendations
  const groups: Partial<Record<Recommendation['pillar'], Recommendation[]>> = {}
  for (const r of rest) {
    if (!groups[r.pillar]) groups[r.pillar] = []
    groups[r.pillar]!.push(r)
  }
  for (const k of Object.keys(groups) as Recommendation['pillar'][]) {
    groups[k]!.sort((a, b) => b.impact - a.impact)
  }

  const totalPoints = recommendations.reduce((s, r) => s + r.impact, 0)

  return (
    <div className="flex flex-col gap-5">
      {/* Summary line */}
      <p className="text-sm text-slate-600">
        {t('actionsCount', { count: recommendations.length })}
        <span className="text-slate-300 mx-1.5">·</span>
        {t('totalPoints', { points: totalPoints })}
      </p>

      {/* Hero "Start with this" card */}
      {hero && (
        <HeroRecCard
          rec={hero}
          recommendationKey="hero"
          currentTier={currentTier}
        />
      )}

      {/* Pillar groups */}
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
                />
              ))}
            </div>
          </div>
        )
      })}
    </div>
  )
}

// ─── Standard recommendation card ────────────────────────────────────────
function RecCard({
  rec, recommendationKey, currentTier,
}: {
  rec: Recommendation
  recommendationKey: string
  currentTier: 'starter' | 'pro'
}) {
  const t = useTranslations('dashboard.recommendations')
  const [expanded, setExpanded] = useState(false)
  const [coachOpen, setCoachOpen] = useState(false)

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
          <div className="flex items-center gap-2 mb-1.5">
            <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${TIME_PILL[rec.difficulty]}`}>
              {t(`difficulty.${rec.difficulty}`)}
            </span>
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
        />
      )}
    </div>
  )
}

// ─── Hero recommendation card (featured "start with this") ───────────────
function HeroRecCard({
  rec, recommendationKey, currentTier,
}: {
  rec: Recommendation
  recommendationKey: string
  currentTier: 'starter' | 'pro'
}) {
  const t = useTranslations('dashboard.recommendations')
  const [expanded, setExpanded] = useState(true) // hero opens by default
  const [coachOpen, setCoachOpen] = useState(false)

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
          <div className="flex items-center gap-2 mb-2">
            <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${TIME_PILL[rec.difficulty]}`}>
              {t(`difficulty.${rec.difficulty}`)}
            </span>
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
        />
      )}
    </div>
  )
}

// ─── Shared expanded body (action steps + link + coach) ──────────────────
function ExpandedActions({
  rec, recommendationKey, currentTier, coachOpen, onToggleCoach,
}: {
  rec: Recommendation
  recommendationKey: string
  currentTier: 'starter' | 'pro'
  coachOpen: boolean
  onToggleCoach: () => void
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
        {rec.url ? (
          <a href={rec.url} target="_blank" rel="noopener noreferrer"
             className="inline-flex items-center gap-1 text-xs font-semibold text-[#4f46e5] hover:text-indigo-700 hover:underline">
            {t('openLink')}
          </a>
        ) : <span />}
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

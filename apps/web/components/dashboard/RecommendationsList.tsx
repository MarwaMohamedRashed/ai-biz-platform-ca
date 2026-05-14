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

const PILLAR_COLORS: Record<Recommendation['pillar'], string> = {
  gbp:          'bg-indigo-50 text-indigo-700',
  reviews:      'bg-amber-50 text-amber-700',
  website:      'bg-emerald-50 text-emerald-700',
  local_search: 'bg-sky-50 text-sky-700',
  ai_citation:  'bg-purple-50 text-purple-700',
}

interface Props {
  recommendations: Recommendation[]
  currentTier?: 'starter' | 'pro'
}

export default function RecommendationsList({ recommendations, currentTier = 'starter' }: Props) {
  const t = useTranslations('dashboard.recommendations')
  const [expanded, setExpanded] = useState<number | null>(null)
  const [coachOpen, setCoachOpen] = useState<number | null>(null)

  if (!recommendations || recommendations.length === 0) {
    return (
      <div className="bg-white rounded-2xl border-l-[3px] border-l-emerald-500 shadow-sm border border-slate-100 p-4">
        <p className="text-sm font-semibold text-[#1e293b]">{t('optimizedTitle')}</p>
        <p className="text-xs text-slate-500 mt-1">{t('optimizedBody')}</p>
      </div>
    )
  }

  return (
    <div className="bg-white rounded-2xl border-l-[3px] border-l-amber-400 shadow-sm border border-slate-100 p-4">
      <div className="flex items-baseline justify-between mb-3">
        <span className="text-[10px] font-bold text-amber-600 uppercase tracking-wider">{t('label')}</span>
        <span className="text-[10px] text-slate-400">{t('actionsCount', { count: recommendations.length })}</span>
      </div>
      <p className="text-xs text-slate-500 mb-3">{t('subtitle')}</p>

      <div className="flex flex-col gap-2">
        {recommendations.map((r, i) => (
          <div key={i} className="border border-slate-100 rounded-xl overflow-hidden">
            <button
              onClick={() => setExpanded(expanded === i ? null : i)}
              className="w-full flex items-center gap-3 p-3 hover:bg-slate-50 transition-colors text-left"
            >
              <div className="flex-shrink-0 w-7 h-7 rounded-full bg-amber-50 flex items-center justify-center">
                <span className="text-xs font-bold text-amber-700">+{r.impact}</span>
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-0.5">
                  <span className={`text-[9px] font-semibold px-1.5 py-0.5 rounded ${PILLAR_COLORS[r.pillar]}`}>
                    {t(`pillars.${r.pillar}`)}
                  </span>
                  <span className="text-[9px] text-slate-400">{t(`difficulty.${r.difficulty}`)}</span>
                </div>
                <p className="text-xs font-semibold text-[#1e293b] truncate">{r.title}</p>
              </div>
              <span className="text-slate-400 text-xs flex-shrink-0">
                {expanded === i ? '−' : '+'}
              </span>
            </button>

            {expanded === i && (
              <div className="px-3 pb-3 pt-1 bg-slate-50 border-t border-slate-100">
                <p className="text-xs text-slate-600 mb-2 leading-relaxed">{r.description}</p>
                <div className="bg-white border border-slate-200 rounded-lg p-2.5 mb-2">
                  <p className="text-[10px] font-bold text-slate-500 uppercase tracking-wide mb-1">{t('whatToDo')}</p>
                  <p className="text-xs text-[#1e293b] leading-relaxed">{r.action}</p>
                </div>
                <div className="flex items-center justify-between gap-2 flex-wrap">
                  {r.url ? (
                    <a
                      href={r.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 text-[11px] font-semibold text-[#4f46e5] hover:text-indigo-700"
                    >
                      {t('openLink')}
                    </a>
                  ) : <span />}
                  <button
                    onClick={() => setCoachOpen(coachOpen === i ? null : i)}
                    className="inline-flex items-center gap-1 text-[11px] font-semibold text-white
                               bg-[#4f46e5] hover:bg-indigo-700 px-2.5 py-1 rounded-lg transition-colors"
                  >
                    🤝 {coachOpen === i ? t('hideHelp') : t('getHelp')}
                  </button>
                </div>

                {coachOpen === i && (
                  <RecommendationCoach
                    recommendation={{
                      title: r.title,
                      description: r.description,
                      action: r.action,
                      pillar: r.pillar,
                      url: r.url,
                      impact: r.impact,
                    }}
                    recommendationKey={`${i}-${r.title}`}
                    currentTier={currentTier}
                  />
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

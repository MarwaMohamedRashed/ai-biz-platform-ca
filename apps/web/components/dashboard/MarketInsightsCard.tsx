'use client'

import { useState } from 'react'
import { useTranslations } from 'next-intl'
import type { MarketInsightsSummary } from '@/lib/market-intelligence'

// Dashboard Monthly Insights card — Phase 5 of the market intelligence layer.
//
// Shows: top 10 questions in the business's (vertical, city) market, which
// ones the business appears in, the top-4 area leaderboard, and a vertical
// benchmark bar. MoM delta shown when prior audit has market_visibility data.
//
// Three tabs: Questions | Leaderboard | Benchmarks
// Source: market_intelligence table, fetched server-side in dashboard/page.tsx
// and passed as a pre-processed summary (no raw mention data on the client).

interface Props {
  insights: MarketInsightsSummary | null
  locale: string
}

type Tab = 'questions' | 'demand' | 'leaderboard' | 'benchmarks'

export default function MarketInsightsCard({ insights, locale }: Props) {
  const t = useTranslations('dashboard.marketInsights')
  const [tab, setTab] = useState<Tab>('questions')

  // No data yet (market row exists but refresh hasn't run, or no market row)
  if (!insights) {
    return (
      <section className="rounded-2xl border border-slate-100 bg-white p-5 md:p-6">
        <Header t={t} insights={null} />
        <p className="mt-4 text-sm text-slate-500 leading-relaxed">
          {t('buildingArea')}
        </p>
      </section>
    )
  }

  const hasQuestions = insights.topQuestions.length > 0
  const hasBiz       = insights.topBusinesses.length > 0
  const hasBenchmarks = (insights.benchmarks.sampleSize ?? 0) >= 5

  return (
    <section className="rounded-2xl border border-slate-100 bg-white overflow-hidden">
      <div className="px-5 pt-5 md:px-6 md:pt-6">
        <Header t={t} insights={insights} />

        {/* MoM share change callout */}
        {insights.momShareChange != null && (
          <MomBadge change={insights.momShareChange} t={t} />
        )}

        {/* Tab bar */}
        <div className="mt-4 flex gap-1 border-b border-slate-100">
          {(['questions', 'demand', 'leaderboard', 'benchmarks'] as Tab[]).map(id => (
            <button
              key={id}
              type="button"
              onClick={() => setTab(id)}
              className={`px-3 py-2 text-xs font-semibold rounded-t transition-colors ${
                tab === id
                  ? 'bg-indigo-50 text-indigo-700 border-b-2 border-indigo-500'
                  : 'text-slate-500 hover:text-slate-700'
              }`}
            >
              {t(`tab.${id}`)}
            </button>
          ))}
        </div>
      </div>

      <div className="px-5 pb-5 md:px-6 md:pb-6 pt-4">
        {tab === 'questions' && (
          hasQuestions
            ? <QuestionsTab questions={insights.topQuestions} t={t} />
            : <EmptyTab t={t} />
        )}
        {tab === 'demand' && (
          <DemandTab demand={insights.categoryDemand} locale={locale} t={t} />
        )}
        {tab === 'leaderboard' && (
          hasBiz
            ? <LeaderboardTab businesses={insights.topBusinesses} t={t} />
            : <EmptyTab t={t} />
        )}
        {tab === 'benchmarks' && (
          hasBenchmarks
            ? <BenchmarksTab b={insights.benchmarks} t={t} />
            : <p className="text-sm text-slate-500">{t('benchmarksNotReady')}</p>
        )}
      </div>
    </section>
  )
}

// ── Sub-components ─────────────────────────────────────────────────────────

function Header({ t, insights }: { t: ReturnType<typeof useTranslations>; insights: MarketInsightsSummary | null }) {
  const statusColor =
    insights?.refreshStatus === 'failed'    ? 'bg-rose-100 text-rose-700' :
    insights?.refreshStatus === 'stale'     ? 'bg-amber-100 text-amber-700' :
    insights?.refreshStatus === 'refreshing'? 'bg-blue-100 text-blue-700' :
                                              'bg-emerald-100 text-emerald-700'

  return (
    <div className="flex items-start justify-between gap-3">
      <div>
        <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
          {t('eyebrow')}
        </span>
        <h2 className="text-base font-bold text-[#1e293b] mt-0.5">
          {insights ? t('headline', { city: insights.city }) : t('headlineFallback')}
        </h2>
        {insights && (
          <p className="text-[11px] text-slate-400 mt-0.5">
            {t('refreshedAt', {
              date: new Date(insights.refreshedAt).toLocaleDateString(
                'en-CA', { month: 'short', day: 'numeric', year: 'numeric' }
              ),
            })}
          </p>
        )}
      </div>
      {insights && (
        <span className={`shrink-0 text-[10px] font-semibold px-2 py-0.5 rounded-full ${statusColor}`}>
          {t(`status.${insights.refreshStatus}`) }
        </span>
      )}
    </div>
  )
}

function MomBadge({ change, t }: { change: number; t: ReturnType<typeof useTranslations> }) {
  const pct = Math.round(Math.abs(change) * 100)
  if (pct === 0) return null
  const up = change > 0
  return (
    <p className={`mt-2 text-[11px] font-semibold ${up ? 'text-emerald-600' : 'text-rose-500'}`}>
      {up ? '▲' : '▼'} {pct}% {up ? t('momUp') : t('momDown')}
    </p>
  )
}

function QuestionsTab({ questions, t }: {
  questions: MarketInsightsSummary['topQuestions']
  t: ReturnType<typeof useTranslations>
}) {
  return (
    <div className="overflow-x-auto -mx-1">
      <table className="w-full text-xs">
        <thead>
          <tr className="text-left text-slate-400 border-b border-slate-100">
            <th className="pb-2 font-semibold pr-3 min-w-[160px]">{t('col.question')}</th>
            <th className="pb-2 font-semibold pr-3 text-right">{t('col.volume')}</th>
            <th className="pb-2 font-semibold pr-3">{t('col.intent')}</th>
            <th className="pb-2 font-semibold text-center">{t('col.mentioned')}</th>
          </tr>
        </thead>
        <tbody>
          {questions.map((q, i) => (
            <tr key={i} className="border-b border-slate-50 last:border-0">
              <td className="py-2 pr-3 text-slate-700 leading-snug max-w-[200px]">
                {q.question}
              </td>
              <td className="py-2 pr-3 text-right tabular-nums text-slate-500">
                {q.searchVolume != null
                  ? q.searchVolume.toLocaleString('en-CA')
                  : <span className="text-slate-300">—</span>
                }
              </td>
              <td className="py-2 pr-3">
                <IntentBadge intent={q.intent} t={t} />
              </td>
              <td className="py-2 text-center">
                {q.mentioned
                  ? <span className="text-emerald-500 font-bold" title={t('mentionedYes')}>✓</span>
                  : <span className="text-slate-300" title={t('mentionedNo')}>—</span>
                }
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function IntentBadge({ intent, t }: { intent: string; t: ReturnType<typeof useTranslations> }) {
  const cls =
    intent === 'commercial'    ? 'bg-indigo-50 text-indigo-600' :
    intent === 'informational' ? 'bg-slate-100 text-slate-500' :
                                 'bg-amber-50 text-amber-600'
  return (
    <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${cls}`}>
      {t(`intent.${intent}`) }
    </span>
  )
}

function LeaderboardTab({ businesses, t }: {
  businesses: MarketInsightsSummary['topBusinesses']
  t: ReturnType<typeof useTranslations>
}) {
  const maxScore = Math.max(...businesses.map(b => b.weightedScore), 0.01)
  return (
    <ol className="space-y-3">
      {businesses.map((b, i) => (
        <li key={i} className="flex items-center gap-3">
          <span className="w-5 text-center text-[11px] font-bold text-slate-400 shrink-0">
            {i + 1}
          </span>
          <div className="flex-1 min-w-0">
            <div className="flex items-center justify-between mb-1 gap-2">
              <span className="text-xs font-semibold text-slate-700 truncate">{b.name}</span>
              <span className="text-[10px] text-slate-400 shrink-0 tabular-nums">
                {b.mentionCount} {t('mentions')}
              </span>
            </div>
            <div className="h-1.5 w-full rounded-full bg-slate-100 overflow-hidden">
              <div
                className="h-full rounded-full bg-indigo-400"
                style={{ width: `${Math.round((b.weightedScore / maxScore) * 100)}%` }}
              />
            </div>
          </div>
        </li>
      ))}
    </ol>
  )
}

function BenchmarksTab({ b, t }: {
  b: MarketInsightsSummary['benchmarks']
  t: ReturnType<typeof useTranslations>
}) {
  const markers = [
    { label: t('bench.yours'), value: b.yourShare, color: '#4f46e5' },
    { label: t('bench.avg'),   value: b.avgShare,  color: '#94a3b8' },
    { label: t('bench.p75'),   value: b.p75Share,  color: '#f97316' },
  ].filter(m => m.value != null) as { label: string; value: number; color: string }[]

  const topShare = b.topShare ?? 1
  const topPct = Math.max(topShare * 100, 1)

  return (
    <div className="space-y-4">
      {/* Bar */}
      <div>
        <div className="relative h-3 w-full rounded-full bg-slate-100 overflow-visible">
          {/* Shaded region: avg → p75 */}
          {b.avgShare != null && b.p75Share != null && (
            <div
              className="absolute h-full bg-slate-200/60 rounded-full"
              style={{
                left:  `${(b.avgShare / topPct) * 100}%`,
                width: `${((b.p75Share - b.avgShare) / topPct) * 100}%`,
              }}
            />
          )}
          {markers.map(m => (
            <div
              key={m.label}
              className="absolute top-1/2 -translate-y-1/2 w-2 h-4 rounded-full border-2 border-white shadow"
              style={{
                left:            `${Math.min(98, (m.value / topPct) * 100)}%`,
                backgroundColor: m.color,
              }}
              title={`${m.label}: ${Math.round(m.value * 100)}%`}
            />
          ))}
        </div>
        <div className="flex justify-between text-[10px] text-slate-400 mt-1">
          <span>0%</span>
          <span>{Math.round(topPct)}%</span>
        </div>
      </div>

      {/* Legend */}
      <dl className="grid grid-cols-[auto,1fr] gap-x-3 gap-y-1.5 text-xs">
        {markers.map(m => (
          <>
            <dt key={`l-${m.label}`} className="flex items-center gap-1.5">
              <span className="inline-block w-2.5 h-2.5 rounded-full" style={{ backgroundColor: m.color }} />
              <span className="font-medium text-slate-600">{m.label}</span>
            </dt>
            <dd key={`v-${m.label}`} className="text-slate-700 tabular-nums font-semibold">
              {Math.round(m.value * 100)}%
            </dd>
          </>
        ))}
      </dl>

      <p className="text-[10.5px] text-slate-400 leading-relaxed">
        {t('benchNote', { n: b.sampleSize })}
      </p>
    </div>
  )
}

function DemandTab({ demand, locale, t }: {
  demand: MarketInsightsSummary['categoryDemand']
  locale: string
  t: ReturnType<typeof useTranslations>
}) {
  const fmt = (n: number) => n.toLocaleString(locale === 'fr' ? 'fr-CA' : 'en-CA')
  const growth = demand.momGrowthPct
  const growthUp = (growth ?? 0) > 0
  const coverage = demand.coveragePct

  return (
    <div className="space-y-5">
      {/* Demand headline: total category volume + MoM growth */}
      <div>
        <div className="flex items-baseline gap-2">
          <span className="text-2xl font-extrabold text-[#1e293b] tabular-nums">
            {fmt(demand.totalVolume)}
          </span>
          <span className="text-xs text-slate-400">{t('demand.searchesPerMonth')}</span>
        </div>
        {growth != null
          ? (
            <p className={`mt-1 text-xs font-semibold ${growthUp ? 'text-emerald-600' : 'text-rose-500'}`}>
              {growthUp ? '▲' : '▼'} {Math.abs(Math.round(growth * 100))}% {t('demand.vsLastMonth')}
            </p>
          )
          : <p className="mt-1 text-[11px] text-slate-400">{t('demand.noHistory')}</p>
        }
      </div>

      {/* Coverage vs demand: the "demand grew, did you keep up?" line */}
      {coverage != null && (
        <p className="text-xs text-slate-600 leading-relaxed bg-slate-50 rounded-lg px-3 py-2">
          {t('demand.coverageLine', { pct: Math.round(coverage * 100) })}
          {growth != null && growthUp && coverage < 0.5 && (
            <span className="text-amber-600 font-medium"> {t('demand.coverageWarn')}</span>
          )}
        </p>
      )}

      {/* Rising queries */}
      {demand.risingKeywords.length > 0 && (
        <div>
          <h3 className="text-[11px] font-bold uppercase tracking-wider text-slate-500 mb-2">
            {t('demand.rising')}
          </h3>
          <ul className="space-y-1.5">
            {demand.risingKeywords.map((r, i) => (
              <li key={i} className="flex items-center justify-between gap-2 text-xs">
                <span className="text-slate-700 truncate">{r.keyword}</span>
                <span className="text-emerald-600 font-semibold shrink-0 tabular-nums">
                  ▲ {Math.round(r.changePct * 100)}%
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Citation sources — where AI/Google point for these questions */}
      {demand.topSources.length > 0 && (
        <div>
          <h3 className="text-[11px] font-bold uppercase tracking-wider text-slate-500 mb-2">
            {t('demand.sources')}
          </h3>
          <div className="flex flex-wrap gap-1.5">
            {demand.topSources.map((s, i) => (
              <span
                key={i}
                className={`text-[11px] font-medium px-2 py-0.5 rounded-full ${
                  s.isDirectory
                    ? 'bg-indigo-50 text-indigo-600'
                    : 'bg-slate-100 text-slate-500'
                }`}
                title={s.domain}
              >
                {s.label}
              </span>
            ))}
          </div>
          <p className="mt-2 text-[10.5px] text-slate-400 leading-relaxed">
            {t('demand.sourcesNote')}
          </p>
        </div>
      )}

      {demand.risingKeywords.length === 0 && demand.topSources.length === 0 && growth == null && (
        <EmptyTab t={t} />
      )}
    </div>
  )
}

function EmptyTab({ t }: { t: ReturnType<typeof useTranslations> }) {
  return <p className="text-sm text-slate-400">{t('noData')}</p>
}

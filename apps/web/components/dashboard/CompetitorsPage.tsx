'use client'

import type { ReactNode } from 'react'
import Link from 'next/link'
import OwnReputationCard from '@/components/dashboard/OwnReputationCard'

interface Breakdown {
  gbp: number
  reviews: number
  website: number
  local_search: number
  ai_citation: number
}

interface Competitor {
  name: string
  place_id: string | null
  rating: number | null
  reviews: number | null
  type: string | null
  website: string | null
  phone: string | null
  address: string | null
  city?: string | null
  region?: string | null
  cross_city?: boolean
  position: number
  score?: number
  breakdown?: Breakdown
  has_full_data?: boolean
  cross_border?: boolean
}

interface CompetitorTheme {
  theme: string
  count: number
  example: string
}

interface CompetitorInsights {
  themes: CompetitorTheme[]
  avg_competitor_rating: number | null
  opportunity_summary: string
  competitors_analysed: number
  reviews_analysed: number
}

interface Audit {
  score: number
  score_breakdown: Breakdown | null
  raw_results: {
    competitors?: Competitor[]
    competitor_insights?: CompetitorInsights
    google?: {
      competitors?: Competitor[]
      local_pack?: { present: boolean; position: number | null }
    }
  } | null
  created_at: string
}

interface Props {
  businessId: string | null
  businessName: string | null
  latestAudit: Audit | null
  locale: string
}

const PILLARS: { key: keyof Breakdown; label: string; max: number }[] = [
  { key: 'gbp',          label: 'GBP',     max: 25 },
  { key: 'reviews',      label: 'Reviews', max: 22 },
  { key: 'website',      label: 'Website', max: 20 },
  { key: 'local_search', label: 'Local',   max: 15 },
  { key: 'ai_citation',  label: 'AI',      max: 18 },
]

function scoreColorClass(score: number | null | undefined): string {
  if (score == null) return 'text-slate-300'
  if (score >= 70) return 'text-green-600'
  if (score >= 40) return 'text-amber-500'
  return 'text-red-500'
}

function competitorKey(c: Competitor): string {
  return c.place_id || (c.name ?? '').trim().toLowerCase()
}

// The dashboard layout's <main> uses overflow-hidden, so each page must own
// its scroll. Without this wrapper, content past the viewport gets clipped.
function PageShell({ children }: { children: ReactNode }) {
  return <div className="flex-1 overflow-y-auto">{children}</div>
}

function mergeCompetitors(scored: Competitor[], raw: Competitor[]): Competitor[] {
  // If the scored list covers everyone in raw, use it directly — it has the richer fields.
  if (scored.length >= raw.length) return scored

  // Otherwise: walk the raw list (which has more entries), and substitute the scored
  // version when the keys match. Result: max-length list with as much scoring data as we have.
  const scoredByKey = new Map<string, Competitor>()
  for (const c of scored) {
    const key = competitorKey(c)
    if (key) scoredByKey.set(key, c)
  }
  return raw.map(c => {
    const key = competitorKey(c)
    return scoredByKey.get(key) ?? c
  })
}

export default function CompetitorsPage({ businessId, businessName, latestAudit, locale }: Props) {
  if (!businessId) {
    return (
      <EmptyState
        title="Complete your profile first"
        body="We need your business name, type, and city before we can find competitors."
        ctaLabel="Go to Settings"
        ctaHref={`/${locale}/dashboard/settings`}
      />
    )
  }

  // Defensive merge across the two storage locations:
  //   raw_results.competitors      → top-level scored list (current shape, has full scoring)
  //   raw_results.google.competitors → inner unscored list (pre-W1.6 shape)
  // If the scored list is smaller than the raw one (can happen for audits written
  // mid-deploy or when scoring partially failed), use the raw list as the base
  // and enrich with scoring data for entries we can match by place_id/name.
  const competitors = mergeCompetitors(
    latestAudit?.raw_results?.competitors ?? [],
    latestAudit?.raw_results?.google?.competitors ?? [],
  )

  const userLocalPack = latestAudit?.raw_results?.google?.local_pack
  const userPosition: number | null = userLocalPack?.present ? (userLocalPack.position ?? null) : null

  if (!latestAudit) {
    return (
      <EmptyState
        title="Run an audit first"
        body="Once you run your first AEO audit, we'll automatically identify your top 3 local competitors."
        ctaLabel="Go to Dashboard"
        ctaHref={`/${locale}/dashboard`}
      />
    )
  }

  if (competitors.length === 0) {
    return (
      <PageShell>
        <div className="max-w-3xl mx-auto p-6 md:p-10">
          <Header businessName={businessName} />
          <div className="bg-white border border-slate-100 rounded-2xl p-6">
            <p className="text-sm text-slate-600">
              We couldn&apos;t identify competitors in Google&apos;s local pack for your category and city.
              This usually means there are very few similar businesses indexed nearby — which is actually
              an opportunity. Re-run the audit after a week to check again.
            </p>
          </div>
        </div>
      </PageShell>
    )
  }

  return (
    <PageShell>
      <div className="max-w-3xl mx-auto p-6 md:p-10">
        <Header businessName={businessName} />

      <p className="text-sm text-slate-600 mb-4">
        Top {competitors.length}{' '}businesses Google ranks above or alongside you for your category in your city,
        scored on the same 5-pillar formula. Per-pillar deltas show where you&apos;re ahead and where you&apos;re behind.
      </p>

      <YourScoreCard
        businessName={businessName}
        score={latestAudit.score}
        breakdown={latestAudit.score_breakdown}
        localPackPosition={userPosition}
      />

      <div className="flex flex-col gap-3 mt-4">
        {[...competitors]
          .sort((a, b) => (b.score ?? 0) - (a.score ?? 0))
          .map((c, i) => (
          <CompetitorRow
            key={c.place_id || c.name || i}
            competitor={c}
            userBreakdown={latestAudit.score_breakdown}
          />
        ))}
      </div>

      {latestAudit.raw_results?.competitor_insights &&
        Object.keys(latestAudit.raw_results.competitor_insights).length > 0 && (
        <CompetitorInsightsSection insights={latestAudit.raw_results.competitor_insights} />
      )}

      <div className="mt-4">
        <OwnReputationCard />
      </div>
    </div>
    </PageShell>
  )
}

function CompetitorInsightsSection({ insights }: { insights: CompetitorInsights }) {
  const themes = insights.themes ?? []
  const { avg_competitor_rating, opportunity_summary, competitors_analysed, reviews_analysed } = insights
  return (
    <div className="mt-6 bg-amber-50 border border-amber-200 rounded-2xl p-5">
      <div className="flex items-center gap-2 mb-1">
        <span className="text-base">💡</span>
        <h2 className="text-sm font-extrabold text-amber-900">Competitor Weaknesses — Your Opportunity</h2>
      </div>
      <p className="text-[11px] text-amber-700 mb-4">
        Analysed {reviews_analysed} customer reviews across {competitors_analysed} competitor
        {competitors_analysed !== 1 ? 's' : ''}.
        {avg_competitor_rating != null && (
          <> Average competitor rating: <strong>{avg_competitor_rating}★</strong>.</>
        )}
      </p>

      {themes.length > 0 ? (
        <div className="flex flex-col gap-2 mb-4">
          {themes.map((t, i) => (
            <div key={i} className="bg-white border border-amber-100 rounded-xl px-4 py-3">
              <div className="flex items-center justify-between mb-0.5">
                <p className="text-xs font-bold text-amber-900">{t.theme}</p>
                <span className="text-[10px] font-semibold text-amber-700 bg-amber-100 px-1.5 py-0.5 rounded-full whitespace-nowrap">
                  {t.count}× mentioned
                </span>
              </div>
              {t.example && (
                <p className="text-[10px] text-slate-500 italic">&quot;{t.example}&quot;</p>
              )}
            </div>
          ))}
        </div>
      ) : (
        <p className="text-xs text-amber-700 mb-4">No clear complaint patterns found — your competitors have strong reputations.</p>
      )}

      {opportunity_summary && (
        <div className="bg-amber-100 rounded-xl px-4 py-3">
          <p className="text-[11px] font-semibold text-amber-900">🎯 Strategic opportunity</p>
          <p className="text-xs text-amber-800 mt-0.5">{opportunity_summary}</p>
        </div>
      )}
    </div>
  )
}

function Header({ businessName }: { businessName: string | null }) {
  return (
    <div className="mb-6">
      <h1 className="text-xl font-extrabold text-[#1e293b]">Competitor Analysis</h1>
      {businessName && (
        <p className="text-xs text-slate-500 mt-1 font-medium">{businessName}</p>
      )}
    </div>
  )
}

function YourScoreCard({ businessName, score, breakdown, localPackPosition }: {
  businessName: string | null; score: number; breakdown: Breakdown | null; localPackPosition: number | null
}) {
  return (
    <div className="bg-indigo-50 border-2 border-[#4f46e5] rounded-2xl p-4">
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-[10px] font-bold text-[#4f46e5] uppercase tracking-wider">You</span>
            {localPackPosition != null ? (
              <span
                className="text-[10px] font-semibold text-indigo-700 bg-indigo-100 px-1.5 py-0.5 rounded-full cursor-default"
                title={`Your business appears at position #${localPackPosition} in Google's map results for your category and city.`}>
                #{localPackPosition} on Google Maps results
              </span>
            ) : (
              <span
                className="text-[10px] font-semibold text-red-600 bg-red-50 px-1.5 py-0.5 rounded-full cursor-default"
                title="Your business doesn't appear in Google's top map results for your category and city. This means customers searching nearby may not find you.">
                ⚠️ Not showing on Google Maps results
              </span>
            )}
          </div>
          {businessName && (
            <p className="text-sm font-semibold text-[#1e293b] truncate">{businessName}</p>
          )}
        </div>
        <p className={`text-2xl font-extrabold ${scoreColorClass(score)}`}>
          {score}<span className="text-xs font-semibold text-slate-400">/100</span>
        </p>
      </div>
      {breakdown && (
        <div className="flex flex-col gap-1.5">
          {PILLARS.map(p => (
            <PillarBar key={p.key} label={p.label} points={breakdown[p.key]} max={p.max} />
          ))}
        </div>
      )}
    </div>
  )
}

function CompetitorRow({ competitor, userBreakdown }: {
  competitor: Competitor; userBreakdown: Breakdown | null
}) {
  const ratingColor = !competitor.rating
    ? 'text-slate-400'
    : competitor.rating >= 4.5
    ? 'text-green-600'
    : competitor.rating >= 4.0
    ? 'text-amber-500'
    : 'text-red-500'

  return (
    <div className="bg-white border border-slate-100 rounded-2xl p-4">
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex items-start gap-3 min-w-0">
          <div className="w-7 h-7 rounded-full bg-indigo-50 text-[#4f46e5]
                          flex items-center justify-center text-xs font-bold flex-shrink-0">
            #{competitor.position}
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-1.5 flex-wrap">
              <p className="text-sm font-semibold text-[#1e293b] truncate">{competitor.name}</p>
              {competitor.cross_border && (
                <span className="text-[9px] font-bold text-amber-700 bg-amber-50 px-1.5 py-0.5 rounded-full whitespace-nowrap"
                  title="Google is associating this business with your category, but it's outside your country.">
                  🌍 Different country
                </span>
              )}
              {!competitor.cross_border && competitor.cross_city && (
                <span className="text-[9px] font-bold text-blue-700 bg-blue-50 px-1.5 py-0.5 rounded-full whitespace-nowrap"
                  title="This business is in a nearby city but ranks for your city's searches — a real competitive threat.">
                  📍 {competitor.city ?? 'Nearby city'}
                </span>
              )}
            </div>
            <div className="flex items-center gap-1.5 flex-wrap">
              {competitor.type && (
                <p className="text-[11px] text-slate-500 truncate">{competitor.type}</p>
              )}
              {!competitor.cross_city && competitor.city && (
                <p className="text-[11px] text-slate-400 truncate">{competitor.city}</p>
              )}
              <span
                className="text-[10px] font-semibold text-indigo-700 bg-indigo-100 px-1.5 py-0.5 rounded-full cursor-default whitespace-nowrap"
                title={`This business appears at position #${competitor.position} in Google's map results for your category and city.`}>
                #{competitor.position} on Google Maps results
              </span>
            </div>
            {competitor.address && (
              <p className="text-[10px] text-slate-400 mt-0.5 truncate" title={competitor.address}>
                {competitor.address}
              </p>
            )}
          </div>
        </div>
        <div className="text-right flex-shrink-0">
          {competitor.score != null ? (
            <p className={`text-2xl font-extrabold ${scoreColorClass(competitor.score)}`}>
              {competitor.score}<span className="text-xs font-semibold text-slate-400">/100</span>
            </p>
          ) : (
            <p className="text-xs text-slate-400">No score</p>
          )}
          {competitor.rating != null && (
            <p className={`text-[11px] font-semibold ${ratingColor}`}>
              {competitor.rating.toFixed(1)}★
              {competitor.reviews != null && (
                <span className="text-slate-500 font-normal"> · {competitor.reviews} reviews</span>
              )}
            </p>
          )}
        </div>
      </div>

      {competitor.breakdown && (
        <div className="flex flex-col gap-1.5">
          {PILLARS.map(p => (
            <PillarBar
              key={p.key}
              label={p.label}
              points={competitor.breakdown![p.key]}
              max={p.max}
              userPoints={userBreakdown?.[p.key]}
            />
          ))}
        </div>
      )}

      {competitor.has_full_data === false && (
        <p className="text-[10px] text-slate-400 italic mt-2">
          Partial data — some competitor signals couldn&apos;t be verified.
        </p>
      )}

      {(competitor.website || competitor.phone) && (
        <div className="flex items-center gap-3 mt-3 pt-3 border-t border-slate-100">
          {competitor.website && (
            <a href={competitor.website} target="_blank" rel="noopener noreferrer"
              className="text-[11px] text-[#4f46e5] hover:underline truncate max-w-[180px]">
              {competitor.website.replace(/^https?:\/\/(www\.)?/, '')}
            </a>
          )}
          {competitor.phone && (
            <span className="text-[11px] text-slate-500">{competitor.phone}</span>
          )}
        </div>
      )}
    </div>
  )
}

function PillarBar({ label, points, max, userPoints }: {
  label: string; points: number; max: number; userPoints?: number
}) {
  const pct = max === 0 ? 0 : (points / max) * 100
  const color = pct >= 75 ? 'bg-green-500' : pct >= 40 ? 'bg-amber-400' : 'bg-red-300'

  let delta: ReactNode = null
  if (userPoints != null) {
    const diff = userPoints - points
    if (diff > 0) {
      delta = <span className="text-[9px] font-bold text-green-600 w-14 text-right">you +{diff}</span>
    } else if (diff < 0) {
      delta = <span className="text-[9px] font-bold text-red-500 w-14 text-right">you {diff}</span>
    } else {
      delta = <span className="text-[9px] text-slate-400 w-14 text-right">tied</span>
    }
  }

  return (
    <div className="flex items-center gap-2">
      <span className="text-[10px] text-slate-600 w-12 flex-shrink-0">{label}</span>
      <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden flex-1">
        <div className={`h-full ${color} rounded-full`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-[10px] text-slate-500 w-10 text-right flex-shrink-0">{points}/{max}</span>
      {delta}
    </div>
  )
}

function EmptyState({ title, body, ctaLabel, ctaHref }: {
  title: string; body: string; ctaLabel: string; ctaHref: string
}) {
  return (
    <div className="max-w-xl mx-auto p-6 md:p-10 text-center">
      <h1 className="text-lg font-extrabold text-[#1e293b] mb-2">{title}</h1>
      <p className="text-sm text-slate-600 mb-4">{body}</p>
      <Link href={ctaHref}
        className="inline-block text-xs font-semibold bg-[#4f46e5] text-white px-3 py-1.5 rounded-lg hover:bg-indigo-700 transition-colors">
        {ctaLabel} →
      </Link>
    </div>
  )
}

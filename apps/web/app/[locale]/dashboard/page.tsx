import { createServerSupabaseClient } from '@/lib/supabase-server'
import { getTranslations } from 'next-intl/server'
import UserMenu from '@/components/dashboard/UserMenu'
import LanguageSwitcher from '@/components/LanguageSwitcher'
import { getLocale } from 'next-intl/server'
import AeoAuditCard from '@/components/dashboard/AeoAuditCard'
import ScoreHistoryChart from '@/components/dashboard/ScoreHistoryChart'
import DownloadPdfButton from '@/components/dashboard/DownloadPdfButton'
import AuditReportPrint from '@/components/dashboard/AuditReportPrint'
import DetectedSignalsCard from '@/components/dashboard/DetectedSignalsCard'
import RoiHeroCard from '@/components/dashboard/RoiHeroCard'
import ProgressCard from '@/components/dashboard/ProgressCard'
import MarketInsightsCard from '@/components/dashboard/MarketInsightsCard'
import RerunAuditButton from '@/components/dashboard/RerunAuditButton'
import { computeDrift } from '@/lib/audit-drift'
import { canonicalVertical, normalizeCity, buildMarketInsights, type MarketInsightsSummary } from '@/lib/market-intelligence'

function getGreetingKey(): 'morning' | 'afternoon' | 'evening' {
  const hour = new Date().getHours()
  if (hour < 12) return 'morning'
  if (hour < 17) return 'afternoon'
  return 'evening'
}

export default async function DashboardPage() {
  const supabase = await createServerSupabaseClient()
  const { data: { user } } = await supabase.auth.getUser()
  const t = await getTranslations('dashboard.chat')

  const { data: profile } = await supabase
    .from('profiles')
    .select('full_name')
    .eq('id', user!.id)
    .single()

  const { data: business } = await supabase
  .from('businesses')
  .select('id, name, type, city, province, competitor_scope, avg_customer_value_cad, monthly_new_online_customers, ltv_multiple_override')
  .limit(1)
  .single()

  // Subscription tier — gates the AI coach (Pro-only feature)
  const { data: subscription } = business
    ? await supabase
        .from('subscriptions')
        .select('plan_tier, status')
        .eq('business_id', business.id)
        .order('created_at', { ascending: false })
        .limit(1)
        .single()
    : { data: null }
  const currentTier: 'starter' | 'pro' = subscription?.plan_tier === 'pro' ? 'pro' : 'starter'

  const { data: auditHistory } = business
    ? await supabase
        .from('aeo_audits')
        .select('score, score_breakdown, raw_results, created_at')
        .eq('business_id', business.id)
        .order('created_at', { ascending: false })
        .limit(6)
    : { data: null }

  const latestAudit = auditHistory?.[0] ?? null
  const historyAsc = auditHistory ? [...auditHistory].reverse() : []
  const locale = await getLocale()

  // Market insights — fetch the cached (vertical, city) intelligence row when
  // the business is local-scoped and has location data. Skip for country/global
  // scope (they get Formula C ROI and no area leaderboard).
  let marketInsights: MarketInsightsSummary | null = null
  const isLocalScope = business?.competitor_scope !== 'country' && business?.competitor_scope !== 'global'
  if (business?.city && business.type && isLocalScope) {
    try {
      const vertical  = canonicalVertical(business.type)
      const cityNorm  = normalizeCity(business.city)
      const { data: marketRow } = await supabase
        .from('market_intelligence')
        .select('id, vertical, city, questions, top_businesses, benchmarks, refresh_status, refreshed_at')
        .eq('vertical', vertical)
        .eq('city', cityNorm)
        .eq('country', 'Canada')
        .single()

      if (marketRow && (marketRow.questions as unknown[]).length > 0) {
        const mv = (latestAudit?.raw_results as any)?.market_visibility ?? null
        const currentShare = mv?.weighted_mention_share ?? null
        const prevShare    = (auditHistory?.[1]?.raw_results as any)?.market_visibility?.weighted_mention_share ?? null
        const coveragePct  = mv?.questions_total
          ? (mv.questions_covered ?? 0) / mv.questions_total
          : null

        // Latest history snapshot holds the previous period's state (written
        // before the last refresh), so its category volume is "last month".
        let prevCategoryVolume: number | null = null
        const { data: histRow } = await supabase
          .from('market_intelligence_history')
          .select('benchmarks')
          .eq('market_id', marketRow.id)
          .order('snapshot_month', { ascending: false })
          .limit(1)
          .maybeSingle()
        prevCategoryVolume =
          (histRow?.benchmarks as any)?.category_volume_summary?.total_volume ?? null

        marketInsights = buildMarketInsights(
          marketRow as any, business.name, currentShare, prevShare,
          prevCategoryVolume, coveragePct,
        )
      }
    } catch {
      // silently degrade — card shows null state
    }
  }

  // Drift between the latest two audits powers the Progress card. The
  // helper returns null gracefully when there's only one audit so far.
  const drift = computeDrift(
    auditHistory?.map(a => ({
      score:      a.score ?? 0,
      created_at: a.created_at,
      raw_results: a.raw_results,
    })) ?? null,
  )

  // Next-monthly-report date used in the locked empty state — 30 days
  // after the latest audit. Formatted server-side for locale stability.
  const nextReportDateLabel = latestAudit
    ? new Date(new Date(latestAudit.created_at).getTime() + 30 * 86_400_000)
        .toLocaleDateString(locale === 'fr' ? 'fr-CA' : 'en-CA', {
          year: 'numeric', month: 'long', day: 'numeric',
        })
    : undefined

  // Fetch own-reputation server-side so AuditReportPrint can include it in the PDF
  type RepItem = { theme?: string; detail?: string; source?: string; example?: string }
  let ownReputation: {
    strengths: (string | RepItem)[]; weaknesses: (string | RepItem)[]; summary: string
    review_count: number; avg_rating: number | null
  } | null = null
  // Fetch translated recommendations server-side when locale != 'en' so the
  // initial page render shows content in the right language.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let initialRecommendations: any[] = latestAudit?.raw_results?.recommendations ?? []
  if (latestAudit && business) {
    try {
      const { data: { session } } = await supabase.auth.getSession()
      if (session?.access_token) {
        const [repRes, recsRes] = await Promise.all([
          fetch(
            `${process.env.NEXT_PUBLIC_API_URL}/api/v1/aeo/own-reputation`,
            { headers: { Authorization: `Bearer ${session.access_token}` }, next: { revalidate: 3600 } },
          ),
          locale !== 'en'
            ? fetch(
                `${process.env.NEXT_PUBLIC_API_URL}/api/v1/aeo/recommendations/${business.id}?locale=${locale}`,
                { headers: { Authorization: `Bearer ${session.access_token}` }, next: { revalidate: 0 } },
              )
            : null,
        ])
        if (repRes.ok) ownReputation = await repRes.json()
        if (recsRes?.ok) {
          const recsData = await recsRes.json()
          if (Array.isArray(recsData.recommendations)) initialRecommendations = recsData.recommendations
        }
      }
    } catch {
      // silently fail — reputation / recommendations fall back to cached values
    }
  } else if (latestAudit) {
    try {
      const { data: { session } } = await supabase.auth.getSession()
      if (session?.access_token) {
        const repRes = await fetch(
          `${process.env.NEXT_PUBLIC_API_URL}/api/v1/aeo/own-reputation`,
          { headers: { Authorization: `Bearer ${session.access_token}` }, next: { revalidate: 3600 } },
        )
        if (repRes.ok) ownReputation = await repRes.json()
      }
    } catch {
      // silently fail
    }
  }
  
  const fullName = profile?.full_name?.trim() || ''
  const firstName = fullName.split(' ')[0]
    || user!.email?.split('@')[0]
    || 'there'

  const initial = firstName[0].toUpperCase()
  const greetingKey = getGreetingKey()
  const reportT = await getTranslations('dashboard.report')
  const reportDate = new Date().toLocaleDateString(locale === 'fr' ? 'fr-CA' : 'en-CA', {
    year: 'numeric', month: 'long', day: 'numeric',
  })

  return (
    <div className="flex flex-col h-full">

      {/* Mobile header */}
      <header className="md:hidden flex items-center justify-between px-4 py-3
                         bg-white border-b border-slate-100 flex-shrink-0">
        <div className="flex items-center gap-2">
          <svg width="28" height="28" viewBox="0 0 40 40" fill="none">
            <rect width="40" height="40" rx="12" fill="#4f46e5"/>
            <path d="M13 10 L13 28 L27 28" stroke="white" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"/>
            <circle cx="28" cy="13" r="4" fill="#f97316"/>
          </svg>
          <span className="text-base font-extrabold tracking-tight">
            <span className="text-[#4f46e5]">Leap</span><span className="text-[#f97316]">One</span>
          </span>
        </div>
        <div className="flex items-center gap-2">
          {/* Mobile: same Re-run audit button as desktop, slightly smaller. */}
          <RerunAuditButton
            businessId={business?.id ?? null}
            hasAudit={!!latestAudit}
            locale={locale}
          />
          <UserMenu initial={initial} name={fullName} email={user!.email ?? ''} />
        </div>
      </header>

      {/* Desktop page header */}
      <div className="hidden md:flex items-center justify-between px-6 py-4
                      border-b border-slate-100 flex-shrink-0 print-hide">
        <div>
          <p className="text-xs text-slate-400">
            {new Date().toLocaleDateString('en-CA', { weekday: 'long', month: 'long', day: 'numeric' })}
          </p>
          <h1 className="text-base font-extrabold text-[#1e293b]">{t('pageTitle')}</h1>
          {business?.name && (
            <p className="text-xs text-slate-500 mt-0.5 font-medium">{business.name}</p>
          )}
        </div>
        <div className="flex items-center gap-3">
          {/* Re-run audit promoted to the page header (was buried mid-page
              inside AeoAuditCard). On success, router.refresh() re-renders
              every Server Component on the dashboard against the new audit. */}
          <RerunAuditButton
            businessId={business?.id ?? null}
            hasAudit={!!latestAudit}
            locale={locale}
          />
          {latestAudit && (
            <DownloadPdfButton businessName={business?.name ?? null} />
          )}
          <LanguageSwitcher />
          <UserMenu initial={initial} name={fullName} email={user!.email ?? ''} />
        </div>
      </div>

      {/* Page body */}
      <div className="flex-1 overflow-y-auto px-4 py-6 md:px-6">
        <div className="max-w-3xl mx-auto flex flex-col gap-4 print-area">

          {/* Print-only branded header — only visible in PDF output */}
          <div className="print-only mb-4 pb-4 border-b border-slate-200">
            <div className="flex items-center gap-3 mb-3">
              <svg width="32" height="32" viewBox="0 0 40 40" fill="none">
                <rect width="40" height="40" rx="10" fill="#4f46e5"/>
                <path d="M13 10 L13 28 L27 28" stroke="white" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"/>
                <circle cx="28" cy="13" r="4" fill="#f97316"/>
              </svg>
              <span className="text-2xl font-extrabold tracking-tight">
                <span className="text-[#4f46e5]">Leap</span><span className="text-[#f97316]">One</span>
              </span>
            </div>
            <h1 className="text-xl font-extrabold text-[#1e293b]">{reportT('title')}</h1>
            {business?.name && (
              <p className="text-sm text-slate-700 mt-1">
                <span className="text-slate-500">{reportT('preparedFor')}:</span>{' '}
                <span className="font-semibold">{business.name}</span>
              </p>
            )}
            <p className="text-xs text-slate-500 mt-0.5">
              {reportT('generatedOn')} {reportDate}
            </p>
          </div>

          {/* Greeting (screen only) */}
          <div className="print-hide">
            <p className="text-base text-[#1e293b]">
              {t(`greeting.${greetingKey}`)},{' '}
              <span className="font-semibold">{firstName}</span>.{' '}
              {t('greeting.attention')}
            </p>
          </div>

          {/* ROI hero — revenue exposure speaks the dentist's language;
              the score is now a diagnostic that lives below this card. */}
          {latestAudit && business && (
            <RoiHeroCard
              score={latestAudit.score ?? null}
              businessType={business.type ?? null}
              avgCustomerValueCad={business.avg_customer_value_cad ?? null}
              monthlyNewOnlineCustomers={business.monthly_new_online_customers ?? null}
              ltvMultipleOverride={business.ltv_multiple_override ?? null}
              locale={locale}
              marketVisibility={(latestAudit.raw_results as any)?.market_visibility ?? null}
            />
          )}

          {/* Score-history trend (renders when 2+ audits exist) */}
          {historyAsc.length >= 2 && (
            <div className="bg-white rounded-2xl shadow-sm border border-slate-100 overflow-hidden">
              <ScoreHistoryChart history={historyAsc} />
            </div>
          )}

          {/* Monthly Progress — month-over-month drift between latest two
              audits. Until the second audit lands this shows a locked
              empty state with the next-cycle unlock date. */}
          {latestAudit && (
            <ProgressCard
              drift={drift}
              businessKey={business?.name ?? null}
              nextReportDateLabel={nextReportDateLabel}
            />
          )}

          {/* Monthly Insights — market intelligence card (Phase 5). Shows top
              questions, area leaderboard, and benchmark bar for this business's
              (vertical, city). null state shows gracefully when data isn't ready. */}
          <MarketInsightsCard
            insights={marketInsights}
            locale={locale}
          />

          {/* What the scanner detected about this business — transparency
              card so the owner can spot wrong detections at a glance.
              Prefers the explicit detected_signals block (new) but falls
              back to the nested website.* fields so older audits also
              surface signals without a re-audit. */}
          {(() => {
            const raw = latestAudit?.raw_results as {
              detected_signals?: {
                cuisine?: string | null
                cuisine_parent?: string | null
                dietary_tags?: string[]
                service_tags?: string[]
              }
              website?: {
                cuisine_hint?: string | null
                cuisine_hint_parent?: string | null
                dietary_tags?: string[]
                service_tags?: string[]
              }
            } | null
            const fromBlock   = raw?.detected_signals
            const fromWebsite = raw?.website
            const signals = fromBlock ?? (fromWebsite ? {
              cuisine:        fromWebsite.cuisine_hint ?? null,
              cuisine_parent: fromWebsite.cuisine_hint_parent ?? null,
              dietary_tags:   fromWebsite.dietary_tags ?? [],
              service_tags:   fromWebsite.service_tags ?? [],
            } : null)
            return <DetectedSignalsCard signals={signals} />
          })()}

          {/* AEO audit + recommendations (screen only — AuditReportPrint covers the PDF).
              key={latestAudit?.created_at} forces a remount when a new audit
              lands so the Client Component picks up fresh props instead of
              clinging to its initial useState values. */}
          <div className="print-hide">
            <AeoAuditCard
              key={latestAudit?.created_at ?? 'no-audit'}
              businessId={business?.id ?? null}
              initialAudit={latestAudit ?? null}
              initialRecommendations={initialRecommendations}
              prevBreakdown={auditHistory?.[1]?.score_breakdown ?? null}
              locale={locale}
              currentTier={currentTier}
            />
          </div>

          {/* Print-only enhanced report — hidden on screen, rendered in PDF */}
          {latestAudit && (
            <AuditReportPrint
              audit={latestAudit}
              businessName={business?.name ?? null}
              auditDate={reportDate}
              reputation={ownReputation}
              locale={locale}
            />
          )}

        </div>
      </div>

    </div>
  )
}

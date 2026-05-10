import { createServerSupabaseClient } from '@/lib/supabase-server'
import { getTranslations } from 'next-intl/server'
import UserMenu from '@/components/dashboard/UserMenu'
import LanguageSwitcher from '@/components/LanguageSwitcher'
import { getLocale } from 'next-intl/server'
import AeoAuditCard from '@/components/dashboard/AeoAuditCard'
import ScoreHistoryChart from '@/components/dashboard/ScoreHistoryChart'

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
  .select('id, name')
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
  
  const fullName = profile?.full_name?.trim() || ''
  const firstName = fullName.split(' ')[0]
    || user!.email?.split('@')[0]
    || 'there'

  const initial = firstName[0].toUpperCase()
  const greetingKey = getGreetingKey()
  const locale = await getLocale()

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
        <UserMenu initial={initial} name={fullName} email={user!.email ?? ''} />
      </header>

      {/* Desktop page header */}
      <div className="hidden md:flex items-center justify-between px-6 py-4
                      border-b border-slate-100 flex-shrink-0">
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
          <LanguageSwitcher />
          <UserMenu initial={initial} name={fullName} email={user!.email ?? ''} />
        </div>
      </div>

      {/* Page body */}
      <div className="flex-1 overflow-y-auto px-4 py-6 md:px-6">
        <div className="max-w-3xl mx-auto flex flex-col gap-4">

          {/* Greeting */}
          <div>
            <p className="text-base text-[#1e293b]">
              {t(`greeting.${greetingKey}`)},{' '}
              <span className="font-semibold">{firstName}</span>.{' '}
              {t('greeting.attention')}
            </p>
          </div>

          {/* Score-history trend (renders when 2+ audits exist) */}
          {historyAsc.length >= 2 && (
            <div className="bg-white rounded-2xl shadow-sm border border-slate-100 overflow-hidden">
              <ScoreHistoryChart history={historyAsc} />
            </div>
          )}

          {/* AEO audit + recommendations */}
          <AeoAuditCard
            businessId={business?.id ?? null}
            initialAudit={latestAudit ?? null}
            initialRecommendations={latestAudit?.raw_results?.recommendations ?? []}
            prevBreakdown={auditHistory?.[1]?.score_breakdown ?? null}
            locale={locale}
            currentTier={currentTier}
          />

        </div>
      </div>

    </div>
  )
}

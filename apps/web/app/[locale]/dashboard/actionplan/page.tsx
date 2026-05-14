import { createServerSupabaseClient } from '@/lib/supabase-server'
import { getLocale, getTranslations } from 'next-intl/server'
import { redirect } from 'next/navigation'
import ActionPlanPage from '@/components/dashboard/ActionPlanPage'
import LanguageSwitcher from '@/components/LanguageSwitcher'
import UserMenu from '@/components/dashboard/UserMenu'

export default async function Page() {
  const supabase = await createServerSupabaseClient()
  const { data: { user } } = await supabase.auth.getUser()
  const locale = await getLocale()
  const t = await getTranslations('dashboard.actionPlan')

  if (!user) redirect(`/${locale}/login`)

  const [{ data: business }, { data: profile }] = await Promise.all([
    supabase.from('businesses').select('id, name').limit(1).single(),
    supabase.from('profiles').select('full_name').eq('id', user.id).single(),
  ])

  // Fetch subscription tier to gate the AI coach
  const { data: subscription } = business
    ? await supabase
        .from('subscriptions')
        .select('plan_tier')
        .eq('business_id', business.id)
        .order('created_at', { ascending: false })
        .limit(1)
        .single()
    : { data: null }
  const currentTier: 'starter' | 'pro' = subscription?.plan_tier === 'pro' ? 'pro' : 'starter'

  // Fetch recommendations — prefer locale-translated version for non-EN
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let recommendations: any[] = []
  if (business) {
    try {
      const { data: { session } } = await supabase.auth.getSession()
      if (session?.access_token) {
        const url = locale !== 'en'
          ? `${process.env.NEXT_PUBLIC_API_URL}/api/v1/aeo/recommendations/${business.id}?locale=${locale}`
          : null

        if (url) {
          const res = await fetch(url, {
            headers: { Authorization: `Bearer ${session.access_token}` },
            next: { revalidate: 0 },
          })
          if (res.ok) {
            const data = await res.json()
            if (Array.isArray(data.recommendations)) recommendations = data.recommendations
          }
        }
      }
    } catch {
      // fall through to raw_results below
    }

    if (recommendations.length === 0) {
      const { data: audit } = await supabase
        .from('aeo_audits')
        .select('raw_results')
        .eq('business_id', business.id)
        .order('created_at', { ascending: false })
        .limit(1)
        .single()
      recommendations = audit?.raw_results?.recommendations ?? []
    }
  }

  const fullName = profile?.full_name?.trim() || ''
  const initial = (fullName || user.email || '?')[0].toUpperCase()

  return (
    <div className="flex flex-col h-full">
      {/* Mobile header */}
      <header className="md:hidden flex items-center justify-between px-4 py-3
                         bg-white border-b border-slate-100 flex-shrink-0">
        <span className="text-sm font-bold text-[#1e293b]">{t('pageTitle')}</span>
        <UserMenu initial={initial} name={fullName} email={user.email ?? ''} />
      </header>

      {/* Desktop header */}
      <div className="hidden md:flex items-center justify-between px-6 py-4
                      border-b border-slate-100 flex-shrink-0">
        <div>
          <h1 className="text-base font-extrabold text-[#1e293b]">{t('pageTitle')}</h1>
          {business?.name && (
            <p className="text-xs text-slate-500 mt-0.5 font-medium">{business.name}</p>
          )}
        </div>
        <div className="flex items-center gap-3">
          <LanguageSwitcher />
          <UserMenu initial={initial} name={fullName} email={user.email ?? ''} />
        </div>
      </div>

      <ActionPlanPage
        businessName={business?.name ?? null}
        recommendations={recommendations}
        currentTier={currentTier}
        locale={locale}
      />
    </div>
  )
}

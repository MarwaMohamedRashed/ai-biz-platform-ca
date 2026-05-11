import { createServerSupabaseClient } from '@/lib/supabase-server'
import { getLocale, getTranslations } from 'next-intl/server'
import { redirect } from 'next/navigation'
import CompetitorsPage from '@/components/dashboard/CompetitorsPage'
import LanguageSwitcher from '@/components/LanguageSwitcher'
import UserMenu from '@/components/dashboard/UserMenu'

export default async function Page() {
  const supabase = await createServerSupabaseClient()
  const { data: { user } } = await supabase.auth.getUser()
  const locale = await getLocale()
  const t = await getTranslations('dashboard.competitors')

  if (!user) redirect(`/${locale}/login`)

  const [{ data: business }, { data: profile }] = await Promise.all([
    supabase.from('businesses').select('id, name, type, city, province').limit(1).single(),
    supabase.from('profiles').select('full_name').eq('id', user.id).single(),
  ])

  const { data: latestAudit } = business
    ? await supabase
        .from('aeo_audits')
        .select('score, score_breakdown, raw_results, created_at')
        .eq('business_id', business.id)
        .order('created_at', { ascending: false })
        .limit(1)
        .single()
    : { data: null }

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
        <h1 className="text-base font-extrabold text-[#1e293b]">{t('pageTitle')}</h1>
        <div className="flex items-center gap-3">
          <LanguageSwitcher />
          <UserMenu initial={initial} name={fullName} email={user.email ?? ''} />
        </div>
      </div>

      <CompetitorsPage
        businessId={business?.id ?? null}
        businessName={business?.name ?? null}
        latestAudit={latestAudit ?? null}
        locale={locale}
      />
    </div>
  )
}

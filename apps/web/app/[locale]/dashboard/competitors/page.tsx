import { createServerSupabaseClient } from '@/lib/supabase-server'
import { getLocale } from 'next-intl/server'
import { redirect } from 'next/navigation'
import CompetitorsPage from '@/components/dashboard/CompetitorsPage'

export default async function Page() {
  const supabase = await createServerSupabaseClient()
  const { data: { user } } = await supabase.auth.getUser()
  const locale = await getLocale()

  if (!user) redirect(`/${locale}/login`)

  const { data: business } = await supabase
    .from('businesses')
    .select('id, name, type, city, province')
    .limit(1)
    .single()

  const { data: latestAudit } = business
    ? await supabase
        .from('aeo_audits')
        .select('score, score_breakdown, raw_results, created_at')
        .eq('business_id', business.id)
        .order('created_at', { ascending: false })
        .limit(1)
        .single()
    : { data: null }

  return (
    <CompetitorsPage
      businessId={business?.id ?? null}
      businessName={business?.name ?? null}
      latestAudit={latestAudit ?? null}
      locale={locale}
    />
  )
}

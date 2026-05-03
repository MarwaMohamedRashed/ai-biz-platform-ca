import { createServerSupabaseClient } from '@/lib/supabase-server'
import { getLocale } from 'next-intl/server'
import { redirect } from 'next/navigation'
import ContentPage from '@/components/dashboard/ContentPage'

export default async function Page() {
  const supabase = await createServerSupabaseClient()
  const { data: { user } } = await supabase.auth.getUser()
  const locale = await getLocale()

  if (!user) redirect(`/${locale}/login`)

  const { data: business } = await supabase
    .from('businesses')
    .select('id, name, type, city')
    .limit(1)
    .single()

  const { data: latestContent } = business
    ? await supabase
        .from('aeo_content')
        .select('*')
        .eq('business_id', business.id)
        .order('created_at', { ascending: false })
        .limit(1)
        .single()
    : { data: null }

  return (
    <ContentPage
      businessId={business?.id ?? null}
      initialContent={latestContent ?? null}
    />
  )
}
import { redirect } from 'next/navigation'
import { getLocale } from 'next-intl/server'
import { createServerSupabaseClient } from '@/lib/supabase-server'
import OnboardingFlow from '@/components/onboarding/OnboardingFlow'

export default async function OnboardingPage() {
  const supabase = await createServerSupabaseClient()
  const { data: { user } } = await supabase.auth.getUser()
  const locale = await getLocale()

  if (!user) redirect(`/${locale}/login`)

  const { data: businesses } = await supabase
    .from('businesses')
    .select('id, onboarding_completed')
    .limit(1)

  const business = businesses?.[0]

  if (business?.onboarding_completed) {
    redirect(`/${locale}/dashboard`)
  }

  const initialStep = business ? 2 : 1
  const initialBusinessId = business?.id ?? null

  return (
    <div className="min-h-screen bg-[#f1f5f9]">
      <OnboardingFlow
        userId={user.id}
        userName={user.user_metadata?.full_name ?? user.user_metadata?.first_name ?? ''}
        initialStep={initialStep}
      />
    </div>
  )
}
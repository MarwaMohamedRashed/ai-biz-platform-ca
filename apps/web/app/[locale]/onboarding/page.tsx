import { redirect } from 'next/navigation'
import { getLocale } from 'next-intl/server'
import { createServerSupabaseClient } from '@/lib/supabase-server'
import OnboardingFlow from '@/components/onboarding/OnboardingFlow'

export default async function OnboardingPage() {
  const supabase = await createServerSupabaseClient()
  const { data: { user } } = await supabase.auth.getUser()
  const locale = await getLocale()

  if (!user) redirect(`/${locale}/login`)

  // Resume-on-refresh:
  //   no business row              → start at Step 1
  //   row exists but not finished  → land on Step 2 with the row's id/name
  //                                  so the extras form can UPDATE it
  //   row exists and finished      → out of onboarding, go to dashboard
  const { data: businesses } = await supabase
    .from('businesses')
    .select('id, name, onboarding_completed')
    .limit(1)

  const business = businesses?.[0]

  if (business?.onboarding_completed) {
    redirect(`/${locale}/dashboard`)
  }

  const initialStep = business ? 2 : 1

  return (
    <div className="min-h-screen bg-[#f1f5f9]">
      <OnboardingFlow
        userId={user.id}
        userName={user.user_metadata?.full_name ?? user.user_metadata?.first_name ?? ''}
        initialStep={initialStep}
        initialBusinessId={business?.id ?? null}
        initialBusinessName={business?.name ?? ''}
      />
    </div>
  )
}
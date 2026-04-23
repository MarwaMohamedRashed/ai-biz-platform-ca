import { createServerSupabaseClient } from '@/lib/supabase-server'
import { redirect } from 'next/navigation'
import { getLocale } from 'next-intl/server'
import Sidebar from '@/components/dashboard/Sidebar'
import BottomNav from '@/components/dashboard/BottomNav'
import IdleTimeout from '@/components/dashboard/IdleTimeout'

export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const supabase = await createServerSupabaseClient()
  const { data: { user } } = await supabase.auth.getUser()
  const locale = await getLocale()

  if (!user) {
    redirect(`/${locale}/login`)
  }
  // If user has no business, send them to onboarding
  const { data: businesses } = await supabase
    .from('businesses')
    .select('id, onboarding_completed')
    .limit(1)

  if (!businesses || businesses.length === 0 || !businesses[0].onboarding_completed) {
  redirect(`/${locale}/onboarding`)
  }
  const businessId = businesses[0].id

  const { data: subscription } = await supabase
    .from('subscriptions')
    .select('status, plan_tier')
    .eq('business_id', businessId)
    .order('created_at', { ascending: false })
    .limit(1)
    .single()

  const planTier = (subscription?.plan_tier ?? 'starter') as 'starter' | 'pro' | 'business'

  const { data: pendingReviews } = await supabase
  .from('reviews')
  .select('id')
  .eq('status', 'pending')

  const pendingCount = pendingReviews?.length ?? 0
  
  const { data: profile } = await supabase
      .from('profiles')
      .select('full_name')
      .eq('id', user.id)
      .single()

  const displayName = profile?.full_name?.trim() || ''

  return (
    <div className="bg-[#f1f5f9] h-screen flex flex-col md:items-center md:justify-center md:p-8">

      {/* App container — full screen on mobile, centered card on desktop */}
      <div className="flex flex-1 w-full overflow-hidden
                      md:flex-none md:max-w-[1200px] md:h-full
                      md:rounded-2xl md:shadow-xl md:border md:border-slate-200 md:bg-white">

        <Sidebar
          user={{ name: displayName, email: user.email ?? '' }}
          locale={locale}
          pendingCount={pendingCount}
          planTier={planTier}
        />

        <main className="flex-1 flex flex-col min-w-0 overflow-hidden pb-16 md:pb-0">
          {children}
          <IdleTimeout />
        </main>

      </div>

      {/* Mobile bottom nav — fixed, viewport-relative */}
      <BottomNav locale={locale} pendingCount={pendingCount} />

    </div>
  )
}

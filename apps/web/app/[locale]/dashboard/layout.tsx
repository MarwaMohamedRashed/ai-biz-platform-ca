import { createServerSupabaseClient } from '@/lib/supabase-server'
import { redirect } from 'next/navigation'
import { getLocale } from 'next-intl/server'
import Sidebar from '@/components/dashboard/Sidebar'
import BottomNav from '@/components/dashboard/BottomNav'

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

  // Fetch profile for name display in sidebar
  const { data: profile } = await supabase
    .from('profiles')
    .select('full_name')
    .eq('id', user.id)
    .single()

  const displayName = profile?.full_name?.trim() || ''

  return (
    <div className="min-h-screen bg-[#f1f5f9] flex">

      {/* Desktop sidebar */}
      <Sidebar
        user={{ name: displayName, email: user.email ?? '' }}
        locale={locale}
      />

      {/* Main content — pushes right of sidebar on desktop, full width on mobile */}
      <div className="flex-1 flex flex-col min-w-0 pb-16 md:pb-0">
        {children}
      </div>

      {/* Mobile bottom nav */}
      <BottomNav locale={locale} />

    </div>
  )
}

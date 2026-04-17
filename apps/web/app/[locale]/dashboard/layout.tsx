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
        />

        <main className="flex-1 flex flex-col min-w-0 overflow-hidden pb-16 md:pb-0">
          {children}
        </main>

      </div>

      {/* Mobile bottom nav — fixed, viewport-relative */}
      <BottomNav locale={locale} />

    </div>
  )
}

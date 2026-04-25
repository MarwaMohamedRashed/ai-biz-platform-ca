import { createServerSupabaseClient } from '@/lib/supabase-server'
import { getTranslations } from 'next-intl/server'
import UserMenu from '@/components/dashboard/UserMenu'
import LanguageSwitcher from '@/components/LanguageSwitcher'
import ReviewsList from '@/components/dashboard/ReviewsList'

export default async function ReviewsPage() {
  const supabase = await createServerSupabaseClient()
  const { data: { user } } = await supabase.auth.getUser()
  const t = await getTranslations('dashboard.reviews')

  const { data: profile } = await supabase
    .from('profiles')
    .select('full_name')
    .eq('id', user!.id)
    .single()

  const fullName = profile?.full_name?.trim() || ''
  const initial = (fullName || user!.email || '?')[0].toUpperCase()

  const { data: reviews } = await supabase
    .from('reviews')
    .select(`
      id, author, rating, text, review_date, status,
      review_responses ( id, ai_draft, final_response, status )
    `)
    .order('review_date', { ascending: false })

  return (
    <div className="flex flex-col h-full">

      {/* Mobile header */}
      <header className="md:hidden flex items-center justify-between px-4 py-3
                         bg-white border-b border-slate-100 flex-shrink-0">
        <div className="flex items-center gap-2">
          <svg width="28" height="28" viewBox="0 0 40 40" fill="none">
            <rect width="40" height="40" rx="12" fill="#4f46e5"/>
            <path d="M13 10 L13 28 L27 28" stroke="white" strokeWidth="3"
              strokeLinecap="round" strokeLinejoin="round"/>
            <circle cx="28" cy="13" r="4" fill="#f97316"/>
          </svg>
          <span className="text-base font-extrabold tracking-tight">
            <span className="text-[#4f46e5]">Leap</span><span className="text-[#f97316]">One</span>
          </span>
        </div>
        <UserMenu initial={initial} name={fullName} email={user!.email ?? ''} />
      </header>

      {/* Desktop header */}
      <div className="hidden md:flex items-center justify-between px-6 py-4
                      border-b border-slate-100 flex-shrink-0">
        <h1 className="text-base font-extrabold text-[#1e293b]">{t('title')}</h1>
        <div className="flex items-center gap-3">
          <LanguageSwitcher />
          <UserMenu initial={initial} name={fullName} email={user!.email ?? ''} />
        </div>
      </div>

      <ReviewsList reviews={reviews ?? []} />

    </div>
  )
}
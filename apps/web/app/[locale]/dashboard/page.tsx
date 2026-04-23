import { createServerSupabaseClient } from '@/lib/supabase-server'
import { getTranslations } from 'next-intl/server'
import ChatInput from '@/components/dashboard/ChatInput'
import UserMenu from '@/components/dashboard/UserMenu'
import LanguageSwitcher from '@/components/LanguageSwitcher'
import Link from 'next/link'
import { getLocale } from 'next-intl/server'
import InsightsCard from '@/components/dashboard/InsightsCard'

function getGreetingKey(): 'morning' | 'afternoon' | 'evening' {
  const hour = new Date().getHours()
  if (hour < 12) return 'morning'
  if (hour < 17) return 'afternoon'
  return 'evening'
}

export default async function DashboardPage() {
  const supabase = await createServerSupabaseClient()
  const { data: { user } } = await supabase.auth.getUser()
  const t = await getTranslations('dashboard.chat')

  const { data: profile } = await supabase
    .from('profiles')
    .select('full_name')
    .eq('id', user!.id)
    .single()

  const { data: reviewRows } = await supabase
    .from('reviews')
    .select('rating, status')

  const ratings = (reviewRows ?? []).filter(r => r.rating !== null).map(r => r.rating as number)
  const avgRating = ratings.length > 0
    ? (ratings.reduce((a, b) => a + b, 0) / ratings.length).toFixed(1)
    : '—'
  const pendingCount = (reviewRows ?? []).filter(r => r.status === 'pending').length
  const respondedCount = (reviewRows ?? []).filter(r => r.status === 'responded').length
  
  const fullName = profile?.full_name?.trim() || ''
  const firstName = fullName.split(' ')[0]
    || user!.email?.split('@')[0]
    || 'there'

  const initial = firstName[0].toUpperCase()
  const greetingKey = getGreetingKey()
  const locale = await getLocale()

  return (
    <div className="flex h-full">

      {/* ── Chat column ── */}
      <div className="flex flex-col flex-1 min-w-0 h-full">

        {/* Mobile header */}
        <header className="md:hidden flex items-center justify-between px-4 py-3
                           bg-white border-b border-slate-100 flex-shrink-0">
          <div className="flex items-center gap-2">
            <svg width="28" height="28" viewBox="0 0 40 40" fill="none">
              <rect width="40" height="40" rx="12" fill="#4f46e5"/>
              <path d="M13 10 L13 28 L27 28" stroke="white" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"/>
              <circle cx="28" cy="13" r="4" fill="#f97316"/>
            </svg>
            <span className="text-base font-extrabold tracking-tight">
              <span className="text-[#4f46e5]">Leap</span><span className="text-[#f97316]">One</span>
            </span>
          </div>
          <UserMenu initial={initial} name={fullName} email={user!.email ?? ''} />
        </header>

        {/* Desktop page header */}
        <div className="hidden md:flex items-center justify-between px-6 py-4
                        border-b border-slate-100 flex-shrink-0">
          <div>
            <p className="text-xs text-slate-400">
              {new Date().toLocaleDateString('en-CA', { weekday: 'long', month: 'long', day: 'numeric' })}
            </p>
            <h1 className="text-base font-extrabold text-[#1e293b]">{t('pageTitle')}</h1>
          </div>
          <div className="flex items-center gap-3">
            <LanguageSwitcher />
            <UserMenu initial={initial} name={fullName} email={user!.email ?? ''} />
          </div>
        </div>

        {/* Chat messages area */}
        <div className="flex-1 overflow-y-auto px-4 py-4 md:px-6 space-y-4">

          {/* AI greeting bubble */}
          <div className="flex gap-3">
            <div className="w-8 h-8 rounded-full bg-[#4f46e5] flex items-center justify-center flex-shrink-0 mt-0.5">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"
                  stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </div>
            <div className="flex flex-col gap-3 max-w-lg">

              {/* Greeting */}
              <div className="bg-white rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm border border-slate-100">
                <p className="text-sm text-[#1e293b]">
                  {t(`greeting.${greetingKey}`)},{' '}
                  <span className="font-semibold">{firstName}</span>!{' '}
                  {t('greeting.attention')}
                </p>
              </div>

              {/* Reviews action card */}
              <div className="bg-white rounded-2xl border-l-[3px] border-l-[#f97316]
                              shadow-sm border border-slate-100 p-4">
                <div className="flex items-start justify-between mb-1.5">
                  <span className="text-[10px] font-bold text-[#f97316] uppercase tracking-wider">
                    {t('reviewsCard.label')}
                  </span>
                  <span className="bg-amber-100 text-amber-700 text-[10px] font-bold px-2 py-0.5 rounded-full">
                    {pendingCount} {t('reviewsCard.badge')}
                  </span>
                </div>
                <p className="text-sm font-semibold text-[#1e293b] mb-1">
                  {pendingCount} {t('reviewsCard.title')}
                </p>
                <p className="text-xs text-slate-500 mb-3">{t('reviewsCard.preview')}</p>
                <div className="flex items-center gap-2">
                  <Link href={`/${locale}/dashboard/reviews`}
                    className="text-xs font-semibold bg-[#4f46e5] text-white px-3 py-1.5 rounded-lg hover:bg-indigo-700 transition-colors">
                    {t('reviewsCard.action')}
                  </Link>
                </div>
              </div>

              {/* Bookings action card */}
              <div className="bg-white rounded-2xl border-l-[3px] border-l-[#4f46e5]
                              shadow-sm border border-slate-100 p-4">
                <div className="flex items-start justify-between mb-1.5">
                  <span className="text-[10px] font-bold text-[#4f46e5] uppercase tracking-wider">
                    {t('bookingsCard.label')}
                  </span>
                  <span className="bg-indigo-100 text-indigo-700 text-[10px] font-bold px-2 py-0.5 rounded-full">
                    {t('bookingsCard.badge')}
                  </span>
                </div>
                <p className="text-sm font-semibold text-[#1e293b] mb-1">
                  2 {t('bookingsCard.title')}
                </p>
                <p className="text-xs text-slate-500 mb-3">{t('bookingsCard.preview')}</p>
                <Link href={`/${locale}/dashboard/bookings`}
                  className="text-xs font-semibold bg-[#4f46e5] text-white px-3 py-1.5 rounded-lg hover:bg-indigo-700 transition-colors">
                  {t('bookingsCard.action')}
                </Link>
              </div>
              {/* Insights card */}
              <InsightsCard />

              {/* Follow-up bubble */}
              <div className="bg-white rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm border border-slate-100">
                <p className="text-sm text-slate-500">{t('followUp')}</p>
              </div>

            </div>
          </div>
        </div>

        {/* Chat input */}
        <ChatInput />

      </div>

      {/* ── Right stats panel — desktop only ── */}
      <aside className="hidden md:flex flex-col w-[220px] flex-shrink-0
                        border-l border-slate-100 overflow-y-auto bg-white">

        {/* Header */}
        <div className="px-5 py-4 border-b border-slate-100">
          <div className="flex items-center gap-2">
            <div className="w-5 h-5 rounded bg-[#4f46e5] flex items-center justify-center">
              <svg width="10" height="10" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <path d="M18 20V10M12 20V4M6 20v-6" stroke="white" strokeWidth="2.5" strokeLinecap="round"/>
              </svg>
            </div>
            <h2 className="text-sm font-bold text-[#1e293b]">{t('thisWeek.title')}</h2>
          </div>
        </div>

        {/* Stats grid */}
        <div className="px-5 py-4 border-b border-slate-100">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <p className="text-[10px] text-slate-400 uppercase tracking-wide mb-1">
                {t('thisWeek.avgRating')}
              </p>
              <p className="text-xl font-bold text-[#f97316]">{avgRating}★</p>
            </div>
            <div>
              <p className="text-[10px] text-slate-400 uppercase tracking-wide mb-1">
                {t('thisWeek.responded')}
              </p>
              <p className="text-xl font-bold text-green-600">{respondedCount}</p>
              <p className="text-[10px] text-slate-400">{t('thisWeek.reviewsThisWeek')}</p>
            </div>
          </div>
        </div>

        {/* Appointments */}
        <div className="px-5 py-4 border-b border-slate-100">
          <p className="text-[10px] text-slate-400 uppercase tracking-wide mb-1">
            {t('thisWeek.appointments')}
          </p>
          <p className="text-3xl font-bold text-[#1e293b]">8</p>
          <p className="text-[10px] text-slate-400 mt-0.5">{t('thisWeek.bookedViaAI')}</p>
        </div>

        {/* Quick actions */}
        <div className="px-5 py-4 flex flex-col gap-2">
          <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">
            {t('thisWeek.quickActions')}
          </p>
          <Link href={`/${locale}/dashboard/reviews`} className="flex items-center gap-2 w-full px-3 py-2.5 rounded-xl
                             border border-slate-200 text-xs font-semibold text-[#1e293b]
                             hover:bg-slate-50 transition-colors text-left">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"
                stroke="#f97316" strokeWidth="2" fill="none"/>
            </svg>
            {t('thisWeek.viewAllReviews')}
          </Link>
          <button className="flex items-center gap-2 w-full px-3 py-2.5 rounded-xl
                             border border-slate-200 text-xs font-semibold text-[#1e293b]
                             hover:bg-slate-50 transition-colors text-left">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <rect x="3" y="4" width="18" height="18" rx="2" stroke="#4f46e5" strokeWidth="2"/>
              <line x1="16" y1="2" x2="16" y2="6" stroke="#4f46e5" strokeWidth="2" strokeLinecap="round"/>
              <line x1="8" y1="2" x2="8" y2="6" stroke="#4f46e5" strokeWidth="2" strokeLinecap="round"/>
              <line x1="3" y1="10" x2="21" y2="10" stroke="#4f46e5" strokeWidth="2" strokeLinecap="round"/>
            </svg>
            {t('thisWeek.addAvailability')}
          </button>
          <button className="flex items-center gap-2 w-full px-3 py-2.5 rounded-xl
                             border border-slate-200 text-xs font-semibold text-[#1e293b]
                             hover:bg-slate-50 transition-colors text-left">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"
                stroke="#64748b" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"
                stroke="#64748b" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
            {t('thisWeek.connectGoogle')}
          </button>
        </div>

      </aside>

    </div>
  )
}

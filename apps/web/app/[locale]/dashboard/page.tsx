import { createServerSupabaseClient } from '@/lib/supabase-server'
import { getTranslations } from 'next-intl/server'
import ChatInput from '@/components/dashboard/ChatInput'
import UserMenu from '@/components/dashboard/UserMenu'
import LanguageSwitcher from '@/components/LanguageSwitcher'
import Link from 'next/link'
import { getLocale } from 'next-intl/server'
import AeoAuditCard from '@/components/dashboard/AeoAuditCard'

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

  const { data: business } = await supabase
  .from('businesses')
  .select('id')
  .limit(1)
  .single()

  const { data: latestAudit } = business
    ? await supabase
        .from('aeo_audits')
        .select('*')
        .eq('business_id', business.id)
        .order('created_at', { ascending: false })
        .limit(1)
        .single()
    : { data: null }
  
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

              {/* AEO coming-soon card */}
              <AeoAuditCard
                businessId={business?.id ?? null}
                initialAudit={latestAudit ?? null}
                locale={locale}
              />

            </div>
          </div>
        </div>

        {/* Chat input */}
        <ChatInput />

      </div>

      {/* ── Right panel — desktop only ── */}
      <aside className="hidden md:flex flex-col w-[220px] flex-shrink-0
                        border-l border-slate-100 overflow-y-auto bg-white">

        <div className="px-5 py-4 border-b border-slate-100">
          <div className="flex items-center gap-2">
            <div className="w-5 h-5 rounded bg-[#4f46e5] flex items-center justify-center">
              <svg width="10" height="10" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <circle cx="12" cy="12" r="3" stroke="white" strokeWidth="2.5"/>
                <path d="M12 2v2M12 20v2M2 12h2M20 12h2" stroke="white" strokeWidth="2" strokeLinecap="round"/>
              </svg>
            </div>
            <h2 className="text-sm font-bold text-[#1e293b]">{t('aeoPanel.title')}</h2>
          </div>
        </div>

        <div className="px-5 py-4 border-b border-slate-100">
          <p className="text-[10px] text-slate-400 uppercase tracking-wide mb-1">{t('aeoPanel.scoreLabel')}</p>
          <p className={`text-3xl font-bold ${latestAudit ? (latestAudit.score >= 70 ? 'text-green-600' : latestAudit.score >= 40 ? 'text-amber-500' : 'text-red-500') : 'text-slate-300'}`}>
            {latestAudit ? latestAudit.score : '—'}
          </p>
          <p className="text-[10px] text-slate-400 mt-0.5">
            {latestAudit ? `Last checked ${new Date(latestAudit.created_at).toLocaleDateString()}` : t('aeoPanel.noAudit')}
          </p>
        </div>

        <div className="px-5 py-4 border-b border-slate-100">
          <p className="text-[10px] text-slate-400 uppercase tracking-wide mb-1">Perplexity</p>
          <p className={`text-sm font-semibold ${latestAudit ? (latestAudit.perplexity_mentioned ? 'text-green-600' : 'text-red-400') : 'text-slate-300'}`}>
            {latestAudit ? (latestAudit.perplexity_mentioned ? '✓ Found' : '✗ Not found') : t('aeoPanel.notChecked')}
          </p>
        </div>

        <div className="px-5 py-4 border-b border-slate-100">
          <p className="text-[10px] text-slate-400 uppercase tracking-wide mb-1">Google AI</p>
          <p className={`text-sm font-semibold ${latestAudit ? (latestAudit.google_ai_mentioned ? 'text-green-600' : 'text-red-400') : 'text-slate-300'}`}>
            {latestAudit ? (latestAudit.google_ai_mentioned ? '✓ Found' : '✗ Not found') : t('aeoPanel.notChecked')}
          </p>
        </div>

        <div className="px-5 py-4">
          <Link href={`/${locale}/dashboard/settings`}
            className="flex items-center justify-center w-full px-3 py-2.5 rounded-xl
                       bg-[#4f46e5] text-xs font-semibold text-white
                       hover:bg-indigo-700 transition-colors">
            {t('aeoPanel.setupCta')}
          </Link>
        </div>

      </aside>

    </div>
  )
}

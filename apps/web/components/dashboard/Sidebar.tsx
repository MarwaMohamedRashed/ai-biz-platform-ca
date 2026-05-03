'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useTranslations } from 'next-intl'

interface Props {
  user: { name: string; email: string }
  locale: string
  pendingCount?: number
  planTier: 'starter' | 'pro' | 'business'
}

export default function Sidebar({ user, locale, planTier }: Props) {
  const pathname = usePathname()
  const t = useTranslations('dashboard')

  const navItems = [
    {
      key: 'chat' as const,
      href: `/${locale}/dashboard`,
      exact: true,
      icon: (active: boolean) => (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"
            stroke={active ? '#4f46e5' : '#64748b'} strokeWidth="2"
            strokeLinecap="round" strokeLinejoin="round"
            fill={active ? '#eef2ff' : 'none'}/>
        </svg>
      ),
    },
    {
      key: 'content' as const,
      href: `/${locale}/dashboard/content`,
      exact: false,
      icon: (active: boolean) => (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"
            stroke={active ? '#4f46e5' : '#64748b'} strokeWidth="2"
            strokeLinecap="round" strokeLinejoin="round"
            fill={active ? '#eef2ff' : 'none'}/>
          <polyline points="14,2 14,8 20,8"
            stroke={active ? '#4f46e5' : '#64748b'} strokeWidth="2"
            strokeLinecap="round" strokeLinejoin="round"/>
          <line x1="16" y1="13" x2="8" y2="13"
            stroke={active ? '#4f46e5' : '#64748b'} strokeWidth="2" strokeLinecap="round"/>
          <line x1="16" y1="17" x2="8" y2="17"
            stroke={active ? '#4f46e5' : '#64748b'} strokeWidth="2" strokeLinecap="round"/>
          <polyline points="10,9 9,9 8,9"
            stroke={active ? '#4f46e5' : '#64748b'} strokeWidth="2" strokeLinecap="round"/>
        </svg>
      ),
    },
    {
      key: 'competitors' as const,
      href: `/${locale}/dashboard/competitors`,
      exact: false,
      icon: (active: boolean) => (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M3 3v18h18" stroke={active ? '#4f46e5' : '#64748b'} strokeWidth="2"
            strokeLinecap="round" strokeLinejoin="round"/>
          <rect x="7"  y="13" width="3" height="5" rx="0.5"
            stroke={active ? '#4f46e5' : '#64748b'} strokeWidth="2"
            fill={active ? '#eef2ff' : 'none'}/>
          <rect x="12" y="9"  width="3" height="9" rx="0.5"
            stroke={active ? '#4f46e5' : '#64748b'} strokeWidth="2"
            fill={active ? '#eef2ff' : 'none'}/>
          <rect x="17" y="6"  width="3" height="12" rx="0.5"
            stroke={active ? '#4f46e5' : '#64748b'} strokeWidth="2"
            fill={active ? '#eef2ff' : 'none'}/>
        </svg>
      ),
    },
    // Phase 3 — restore when Google/Meta API approved (~July 2026)
    // { key: 'reviews', href: `/${locale}/dashboard/reviews`, exact: false, badge: pendingCount, icon: ... },
    // { key: 'bookings', href: `/${locale}/dashboard/bookings`, exact: false, icon: ... },
    // { key: 'guide',    href: `/${locale}/dashboard/guide`,    exact: false, icon: ... },
    {
      key: 'settings' as const,
      href: `/${locale}/dashboard/settings`,
      exact: false,
      icon: (active: boolean) => (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <circle cx="12" cy="12" r="3"
          stroke={active ? '#4f46e5' : '#64748b'} strokeWidth="2"/>
        <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06-.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"
          stroke={active ? '#4f46e5' : '#64748b'} strokeWidth="2"
          strokeLinecap="round" strokeLinejoin="round"/>
      </svg>
      ),
    },
    {
      key: 'plan' as const,
      href: `/${locale}/dashboard/plan`,
      exact: false,
      icon: (active: boolean) => (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <rect x="1" y="4" width="22" height="16" rx="2" ry="2"
            stroke={active ? '#4f46e5' : '#64748b'} strokeWidth="2"
            fill={active ? '#eef2ff' : 'none'}/>
          <line x1="1" y1="10" x2="23" y2="10"
            stroke={active ? '#4f46e5' : '#64748b'} strokeWidth="2" strokeLinecap="round"/>
        </svg>
      ),
    },
  ]

  const isActive = (href: string, exact: boolean) =>
    exact ? pathname === href : pathname.startsWith(href)

  const initial = (user.name || user.email)[0]?.toUpperCase() ?? '?'

  return (
    <aside className="hidden md:flex flex-col w-[220px] flex-shrink-0
                      bg-white border-r border-slate-100">

      {/* Logo */}
      <div className="flex items-center gap-2.5 px-5 py-5">
        <div className="w-8 h-8 rounded-lg bg-[#4f46e5] flex items-center justify-center flex-shrink-0">
          <svg width="16" height="16" viewBox="0 0 40 40" fill="none">
            <path d="M13 10 L13 28 L27 28" stroke="white" strokeWidth="4"
              strokeLinecap="round" strokeLinejoin="round"/>
            <circle cx="28" cy="13" r="5" fill="#f97316"/>
          </svg>
        </div>
        <span className="text-lg font-extrabold tracking-tight">
          <span className="text-[#4f46e5]">Leap</span><span className="text-[#f97316]">One</span>
        </span>
      </div>

      {/* Business card */}
      <div className="px-4 pb-4">
        <div className="flex items-center gap-3 bg-slate-50 rounded-xl px-3 py-2.5">
          <div className="w-8 h-8 rounded-full bg-[#4f46e5] flex items-center justify-center
                          text-white text-xs font-bold flex-shrink-0">
            {initial}
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold text-[#1e293b] truncate">
              {user.name || user.email}
            </p>
            <span className="text-[10px] font-bold text-[#4f46e5] bg-indigo-50
                             px-1.5 py-0.5 rounded-full">
              {t(`planTier.${planTier}`)}
            </span>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 flex flex-col gap-0.5 px-3 py-2 overflow-y-auto">
        {navItems.map(item => {
          const active = isActive(item.href, item.exact)
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-semibold transition-colors
                ${active
                  ? 'bg-[#eef2ff] text-[#4f46e5]'
                  : 'text-slate-600 hover:bg-slate-50 hover:text-[#1e293b]'
                }`}
            >
              {item.icon(active)}
              {t(`nav.${item.key}`)}
            </Link>
          )
        })}
      </nav>

    </aside>
  )
}

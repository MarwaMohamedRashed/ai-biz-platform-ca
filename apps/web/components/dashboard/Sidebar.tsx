'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useTranslations } from 'next-intl'

interface Props {
  user: { name: string; email: string }
  locale: string
  pendingCount: number
  planTier: 'starter' | 'pro' | 'business'
}

export default function Sidebar({ user, locale, pendingCount, planTier }: Props) {
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
      key: 'reviews' as const,
      href: `/${locale}/dashboard/reviews`,
      exact: false,
      badge: pendingCount,
      icon: (active: boolean) => (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"
            stroke={active ? '#4f46e5' : '#64748b'} strokeWidth="2"
            strokeLinecap="round" strokeLinejoin="round"
            fill={active ? '#eef2ff' : 'none'}/>
        </svg>
      ),
    },
    {
      key: 'bookings' as const,
      href: `/${locale}/dashboard/bookings`,
      exact: false,
      icon: (active: boolean) => (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <rect x="3" y="4" width="18" height="18" rx="2" ry="2"
            stroke={active ? '#4f46e5' : '#64748b'} strokeWidth="2"
            fill={active ? '#eef2ff' : 'none'}/>
          <line x1="16" y1="2" x2="16" y2="6" stroke={active ? '#4f46e5' : '#64748b'} strokeWidth="2" strokeLinecap="round"/>
          <line x1="8" y1="2" x2="8" y2="6" stroke={active ? '#4f46e5' : '#64748b'} strokeWidth="2" strokeLinecap="round"/>
          <line x1="3" y1="10" x2="21" y2="10" stroke={active ? '#4f46e5' : '#64748b'} strokeWidth="2" strokeLinecap="round"/>
        </svg>
      ),
    },
    {
      key: 'guide' as const,
      href: `/${locale}/dashboard/guide`,
      exact: false,
      icon: (active: boolean) => (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"
            stroke={active ? '#4f46e5' : '#64748b'} strokeWidth="2"
            strokeLinecap="round" strokeLinejoin="round"
            fill={active ? '#eef2ff' : 'none'}/>
          <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"
            stroke={active ? '#4f46e5' : '#64748b'} strokeWidth="2"
            strokeLinecap="round" strokeLinejoin="round"
            fill={active ? '#eef2ff' : 'none'}/>
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
              {(item.badge ?? 0) > 0 && (
                <span className="ml-auto w-5 h-5 rounded-full bg-[#f97316] flex items-center justify-center
                                 text-[10px] font-bold text-white">
                  {item.badge}
                </span>
              )}
            </Link>
          )
        })}
      </nav>

    </aside>
  )
}

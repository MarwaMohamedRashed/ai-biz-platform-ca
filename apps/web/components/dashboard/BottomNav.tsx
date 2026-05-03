'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useTranslations } from 'next-intl'

interface Props {
  locale: string
  pendingCount: number
}

export default function BottomNav({ locale, pendingCount: _pendingCount }: Props) {
  const pathname = usePathname()
  const t = useTranslations('dashboard.nav')

  const navItems = [
    {
      key: 'chat' as const,
      href: `/${locale}/dashboard`,
      exact: true,
      icon: (active: boolean) => (
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"
            stroke={active ? '#4f46e5' : '#94a3b8'} strokeWidth="2"
            strokeLinecap="round" strokeLinejoin="round"
            fill={active ? '#eef2ff' : 'none'}/>
        </svg>
      ),
    },
    {
      key: 'competitors' as const,
      href: `/${locale}/dashboard/competitors`,
      exact: false,
      icon: (active: boolean) => (
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M3 3v18h18" stroke={active ? '#4f46e5' : '#94a3b8'} strokeWidth="2"
            strokeLinecap="round" strokeLinejoin="round"/>
          <rect x="7"  y="13" width="3" height="5" rx="0.5"
            stroke={active ? '#4f46e5' : '#94a3b8'} strokeWidth="2"
            fill={active ? '#eef2ff' : 'none'}/>
          <rect x="12" y="9"  width="3" height="9" rx="0.5"
            stroke={active ? '#4f46e5' : '#94a3b8'} strokeWidth="2"
            fill={active ? '#eef2ff' : 'none'}/>
          <rect x="17" y="6"  width="3" height="12" rx="0.5"
            stroke={active ? '#4f46e5' : '#94a3b8'} strokeWidth="2"
            fill={active ? '#eef2ff' : 'none'}/>
        </svg>
      ),
    },
    {
      key: 'settings' as const,
      href: `/${locale}/dashboard/settings`,
      exact: false,
      icon: (active: boolean) => (
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <circle cx="12" cy="12" r="3"
            stroke={active ? '#4f46e5' : '#94a3b8'} strokeWidth="2"/>
          <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06-.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"
            stroke={active ? '#4f46e5' : '#94a3b8'} strokeWidth="2"
            strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      ),
    },
    {
      key: 'plan' as const,
      href: `/${locale}/dashboard/plan`,
      exact: false,
      icon: (active: boolean) => (
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <rect x="1" y="4" width="22" height="16" rx="2" ry="2"
            stroke={active ? '#4f46e5' : '#94a3b8'} strokeWidth="2"
            fill={active ? '#eef2ff' : 'none'}/>
          <line x1="1" y1="10" x2="23" y2="10"
            stroke={active ? '#4f46e5' : '#94a3b8'} strokeWidth="2" strokeLinecap="round"/>
        </svg>
      ),
    },
  ]

  const isActive = (href: string, exact: boolean) =>
    exact ? pathname === href : pathname.startsWith(href)

  return (
    <nav className="md:hidden fixed bottom-0 left-0 right-0 z-50
                    bg-white border-t border-slate-100 flex">
      {navItems.map(item => {
        const active = isActive(item.href, item.exact)
        return (
          <Link
            key={item.href}
            href={item.href}
            className="flex-1 flex flex-col items-center justify-center py-2 gap-1 relative">
            {item.icon(active)}
            <span className={`text-[10px] font-semibold ${active ? 'text-[#4f46e5]' : 'text-slate-400'}`}>
              {t(item.key)}
            </span>
          </Link>
        )
      })}
    </nav>
  )
}

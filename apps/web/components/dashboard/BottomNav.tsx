'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'

interface Props {
  locale: string
}

export default function BottomNav({ locale }: Props) {
  const pathname = usePathname()

  const navItems = [
    {
      label: 'Chat',
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
      label: 'Reviews',
      href: `/${locale}/dashboard/reviews`,
      exact: false,
      badge: 3,
      icon: (active: boolean) => (
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"
            stroke={active ? '#4f46e5' : '#94a3b8'} strokeWidth="2"
            strokeLinecap="round" strokeLinejoin="round"
            fill={active ? '#eef2ff' : 'none'}/>
        </svg>
      ),
    },
    {
      label: 'Bookings',
      href: `/${locale}/dashboard/bookings`,
      exact: false,
      icon: (active: boolean) => (
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <rect x="3" y="4" width="18" height="18" rx="2" ry="2"
            stroke={active ? '#4f46e5' : '#94a3b8'} strokeWidth="2"
            strokeLinecap="round" strokeLinejoin="round"
            fill={active ? '#eef2ff' : 'none'}/>
          <line x1="16" y1="2" x2="16" y2="6" stroke={active ? '#4f46e5' : '#94a3b8'} strokeWidth="2" strokeLinecap="round"/>
          <line x1="8" y1="2" x2="8" y2="6" stroke={active ? '#4f46e5' : '#94a3b8'} strokeWidth="2" strokeLinecap="round"/>
          <line x1="3" y1="10" x2="21" y2="10" stroke={active ? '#4f46e5' : '#94a3b8'} strokeWidth="2" strokeLinecap="round"/>
        </svg>
      ),
    },
    {
      label: 'Guide',
      href: `/${locale}/dashboard/guide`,
      exact: false,
      icon: (active: boolean) => (
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"
            stroke={active ? '#4f46e5' : '#94a3b8'} strokeWidth="2"
            strokeLinecap="round" strokeLinejoin="round"
            fill={active ? '#eef2ff' : 'none'}/>
          <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"
            stroke={active ? '#4f46e5' : '#94a3b8'} strokeWidth="2"
            strokeLinecap="round" strokeLinejoin="round"
            fill={active ? '#eef2ff' : 'none'}/>
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
            <div className="relative">
              {item.icon(active)}
              {item.badge && !active && (
                <span className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-[#f97316]
                                 flex items-center justify-center text-[9px] font-bold text-white">
                  {item.badge}
                </span>
              )}
            </div>
            <span className={`text-[10px] font-semibold ${active ? 'text-[#4f46e5]' : 'text-slate-400'}`}>
              {item.label}
            </span>
          </Link>
        )
      })}
    </nav>
  )
}

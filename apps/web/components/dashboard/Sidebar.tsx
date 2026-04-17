'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import SignOutButton from './SignOutButton'

interface Props {
  user: { name: string; email: string }
  locale: string
}

export default function Sidebar({ user, locale }: Props) {
  const pathname = usePathname()

  const navItems = [
    {
      label: 'Chat',
      href: `/${locale}/dashboard`,
      exact: true,
      icon: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"
            stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      ),
    },
    {
      label: 'Reviews',
      href: `/${locale}/dashboard/reviews`,
      exact: false,
      badge: 3,
      icon: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"
            stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      ),
    },
    {
      label: 'Bookings',
      href: `/${locale}/dashboard/bookings`,
      exact: false,
      icon: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <rect x="3" y="4" width="18" height="18" rx="2" ry="2" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          <line x1="16" y1="2" x2="16" y2="6" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
          <line x1="8" y1="2" x2="8" y2="6" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
          <line x1="3" y1="10" x2="21" y2="10" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
        </svg>
      ),
    },
    {
      label: 'Guide',
      href: `/${locale}/dashboard/guide`,
      exact: false,
      icon: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      ),
    },
  ]

  const isActive = (href: string, exact: boolean) =>
    exact ? pathname === href : pathname.startsWith(href)

  const initial = (user.name || user.email)[0]?.toUpperCase() ?? '?'

  return (
    <aside className="hidden md:flex flex-col w-[240px] flex-shrink-0 min-h-screen
                      bg-gradient-to-b from-[#4f46e5] to-[#3730a3] p-6">

      {/* Logo */}
      <div className="flex items-center gap-2.5 mb-10">
        <svg width="32" height="32" viewBox="0 0 40 40" fill="none">
          <rect width="40" height="40" rx="12" fill="rgba(255,255,255,0.15)"/>
          <path d="M13 10 L13 28 L27 28" stroke="white" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"/>
          <circle cx="28" cy="13" r="4" fill="#f97316"/>
        </svg>
        <span className="text-xl font-extrabold text-white tracking-tight">
          Leap<span className="text-[#f97316]">One</span>
        </span>
      </div>

      {/* Nav */}
      <nav className="flex-1 flex flex-col gap-1">
        {navItems.map(item => (
          <Link
            key={item.href}
            href={item.href}
            className={`flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-semibold transition-colors
              ${isActive(item.href, item.exact)
                ? 'bg-white/20 text-white'
                : 'text-white/60 hover:text-white hover:bg-white/10'
              }`}
          >
            {item.icon}
            {item.label}
            {item.badge && (
              <span className="ml-auto w-5 h-5 rounded-full bg-[#f97316] flex items-center justify-center
                               text-[10px] font-bold text-white">
                {item.badge}
              </span>
            )}
          </Link>
        ))}
      </nav>

      {/* User + sign out */}
      <div className="border-t border-white/20 pt-4 mt-4">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-8 h-8 rounded-full bg-white/20 flex items-center justify-center
                          text-white text-xs font-bold flex-shrink-0">
            {initial}
          </div>
          <div className="min-w-0">
            <p className="text-sm font-semibold text-white truncate">
              {user.name || user.email}
            </p>
            {user.name && (
              <p className="text-xs text-white/50 truncate">{user.email}</p>
            )}
          </div>
        </div>
        <SignOutButton />
      </div>
    </aside>
  )
}

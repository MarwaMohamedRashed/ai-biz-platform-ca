'use client'

import { useState, useRef, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useLocale, useTranslations } from 'next-intl'
import { createClient } from '@/lib/supabase'

interface Props {
  initial: string
  name: string
  email: string
}

export default function UserMenu({ initial, name, email }: Props) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const router = useRouter()
  const locale = useLocale()
  const t = useTranslations('dashboard')

  useEffect(() => {
    function handleOutsideClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleOutsideClick)
    return () => document.removeEventListener('mousedown', handleOutsideClick)
  }, [])

  async function handleSignOut() {
    const supabase = createClient()
    await supabase.auth.signOut()
    router.push(`/${locale}/login`)
    router.refresh()
  }

  return (
    <div ref={ref} className="relative">

      {/* Avatar button */}
      <button
        onClick={() => setOpen(v => !v)}
        aria-label="Account menu"
        className="w-8 h-8 rounded-full bg-[#4f46e5] flex items-center justify-center
                   text-white text-xs font-bold hover:bg-indigo-700 transition-colors">
        {initial}
      </button>

      {/* Dropdown */}
      {open && (
        <div className="absolute right-0 top-10 w-52 bg-white rounded-xl shadow-lg
                        border border-slate-200 overflow-hidden z-50">

          {/* User info */}
          <div className="px-4 py-3 border-b border-slate-100">
            <p className="text-xs font-semibold text-[#1e293b] truncate">{name || email}</p>
            {name && <p className="text-[11px] text-slate-400 truncate">{email}</p>}
          </div>

          {/* Sign out */}
          <button
            onClick={handleSignOut}
            className="flex items-center gap-2 w-full px-4 py-3 text-sm text-slate-600
                       hover:bg-slate-50 transition-colors text-left">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"
                stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              <polyline points="16 17 21 12 16 7"
                stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              <line x1="21" y1="12" x2="9" y2="12"
                stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
            {t('signOut')}
          </button>

        </div>
      )}

    </div>
  )
}

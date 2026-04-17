'use client'

import { useState } from 'react'
import { useTranslations } from 'next-intl'
import { useLocale } from 'next-intl'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { createClient } from '@/lib/supabase'

export default function LoginForm() {
  const t = useTranslations('auth.login')
  const locale = useLocale()
  const router = useRouter()

  // ── Form state ──────────────────────────────────────────────────────────────
  const [email, setEmail]       = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading]   = useState(false)
  const [error, setError]       = useState('')

  // ── Submit handler ──────────────────────────────────────────────────────────
  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()   // stop the browser from reloading the page
    setError('')
    setLoading(true)

    const supabase = createClient()

    const { error } = await supabase.auth.signInWithPassword({ email, password })

    if (error) {
      setError(error.message)
      setLoading(false)
      return
    }

    // Success — send user to the dashboard
    router.push(`/${locale}/dashboard`)
    router.refresh()     // tells Next.js to re-fetch server data with new session
  }

  // ── UI ──────────────────────────────────────────────────────────────────────
  return (
    <>
      {/* Inline error banner */}
      {error && (
        <div className="mb-4 px-3.5 py-2.5 rounded-[10px] bg-red-50 border border-red-200
                        text-xs text-red-600 font-medium">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-3.5">
        <div>
          <label className="block text-xs font-semibold text-slate-600 mb-1.5">
            {t('emailAddress')}
          </label>
          <input
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={e => setEmail(e.target.value)}
            className="w-full px-3.5 py-[11px] border-[1.5px] border-slate-200 rounded-[10px]
                       text-sm text-[#1e293b] bg-[#f8fafc]
                       focus:outline-none focus:border-[#4f46e5] focus:bg-white transition-colors" />
        </div>

        <div>
          <label className="block text-xs font-semibold text-slate-600 mb-1.5">
            {t('password')}
          </label>
          <input
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={e => setPassword(e.target.value)}
            className="w-full px-3.5 py-[11px] border-[1.5px] border-slate-200 rounded-[10px]
                       text-sm text-[#1e293b] bg-[#f8fafc]
                       focus:outline-none focus:border-[#4f46e5] focus:bg-white transition-colors" />
        </div>

        <div className="text-right">
          <Link href={`/${locale}/forgot-password`}
            className="text-xs text-[#4f46e5] font-medium hover:underline">
            {t('forgotPassword')}
          </Link>
        </div>

        <button
          type="submit"
          disabled={loading}
          className="w-full py-3 bg-[#4f46e5] text-white rounded-[10px] text-sm font-semibold
                     shadow-[0_4px_12px_rgba(79,70,229,0.28)] hover:bg-indigo-700 transition-colors 
                     disabled:opacity-60 disabled:cursor-not-allowed">
          {loading ? t('signingIn') : t('submit')}
        </button>
      </form>
    </>
  )
}

'use client'
import { useState } from 'react'
import { useTranslations } from 'next-intl'
import { useLocale } from 'next-intl'
import { useRouter } from 'next/navigation'
import { createClient } from '@/lib/supabase'

export default function SignupForm() {
  const t = useTranslations('auth.signup')
  const locale = useLocale()
  const router = useRouter()

  // your state will go here
  const [firstName, setFirstName] = useState('')
  const [lastName, setLastName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [terms, setTerms] = useState(false)

  // your handleSubmit will go here
  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')

    // ── Validate before calling Supabase ──────────────────────
    if (!terms) {
        setError(t('errorTerms'))
        return
    }

    if (password.length < 8) {
        setError(t('errorPasswordLength'))
        return
    }

    if (!/[A-Z]/.test(password) || !/[0-9]/.test(password)) {
        setError(t('errorPasswordWeak'))
        return
    }
    if (password !== confirmPassword) {
        setError(t('errorPasswordMatch'))
        return
    }

    setLoading(true)

    // ── Call Supabase ──────────────────────────────────────────
    const supabase = createClient()

    const { data, error } = await supabase.auth.signUp({
        email,
        password,
        options: {
        data: { first_name: firstName, last_name: lastName },
        emailRedirectTo: `${window.location.origin}/${locale}/auth/callback`
        }
    })

    if (error) {
        setError(error.message)
        setLoading(false)
        return
    }
    if (!data.user || data.user.identities?.length === 0) {
        setError(t('errorEmailExists'))
        setLoading(false)
        return
    }
    

    router.push(`/${locale}/verify-email`)
  }

  return (
    // your JSX will go here
    <>
        {/* Error banner — show only when there is an error */}
        {error && (
        <div className="mb-4 px-3.5 py-2.5 rounded-[10px] bg-red-50 border border-red-200
                        text-xs text-red-600 font-medium">
            {error}
        </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-3.5" >
                    <div className="flex gap-3">
                        <div className="flex-1">
                        <label className="block text-xs font-semibold text-slate-600 mb-1.5">
                            {t('firstName')}
                        </label>
                        <input type="text" autoComplete="given-name"
                            value={firstName}
                            onChange={e => setFirstName(e.target.value)}
                            className="w-full px-3.5 py-[11px] border-[1.5px] border-slate-200 rounded-[10px]
                                    text-sm text-[#1e293b] bg-[#f8fafc]
                                    focus:outline-none focus:border-[#4f46e5] focus:bg-white transition-colors" />
                        </div>
                        <div className="flex-1">
                        <label className="block text-xs font-semibold text-slate-600 mb-1.5">
                            {t('lastName')}
                        </label>
                        <input type="text" autoComplete="family-name"
                            value={lastName}
                            onChange={e => setLastName(e.target.value)}
                            className="w-full px-3.5 py-[11px] border-[1.5px] border-slate-200 rounded-[10px]
                                    text-sm text-[#1e293b] bg-[#f8fafc]
                                    focus:outline-none focus:border-[#4f46e5] focus:bg-white transition-colors" />
                        </div>
                    </div>

                    <div>
                        <label className="block text-xs font-semibold text-slate-600 mb-1.5">
                        {t('workEmail')}
                        </label>
                        <input type="email" autoComplete="email"
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
                        <input type="password" autoComplete="new-password"
                            value={password}
                            onChange={e => setPassword(e.target.value)}
                        className="w-full px-3.5 py-[11px] border-[1.5px] border-slate-200 rounded-[10px]
                                    text-sm text-[#1e293b] bg-[#f8fafc]
                                    focus:outline-none focus:border-[#4f46e5] focus:bg-white transition-colors" />
                    </div>

                    <div>
                        <label className="block text-xs font-semibold text-slate-600 mb-1.5">
                        {t('confirmPassword')}
                        </label>
                        <input type="password" autoComplete="new-password"
                            value={confirmPassword}
                            onChange={e => setConfirmPassword(e.target.value)}
                        className="w-full px-3.5 py-[11px] border-[1.5px] border-slate-200 rounded-[10px]
                                    text-sm text-[#1e293b] bg-[#f8fafc]
                                    focus:outline-none focus:border-[#4f46e5] focus:bg-white transition-colors" />
                    </div>

                    <div className="flex items-start gap-2.5 py-1">
                        <input type="checkbox" id="terms"
                        checked={terms}
                        onChange={e => setTerms(e.target.checked)}
                        className="mt-0.5 w-3.5 h-3.5 flex-shrink-0 accent-[#4f46e5]" />
                        <label htmlFor="terms" className="text-xs text-slate-500 leading-relaxed">
                        {t('terms')}
                        </label>
                    </div>

                    <button type="submit"
                    disabled={loading}
                        className="w-full py-3 bg-[#4f46e5] text-white rounded-[10px] text-sm font-semibold
                                shadow-[0_4px_12px_rgba(79,70,229,0.28)] hover:bg-indigo-700 transition-colors disabled:opacity-60 disabled:cursor-not-allowed">
                        {loading ? t('signingUp') : t('submit')}
                    </button>
                    </form>
    </>
  )
}

'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { useTranslations, useLocale } from 'next-intl'
import { createClient } from '@/lib/supabase'

export default function ResetPasswordForm() {
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const t = useTranslations('auth.resetPassword')
  const locale = useLocale()
  const router = useRouter()

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')

    if (password.length < 8) {
      setError(t('errorLength'))
      return
    }
    if (!/[A-Z]/.test(password) || !/[0-9]/.test(password)) {
      setError(t('errorWeak'))
      return
    }
    if (password !== confirm) {
      setError(t('errorMatch'))
      return
    }

    setLoading(true)
    const supabase = createClient()
    const { error } = await supabase.auth.updateUser({ password })
    setLoading(false)

    if (error) {
      setError(error.message)
      return
    }

    router.push(`/${locale}/dashboard`)
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-xl px-4 py-3">
          {error}
        </div>
      )}

      <div className="flex flex-col gap-1.5">
        <label className="text-sm font-medium text-[#1e293b]">{t('newPassword')}</label>
        <input
          type="password"
          required
          value={password}
          onChange={e => setPassword(e.target.value)}
          className="border border-slate-200 rounded-xl px-4 py-3 text-sm text-[#1e293b]
                     outline-none focus:border-[#4f46e5] transition-colors" />
      </div>

      <div className="flex flex-col gap-1.5">
        <label className="text-sm font-medium text-[#1e293b]">{t('confirmPassword')}</label>
        <input
          type="password"
          required
          value={confirm}
          onChange={e => setConfirm(e.target.value)}
          className="border border-slate-200 rounded-xl px-4 py-3 text-sm text-[#1e293b]
                     outline-none focus:border-[#4f46e5] transition-colors" />
      </div>

      <button
        type="submit"
        disabled={loading || !password || !confirm}
        className="w-full py-3 rounded-xl bg-[#4f46e5] text-white text-sm font-semibold
                   hover:bg-indigo-700 transition-colors disabled:opacity-50">
        {loading ? t('saving') : t('submit')}
      </button>
    </form>
  )
}
'use client'

import { useState } from 'react'
import { useTranslations } from 'next-intl'
import { createClient } from '@/lib/supabase'

interface Props {
  name: string
  email: string
  avatarUrl: string
}

export default function ProfileForm({ name, email, avatarUrl }: Props) {
  const [fullName, setFullName] = useState(name)
  const [loading, setLoading] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState('')
  const t = useTranslations('dashboard.profile')

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setSaved(false)
    setLoading(true)

    const supabase = createClient()
    const { error } = await supabase.auth.updateUser({
      data: { full_name: fullName }
    })

    setLoading(false)

    if (error) {
      setError(error.message)
      return
    }
    const { data: { user } } = await supabase.auth.getUser()
    if (user) {
        await supabase.from('profiles').update({ full_name: fullName }).eq('id', user.id)
    }

    setSaved(true)
  }

  const initials = fullName
    .split(' ')
    .map(w => w[0])
    .join('')
    .toUpperCase()
    .slice(0, 2)

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-6">

      {/* Avatar */}
     <div className="flex items-center gap-4">
    {avatarUrl ? (
      <img src={avatarUrl} alt={fullName} className="w-16 h-16 rounded-full object-cover" />
    ) : (
      <div className="w-16 h-16 rounded-full bg-[#4f46e5] flex items-center justify-center
                      text-white text-xl font-bold">
        {initials || '?'}
      </div>
    )}
    <div>
      <p className="text-sm font-medium text-[#1e293b]">{fullName || email}</p>
      <p className="text-xs text-slate-400">{email}</p>
    </div>
  </div>

      {/* Error */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-xl px-4 py-3">
          {error}
        </div>
      )}

      {/* Full name */}
      <div className="flex flex-col gap-1.5">
        <label className="text-sm font-medium text-[#1e293b]">{t('fullName')}</label>
        <input
          type="text"
          value={fullName}
          onChange={e => setFullName(e.target.value)}
          className="border border-slate-200 rounded-xl px-4 py-3 text-sm text-[#1e293b]
                     outline-none focus:border-[#4f46e5] transition-colors" />
      </div>

      {/* Email (read-only) */}
      <div className="flex flex-col gap-1.5">
        <label className="text-sm font-medium text-[#1e293b]">{t('email')}</label>
        <input
          type="email"
          value={email}
          readOnly
          className="border border-slate-200 rounded-xl px-4 py-3 text-sm text-slate-400
                     bg-slate-50 cursor-not-allowed" />
        <p className="text-xs text-slate-400">{t('emailHint')}</p>
      </div>

      {/* Save button */}
      <button
        type="submit"
        disabled={loading}
        className="w-full py-3 rounded-xl bg-[#4f46e5] text-white text-sm font-semibold
                   hover:bg-indigo-700 transition-colors disabled:opacity-50">
        {loading ? t('saving') : saved ? t('saved') : t('save')}
      </button>

    </form>
  )
}
'use client'

import { useState } from 'react'
import { useTranslations } from 'next-intl'
import { createClient } from '@/lib/supabase'

const COUNTRIES = [
  'Canada', 'United States', 'United Kingdom', 'Australia', 'France',
  'Germany', 'Spain', 'Italy', 'Netherlands', 'Belgium', 'Switzerland',
  'New Zealand', 'Ireland', 'Portugal', 'Mexico', 'Brazil', 'India',
  'Japan', 'South Korea', 'Singapore', 'South Africa', 'Other'
]

const TYPES = ['restaurant', 'salon', 'retail', 'plumber', 'cafe', 'other'] as const

interface Props {
  userId: string
  onComplete: (businessName: string) => void
}

export default function StepBusinessInfo({ userId, onComplete }: Props) {
  const t = useTranslations('onboarding.step1')
  const [name, setName] = useState('')
  const [type, setType] = useState('')
  const [country, setCountry] = useState('Canada')
  const [city, setCity] = useState('')
  const [province, setProvince] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [customType, setCustomType] = useState('')

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!name || !type || !city) return
    setError('')
    setLoading(true)

    const supabase = createClient()
   const { error } = await supabase.from('businesses').insert({
    user_id: userId,
    name,
    type: type === 'other' ? customType : type,
    country,
    city,
    province: province || null
  })

  setLoading(false)

  if (error) {
    setError(error.message)
    return
  }

  onComplete(name)
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold text-[#1e293b]">{t('heading')}</h1>
        <p className="text-sm text-slate-500 mt-1">{t('subtitle')}</p>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-xl px-4 py-3">
          {error}
        </div>
      )}

      {/* Business name */}
      <div className="flex flex-col gap-1.5">
        <label className="text-sm font-medium text-[#1e293b]">{t('businessName')}</label>
        <input
          type="text"
          required
          value={name}
          onChange={e => setName(e.target.value)}
          className="border border-slate-200 rounded-xl px-4 py-3 text-sm text-[#1e293b]
                     outline-none focus:border-[#4f46e5] transition-colors" />
      </div>

      {/* Business type chips */}
      <div className="flex flex-col gap-2">
        <label className="text-sm font-medium text-[#1e293b]">{t('businessType')}</label>
        <div className="flex flex-wrap gap-2">
          {TYPES.map(bt => (
            <button
              key={bt}
              type="button"
              onClick={() => setType(bt)}
              className={`px-4 py-2 rounded-full text-sm font-medium border transition-colors
                ${type === bt
                  ? 'bg-[#4f46e5] text-white border-[#4f46e5]'
                  : 'bg-white text-slate-600 border-slate-200 hover:border-[#4f46e5]'
                }`}>
              {t(`types.${bt}`)}
            </button>
          ))}
        </div>
      </div>

      {type === 'other' && (
        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-medium text-[#1e293b]">{t('customType')}</label>
          <input
            type="text"
            required
            value={customType}
            onChange={e => setCustomType(e.target.value)}
            placeholder={t('customTypePlaceholder')}
            className="border border-slate-200 rounded-xl px-4 py-3 text-sm text-[#1e293b]
                      outline-none focus:border-[#4f46e5] transition-colors" />
        </div>
      )}

      {/* Country */}
      <div className="flex flex-col gap-1.5">
        <label className="text-sm font-medium text-[#1e293b]">{t('country')}</label>
        <select
          value={country}
          onChange={e => setCountry(e.target.value)}
          className="border border-slate-200 rounded-xl px-4 py-3 text-sm text-[#1e293b]
                     outline-none focus:border-[#4f46e5] transition-colors bg-white">
          {COUNTRIES.map(c => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
      </div>

      {/* City + Province/State */}
      <div className="flex gap-3">
        <div className="flex flex-col gap-1.5 flex-1">
          <label className="text-sm font-medium text-[#1e293b]">{t('city')}</label>
          <input
            type="text"
            required
            value={city}
            onChange={e => setCity(e.target.value)}
            className="border border-slate-200 rounded-xl px-4 py-3 text-sm text-[#1e293b]
                       outline-none focus:border-[#4f46e5] transition-colors" />
        </div>
        <div className="flex flex-col gap-1.5 w-32">
          <label className="text-sm font-medium text-[#1e293b]">{t('provinceState')}</label>
          <input
            type="text"
            value={province}
            onChange={e => setProvince(e.target.value)}
            className="border border-slate-200 rounded-xl px-4 py-3 text-sm text-[#1e293b]
                       outline-none focus:border-[#4f46e5] transition-colors" />
        </div>
      </div>

      <button
        type="submit"
        disabled={loading || !name || !type || !city || (type === 'other' && !customType)}
        className="w-full py-3 rounded-xl bg-[#4f46e5] text-white text-sm font-semibold
                   hover:bg-indigo-700 transition-colors disabled:opacity-50">
        {loading ? t('saving') : t('next')}
      </button>
    </form>
  )
}
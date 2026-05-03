'use client'
import { useEffect, useRef, useState } from 'react'
import { useTranslations, useLocale } from 'next-intl'
import { createClient } from '@/lib/supabase'

const COUNTRIES = [
  'Canada', 'United States', 'United Kingdom', 'Australia', 'France',
  'Germany', 'Spain', 'Italy', 'Netherlands', 'Belgium', 'Switzerland',
  'New Zealand', 'Ireland', 'Portugal', 'Mexico', 'Brazil', 'India',
  'Japan', 'South Korea', 'Singapore', 'South Africa',
]

async function apiAuth(path: string, options: RequestInit = {}) {
  const { data: { session } } = await createClient().auth.getSession()
  const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${session?.access_token}`,
      ...(options.headers ?? {}),
    },
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export default function SettingsPage() {
  const t = useTranslations('dashboard.settings')
  const locale = useLocale()

  // ── Business profile state ─────────────────────────────────────────────────
  const [bizName, setBizName] = useState('')
  const [bizType, setBizType] = useState('')
  const [bizCity, setBizCity] = useState('')
  const [bizProvince, setBizProvince] = useState('')
  const [bizCountry, setBizCountry] = useState('Canada')
  const [bizWebsite, setBizWebsite] = useState('')
  const [bizServices, setBizServices] = useState('')
  const [bizSaving, setBizSaving] = useState(false)
  const [bizSaved, setBizSaved] = useState(false)
  const [bizError, setBizError] = useState('')

  // ── Review response settings state ────────────────────────────────────────
  const [tone_preference, setTone_preference] = useState('casual')
  const [response_language, setResponse_language] = useState('match_reviewer')
  const [business_description, setBusiness_description] = useState('')
  const [response_length, setResponse_length] = useState('medium')
  const [cta_custom_text, setCta_custom_text] = useState('')
  const [auto_draft_enabled, setAuto_draft_enabled] = useState(false)
  const [cta_enabled, setCta_enabled] = useState(true)
  const [delay_acknowledgment, setDelay_acknowledgment] = useState(false)
  const [revSaving, setRevSaving] = useState(false)
  const [revSaved, setRevSaved] = useState(false)
  const [revError, setRevError] = useState('')

  const bizSavedTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const revSavedTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  // ── Load both on mount ─────────────────────────────────────────────────────
  useEffect(() => {
    apiAuth('/api/v1/aeo/business')
      .then(data => {
        setBizName(data.name ?? '')
        setBizType(data.type ?? '')
        setBizCity(data.city ?? '')
        setBizProvince(data.province ?? '')
        setBizCountry(data.country ?? 'Canada')
        setBizWebsite(data.website ?? '')
        setBizServices(data.services ?? '')
      })
      .catch(() => {/* silently ignore — fields stay blank */})

    apiAuth('/api/v1/settings/')
      .then(data => {
        const s = data.business_settings
        if (!s) return
        setTone_preference(s.tone_preference || 'casual')
        setResponse_language(s.response_language || 'match_reviewer')
        setBusiness_description(s.business_description || '')
        setResponse_length(s.response_length || 'medium')
        setCta_custom_text(s.cta_custom_text || '')
        setAuto_draft_enabled(s.auto_draft_enabled ?? false)
        setCta_enabled(s.cta_enabled ?? true)
        setDelay_acknowledgment(s.delay_acknowledgment ?? false)
      })
      .catch(() => {/* silently ignore */})
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [locale])

  // ── Save business profile ─────────────────────────────────────────────────
  async function handleBizSave(e: React.FormEvent) {
    e.preventDefault()
    setBizSaving(true)
    setBizError('')
    setBizSaved(false)
    try {
      await apiAuth('/api/v1/aeo/business', {
        method: 'PUT',
        body: JSON.stringify({
          name: bizName, type: bizType, city: bizCity,
          province: bizProvince || null, country: bizCountry,
          website: bizWebsite || null, services: bizServices || null,
        }),
      })
      setBizSaved(true)
      if (bizSavedTimer.current) clearTimeout(bizSavedTimer.current)
      bizSavedTimer.current = setTimeout(() => setBizSaved(false), 3000)
    } catch {
      setBizError(t('businessProfile.errorSave'))
    } finally {
      setBizSaving(false)
    }
  }

  // ── Save review response settings ─────────────────────────────────────────
  async function handleRevSave(e: React.FormEvent) {
    e.preventDefault()
    setRevSaving(true)
    setRevError('')
    setRevSaved(false)
    try {
      await apiAuth('/api/v1/settings/', {
        method: 'PUT',
        body: JSON.stringify({
          tone_preference, response_language, business_description,
          response_length, cta_custom_text, auto_draft_enabled,
          cta_enabled, delay_acknowledgment,
        }),
      })
      setRevSaved(true)
      if (revSavedTimer.current) clearTimeout(revSavedTimer.current)
      revSavedTimer.current = setTimeout(() => setRevSaved(false), 3000)
    } catch {
      setRevError(t('errorSave'))
    } finally {
      setRevSaving(false)
    }
  }

  const inputClass = 'w-full border-[1.5px] border-slate-200 rounded-xl px-3 py-2.5 text-sm text-[#1e293b] focus:outline-none focus:border-[#4f46e5] transition-colors'
  const labelClass = 'block text-xs font-semibold text-slate-600 mb-1'

  return (
    <div className="flex-1 overflow-y-auto px-4 md:px-6 py-4 max-w-2xl">

      {/* ── Business profile ─────────────────────────────────────────────── */}
      <form onSubmit={handleBizSave} className="bg-white rounded-2xl border border-slate-100 shadow-sm p-5 mb-5">
        <div className="mb-4">
          <h2 className="text-sm font-extrabold text-[#1e293b]">{t('businessProfile.title')}</h2>
          <p className="text-[11px] text-slate-500 mt-0.5">{t('businessProfile.subtitle')}</p>
        </div>

        <div className="mb-4">
          <label className={labelClass}>{t('businessProfile.nameLabel')}</label>
          <input required type="text" value={bizName} onChange={e => setBizName(e.target.value)} className={inputClass} />
        </div>

        <div className="mb-4">
          <label className={labelClass}>{t('businessProfile.typeLabel')}</label>
          <input type="text" value={bizType} onChange={e => setBizType(e.target.value)} className={inputClass}
            placeholder="e.g. physiotherapy clinic, italian restaurant" />
          <p className="text-[10px] text-slate-400 mt-1">{t('businessProfile.typeHint')}</p>
        </div>

        <div className="grid grid-cols-2 gap-3 mb-4">
          <div>
            <label className={labelClass}>{t('businessProfile.cityLabel')}</label>
            <input required type="text" value={bizCity} onChange={e => setBizCity(e.target.value)} className={inputClass} />
          </div>
          <div>
            <label className={labelClass}>{t('businessProfile.provinceLabel')}</label>
            <input type="text" value={bizProvince} onChange={e => setBizProvince(e.target.value)} className={inputClass}
              placeholder="ON, QC, BC…" />
          </div>
        </div>

        <div className="mb-4">
          <label className={labelClass}>{t('businessProfile.countryLabel')}</label>
          <select value={bizCountry} onChange={e => setBizCountry(e.target.value)} className={inputClass}>
            {COUNTRIES.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>

        <div className="mb-4">
          <label className={labelClass}>{t('businessProfile.websiteLabel')}</label>
          <input type="url" value={bizWebsite} onChange={e => setBizWebsite(e.target.value)} className={inputClass}
            placeholder={t('businessProfile.websitePlaceholder')} />
        </div>

        <div className="mb-4">
          <label className={labelClass}>{t('businessProfile.servicesLabel')}</label>
          <input type="text" value={bizServices} onChange={e => setBizServices(e.target.value)} className={inputClass} />
          <p className="text-[10px] text-slate-400 mt-1">{t('businessProfile.servicesHint')}</p>
        </div>

        {bizError && <p className="text-xs text-red-500 mb-3">{bizError}</p>}

        <div className="flex items-center gap-3">
          <button type="submit" disabled={bizSaving}
            className="px-4 py-2.5 bg-[#4f46e5] text-white text-xs font-semibold rounded-xl hover:bg-indigo-700 transition-colors disabled:opacity-50">
            {bizSaving ? t('businessProfile.saving') : t('businessProfile.save')}
          </button>
          {bizSaved && <span className="text-xs text-green-600 font-semibold">✓ {t('businessProfile.saved')}</span>}
        </div>
      </form>

      {/* ── Review response settings ─────────────────────────────────────── */}
      <form onSubmit={handleRevSave} className="bg-white rounded-2xl border border-slate-100 shadow-sm p-5 mb-6">
        <div className="mb-4">
          <h2 className="text-sm font-extrabold text-[#1e293b]">{t('reviewSettings')}</h2>
        </div>

        <div className="mb-4">
          <label className={labelClass}>{t('toneLabel')}</label>
          <select value={tone_preference} onChange={e => setTone_preference(e.target.value)} className={inputClass}>
            <option value="casual">{t('toneOptions.casual')}</option>
            <option value="professional">{t('toneOptions.professional')}</option>
            <option value="playful">{t('toneOptions.playful')}</option>
          </select>
        </div>

        <div className="mb-4">
          <label className={labelClass}>{t('languageLabel')}</label>
          <select value={response_language} onChange={e => setResponse_language(e.target.value)} className={inputClass}>
            <option value="match_reviewer">{t('languageOptions.match_reviewer')}</option>
            <option value="english">{t('languageOptions.english')}</option>
            <option value="french">{t('languageOptions.french')}</option>
          </select>
        </div>

        <div className="mb-4">
          <label className={labelClass}>{t('descriptionLabel')}</label>
          <textarea value={business_description} onChange={e => setBusiness_description(e.target.value)}
            className={inputClass} rows={4} />
        </div>

        <div className="mb-4">
          <label className={labelClass}>{t('lengthLabel')}</label>
          <select value={response_length} onChange={e => setResponse_length(e.target.value)} className={inputClass}>
            <option value="short">{t('lengthOptions.short')}</option>
            <option value="medium">{t('lengthOptions.medium')}</option>
            <option value="long">{t('lengthOptions.long')}</option>
          </select>
        </div>

        <div className="mb-4">
          <label className={labelClass}>{t('ctaCustomLabel')}</label>
          <input type="text" value={cta_custom_text} onChange={e => setCta_custom_text(e.target.value)} className={inputClass} />
          <p className="text-[10px] text-slate-400 mt-1">{t('ctaCustomHint')}</p>
        </div>

        <div className="mb-4">
          <div className="flex items-center gap-2">
            <input type="checkbox" id="auto_draft" checked={auto_draft_enabled} onChange={e => setAuto_draft_enabled(e.target.checked)}
              className="h-4 w-4 text-[#4f46e5] border-gray-300 rounded focus:ring-[#4f46e5]" />
            <label htmlFor="auto_draft" className="text-xs font-semibold text-slate-600">{t('autoDraftLabel')}</label>
          </div>
          <p className="text-[10px] text-slate-400 mt-0.5 ml-6">{t('autoDraftHint')}</p>
        </div>

        <div className="mb-4">
          <div className="flex items-center gap-2">
            <input type="checkbox" id="cta_enabled" checked={cta_enabled} onChange={e => setCta_enabled(e.target.checked)}
              className="h-4 w-4 text-[#4f46e5] border-gray-300 rounded focus:ring-[#4f46e5]" />
            <label htmlFor="cta_enabled" className="text-xs font-semibold text-slate-600">{t('ctaEnabledLabel')}</label>
          </div>
          <p className="text-[10px] text-slate-400 mt-0.5 ml-6">{t('ctaEnabledHint')}</p>
        </div>

        <div className="mb-4">
          <div className="flex items-center gap-2">
            <input type="checkbox" id="delay_ack" checked={delay_acknowledgment} onChange={e => setDelay_acknowledgment(e.target.checked)}
              className="h-4 w-4 text-[#4f46e5] border-gray-300 rounded focus:ring-[#4f46e5]" />
            <label htmlFor="delay_ack" className="text-xs font-semibold text-slate-600">{t('delayLabel')}</label>
          </div>
          <p className="text-[10px] text-slate-400 mt-0.5 ml-6">{t('delayHint')}</p>
        </div>

        {revError && <p className="text-xs text-red-500 mb-3">{revError}</p>}

        <div className="flex items-center gap-3">
          <button type="submit" disabled={revSaving}
            className="px-4 py-2.5 bg-[#4f46e5] text-white text-xs font-semibold rounded-xl hover:bg-indigo-700 transition-colors disabled:opacity-50">
            {revSaving ? t('saving') : t('save')}
          </button>
          {revSaved && <span className="text-xs text-green-600 font-semibold">✓ {t('saved')}</span>}
        </div>
      </form>

    </div>
  )
}
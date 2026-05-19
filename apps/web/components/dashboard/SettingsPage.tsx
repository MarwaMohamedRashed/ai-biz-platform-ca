'use client'
import { useEffect, useRef, useState } from 'react'
import { useTranslations, useLocale } from 'next-intl'
import { createClient } from '@/lib/supabase'
import HoursEditor, { HoursValue } from './HoursEditor'

const COUNTRIES = [
  'Canada', 'United States', 'United Kingdom', 'Australia', 'France',
  'Germany', 'Spain', 'Italy', 'Netherlands', 'Belgium', 'Switzerland',
  'New Zealand', 'Ireland', 'Portugal', 'Mexico', 'Brazil', 'India',
  'Japan', 'South Korea', 'Singapore', 'South Africa',
]

// Mirrors onboarding/StepBusinessInfo TYPES so Settings and the
// onboarding chip flow stay in sync (same labels via onboarding.step1.types.*).
// `phrase` is what we store in businesses.type — feeds the audit's search
// queries, so it reads as a natural noun phrase.
const BUSINESS_TYPES = [
  { key: 'restaurant',       phrase: 'restaurant' },
  { key: 'cafe',             phrase: 'cafe' },
  { key: 'salon',            phrase: 'salon' },
  { key: 'retail',           phrase: 'retail' },
  { key: 'dentist',          phrase: 'dentist' },
  { key: 'physiotherapist',  phrase: 'physiotherapy clinic' },
  { key: 'family_doctor',    phrase: 'family doctor' },
  { key: 'chiropractor',     phrase: 'chiropractor' },
  { key: 'optometrist',      phrase: 'optometrist' },
  { key: 'veterinarian',     phrase: 'veterinarian' },
  { key: 'lawyer',           phrase: 'lawyer' },
  { key: 'accountant',       phrase: 'accountant' },
  { key: 'realtor',          phrase: 'realtor' },
  { key: 'plumber',          phrase: 'plumber' },
  { key: 'auto_repair',      phrase: 'auto repair' },
  { key: 'cleaning_service', phrase: 'cleaning service' },
  { key: 'personal_trainer', phrase: 'personal trainer' },
  { key: 'other',            phrase: 'other' },
] as const

const BUSINESS_TYPE_PHRASES = new Set(BUSINESS_TYPES.map(b => b.phrase))

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
  const tPlan = useTranslations('dashboard.plan')
  const tTypes = useTranslations('onboarding.step1')
  const locale = useLocale()

  // ── Business profile state ─────────────────────────────────────────────────
  const [bizName, setBizName] = useState('')
  // `bizType` is the canonical phrase stored on the row. `bizTypeSelect`
  // tracks the dropdown value separately so a saved phrase that isn't in
  // BUSINESS_TYPES (legacy data, or a custom value entered before this
  // dropdown existed) cleanly maps to "other" + a populated text input.
  const [bizType, setBizType] = useState('')
  const [bizTypeSelect, setBizTypeSelect] = useState('')
  const [bizCity, setBizCity] = useState('')
  const [bizProvince, setBizProvince] = useState('')
  const [bizCountry, setBizCountry] = useState('Canada')
  const [bizWebsite, setBizWebsite] = useState('')
  const [bizServices, setBizServices] = useState('')
  // Schema-generator fields (migration 015)
  const [bizStreet, setBizStreet] = useState('')
  const [bizPostal, setBizPostal] = useState('')
  const [bizPhone, setBizPhone] = useState('')
  const [bizImage, setBizImage] = useState('')
  const [bizPriceRange, setBizPriceRange] = useState('')
  const [bizHours, setBizHours] = useState<HoursValue>({})
  const [bizCompetitorScope, setBizCompetitorScope] = useState<'local' | 'country' | 'global'>('local')
  // ROI inputs (migration 022). Stored as strings so the empty state is
  // clean — converted to numbers (or null) just before save.
  const [bizAvgCustomerValue, setBizAvgCustomerValue]   = useState('')
  const [bizMonthlyOnline, setBizMonthlyOnline]         = useState('')
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

  const [portalLoading, setPortalLoading] = useState(false)
  const [portalError, setPortalError] = useState('')

  const bizSavedTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const revSavedTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  // ── Load both on mount ─────────────────────────────────────────────────────
  useEffect(() => {
    apiAuth('/api/v1/aeo/business')
      .then(data => {
        setBizName(data.name ?? '')
        const savedType = (data.type ?? '') as string
        setBizType(savedType)
        // Map the saved phrase to a dropdown option. Anything we don't
        // recognize falls through to "other" and the text box surfaces
        // the original value so the user can edit it.
        if (!savedType) {
          setBizTypeSelect('')
        } else if (BUSINESS_TYPE_PHRASES.has(savedType as typeof BUSINESS_TYPES[number]['phrase'])) {
          setBizTypeSelect(savedType)
        } else {
          setBizTypeSelect('other')
        }
        setBizCity(data.city ?? '')
        setBizProvince(data.province ?? '')
        setBizCountry(data.country ?? 'Canada')
        setBizWebsite(data.website ?? '')
        setBizServices(data.services ?? '')
        setBizStreet(data.street_address ?? '')
        setBizPostal(data.postal_code ?? '')
        setBizPhone(data.phone ?? '')
        setBizImage(data.image_url ?? '')
        setBizPriceRange(data.price_range ?? '')
        setBizHours(data.hours ?? {})
        const scope = data.competitor_scope
        if (scope === 'local' || scope === 'country' || scope === 'global') {
          setBizCompetitorScope(scope)
        }
        // ROI inputs — empty string = "not set" so the UI shows the
        // placeholder. We don't convert to "0" because 0 is a valid
        // (if unusual) answer for "monthly new customers".
        setBizAvgCustomerValue(
          data.avg_customer_value_cad != null ? String(data.avg_customer_value_cad) : ''
        )
        setBizMonthlyOnline(
          data.monthly_new_online_customers != null ? String(data.monthly_new_online_customers) : ''
        )
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
    // "Other" selected with an empty text input would silently blank the
    // business type on the row. Block the save and surface a hint instead.
    if (bizTypeSelect === 'other' && !bizType.trim()) {
      setBizError(t('businessProfile.typeRequired'))
      return
    }
    setBizSaving(true)
    setBizError('')
    setBizSaved(false)
    try {
      const avgValueNum = bizAvgCustomerValue.trim() ? Number(bizAvgCustomerValue) : null
      const monthlyOnlineNum = bizMonthlyOnline.trim() ? Math.round(Number(bizMonthlyOnline)) : null
      await apiAuth('/api/v1/aeo/business', {
        method: 'PUT',
        body: JSON.stringify({
          name: bizName, type: bizType, city: bizCity,
          province: bizProvince || null, country: bizCountry,
          website: bizWebsite || null, services: bizServices || null,
          street_address: bizStreet || null,
          postal_code: bizPostal || null,
          phone: bizPhone || null,
          image_url: bizImage || null,
          price_range: bizPriceRange || null,
          hours: Object.keys(bizHours).length ? bizHours : null,
          competitor_scope: bizCompetitorScope,
          avg_customer_value_cad:       Number.isFinite(avgValueNum) ? avgValueNum : null,
          monthly_new_online_customers: Number.isFinite(monthlyOnlineNum) ? monthlyOnlineNum : null,
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

  // ── Manage subscription ───────────────────────────────────────────────────
  async function handleManageSubscription() {
    setPortalLoading(true)
    setPortalError('')
    try {
      const data = await apiAuth('/api/v1/billing/portal-session', {
        method: 'POST',
        body: JSON.stringify({ locale }),
      })
      window.location.href = data.url
    } catch {
      setPortalError(tPlan('portalError'))
      setPortalLoading(false)
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
          <select
            value={bizTypeSelect}
            onChange={e => {
              const next = e.target.value
              setBizTypeSelect(next)
              if (next === '') {
                setBizType('')
              } else if (next === 'other') {
                // If we already had a non-listed custom phrase, keep it.
                // Otherwise clear so the text input renders empty.
                if (BUSINESS_TYPE_PHRASES.has(bizType as typeof BUSINESS_TYPES[number]['phrase'])) {
                  setBizType('')
                }
              } else {
                setBizType(next)
              }
            }}
            className={inputClass}>
            <option value="">—</option>
            {BUSINESS_TYPES.map(bt => (
              <option key={bt.key} value={bt.phrase}>{tTypes(`types.${bt.key}`)}</option>
            ))}
          </select>
          {bizTypeSelect === 'other' && (
            <input
              type="text"
              value={bizType}
              onChange={e => setBizType(e.target.value)}
              placeholder="e.g. physiotherapy clinic, italian restaurant"
              className={`${inputClass} mt-2`} />
          )}
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

        {/* ── Schema generator fields ──────────────────────────────────── */}
        <div className="mt-6 pt-5 border-t border-slate-100">
          <h3 className="text-xs font-extrabold text-[#1e293b] mb-1">{t('businessProfile.schemaSectionTitle')}</h3>
          <p className="text-[11px] text-slate-500 mb-4">{t('businessProfile.schemaSectionSubtitle')}</p>

          <div className="mb-4">
            <label className={labelClass}>{t('businessProfile.streetAddressLabel')}</label>
            <input type="text" value={bizStreet} onChange={e => setBizStreet(e.target.value)} className={inputClass}
              placeholder={t('businessProfile.streetAddressPlaceholder')} />
          </div>

          <div className="grid grid-cols-2 gap-3 mb-4">
            <div>
              <label className={labelClass}>{t('businessProfile.postalCodeLabel')}</label>
              <input type="text" value={bizPostal} onChange={e => setBizPostal(e.target.value)} className={inputClass}
                placeholder={t('businessProfile.postalCodePlaceholder')} />
            </div>
            <div>
              <label className={labelClass}>{t('businessProfile.phoneLabel')}</label>
              <input type="tel" value={bizPhone} onChange={e => setBizPhone(e.target.value)} className={inputClass}
                placeholder={t('businessProfile.phonePlaceholder')} />
            </div>
          </div>

          <div className="mb-4">
            <label className={labelClass}>{t('businessProfile.imageUrlLabel')}</label>
            <input type="url" value={bizImage} onChange={e => setBizImage(e.target.value)} className={inputClass}
              placeholder={t('businessProfile.imageUrlPlaceholder')} />
            <p className="text-[10px] text-slate-400 mt-1">{t('businessProfile.imageUrlHint')}</p>
          </div>

          <div className="mb-4">
            <label className={labelClass}>{t('businessProfile.priceRangeLabel')}</label>
            <select value={bizPriceRange} onChange={e => setBizPriceRange(e.target.value)} className={inputClass}>
              <option value="">—</option>
              <option value="$">$</option>
              <option value="$$">$$</option>
              <option value="$$$">$$$</option>
              <option value="$$$$">$$$$</option>
            </select>
            <p className="text-[10px] text-slate-400 mt-1">{t('businessProfile.priceRangeHint')}</p>
          </div>

          <div className="mb-4">
            <label className={labelClass}>{t('businessProfile.hoursLabel')}</label>
            <p className="text-[10px] text-slate-400 mb-2">{t('businessProfile.hoursHint')}</p>
            <HoursEditor value={bizHours} onChange={setBizHours} />
          </div>

          {/* ROI inputs (migration 022). Drives dashboard revenue-exposure
              hero and per-recommendation $ tags. Both optional — vertical
              defaults fill in any missing value. */}
          <div className="mb-4 border-t border-slate-100 pt-4">
            <p className="text-xs font-bold text-[#1e293b] mb-1">{t('businessProfile.roiHeading')}</p>
            <p className="text-[10px] text-slate-500 mb-3">{t('businessProfile.roiSubtitle')}</p>

            <div className="mb-3">
              <label className={labelClass}>{t('businessProfile.avgCustomerValueLabel')}</label>
              <div className="relative">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-xs text-slate-400 pointer-events-none">$</span>
                <input
                  type="number"
                  inputMode="decimal"
                  min="0"
                  step="any"
                  value={bizAvgCustomerValue}
                  onChange={e => setBizAvgCustomerValue(e.target.value)}
                  placeholder={t('businessProfile.avgCustomerValuePlaceholder')}
                  className={`${inputClass} pl-7`} />
              </div>
              <p className="text-[10px] text-slate-400 mt-1">{t('businessProfile.avgCustomerValueHint')}</p>
            </div>

            <div>
              <label className={labelClass}>{t('businessProfile.monthlyOnlineLabel')}</label>
              <input
                type="number"
                inputMode="numeric"
                min="0"
                step="1"
                value={bizMonthlyOnline}
                onChange={e => setBizMonthlyOnline(e.target.value)}
                placeholder={t('businessProfile.monthlyOnlinePlaceholder')}
                className={inputClass} />
              <p className="text-[10px] text-slate-400 mt-1">{t('businessProfile.monthlyOnlineHint')}</p>
            </div>
          </div>

          {/* Competitor scope -- who should the audit compare you to? */}
          <div className="mb-4">
            <label className={labelClass}>{t('businessProfile.competitorScopeLabel')}</label>
            <div className="flex flex-col gap-2 mt-1">
              {(['local', 'country', 'global'] as const).map(scope => {
                const active = bizCompetitorScope === scope
                return (
                  <button
                    key={scope}
                    type="button"
                    onClick={() => setBizCompetitorScope(scope)}
                    className={`flex items-start gap-3 text-left px-3 py-2.5 rounded-xl border transition-colors
                      ${active
                        ? 'border-[#4f46e5] bg-indigo-50/50'
                        : 'border-slate-200 bg-white hover:border-[#4f46e5]/60'}`}>
                    <span className={`mt-0.5 w-3.5 h-3.5 rounded-full border-2 flex-shrink-0 flex items-center justify-center
                      ${active ? 'border-[#4f46e5]' : 'border-slate-300'}`}>
                      {active && <span className="w-1.5 h-1.5 rounded-full bg-[#4f46e5]" />}
                    </span>
                    <div className="flex-1 min-w-0">
                      <p className={`text-xs font-semibold ${active ? 'text-[#4f46e5]' : 'text-[#1e293b]'}`}>
                        {t(`businessProfile.competitorScopes.${scope}.title`)}
                      </p>
                      <p className="text-[10px] text-slate-500 mt-0.5">
                        {t(`businessProfile.competitorScopes.${scope}.subtitle`)}
                      </p>
                    </div>
                  </button>
                )
              })}
            </div>
            <p className="text-[10px] text-slate-400 mt-1">{t('businessProfile.competitorScopeHint')}</p>
          </div>
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

      {/* ── Subscription ─────────────────────────────────────────────────── */}
      <div className="bg-white rounded-2xl border border-slate-100 shadow-sm p-5 mb-5
                      flex items-center justify-between">
        <div>
          <h2 className="text-sm font-extrabold text-[#1e293b]">{tPlan('title')}</h2>
          <p className="text-[11px] text-slate-500 mt-0.5">{tPlan('subtitle')}</p>
        </div>
        <div className="flex flex-col items-end gap-1">
          <button
            type="button"
            onClick={handleManageSubscription}
            disabled={portalLoading}
            className="text-xs font-semibold text-[#4f46e5] hover:underline disabled:opacity-50 whitespace-nowrap">
            {portalLoading ? '…' : tPlan('manageBtn')} →
          </button>
          {portalError && <p className="text-[10px] text-red-500">{portalError}</p>}
        </div>
      </div>

      {/* ── Review response settings ─────────────────────────────────────── */}
      <form onSubmit={handleRevSave} className="hidden bg-white rounded-2xl border border-slate-100 shadow-sm p-5 mb-6">
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
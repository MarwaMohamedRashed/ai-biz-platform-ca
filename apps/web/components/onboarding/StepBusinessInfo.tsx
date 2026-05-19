'use client'

import { useState } from 'react'
import { useTranslations } from 'next-intl'

// LeapOne is Canada-only at launch. We hardcode 'Canada' on submit so we
// can keep tax/billing aligned with Stripe Tax (HST/GST/PST) and so the
// Canadian-specific recommendations (HomeStars, RateMDs, Realtor.ca, etc.)
// always apply. Non-Canadian visitors get a waitlist link.
const CA_PROVINCES = [
  'AB', 'BC', 'MB', 'NB', 'NL', 'NS', 'NT', 'NU', 'ON', 'PE', 'QC', 'SK', 'YT',
] as const

// `key` is the stable identifier (used in i18n bundles and the FastAPI
// vertical detectors). `phrase` is what we actually store in
// businesses.type — it doubles as the search phrase the audit feeds
// into Google ("best family doctor Burlington"), so it should read like
// a natural noun phrase, not snake_case.
//
// Order matters here — the chips appear in this order on the screen.
// Most-common consumer services first, then healthcare, then
// professional, then trades, then the generic 'other' fallback.
const TYPES = [
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

const COMPETITOR_SCOPES = ['local', 'country', 'global'] as const
type CompetitorScope = typeof COMPETITOR_SCOPES[number]

// Step 1 is rendered as the 'required' mode: identity + full address. Step 2
// is the same component in 'extras' mode: service description, logo, price,
// competitor scope. Splitting via a `mode` prop (instead of internal
// sub-state) lets OnboardingFlow own the stepper position, so the user sees
// a real "Step 2" in the left rail when they advance.
//
// Both mutations go through server routes (/api/onboarding/business and
// /api/onboarding/business/extras). The browser supabase-js client has a
// known quirk on second-login where the cookie holds a valid refresh token
// but the access_token isn't always attached to mutation requests, causing
// RLS 403s even when the session looks healthy. Server routes use
// createServerClient with the request cookie, which is deterministic.

interface RequiredProps {
  mode: 'required'
  userId: string
  onComplete: (businessName: string, businessId: string) => void
}

interface ExtrasProps {
  mode: 'extras'
  businessId: string
  businessName: string
  onComplete: () => void
}

type Props = RequiredProps | ExtrasProps

export default function StepBusinessInfo(props: Props) {
  if (props.mode === 'required') return <RequiredStep {...props} />
  return <ExtrasStep {...props} />
}

// ── Step 1: identity + full address ────────────────────────────────────────
function RequiredStep({ onComplete }: RequiredProps) {
  const t = useTranslations('onboarding.step1')

  const [name, setName] = useState('')
  const [type, setType] = useState('')
  const [customType, setCustomType] = useState('')
  const [website, setWebsite] = useState('')
  const [streetAddress, setStreetAddress] = useState('')
  const [city, setCity] = useState('')
  const [province, setProvince] = useState('')
  const [postalCode, setPostalCode] = useState('')
  const [phone, setPhone] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!name || !type || !city || !province) return
    if (type === 'other' && !customType) return
    setError('')
    setLoading(true)

    let res: Response
    try {
      res = await fetch('/api/onboarding/business', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name,
          type:           type === 'other' ? customType : type,
          country:        'Canada',
          city,
          province,
          website:        website || null,
          street_address: streetAddress || null,
          postal_code:    postalCode || null,
          phone:          phone || null,
        }),
      })
    } catch {
      setLoading(false)
      setError('Network error — please try again.')
      return
    }

    setLoading(false)
    if (!res.ok) {
      let msg = `Save failed (${res.status})`
      try {
        const body = await res.json()
        if (body?.error) msg = body.error
      } catch {}
      setError(msg)
      return
    }

    const { id } = await res.json()
    if (!id) {
      setError('Server did not return a business id.')
      return
    }
    onComplete(name, id)
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

      {/* Website */}
      <div className="flex flex-col gap-1.5">
        <label className="text-sm font-medium text-[#1e293b]">{t('websiteLabel')}</label>
        <input
          type="url"
          value={website}
          onChange={e => setWebsite(e.target.value)}
          placeholder="https://yourbusiness.com"
          className="border border-slate-200 rounded-xl px-4 py-3 text-sm text-[#1e293b]
                    outline-none focus:border-[#4f46e5] transition-colors" />
        <p className="text-xs text-slate-400">{t('websiteHint')}</p>
      </div>

      {/* Business type chips */}
      <div className="flex flex-col gap-2">
        <label className="text-sm font-medium text-[#1e293b]">{t('businessType')}</label>
        <div className="flex flex-wrap gap-2">
          {TYPES.map(bt => (
            <button
              key={bt.key}
              type="button"
              onClick={() => setType(bt.phrase)}
              className={`px-4 py-2 rounded-full text-sm font-medium border transition-colors
                ${type === bt.phrase
                  ? 'bg-[#4f46e5] text-white border-[#4f46e5]'
                  : 'bg-white text-slate-600 border-slate-200 hover:border-[#4f46e5]'
                }`}>
              {t(`types.${bt.key}`)}
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

      {/* Canada-only badge + waitlist escape for non-Canadian visitors */}
      <div className="bg-slate-50 border border-slate-200 rounded-xl px-4 py-2.5 flex items-center justify-between gap-3 flex-wrap">
        <span className="text-xs font-semibold text-[#1e293b]">{t('canadaOnlyBadge')}</span>
        <span className="text-xs text-slate-500">
          {t('waitlistPrompt')}{' '}
          <a
            href="mailto:support@leapone.ca?subject=Waitlist%20for%20LeapOne&body=Hi%20LeapOne%20team%2C%0A%0AI%27d%20like%20to%20join%20the%20waitlist%20for%20when%20you%20expand%20outside%20Canada.%0A%0ACountry%3A%20%0ABusiness%20name%3A%20%0A%0AThanks%21"
            className="text-[#4f46e5] font-semibold hover:underline">
            {t('waitlistCta')}
          </a>
        </span>
      </div>

      {/* ── Full address block (street → city/province → postal + phone) ── */}
      <div className="flex flex-col gap-1.5">
        <label className="text-sm font-medium text-[#1e293b]">{t('streetAddressLabel')}</label>
        <input
          type="text"
          value={streetAddress}
          onChange={e => setStreetAddress(e.target.value)}
          placeholder={t('streetAddressPlaceholder')}
          className="border border-slate-200 rounded-xl px-4 py-3 text-sm text-[#1e293b]
                    outline-none focus:border-[#4f46e5] transition-colors" />
        <p className="text-xs text-slate-400">{t('streetAddressHint')}</p>
      </div>

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
        <div className="flex flex-col gap-1.5 w-48">
          <label className="text-sm font-medium text-[#1e293b]">{t('provinceState')}</label>
          <select
            required
            value={province}
            onChange={e => setProvince(e.target.value)}
            className="border border-slate-200 rounded-xl px-4 py-3 text-sm text-[#1e293b]
                       outline-none focus:border-[#4f46e5] transition-colors bg-white">
            <option value="">{t('provincePlaceholder')}</option>
            {CA_PROVINCES.map(code => (
              <option key={code} value={code}>{t(`provinces.${code}`)} ({code})</option>
            ))}
          </select>
        </div>
      </div>

      <div className="flex gap-3">
        <div className="flex flex-col gap-1.5 flex-1">
          <label className="text-sm font-medium text-[#1e293b]">{t('postalCodeLabel')}</label>
          <input
            type="text"
            value={postalCode}
            onChange={e => setPostalCode(e.target.value)}
            placeholder={t('postalCodePlaceholder')}
            className="border border-slate-200 rounded-xl px-4 py-3 text-sm text-[#1e293b]
                      outline-none focus:border-[#4f46e5] transition-colors" />
        </div>
        <div className="flex flex-col gap-1.5 flex-1">
          <label className="text-sm font-medium text-[#1e293b]">{t('phoneLabel')}</label>
          <input
            type="tel"
            value={phone}
            onChange={e => setPhone(e.target.value)}
            placeholder={t('phonePlaceholder')}
            className="border border-slate-200 rounded-xl px-4 py-3 text-sm text-[#1e293b]
                      outline-none focus:border-[#4f46e5] transition-colors" />
        </div>
      </div>

      <button
        type="submit"
        disabled={loading || !name || !type || !city || !province || (type === 'other' && !customType)}
        className="w-full py-3 rounded-xl bg-[#4f46e5] text-white text-sm font-semibold
                   hover:bg-indigo-700 transition-colors disabled:opacity-50">
        {loading ? t('saving') : t('next')}
      </button>
    </form>
  )
}

// ── Step 2: service description + extras ───────────────────────────────────
function ExtrasStep({ businessId, businessName, onComplete }: ExtrasProps) {
  const t = useTranslations('onboarding.step1')

  const [services, setServices] = useState('')
  const [imageUrl, setImageUrl] = useState('')
  const [priceRange, setPriceRange] = useState('')
  const [competitorScope, setCompetitorScope] = useState<CompetitorScope>('local')
  // ROI inputs — drive the dashboard's revenue-exposure hero card. Both
  // optional: when empty we fall back to industry defaults at compute time
  // (see apps/web/lib/roi.ts).
  const [avgCustomerValue, setAvgCustomerValue] = useState('')
  const [monthlyOnlineCustomers, setMonthlyOnlineCustomers] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)

    // Parse the optional numeric fields. Empty string → null; non-numeric
    // input gets silently dropped (the input is type=number so the browser
    // already validates, but parseFloat hardens us against pasted junk).
    const avgCustomerValueNum = avgCustomerValue.trim()
      ? Number(avgCustomerValue) : null
    const monthlyOnlineNum = monthlyOnlineCustomers.trim()
      ? Math.round(Number(monthlyOnlineCustomers)) : null

    let res: Response
    try {
      res = await fetch('/api/onboarding/business/extras', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          business_id:                  businessId,
          services:                     services || null,
          image_url:                    imageUrl || null,
          price_range:                  priceRange || null,
          competitor_scope:             competitorScope,
          avg_customer_value_cad:       Number.isFinite(avgCustomerValueNum as number) ? avgCustomerValueNum : null,
          monthly_new_online_customers: Number.isFinite(monthlyOnlineNum as number) ? monthlyOnlineNum : null,
        }),
      })
    } catch {
      setLoading(false)
      setError('Network error — please try again.')
      return
    }

    setLoading(false)
    if (!res.ok) {
      let msg = `Save failed (${res.status})`
      try {
        const body = await res.json()
        if (body?.error) msg = body.error
      } catch {}
      setError(msg)
      return
    }
    onComplete()
  }

  // Skip just advances without an UPDATE — defaults from the row insert (and
  // the competitor_scope CHECK default of 'local') remain in place.
  function handleSkip() {
    onComplete()
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold text-[#1e293b]">{t('extrasHeading')}</h1>
        <p className="text-sm text-slate-500 mt-1">
          {t('extrasSubtitleNamed', { name: businessName })}
        </p>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-xl px-4 py-3">
          {error}
        </div>
      )}

      {/* Services / description */}
      <div className="flex flex-col gap-1.5">
        <label className="text-sm font-medium text-[#1e293b]">{t('servicesLabel')}</label>
        <textarea
          value={services}
          onChange={e => setServices(e.target.value)}
          rows={3}
          placeholder={t('servicesPlaceholder')}
          className="border border-slate-200 rounded-xl px-4 py-3 text-sm text-[#1e293b]
                    outline-none focus:border-[#4f46e5] transition-colors resize-none" />
        <p className="text-xs text-slate-400">{t('servicesHint')}</p>
      </div>

      {/* Logo / photo */}
      <div className="flex flex-col gap-1.5">
        <label className="text-sm font-medium text-[#1e293b]">{t('imageUrlLabel')}</label>
        <input
          type="url"
          value={imageUrl}
          onChange={e => setImageUrl(e.target.value)}
          placeholder={t('imageUrlPlaceholder')}
          className="border border-slate-200 rounded-xl px-4 py-3 text-sm text-[#1e293b]
                    outline-none focus:border-[#4f46e5] transition-colors" />
      </div>

      {/* Price range — plain-language labels, $-string values for schema */}
      <div className="flex flex-col gap-1.5">
        <label className="text-sm font-medium text-[#1e293b]">{t('priceRangeLabel')}</label>
        <select
          value={priceRange}
          onChange={e => setPriceRange(e.target.value)}
          className="border border-slate-200 rounded-xl px-4 py-3 text-sm text-[#1e293b]
                    outline-none focus:border-[#4f46e5] transition-colors bg-white">
          <option value="">—</option>
          <option value="$">{t('priceRange.budget')}</option>
          <option value="$$">{t('priceRange.moderate')}</option>
          <option value="$$$">{t('priceRange.upscale')}</option>
          <option value="$$$$">{t('priceRange.premium')}</option>
        </select>
        <p className="text-xs text-slate-400">{t('priceRangeHint')}</p>
      </div>

      <p className="text-xs text-slate-400 -mt-2">{t('schemaTip')}</p>

      {/* ── Revenue inputs (ROI MVP) ───────────────────────────────────────
          Both optional. When filled, the dashboard's revenue-exposure hero
          card uses these instead of vertical-default proxies. The dentist-
          owner feedback was clear: owners care about $$$, not visibility
          scores. These two questions are the cheapest way to make the
          rest of the dashboard speak in dollars. */}
      <div className="border-t border-slate-100 pt-6 flex flex-col gap-4">
        <div>
          <h3 className="text-sm font-semibold text-[#1e293b]">{t('roi.heading')}</h3>
          <p className="text-xs text-slate-500 mt-0.5">{t('roi.subtitle')}</p>
        </div>

        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-medium text-[#1e293b]">{t('roi.avgCustomerValueLabel')}</label>
          <div className="relative">
            <span className="absolute left-4 top-1/2 -translate-y-1/2 text-sm text-slate-400 pointer-events-none">$</span>
            <input
              type="number"
              inputMode="decimal"
              min="0"
              step="any"
              value={avgCustomerValue}
              onChange={e => setAvgCustomerValue(e.target.value)}
              placeholder={t('roi.avgCustomerValuePlaceholder')}
              className="w-full border border-slate-200 rounded-xl pl-8 pr-4 py-3 text-sm text-[#1e293b]
                        outline-none focus:border-[#4f46e5] transition-colors" />
          </div>
          <p className="text-xs text-slate-400">{t('roi.avgCustomerValueHint')}</p>
        </div>

        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-medium text-[#1e293b]">{t('roi.monthlyOnlineLabel')}</label>
          <input
            type="number"
            inputMode="numeric"
            min="0"
            step="1"
            value={monthlyOnlineCustomers}
            onChange={e => setMonthlyOnlineCustomers(e.target.value)}
            placeholder={t('roi.monthlyOnlinePlaceholder')}
            className="border border-slate-200 rounded-xl px-4 py-3 text-sm text-[#1e293b]
                      outline-none focus:border-[#4f46e5] transition-colors" />
          <p className="text-xs text-slate-400">{t('roi.monthlyOnlineHint')}</p>
        </div>
      </div>

      {/* Competitor scope */}
      <div className="flex flex-col gap-2">
        <label className="text-sm font-medium text-[#1e293b]">{t('competitorScopeLabel')}</label>
        <div className="flex flex-col gap-2">
          {COMPETITOR_SCOPES.map(scope => {
            const active = competitorScope === scope
            return (
              <button
                key={scope}
                type="button"
                onClick={() => setCompetitorScope(scope)}
                className={`flex items-start gap-3 text-left px-4 py-3 rounded-xl border transition-colors
                  ${active
                    ? 'border-[#4f46e5] bg-indigo-50/50'
                    : 'border-slate-200 bg-white hover:border-[#4f46e5]/60'}`}>
                <span className={`mt-0.5 w-4 h-4 rounded-full border-2 flex-shrink-0 flex items-center justify-center
                  ${active ? 'border-[#4f46e5]' : 'border-slate-300'}`}>
                  {active && <span className="w-2 h-2 rounded-full bg-[#4f46e5]" />}
                </span>
                <div className="flex-1 min-w-0">
                  <p className={`text-sm font-semibold ${active ? 'text-[#4f46e5]' : 'text-[#1e293b]'}`}>
                    {t(`competitorScopes.${scope}.title`)}
                  </p>
                  <p className="text-xs text-slate-500 mt-0.5">
                    {t(`competitorScopes.${scope}.subtitle`)}
                  </p>
                </div>
              </button>
            )
          })}
        </div>
        <p className="text-xs text-slate-400">{t('competitorScopeHint')}</p>
      </div>

      <div className="flex flex-col gap-3">
        <button
          type="submit"
          disabled={loading}
          className="w-full py-3 rounded-xl bg-[#4f46e5] text-white text-sm font-semibold
                     hover:bg-indigo-700 transition-colors disabled:opacity-50">
          {loading ? t('saving') : t('extrasContinue')}
        </button>
        <button
          type="button"
          onClick={handleSkip}
          disabled={loading}
          className="text-xs font-semibold text-slate-500 hover:text-[#4f46e5] hover:underline">
          {t('extrasSkip')}
        </button>
      </div>
    </form>
  )
}

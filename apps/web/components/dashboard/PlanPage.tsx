'use client'
import { useState } from 'react'
import { useTranslations } from 'next-intl'
import { createClient } from '@/lib/supabase'

type Tier = 'starter' | 'pro' | 'business'

interface Props {
  currentTier: Tier
  planStatus: string
  hasSubscription: boolean
  locale: string
}

const TIERS: Tier[] = ['starter', 'pro', 'business']

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

export default function PlanPage({ currentTier, planStatus, hasSubscription, locale }: Props) {
  const t = useTranslations('dashboard.plan')
  const [loadingTier, setLoadingTier] = useState<Tier | null>(null)
  const [loadingPortal, setLoadingPortal] = useState(false)
  const [checkoutError, setCheckoutError] = useState('')
  const [portalError, setPortalError] = useState('')

  const isTrial = planStatus === 'trialing'

  async function handleUpgrade(tier: Tier) {
    setLoadingTier(tier)
    setCheckoutError('')
    try {
      const data = await apiAuth('/api/v1/billing/checkout-session', {
        method: 'POST',
        body: JSON.stringify({ plan: tier, locale }),
      })
      window.location.href = data.url
    } catch {
      setCheckoutError(t('upgradeError'))
      setLoadingTier(null)
    }
  }

  async function handleManage() {
    setLoadingPortal(true)
    setPortalError('')
    try {
      const data = await apiAuth('/api/v1/billing/portal-session', {
        method: 'POST',
        body: JSON.stringify({ locale }),
      })
      window.location.href = data.url
    } catch {
      setPortalError(t('portalError'))
      setLoadingPortal(false)
    }
  }

  return (
    <div className="flex-1 overflow-y-auto px-4 md:px-6 py-4">
      <p className="text-xs text-slate-500 mb-5">{t('subtitle')}</p>

      {isTrial && (
        <div className="mb-4 inline-flex items-center gap-1.5 bg-amber-50 border border-amber-200
                        text-amber-700 text-xs font-semibold px-3 py-1.5 rounded-full">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2"/>
            <path d="M12 8v4M12 16h.01" stroke="currentColor" strokeWidth="2"
              strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          {t('trialBadge')}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        {TIERS.map(tier => {
          const isCurrent = tier === currentTier
          const isAgency = tier === 'business'
          const isUpgrade = !isCurrent && !isAgency
          const isLoading = loadingTier === tier

          return (
            <div
              key={tier}
              className={`relative rounded-2xl border p-5 flex flex-col transition-shadow
                ${isCurrent
                  ? 'border-[#4f46e5] shadow-md shadow-indigo-100 bg-white'
                  : 'border-slate-200 bg-white hover:shadow-sm'
                }`}
            >
              {isCurrent && (
                <span className="absolute -top-2.5 left-5 bg-[#4f46e5] text-white text-[10px]
                                 font-bold px-2.5 py-0.5 rounded-full">
                  {t('currentBadge')}
                </span>
              )}

              <div className="mb-3">
                <h3 className="text-sm font-extrabold text-[#1e293b]">{t(`${tier}.name`)}</h3>
                <div className="flex items-baseline gap-0.5 mt-0.5">
                  <span className="text-2xl font-extrabold text-[#1e293b]">{t(`${tier}.price`)}</span>
                  <span className="text-xs text-slate-500">{t(`${tier}.period`)}</span>
                </div>
                <p className="text-[11px] text-slate-500 mt-1">{t(`${tier}.tagline`)}</p>
              </div>

              <ul className="flex-1 space-y-1.5 mb-4">
                {(t.raw(`${tier}.features`) as string[]).map((feature, i) => (
                  <li key={i} className="flex items-start gap-2 text-xs text-slate-700">
                    <svg className="flex-shrink-0 mt-0.5 text-[#4f46e5]"
                         width="13" height="13" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                      <polyline points="20 6 9 17 4 12"
                        stroke="currentColor" strokeWidth="2.5"
                        strokeLinecap="round" strokeLinejoin="round"/>
                    </svg>
                    {feature}
                  </li>
                ))}
              </ul>

              {isCurrent ? (
                <button disabled
                  className="w-full py-2 rounded-xl bg-slate-100 text-slate-400 text-xs font-semibold cursor-default">
                  {t('currentBadge')}
                </button>
              ) : isAgency ? (
                <span className="text-center text-[10px] text-slate-400">{t('contactBtn')}</span>
              ) : (
                <button
                  onClick={() => handleUpgrade(tier)}
                  disabled={isLoading}
                  className="w-full py-2 rounded-xl bg-[#4f46e5] text-white text-xs font-semibold
                             hover:bg-indigo-700 transition-colors disabled:opacity-60
                             flex items-center justify-center gap-1.5">
                  {isLoading ? '…' : t('upgradeBtn')}
                </button>
              )}
            </div>
          )
        })}
      </div>

      {checkoutError && (
        <p className="text-xs text-red-500 mb-4 text-center">{checkoutError}</p>
      )}

      {hasSubscription && (
        <div className="flex flex-col items-center gap-2 mb-4">
          <button
            onClick={handleManage}
            disabled={loadingPortal}
            className="text-xs font-semibold text-[#4f46e5] hover:underline disabled:opacity-50">
            {loadingPortal ? '…' : t('manageBtn')} →
          </button>
          {portalError && <p className="text-xs text-red-500">{portalError}</p>}
        </div>
      )}

      <p className="text-[10px] text-slate-400 text-center">{t('billingNote')}</p>
    </div>
  )
}

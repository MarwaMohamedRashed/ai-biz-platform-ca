'use client'
import { useTranslations } from 'next-intl'

type Tier = 'starter' | 'pro' | 'business'

interface Props {
  currentTier: Tier
  planStatus: string
}

const TIERS: Tier[] = ['starter', 'pro', 'business']

export default function PlanPage({ currentTier, planStatus }: Props) {
  const t = useTranslations('dashboard.plan')

  const isTrial = planStatus === 'trialing'

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
          const isFirst = tier === 'starter'

          return (
            <div
              key={tier}
              className={`relative rounded-2xl border p-5 flex flex-col transition-shadow
                ${isCurrent
                  ? 'border-[#4f46e5] shadow-md shadow-indigo-100 bg-white'
                  : 'border-slate-200 bg-white hover:shadow-sm'
                }`}
            >
              {/* Current plan badge */}
              {isCurrent && (
                <span className="absolute -top-2.5 left-5 bg-[#4f46e5] text-white text-[10px]
                                 font-bold px-2.5 py-0.5 rounded-full">
                  {t('currentBadge')}
                </span>
              )}

              {/* Tier header */}
              <div className="mb-3">
                <h3 className="text-sm font-extrabold text-[#1e293b]">{t(`${tier}.name`)}</h3>
                <div className="flex items-baseline gap-0.5 mt-0.5">
                  <span className="text-2xl font-extrabold text-[#1e293b]">{t(`${tier}.price`)}</span>
                  <span className="text-xs text-slate-500">{t(`${tier}.period`)}</span>
                </div>
                <p className="text-[11px] text-slate-500 mt-1">{t(`${tier}.tagline`)}</p>
              </div>

              {/* Feature list */}
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

              {/* CTA */}
              {isCurrent ? (
                <button disabled
                  className="w-full py-2 rounded-xl bg-slate-100 text-slate-400 text-xs font-semibold cursor-default">
                  {t('currentBadge')}
                </button>
              ) : isFirst ? (
                /* Downgrade — not common, show nothing actionable */
                <span className="text-center text-[10px] text-slate-400">{t('contactBtn')}</span>
              ) : (
                <button disabled
                  className="w-full py-2 rounded-xl bg-[#4f46e5]/10 text-[#4f46e5] text-xs font-semibold
                             cursor-default flex items-center justify-center gap-1.5">
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                    <path d="M12 2L2 7l10 5 10-5-10-5z" stroke="currentColor" strokeWidth="2"
                      strokeLinecap="round" strokeLinejoin="round"/>
                    <path d="M2 17l10 5 10-5M2 12l10 5 10-5" stroke="currentColor" strokeWidth="2"
                      strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                  {t('comingSoon')}
                </button>
              )}
            </div>
          )
        })}
      </div>

      <p className="text-[10px] text-slate-400 text-center">{t('billingNote')}</p>
    </div>
  )
}

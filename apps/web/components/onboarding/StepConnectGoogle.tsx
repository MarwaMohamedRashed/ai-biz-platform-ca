'use client'

import { useTranslations } from 'next-intl'

interface Props {
  onSkip: () => void
}

export default function StepConnectGoogle({ onSkip }: Props) {
  const t = useTranslations('onboarding.step2')

  const permissions = [t('permission1'), t('permission2'), t('permission3')]

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold text-[#1e293b]">{t('heading')}</h1>
        <p className="text-sm text-slate-500 mt-1">{t('subtitle')}</p>
      </div>

      <div className="bg-slate-50 rounded-xl p-4 flex flex-col gap-3">
        {permissions.map((p, i) => (
          <div key={i} className="flex items-center gap-3">
            <div className="w-5 h-5 rounded-full bg-indigo-100 flex items-center justify-center flex-shrink-0">
              <svg width="10" height="10" viewBox="0 0 24 24" fill="none">
                <polyline points="20 6 9 17 4 12" stroke="#4f46e5" strokeWidth="3"
                  strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </div>
            <span className="text-sm text-slate-700">{p}</span>
          </div>
        ))}
      </div>

      <button
        disabled
        className="w-full py-3 rounded-xl bg-slate-100 text-slate-400 text-sm font-semibold cursor-not-allowed">
        {t('comingSoon')}
      </button>

      <button
        onClick={onSkip}
        className="text-sm text-slate-500 hover:text-[#4f46e5] transition-colors text-center">
        {t('skip')}
      </button>
    </div>
  )
}
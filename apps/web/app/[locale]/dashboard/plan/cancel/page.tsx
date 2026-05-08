import Link from 'next/link'
import { getLocale, getTranslations } from 'next-intl/server'

export default async function PlanCancelPage() {
  const locale = await getLocale()
  const t = await getTranslations('dashboard.plan')

  return (
    <div className="flex flex-col items-center justify-center h-full px-4 text-center">
      <div className="bg-white rounded-2xl border border-slate-100 shadow-sm p-8 max-w-md w-full">
        <div className="w-12 h-12 bg-slate-100 rounded-full flex items-center justify-center mx-auto mb-4">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <line x1="18" y1="6" x2="6" y2="18"
              stroke="#64748b" strokeWidth="2.5" strokeLinecap="round"/>
            <line x1="6" y1="6" x2="18" y2="18"
              stroke="#64748b" strokeWidth="2.5" strokeLinecap="round"/>
          </svg>
        </div>
        <h1 className="text-lg font-extrabold text-[#1e293b] mb-2">{t('cancel.title')}</h1>
        <p className="text-sm text-slate-500 mb-6">{t('cancel.body')}</p>
        <Link
          href={`/${locale}/dashboard/plan`}
          className="inline-block px-5 py-2.5 bg-[#4f46e5] text-white text-xs font-semibold
                     rounded-xl hover:bg-indigo-700 transition-colors">
          {t('cancel.cta')}
        </Link>
      </div>
    </div>
  )
}

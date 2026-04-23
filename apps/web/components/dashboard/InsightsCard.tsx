'use client'

import { useState } from 'react'
import { useTranslations, useLocale } from 'next-intl'
import Link from 'next/link'

type Period = '30d' | '90d' | '6m' | 'all'

export default function InsightsCard() {
  const t = useTranslations('dashboard.insights')
  const locale = useLocale()
  const [period, setPeriod] = useState<Period>('30d')

  const periods: Period[] = ['30d', '90d', '6m', 'all']

  return (
    <div className="bg-white rounded-2xl border-l-[3px] border-l-green-500
                    shadow-sm border border-slate-100 p-4">

      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <span className="text-[10px] font-bold text-green-600 uppercase tracking-wider">
          {t('label')}
        </span>
      </div>

      {/* Period selector */}
      <div className="flex gap-1 mb-4 flex-wrap">
        {periods.map(p => (
          <button key={p} onClick={() => setPeriod(p)}
            className={`px-2.5 py-1 rounded-full text-[10px] font-semibold transition-colors
              ${period === p
                ? 'bg-[#4f46e5] text-white'
                : 'bg-slate-100 text-slate-500 hover:bg-slate-200'
              }`}>
            {t(`periods.${p}`)}
          </button>
        ))}
      </div>

      {/* Metric row */}
      <div className="flex gap-3 mb-4">
        <div className="flex-1 bg-slate-50 rounded-xl px-3 py-2 text-center">
          <p className="text-[10px] text-slate-400 mb-0.5">{t('avgRating')}</p>
          <p className="text-lg font-bold text-[#f97316]">—</p>
        </div>
        <div className="flex-1 bg-slate-50 rounded-xl px-3 py-2 text-center">
          <p className="text-[10px] text-slate-400 mb-0.5">{t('reviewCount')}</p>
          <p className="text-lg font-bold text-[#1e293b]">—</p>
        </div>
      </div>

      {/* Strengths & Weaknesses */}
      <div className="flex gap-3 mb-4">
        <div className="flex-1">
          <p className="text-[10px] font-bold text-green-600 mb-1.5">✓ {t('strengths')}</p>
          <p className="text-[10px] text-slate-400 italic">{t('emptyStrengths')}</p>
        </div>
        <div className="flex-1">
          <p className="text-[10px] font-bold text-rose-500 mb-1.5">✗ {t('weaknesses')}</p>
          <p className="text-[10px] text-slate-400 italic">{t('emptyWeaknesses')}</p>
        </div>
      </div>

      {/* Link to full page */}
      <Link href={`/${locale}/dashboard/insights`}
        className="text-xs font-semibold text-[#4f46e5] hover:underline">
        {t('viewFull')}
      </Link>

    </div>
  )
}
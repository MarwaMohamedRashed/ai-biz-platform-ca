'use client'

import { useState } from 'react'
import { useTranslations } from 'next-intl'

type Period = '30d' | '90d' | '6m' | 'all'

export default function InsightsPage() {
  const t = useTranslations('dashboard.insights')
  const [period, setPeriod] = useState<Period>('30d')

  const periods: Period[] = ['30d', '90d', '6m', 'all']

  return (
    <div className="flex-1 overflow-y-auto px-4 md:px-6 py-4">

      {/* Period selector */}
      <div className="flex gap-2 mb-6 flex-wrap">
        {periods.map(p => (
          <button key={p} onClick={() => setPeriod(p)}
            className={`px-3 py-1.5 rounded-full text-xs font-semibold transition-colors
              ${period === p
                ? 'bg-[#4f46e5] text-white'
                : 'bg-slate-100 text-slate-500 hover:bg-slate-200'
              }`}>
            {t(`periods.${p}`)}
          </button>
        ))}
      </div>

      {/* Metric row */}
      <div className="grid grid-cols-2 gap-3 mb-6">
        <div className="bg-white rounded-2xl border border-slate-100 shadow-sm px-4 py-3 text-center">
          <p className="text-xs text-slate-400 mb-1">{t('avgRating')}</p>
          <p className="text-2xl font-bold text-[#f97316]">—</p>
        </div>
        <div className="bg-white rounded-2xl border border-slate-100 shadow-sm px-4 py-3 text-center">
          <p className="text-xs text-slate-400 mb-1">{t('reviewCount')}</p>
          <p className="text-2xl font-bold text-[#1e293b]">—</p>
        </div>
      </div>

      {/* Strengths & Weaknesses */}
      <div className="grid md:grid-cols-2 gap-4 mb-6">

        <div className="bg-white rounded-2xl border border-slate-100 shadow-sm p-4">
          <p className="text-xs font-bold text-green-600 mb-3">✓ {t('strengths')}</p>
          <p className="text-xs text-slate-400 italic">{t('emptyStrengths')}</p>
        </div>

        <div className="bg-white rounded-2xl border border-slate-100 shadow-sm p-4">
          <p className="text-xs font-bold text-rose-500 mb-3">✗ {t('weaknesses')}</p>
          <p className="text-xs text-slate-400 italic">{t('emptyWeaknesses')}</p>
        </div>

      </div>

      {/* Summary */}
      <div className="bg-white rounded-2xl border border-slate-100 shadow-sm p-4">
        <p className="text-xs font-bold text-[#1e293b] mb-2">{t('summaryTitle')}</p>
        <p className="text-xs text-slate-400 italic">{t('emptySummary')}</p>
      </div>

    </div>
  )
}
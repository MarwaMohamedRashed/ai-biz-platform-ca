'use client'

import { useTranslations } from 'next-intl'
import RecommendationsList, { Recommendation } from './RecommendationsList'
import type { RoiBreakdown } from '@/lib/roi'

interface Props {
  businessName: string | null
  recommendations: Recommendation[]
  currentTier: 'starter' | 'pro'
  locale: string
  /** ROI breakdown computed server-side. When provided, each recommendation
   *  shows a dollar-range impact tag using lib/roi.recommendationImpactRange. */
  roi: RoiBreakdown | null
}

export default function RecommendationsPage({ businessName, recommendations, currentTier, locale, roi }: Props) {
  const t = useTranslations('dashboard.actionPlan')

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-3xl mx-auto p-6 md:p-10">
        {businessName && (
          <p className="text-xs text-slate-500 mb-1 font-medium">{businessName}</p>
        )}
        <p className="text-sm text-slate-600 mb-6">{t('subtitle')}</p>

        {recommendations.length === 0 ? (
          <div className="bg-white rounded-2xl border border-slate-100 p-6 text-center">
            <p className="text-sm font-semibold text-[#1e293b] mb-1">{t('noAuditTitle')}</p>
            <p className="text-xs text-slate-500 mb-4">{t('noAuditBody')}</p>
            <a
              href={`/${locale}/dashboard`}
              className="text-xs font-semibold bg-[#4f46e5] text-white px-3 py-1.5 rounded-lg hover:bg-indigo-700 transition-colors"
            >
              {t('goRunAudit')}
            </a>
          </div>
        ) : (
          <RecommendationsList
            recommendations={recommendations}
            currentTier={currentTier}
            businessKey={businessName ?? undefined}
            roi={roi}
            locale={locale}
          />
        )}
      </div>
    </div>
  )
}

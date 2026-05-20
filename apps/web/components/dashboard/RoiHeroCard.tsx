'use client'

import { useState } from 'react'
import { useTranslations } from 'next-intl'
import {
  computeRoi,
  computeRoiV2,
  formatCadRange,
  formatCad,
  type RoiBreakdown,
  type MarketVisibility,
  DEFAULT_AI_SHARE,
} from '@/lib/roi'

// Dashboard hero card. Speaks the dentist's language: revenue, not visibility.
//
// Hero metric: monthly AI-influenced revenue exposure (range, not point).
// Secondary metric: capture share % (where the AEO score lives, repositioned
// as a diagnostic, not the destination).
// Tertiary: upside to the practical ceiling at score 95.
//
// Inputs flow from the onboarding extras form (avg_customer_value_cad,
// monthly_new_online_customers). When either is missing we fall back to
// industry defaults from apps/web/lib/roi-defaults.ts and surface that
// fact in the "How we calculate this" disclosure.
//
// Caveat baked into the framing: we say "exposure" not "captured revenue".
// Score → revenue is correlational, not causal — see leapone-roi-framework
// caveat #3 and project_roi_mvp memory.

interface Props {
  score:                       number | null
  businessType:                string | null
  avgCustomerValueCad:         number | null
  monthlyNewOnlineCustomers:   number | null
  ltvMultipleOverride:         number | null
  locale:                      string
  marketVisibility?:           MarketVisibility | null
}

export default function RoiHeroCard({
  score,
  businessType,
  avgCustomerValueCad,
  monthlyNewOnlineCustomers,
  ltvMultipleOverride,
  locale,
  marketVisibility,
}: Props) {
  const t = useTranslations('dashboard.roi')
  const [showMath, setShowMath] = useState(false)

  // We don't render the hero card before the first audit completes — the
  // score is the spine of every figure. Owners on a brand-new business id
  // see the existing "run your first audit" CTA from the audit card.
  if (score == null) return null

  const roiInputs = {
    businessType,
    avgCustomerValueCad,
    monthlyNewOnlineCustomers,
    ltvMultipleOverride,
    score,
  }
  const roi = computeRoiV2(roiInputs, marketVisibility)

  // Pick a visual band based on capture %. Same thresholds as the audit
  // card's scoreTier so the two cards feel consistent.
  const captureRatio = score / 100
  const bandClass =
    score >= 70 ? 'from-emerald-50 to-emerald-100/60 border-emerald-200' :
    score >= 40 ? 'from-amber-50 to-amber-100/60 border-amber-200' :
                  'from-rose-50 to-rose-100/60 border-rose-200'
  const accentText =
    score >= 70 ? 'text-emerald-700' :
    score >= 40 ? 'text-amber-700' :
                  'text-rose-700'

  return (
    <section className={`rounded-2xl border bg-gradient-to-br ${bandClass} p-5 md:p-6`}>
      {/* Eyebrow + headline + hero range */}
      <div className="flex flex-col gap-2">
        <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
          {t('eyebrow')}
        </span>
        <h2 className="text-base md:text-lg font-bold text-[#1e293b] leading-tight">
          {t('headline')}
        </h2>
        <p className="text-2xl md:text-3xl font-extrabold text-[#1e293b] mt-1 tabular-nums">
          {formatCadRange(roi.exposureMonthly, locale)}
          <span className="text-sm font-semibold text-slate-500 ml-2">{t('perMonth')}</span>
        </p>
        <p className={`text-xs md:text-sm font-medium ${accentText}`}>
          {t('captureLine', {
            pct: Math.round(captureRatio * 100),
            atRisk: formatCadRange(roi.atRiskMonthly, locale),
          })}
        </p>
      </div>

      {/* Inline horizontal bar — visual representation of capture vs gap */}
      <div className="mt-4 h-2 w-full rounded-full bg-white/70 overflow-hidden">
        <div
          className={`h-full rounded-full ${
            score >= 70 ? 'bg-emerald-500' :
            score >= 40 ? 'bg-amber-500' :
                          'bg-rose-500'
          }`}
          style={{ width: `${Math.min(100, Math.max(2, captureRatio * 100))}%` }}
        />
      </div>

      {/* Upside + potential summary */}
      <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-3">
        <SummaryCell
          label={t('upsideLabel')}
          value={formatCadRange(roi.upsideMonthly, locale)}
          hint={t('upsideHint')}
        />
        <SummaryCell
          label={t('potentialLabel')}
          value={formatCadRange(roi.potentialMonthly, locale)}
          hint={t('potentialHint')}
        />
      </div>

      {/* Disclosure — required under every dollar figure. Always visible
          in summary form; full math reveals on click. */}
      <div className="mt-4 pt-3 border-t border-white/60">
        <button
          type="button"
          onClick={() => setShowMath(s => !s)}
          className="text-[11px] font-semibold text-slate-500 hover:text-[#4f46e5] inline-flex items-center gap-1">
          {showMath ? t('hideMath') : t('showMath')}
          <span aria-hidden="true">{showMath ? '−' : '+'}</span>
        </button>
        {showMath && (
          <RoiMathBlock roi={roi} t={t} locale={locale} />
        )}
        <div className="flex items-start justify-between gap-2 mt-2">
          <p className="text-[10.5px] text-slate-500 leading-relaxed flex-1">
            {roi.formulaSource === 'A'
              ? t('disclosureA', { aiShare: Math.round(roi.resolved.aiShare * 100) })
              : roi.formulaSource === 'B'
              ? t('disclosureB', { aiShare: Math.round(roi.resolved.aiShare * 100) })
              : t('disclosure', { aiShare: Math.round(DEFAULT_AI_SHARE * 100) })
            }
          </p>
          <span className={`shrink-0 text-[10px] font-semibold px-2 py-0.5 rounded-full ${
            roi.formulaSource === 'C'
              ? 'bg-slate-100 text-slate-500'
              : 'bg-indigo-50 text-indigo-600'
          }`}>
            {t(`formulaSource.${roi.formulaSource}`)}
          </span>
        </div>
      </div>
    </section>
  )
}

function SummaryCell({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <div className="rounded-xl bg-white/70 px-3 py-2.5">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">{label}</p>
      <p className="text-sm font-bold text-[#1e293b] tabular-nums">{value}</p>
      <p className="text-[10.5px] text-slate-500 mt-0.5 leading-snug">{hint}</p>
    </div>
  )
}

function RoiMathBlock({
  roi,
  t,
  locale,
}: {
  roi: RoiBreakdown
  t: ReturnType<typeof useTranslations>
  locale: string
}) {
  const r = roi.resolved
  return (
    <div className="mt-3 rounded-lg bg-white/80 p-3 text-[11px] text-slate-600 leading-relaxed">
      <dl className="grid grid-cols-[auto,1fr] gap-x-3 gap-y-1.5 tabular-nums">
        {roi.formulaSource === 'A' || roi.formulaSource === 'B' ? (
          <>
            <dt className="font-semibold">{t('math.aiShare')}</dt>
            <dd>{Math.round(r.aiShare * 100)}%</dd>

            <dt className="font-semibold">{t('math.avgCustomerValue')}</dt>
            <dd>
              {formatCad(r.avgCustomerValueCad, locale)}
              {!r.avgCustomerValueFromOwner && (
                <span className="text-slate-400 ml-1">{t('math.usingDefault')}</span>
              )}
            </dd>

            <dt className="font-semibold">{t('math.ltvMultiple')}</dt>
            <dd>
              {r.ltvMultiple}×
              {!r.ltvFromOwner && (
                <span className="text-slate-400 ml-1">{t('math.usingDefault')}</span>
              )}
            </dd>

            <dt className="font-semibold">{t('math.lifetimeValue')}</dt>
            <dd>{formatCad(roi.lifetimeValueCad, locale)}</dd>
          </>
        ) : (
          <>
            <dt className="font-semibold">{t('math.score')}</dt>
            <dd>{r.score}/100</dd>

            <dt className="font-semibold">{t('math.monthlyOnline')}</dt>
            <dd>
              {r.monthlyNewOnlineCustomers}
              {!r.monthlyNewOnlineCustomersFromOwner && (
                <span className="text-slate-400 ml-1">{t('math.usingDefault')}</span>
              )}
            </dd>

            <dt className="font-semibold">{t('math.aiShare')}</dt>
            <dd>{Math.round(r.aiShare * 100)}%</dd>

            <dt className="font-semibold">{t('math.avgCustomerValue')}</dt>
            <dd>
              {formatCad(r.avgCustomerValueCad, locale)}
              {!r.avgCustomerValueFromOwner && (
                <span className="text-slate-400 ml-1">{t('math.usingDefault')}</span>
              )}
            </dd>

            <dt className="font-semibold">{t('math.ltvMultiple')}</dt>
            <dd>
              {r.ltvMultiple}×
              {!r.ltvFromOwner && (
                <span className="text-slate-400 ml-1">{t('math.usingDefault')}</span>
              )}
            </dd>

            <dt className="font-semibold">{t('math.aiInfluenced')}</dt>
            <dd>{roi.aiInfluencedCustomersPerMonth.toFixed(1)} {t('math.customersUnit')}</dd>

            <dt className="font-semibold">{t('math.lifetimeValue')}</dt>
            <dd>{formatCad(roi.lifetimeValueCad, locale)}</dd>
          </>
        )}
      </dl>
    </div>
  )
}

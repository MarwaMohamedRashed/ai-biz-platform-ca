'use client'

import { useState } from 'react'
import { useLocale, useTranslations } from 'next-intl'
import StepBusinessInfo from './StepBusinessInfo'
import StepRunAudit, { type AuditResult } from './StepRunAudit'
import StepConfirmCompetitors from './StepConfirmCompetitors'
import StepQuickWins from './StepQuickWins'

interface Props {
  userId: string
  userName: string
  initialStep: number
  initialBusinessId?: string | null
  initialBusinessName?: string
}

// Five-step onboarding:
//   1. Business info + full address          (StepBusinessInfo mode='required')
//   2. Service description + extras          (StepBusinessInfo mode='extras')
//   3. Check your AI visibility (audit)      (StepRunAudit)
//   4. Confirm competitors                   (StepConfirmCompetitors)
//   5. Your first wins                       (StepQuickWins)
// Step 1 INSERTs the business and hands the id straight back, so we no
// longer need a follow-up query to find it before the audit runs.
export default function OnboardingFlow({
  userId,
  userName,
  initialStep,
  initialBusinessId = null,
  initialBusinessName = '',
}: Props) {
  const [step, setStep] = useState(initialStep)
  const [businessName, setBusinessName] = useState(initialBusinessName)
  const [businessId, setBusinessId] = useState<string | null>(initialBusinessId)
  const [auditResult, setAuditResult] = useState<AuditResult | null>(null)
  const t = useTranslations('onboarding.stepper')
  const locale = useLocale()

  const steps = [t('step1'), t('step2'), t('step3'), t('step4'), t('step5')]

  const firstName = (userName || '').trim().split(' ')[0] || 'there'

  return (
    <div className="min-h-screen flex flex-col md:flex-row">

      {/* Left stepper panel */}
      <div className="bg-[#4f46e5] md:w-64 md:min-h-screen px-6 py-8 flex md:flex-col gap-4">
        {/* Brand mark — matches the login page so the user sees the same
            LeapOne identity through signup → onboarding → dashboard. */}
        <div className="hidden md:flex items-center gap-2.5 mb-6">
          <svg width="32" height="32" viewBox="0 0 40 40" fill="none" aria-hidden="true">
            <rect width="40" height="40" rx="12" fill="rgba(255,255,255,0.15)"/>
            <path d="M13 10 L13 28 L27 28" stroke="white" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"/>
            <circle cx="28" cy="13" r="4" fill="#f97316"/>
          </svg>
          <span className="text-[20px] font-extrabold text-white tracking-tight">
            Leap<span className="text-[#f97316]">One</span>
          </span>
        </div>
        {steps.map((label, i) => {
          const num = i + 1
          const active = num === step
          const done = num < step
          return (
            <div key={num} className="flex items-center gap-3">
              <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0
                ${done ? 'bg-white text-[#4f46e5]' : active ? 'bg-white text-[#4f46e5]' : 'bg-indigo-400/40 text-white'}`}>
                {done ? '✓' : num}
              </div>
              <span className={`text-sm hidden md:block ${active ? 'text-white font-semibold' : done ? 'text-indigo-200' : 'text-indigo-300'}`}>
                {label}
              </span>
            </div>
          )
        })}
      </div>

      {/* Right content panel */}
      <div className="flex-1 flex items-center justify-center p-6 md:p-12">
        <div className="w-full max-w-md">
          {step === 1 && (
            <StepBusinessInfo
              mode="required"
              userId={userId}
              onComplete={(name, id) => {
                setBusinessName(name)
                setBusinessId(id)
                setStep(2)
              }}
            />
          )}
          {step === 2 && businessId && (
            <StepBusinessInfo
              mode="extras"
              businessId={businessId}
              businessName={businessName}
              onComplete={() => setStep(3)}
            />
          )}
          {step === 3 && (
            <StepRunAudit
              businessId={businessId}
              locale={locale}
              onComplete={result => { setAuditResult(result); setStep(4) }}
            />
          )}
          {step === 4 && (
            <StepConfirmCompetitors
              auditResult={auditResult}
              onComplete={() => setStep(5)}
            />
          )}
          {step === 5 && (
            <StepQuickWins
              businessName={businessName}
              firstName={firstName}
              auditResult={auditResult}
            />
          )}
        </div>
      </div>

    </div>
  )
}

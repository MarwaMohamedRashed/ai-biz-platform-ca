'use client'

import { useState, useCallback } from 'react'
import { useLocale, useTranslations } from 'next-intl'
import { createClient } from '@/lib/supabase'
import StepBusinessInfo from './StepBusinessInfo'
import StepRunAudit, { type AuditResult } from './StepRunAudit'
import StepQuickWins from './StepQuickWins'

interface Props {
  userId: string
  userName: string
  initialStep: number
}

export default function OnboardingFlow({ userId, userName, initialStep }: Props) {
  const [step, setStep] = useState(initialStep)
  const [businessName, setBusinessName] = useState('')
  const [businessId, setBusinessId] = useState<string | null>(null)
  const [auditResult, setAuditResult] = useState<AuditResult | null>(null)
  const t = useTranslations('onboarding.stepper')
  const locale = useLocale()

  const steps = [t('step1'), t('step2'), t('step3')]

  // After business is saved we need its id for the audit call.
  const handleBusinessSaved = useCallback(async (name: string) => {
    setBusinessName(name)
    try {
      const supabase = createClient()
      const { data } = await supabase
        .from('businesses')
        .select('id')
        .eq('user_id', userId)
        .order('created_at', { ascending: false })
        .limit(1)
        .single()
      if (data?.id) setBusinessId(data.id)
    } catch {
      // Audit step will surface the failed-state UI if businessId is null
    }
    setStep(2)
  }, [userId])

  const firstName = (userName || '').trim().split(' ')[0] || 'there'

  return (
    <div className="min-h-screen flex flex-col md:flex-row">

      {/* Left stepper panel */}
      <div className="bg-[#4f46e5] md:w-64 md:min-h-screen px-6 py-8 flex md:flex-col gap-4">
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
              userId={userId}
              onComplete={handleBusinessSaved}
            />
          )}
          {step === 2 && (
            <StepRunAudit
              businessId={businessId}
              locale={locale}
              onComplete={result => { setAuditResult(result); setStep(3) }}
            />
          )}
          {step === 3 && (
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
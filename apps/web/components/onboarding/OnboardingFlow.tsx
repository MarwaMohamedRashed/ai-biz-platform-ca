'use client'

import { useState } from 'react'
import { useTranslations } from 'next-intl'
import StepBusinessInfo from './StepBusinessInfo'
import StepSuccess from './StepSuccess'
// Phase 3 — restore when Google/Meta API approved (~July 2026)
// import StepConnectGoogle from './StepConnectGoogle'
// import StepSyncing from './StepSyncing'

interface Props {
  userId: string
  userName: string
  initialStep: number
}

export default function OnboardingFlow({ userId, userName, initialStep }: Props) {
  
  
  const [step, setStep] = useState(initialStep)
  const [businessName, setBusinessName] = useState('')
  const t = useTranslations('onboarding.stepper')

  const steps = [t('step1'), t('step2')]

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
              onComplete={(name) => { setBusinessName(name); setStep(2) }}
            />
          )}
          {step === 2 && (
            <StepSuccess businessName={businessName} userName={userName} />
          )}
          {/* Phase 3 — restore when Google/Meta API approved (~July 2026)
          {step === 3 && <StepConnectGoogle onSkip={() => setStep(3)} />}
          {step === 4 && <StepSyncing onComplete={() => setStep(4)} />}
          */}
        </div>
      </div>

    </div>
  )
}
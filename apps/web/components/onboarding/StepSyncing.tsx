'use client'

import { useEffect } from 'react'
import { useTranslations } from 'next-intl'

interface Props {
  onComplete: () => void
}

export default function StepSyncing({ onComplete }: Props) {
  const t = useTranslations('onboarding.step3')

  useEffect(() => {
    const timer = setTimeout(onComplete, 2000)
    return () => clearTimeout(timer)
  }, [onComplete])

  return (
    <div className="flex flex-col items-center gap-6 py-12">
      <div className="w-12 h-12 border-4 border-[#4f46e5] border-t-transparent rounded-full animate-spin" />
      <div className="text-center">
        <h1 className="text-xl font-bold text-[#1e293b]">{t('heading')}</h1>
        <p className="text-sm text-slate-500 mt-1">{t('body')}</p>
      </div>
    </div>
  )
}
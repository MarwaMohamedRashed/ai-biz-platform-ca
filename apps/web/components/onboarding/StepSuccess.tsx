'use client'

import { useRouter } from 'next/navigation'
import { useLocale, useTranslations } from 'next-intl'
import { createClient } from '@/lib/supabase'

interface Props {
  businessName: string
  userName: string
}

export default function StepSuccess({ businessName, userName }: Props) {
  const t = useTranslations('onboarding.step4')
  const router = useRouter()
  const locale = useLocale()

 async function handleGoToDashboard() {
  const supabase = createClient()
  const { data: businesses } = await supabase
    .from('businesses')
    .select('id')
    .limit(1)

  if (businesses?.[0]) {
    const businessId = businesses[0].id

    await supabase.from('businesses')
      .update({ onboarding_completed: true })
      .eq('id', businessId)

    const trialEnds = new Date()
    trialEnds.setDate(trialEnds.getDate() + 14)

    await supabase.from('subscriptions').insert({
      business_id: businessId,
      plan_tier: 'starter',
      status: 'trialing',
      trial_ends: trialEnds.toISOString()
    })
  }

  router.push(`/${locale}/dashboard`)
}

  return (
    <div className="flex flex-col items-center gap-6 py-12 text-center">
      <div className="w-16 h-16 rounded-full bg-green-100 flex items-center justify-center">
        <svg width="32" height="32" viewBox="0 0 24 24" fill="none">
          <polyline points="20 6 9 17 4 12" stroke="#16a34a" strokeWidth="2.5"
            strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      </div>
      <div>
        <h1 className="text-2xl font-bold text-[#1e293b]">{t('heading')}</h1>
        <p className="text-sm text-slate-500 mt-2">{t('body')}</p>
        {businessName && (
          <p className="text-sm font-medium text-[#4f46e5] mt-1">{businessName}</p>
        )}
      </div>
      <button
        onClick={handleGoToDashboard}
        className="w-full py-3 rounded-xl bg-[#4f46e5] text-white text-sm font-semibold
                   hover:bg-indigo-700 transition-colors">
        {t('cta')}
      </button>
    </div>
  )
}
import { getTranslations } from 'next-intl/server'
import { getLocale } from 'next-intl/server'
import ResetPasswordForm from '@/components/ResetPasswordForm'

export default async function ResetPasswordPage() {
  const t = await getTranslations('auth.resetPassword')
  const locale = await getLocale()

  return (
    <main className="min-h-screen bg-[#f1f5f9] flex items-center justify-center p-4">
      <div className="w-full max-w-md bg-white rounded-2xl shadow-xl p-8 flex flex-col gap-6">

        {/* Logo */}
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-[#4f46e5] flex items-center justify-center">
            <svg width="16" height="16" viewBox="0 0 40 40" fill="none">
              <path d="M13 10 L13 28 L27 28" stroke="white" strokeWidth="4"
                strokeLinecap="round" strokeLinejoin="round"/>
              <circle cx="28" cy="13" r="5" fill="#f97316"/>
            </svg>
          </div>
          <span className="text-lg font-extrabold tracking-tight">
            <span className="text-[#4f46e5]">Leap</span><span className="text-[#f97316]">One</span>
          </span>
        </div>

        {/* Heading */}
        <div className="flex flex-col gap-1">
          <h1 className="text-2xl font-bold text-[#1e293b]">{t('heading')}</h1>
          <p className="text-sm text-slate-500">{t('subtitle')}</p>
        </div>

        {/* Form */}
        <ResetPasswordForm />

      </div>
    </main>
  )
}
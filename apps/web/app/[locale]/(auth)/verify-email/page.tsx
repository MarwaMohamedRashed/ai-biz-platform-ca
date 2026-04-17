import { getTranslations, getLocale } from 'next-intl/server'
import Link from 'next/link'
export default async function VerifyEmailPage() {
  const t = await getTranslations('auth.verifyEmail')
  const locale = await getLocale()

  return (
    <main className="min-h-screen bg-[#f1f5f9] flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-xl border border-slate-200 p-10 max-w-md w-full text-center">

        {/* Envelope icon */}
        <div className="w-16 h-16 rounded-full bg-indigo-50 flex items-center justify-center mx-auto mb-6">
          ✉️
        </div>

        <h1 className="text-2xl font-extrabold text-[#1e293b] mb-3" >
            {t('heading')}
        </h1>
        <p className="text-sm text-slate-500 leading-relaxed mb-8">
            {t('body')}
        </p>

        <Link  className="inline-block text-sm font-semibold text-[#4f46e5] hover:underline"  href={`/${locale}/login`}>
          {t('backToLogin')}
        </Link>

      </div>
    </main>
  )
}
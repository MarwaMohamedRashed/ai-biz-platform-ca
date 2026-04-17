import { useTranslations } from 'next-intl'
import Link from 'next/link'
import LanguageSwitcher from '@/components/LanguageSwitcher'
import LoginForm from '@/components/LoginForm'
import GoogleAuthButton from '@/components/GoogleAuthButton'
import AuthErrorBanner from '@/components/AuthErrorBanner'

export default function LoginPage() {
  const t = useTranslations('auth.login')
  const tb = useTranslations('auth.branding')

  return (
    <main className="min-h-screen bg-[#f1f5f9] flex items-center justify-center p-4 md:p-8">

      {/* Outer card: full-width on mobile, centered card on desktop */}
      <div className="w-full md:max-w-[900px] flex flex-col md:flex-row
                      md:rounded-2xl md:shadow-xl md:border md:border-slate-200
                      md:overflow-hidden md:min-h-[580px]">

        {/* Left branding panel — desktop only */}
        <div className="hidden md:flex md:w-[42%] md:flex-shrink-0 flex-col justify-between
                        bg-gradient-to-br from-[#4f46e5] via-[#4338ca] to-[#3730a3]
                        p-12 relative overflow-hidden">
          <div className="absolute -top-20 -right-20 w-64 h-64 rounded-full bg-white/[0.06]" />
          <div className="absolute -bottom-16 -left-16 w-52 h-52 rounded-full bg-white/[0.04]" />

          <div className="flex items-center gap-2.5 relative z-10">
            <svg width="36" height="36" viewBox="0 0 40 40" fill="none">
              <rect width="40" height="40" rx="12" fill="rgba(255,255,255,0.15)"/>
              <path d="M13 10 L13 28 L27 28" stroke="white" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"/>
              <circle cx="28" cy="13" r="4" fill="#f97316"/>
            </svg>
            <span className="text-[22px] font-extrabold text-white tracking-tight">
              Leap<span className="text-[#f97316]">One</span>
            </span>
          </div>

          <div className="relative z-10">
            <h2 className="text-[28px] font-extrabold text-white leading-tight tracking-tight mb-4">
              {tb('headline1')}<br/>
              <span className="text-[#f97316]">{tb('headline2')}</span>
            </h2>
            <p className="text-sm text-white/75 leading-relaxed mb-7">{tb('description')}</p>
            <ul className="flex flex-col gap-2.5">
              {[tb('feature1'), tb('feature2'), tb('feature3'), tb('feature4')].map((feat, i) => (
                <li key={i} className="flex items-center gap-2.5 text-[13px] text-white/85 font-medium">
                  <span className="w-5 h-5 rounded-full bg-[#f97316]/25 border border-[#f97316]
                                   flex items-center justify-center text-[10px] flex-shrink-0">✦</span>
                  {feat}
                </li>
              ))}
            </ul>
          </div>

          <p className="text-[11px] text-white/45 relative z-10">{tb('footer')}</p>
        </div>

        {/* Right form panel */}
        <div className="flex-1 md:bg-white flex flex-col">

          <div className="flex justify-end p-4 md:p-6">
            <LanguageSwitcher />
          </div>

          <div className="flex-1 flex items-center justify-center px-6 pb-8 md:px-8 md:pb-12">

            {/* Mobile: white card. Desktop: transparent (outer card handles it) */}
            <div className="w-full max-w-sm md:max-w-[440px]
                            bg-white md:bg-transparent
                            rounded-3xl md:rounded-none
                            shadow-lg md:shadow-none
                            overflow-hidden md:overflow-visible">

              {/* Logo — mobile only */}
              <div className="md:hidden flex flex-col items-center pt-8 pb-6 gap-3">
                <svg width="64" height="64" viewBox="0 0 40 40" fill="none">
                  <rect width="40" height="40" rx="12" fill="#4f46e5"/>
                  <path d="M13 10 L13 28 L27 28" stroke="white" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"/>
                  <circle cx="28" cy="13" r="4" fill="#f97316"/>
                </svg>
                <div className="text-[26px] font-extrabold tracking-tight">
                  <span className="text-[#4f46e5]">Leap</span><span className="text-[#f97316]">One</span>
                </div>
                <p className="text-[13px] text-slate-500">{t('tagline')}</p>
              </div>

              <div className="px-6 pb-9 md:px-0 md:pb-0 md:w-full">

                <div className="text-center md:text-left mb-6">
                  <h1 className="text-xl md:text-[22px] font-extrabold text-[#1e293b] mb-1">
                    {t('welcomeBack')}
                  </h1>
                  <p className="text-[13px] text-slate-500">{t('signInSubtitle')}</p>
                </div>

              <GoogleAuthButton translationKey="continueWithGoogle" />

                <div className="flex items-center gap-3 mb-5">
                  <div className="flex-1 h-px bg-slate-200" />
                  <span className="text-xs text-slate-400 font-medium">{t('orSignInWith')}</span>
                  <div className="flex-1 h-px bg-slate-200" />
                </div>
                <AuthErrorBanner />
                <LoginForm />

                <p className="text-center text-[13px] text-slate-500 mt-4">
                  {t('noAccount')}{' '}
                  <Link href="/signup" className="text-[#4f46e5] font-semibold hover:underline">
                    {t('signUpFree')}
                  </Link>
                </p>

              </div>
            </div>
          </div>
        </div>

      </div>
    </main>
  )
}



'use client'

import { useLocale } from 'next-intl'
import { usePathname, useRouter } from 'next/navigation'

export default function LanguageSwitcher() {
  const locale = useLocale()
  const pathname = usePathname()
  const router = useRouter()

  function switchTo(newLocale: string) {
    const segments = pathname.split('/')
    segments[1] = newLocale
    router.push(segments.join('/'))
  }

  return (
    <div className="flex items-center gap-1 text-xs font-semibold">
      <button
        onClick={() => switchTo('en')}
        className={
          locale === 'en'
            ? 'text-[#4f46e5]'
            : 'text-slate-400 hover:text-slate-600 transition-colors'
        }
      >
        EN
      </button>
      <span className="text-slate-300">|</span>
      <button
        onClick={() => switchTo('fr')}
        className={
          locale === 'fr'
            ? 'text-[#4f46e5]'
            : 'text-slate-400 hover:text-slate-600 transition-colors'
        }
      >
        FR
      </button>
    </div>
  )
}

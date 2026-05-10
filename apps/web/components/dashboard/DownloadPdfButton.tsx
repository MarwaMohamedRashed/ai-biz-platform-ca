'use client'

import { useTranslations } from 'next-intl'

interface Props {
  businessName: string | null
}

export default function DownloadPdfButton({ businessName }: Props) {
  const t = useTranslations('dashboard.report')

  function handleDownload() {
    const slug = (businessName || 'leapone-aeo')
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '')
      .slice(0, 60)
    const date = new Date().toISOString().slice(0, 10)
    const previousTitle = document.title
    document.title = `leapone-aeo-${slug}-${date}`
    document.body.classList.add('printing-report')
    function cleanup() {
      document.body.classList.remove('printing-report')
      document.title = previousTitle
      window.removeEventListener('afterprint', cleanup)
    }
    window.addEventListener('afterprint', cleanup)
    window.print()
  }

  return (
    <button
      type="button"
      onClick={handleDownload}
      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg
                 text-xs font-semibold text-[#4f46e5] bg-indigo-50
                 hover:bg-indigo-100 transition-colors print-hide">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"
          stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
        <polyline points="7 10 12 15 17 10"
          stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
        <line x1="12" y1="15" x2="12" y2="3"
          stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
      </svg>
      {t('download')}
    </button>
  )
}

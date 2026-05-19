'use client'

import { useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useTranslations } from 'next-intl'
import { createClient } from '@/lib/supabase'

// Page-header-mounted "Re-run audit" button. Moved out of AeoAuditCard
// (where it lived buried in the middle of the dashboard) so the most
// important action on the page is reachable without scrolling.
//
// On success we trigger Next.js router.refresh() rather than dispatching
// a window event — that re-runs every Server Component on the dashboard
// (audit card, ROI hero, Progress card, DetectedSignalsCard,
// AuditReportPrint) against the new audit row. No prop wiring required.

interface Props {
  businessId: string | null
  hasAudit:   boolean
  locale:     string
}

export default function RerunAuditButton({ businessId, hasAudit, locale }: Props) {
  const t = useTranslations('dashboard.aeo')
  const router = useRouter()
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState<'' | 'generic' | 'upgrade_required'>('')

  async function runAudit() {
    if (!businessId || loading) return
    setLoading(true)
    setError('')
    try {
      const { data: { session } } = await createClient().auth.getSession()
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/v1/aeo/audit`, {
        method: 'POST',
        headers: {
          'Content-Type':  'application/json',
          'Authorization': `Bearer ${session?.access_token}`,
        },
        body: JSON.stringify({ business_id: businessId, locale }),
      })
      if (res.status === 402) {
        setError('upgrade_required')
        return
      }
      if (!res.ok) throw new Error('audit failed')
      // Re-render Server Components against the freshly-written audit row.
      router.refresh()
    } catch {
      setError('generic')
    } finally {
      setLoading(false)
    }
  }

  if (!businessId) return null

  return (
    <div className="flex flex-col items-end gap-1.5">
      <button
        type="button"
        onClick={runAudit}
        disabled={loading}
        className="inline-flex items-center gap-1.5 text-xs font-semibold bg-[#4f46e5] text-white
                   px-3 py-1.5 rounded-lg hover:bg-indigo-700 transition-colors disabled:opacity-50">
        {loading ? (
          <>
            <span className="w-3 h-3 border-2 border-white/40 border-t-white rounded-full animate-spin" aria-hidden="true" />
            {t('running')}
          </>
        ) : hasAudit ? t('rerunAudit') : t('runAudit')}
      </button>
      {error === 'upgrade_required' && (
        <Link href={`/${locale}/dashboard/plan`}
              className="text-[10.5px] font-semibold text-amber-700 hover:underline text-right">
          {t('upgradeTitle')} →
        </Link>
      )}
      {error === 'generic' && (
        <p className="text-[10.5px] text-red-500">{t('auditFailed')}</p>
      )}
    </div>
  )
}

import { getTranslations } from 'next-intl/server'

// Read-only display of what the AEO scanner picked up about this business
// from the website homepage + the user's free-form services field during
// the last audit. Mounting this on the dashboard gives the owner (and us
// during testing) a transparency window: if the cuisine looks wrong, or
// dietary signals are missing, we know to refine detection.
//
// Edit affordance intentionally deferred — see project_onboarding_server_routes
// memory and the conversation around the minimal version. Add it later only
// if real owners report wrong detections.

interface DetectedSignals {
  cuisine?:        string | null
  cuisine_parent?: string | null
  dietary_tags?:   string[]
  service_tags?:   string[]
}

interface Props {
  signals: DetectedSignals | null | undefined
}

export default async function DetectedSignalsCard({ signals }: Props) {
  const t = await getTranslations('dashboard.detectedSignals')

  if (!signals) return null

  const cuisine      = signals.cuisine
  const dietary      = signals.dietary_tags ?? []
  const services     = signals.service_tags ?? []
  const hasAnything  = !!cuisine || dietary.length > 0 || services.length > 0

  if (!hasAnything) return null

  return (
    <section className="bg-white rounded-2xl shadow-sm border border-slate-100 p-5 print-hide">
      <div className="flex items-start justify-between gap-3 mb-3">
        <div>
          <h2 className="text-sm font-extrabold text-[#1e293b]">{t('title')}</h2>
          <p className="text-xs text-slate-500 mt-0.5">{t('subtitle')}</p>
        </div>
      </div>

      <div className="flex flex-col gap-3">
        {cuisine && (
          <Row label={t('cuisine')}>
            <Chip>{cuisine}</Chip>
          </Row>
        )}
        {dietary.length > 0 && (
          <Row label={t('dietary')}>
            {dietary.map(tag => <Chip key={tag}>{tag}</Chip>)}
          </Row>
        )}
        {services.length > 0 && (
          <Row label={t('services')}>
            {services.map(tag => <Chip key={tag}>{tag}</Chip>)}
          </Row>
        )}
      </div>
    </section>
  )
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1.5 sm:flex-row sm:items-start sm:gap-3">
      <span className="text-xs font-semibold text-slate-500 sm:w-24 sm:pt-1.5 flex-shrink-0">
        {label}
      </span>
      <div className="flex flex-wrap gap-1.5">{children}</div>
    </div>
  )
}

function Chip({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium
                     bg-indigo-50 text-[#4f46e5] border border-indigo-100">
      {children}
    </span>
  )
}

'use client'

import { useTranslations } from 'next-intl'

const DAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'] as const
type Day = typeof DAYS[number]

export type HoursValue = Partial<Record<Day, string>>  // "HH:MM-HH:MM" or "closed"

interface Props {
  value: HoursValue
  onChange: (next: HoursValue) => void
}

function parseRange(v: string | undefined): { open: string; close: string; closed: boolean } {
  if (!v || v === 'closed') return { open: '09:00', close: '17:00', closed: v === 'closed' }
  const m = v.match(/^(\d{2}:\d{2})-(\d{2}:\d{2})$/)
  if (!m) return { open: '09:00', close: '17:00', closed: false }
  return { open: m[1], close: m[2], closed: false }
}

export default function HoursEditor({ value, onChange }: Props) {
  const t = useTranslations('dashboard.settings.businessProfile')

  function setDay(day: Day, next: { open?: string; close?: string; closed?: boolean }) {
    const cur = parseRange(value[day])
    const merged = { ...cur, ...next }
    const newVal: HoursValue = { ...value }
    newVal[day] = merged.closed ? 'closed' : `${merged.open}-${merged.close}`
    onChange(newVal)
  }

  return (
    <div className="flex flex-col gap-2">
      {DAYS.map(day => {
        const { open, close, closed } = parseRange(value[day])
        return (
          <div key={day} className="flex items-center gap-2 text-xs">
            <span className="w-20 capitalize text-slate-600">{day}</span>
            <label className="flex items-center gap-1 text-slate-500">
              <input
                type="checkbox"
                checked={closed}
                onChange={e => setDay(day, { closed: e.target.checked })}
                className="h-3.5 w-3.5 text-[#4f46e5] border-gray-300 rounded focus:ring-[#4f46e5]"
              />
              {t('hoursClosed')}
            </label>
            <input
              type="time"
              value={open}
              disabled={closed}
              onChange={e => setDay(day, { open: e.target.value })}
              className="border border-slate-200 rounded-lg px-2 py-1 text-xs text-[#1e293b]
                         focus:outline-none focus:border-[#4f46e5] disabled:bg-slate-50 disabled:text-slate-400"
            />
            <span className="text-slate-400">–</span>
            <input
              type="time"
              value={close}
              disabled={closed}
              onChange={e => setDay(day, { close: e.target.value })}
              className="border border-slate-200 rounded-lg px-2 py-1 text-xs text-[#1e293b]
                         focus:outline-none focus:border-[#4f46e5] disabled:bg-slate-50 disabled:text-slate-400"
            />
          </div>
        )
      })}
    </div>
  )
}

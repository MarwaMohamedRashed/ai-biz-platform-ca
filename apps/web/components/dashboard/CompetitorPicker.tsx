'use client'

import { useState, useCallback, useRef, useEffect } from 'react'
import { useTranslations } from 'next-intl'
import { createClient } from '@/lib/supabase'

export interface CompetitorEntry {
  place_id: string
  name: string
  source: 'auto' | 'manual'
  added_at?: string
  last_seen_at?: string | null
  status?: 'active' | 'stale' | 'closed'
  // Scored data (present after the audit has scored this entry)
  score?: number
  rating?: number | null
  reviews?: number | null
  address?: string | null
}

interface SearchResult {
  place_id: string
  name: string
  address?: string
  rating?: number
  reviews?: number
  type?: string
  website?: string
}

interface Props {
  /** Current confirmed list. Editor is initialized from this. */
  initialList: CompetitorEntry[]
  /** Optional Google-suggested additions to show below the editor. */
  suggestions?: CompetitorEntry[]
  /** Called when the save succeeds with the fully-scored response from the API. */
  onSaved?: (competitors: CompetitorEntry[]) => void
  /** Hide the Save button — caller is wrapping in a multi-step flow. */
  hideSave?: boolean
  /** Imperative save handle exposed to the parent (onboarding multi-step wraps this). */
  saveRef?: React.MutableRefObject<(() => Promise<void>) | null>
}

const MAX_COMPETITORS = 5

export default function CompetitorPicker({
  initialList, suggestions = [], onSaved, hideSave, saveRef,
}: Props) {
  const t = useTranslations('dashboard.competitorPicker')
  const [list, setList] = useState<CompetitorEntry[]>(() => initialList.slice(0, MAX_COMPETITORS))
  const [query, setQuery] = useState('')
  const [searchResults, setSearchResults] = useState<SearchResult[]>([])
  const [searching, setSearching] = useState(false)
  const [searchEmpty, setSearchEmpty] = useState(false)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState('')
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const atMax = list.length >= MAX_COMPETITORS

  // ─── Search (debounced) ──────────────────────────────────────────────
  const runSearch = useCallback(async (q: string) => {
    if (q.trim().length < 2) {
      setSearchResults([])
      setSearchEmpty(false)
      return
    }
    setSearching(true)
    setSearchEmpty(false)
    try {
      const { data: { session } } = await createClient().auth.getSession()
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/api/v1/aeo/competitor-search?q=${encodeURIComponent(q)}`,
        { headers: { Authorization: `Bearer ${session?.access_token}` } },
      )
      if (!res.ok) throw new Error('search failed')
      const data = await res.json()
      const results = (data.results || []) as SearchResult[]
      setSearchResults(results)
      setSearchEmpty(results.length === 0)
    } catch {
      setSearchResults([])
      setSearchEmpty(true)
    } finally {
      setSearching(false)
    }
  }, [])

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => runSearch(query), 350)
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current) }
  }, [query, runSearch])

  // ─── List mutations ──────────────────────────────────────────────────
  function addCompetitor(c: SearchResult | CompetitorEntry, source: 'auto' | 'manual' = 'manual') {
    if (atMax) return
    if (list.some(e => e.place_id === c.place_id)) return
    const entry: CompetitorEntry = {
      place_id: c.place_id,
      name:     c.name,
      source,
    }
    setList([...list, entry])
    setQuery('')
    setSearchResults([])
  }
  function removeCompetitor(place_id: string) {
    setList(list.filter(c => c.place_id !== place_id))
  }

  // ─── Save (also exposed via imperative ref for onboarding wrap) ──────
  const save = useCallback(async () => {
    setSaving(true)
    setError('')
    setSaved(false)
    try {
      const { data: { session } } = await createClient().auth.getSession()
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/v1/aeo/competitors`, {
        method: 'POST',
        headers: {
          'Content-Type':  'application/json',
          'Authorization': `Bearer ${session?.access_token}`,
        },
        body: JSON.stringify({
          competitors: list.map(c => ({
            place_id: c.place_id,
            name:     c.name,
            source:   c.source,
          })),
        }),
      })
      if (!res.ok) throw new Error('save failed')
      const data = await res.json()
      setSaved(true)
      onSaved?.(data.competitors || [])
      setTimeout(() => setSaved(false), 3000)
    } catch {
      setError(t('scoreError'))
    } finally {
      setSaving(false)
    }
  }, [list, onSaved, t])

  useEffect(() => {
    if (saveRef) saveRef.current = save
    return () => { if (saveRef) saveRef.current = null }
  }, [save, saveRef])

  // Suggestions still relevant after current list edits
  const relevantSuggestions = suggestions.filter(s => !list.some(c => c.place_id === s.place_id))

  return (
    <div className="flex flex-col gap-4">
      {/* ── Current list ── */}
      <div>
        <div className="flex items-baseline justify-between mb-2">
          <h3 className="text-sm font-extrabold text-[#1e293b]">{t('currentList')}</h3>
          <span className="text-xs text-slate-400">{list.length} / {MAX_COMPETITORS}</span>
        </div>
        {list.length === 0 ? (
          <p className="text-xs text-slate-500 italic px-1 py-3">{t('emptyList')}</p>
        ) : (
          <div className="flex flex-col gap-2">
            {list.map(c => (
              <CompetitorRow key={c.place_id} entry={c} onRemove={() => removeCompetitor(c.place_id)} />
            ))}
          </div>
        )}
      </div>

      {/* ── Add competitor (search) ── */}
      {!atMax && (
        <div>
          <label className="text-sm font-semibold text-[#1e293b] mb-1.5 block">
            {t('addCta')}
          </label>
          <input
            type="text"
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder={t('addPlaceholder')}
            className="w-full border border-slate-200 rounded-xl px-4 py-2.5 text-sm text-[#1e293b]
                       outline-none focus:border-[#4f46e5] transition-colors" />

          {searching && (
            <p className="text-xs text-slate-400 mt-2 px-1">{t('searching')}</p>
          )}
          {!searching && searchResults.length > 0 && (
            <div className="mt-2 border border-slate-200 rounded-xl divide-y divide-slate-100 max-h-64 overflow-y-auto">
              {searchResults.map(r => (
                <button
                  key={r.place_id}
                  type="button"
                  onClick={() => addCompetitor(r, 'manual')}
                  className="w-full text-left px-3 py-2.5 hover:bg-slate-50 transition-colors flex items-start gap-3">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-[#1e293b] truncate">{r.name}</p>
                    {r.address && (
                      <p className="text-xs text-slate-500 truncate">{r.address}</p>
                    )}
                    <div className="flex items-center gap-2 text-[11px] text-slate-500 mt-0.5">
                      {r.rating && <span>{t('rating', { rating: r.rating })}</span>}
                      {typeof r.reviews === 'number' && (
                        <span>{t('reviewsCount', { count: r.reviews })}</span>
                      )}
                      {r.type && <span className="text-slate-400">· {r.type}</span>}
                    </div>
                  </div>
                  <span className="text-[#4f46e5] text-lg flex-shrink-0">+</span>
                </button>
              ))}
            </div>
          )}
          {!searching && searchEmpty && query.length >= 2 && (
            <p className="text-xs text-slate-500 mt-2 px-1">{t('searchEmpty')}</p>
          )}
        </div>
      )}
      {atMax && (
        <p className="text-xs text-slate-400 italic px-1">{t('max')}</p>
      )}

      {/* ── Suggestions ── */}
      {relevantSuggestions.length > 0 && (
        <div className="pt-3 border-t border-slate-100">
          <h3 className="text-sm font-extrabold text-[#1e293b]">{t('suggestionsTitle')}</h3>
          <p className="text-xs text-slate-500 mb-2">{t('suggestionsHint')}</p>
          <div className="flex flex-col gap-2">
            {relevantSuggestions.slice(0, 5).map(s => (
              <div key={s.place_id} className="bg-slate-50 border border-slate-100 rounded-xl px-3 py-2 flex items-center justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-[#1e293b] truncate">{s.name}</p>
                  {s.address && <p className="text-xs text-slate-500 truncate">{s.address}</p>}
                </div>
                <button
                  type="button"
                  onClick={() => addCompetitor(s, 'auto')}
                  disabled={atMax}
                  className="text-xs font-semibold text-[#4f46e5] hover:underline disabled:opacity-40 disabled:no-underline flex-shrink-0">
                  {t('acceptSuggestion')}
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {error && <p className="text-xs text-red-500">{error}</p>}

      {/* ── Save row ── */}
      {!hideSave && (
        <div className="flex items-center gap-3 pt-2">
          <button
            type="button"
            onClick={save}
            disabled={saving}
            className="px-4 py-2 bg-[#4f46e5] text-white text-xs font-semibold rounded-xl
                       hover:bg-indigo-700 transition-colors disabled:opacity-50">
            {saving ? t('saving') : t('save')}
          </button>
          {saved && <span className="text-xs text-green-600 font-semibold">✓ {t('saved')}</span>}
        </div>
      )}

      {/* ── Scoring overlay ── */}
      {saving && <ScoringModal />}
    </div>
  )
}

function CompetitorRow({ entry, onRemove }: { entry: CompetitorEntry; onRemove: () => void }) {
  const t = useTranslations('dashboard.competitorPicker')
  const stale  = entry.status === 'stale'
  const closed = entry.status === 'closed'
  return (
    <div className={`border rounded-xl px-3 py-2.5 flex items-start gap-3
      ${closed ? 'bg-slate-50 border-slate-200 opacity-70'
        : stale ? 'bg-amber-50/50 border-amber-100'
        : 'bg-white border-slate-200'}`}>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-0.5">
          <p className="text-sm font-semibold text-[#1e293b] truncate">{entry.name}</p>
          <span className={`text-[9px] font-semibold px-1.5 py-0.5 rounded-full flex-shrink-0
            ${entry.source === 'manual' ? 'bg-indigo-50 text-indigo-700' : 'bg-slate-100 text-slate-600'}`}>
            {entry.source === 'manual' ? t('sourceManual') : t('sourceAuto')}
          </span>
        </div>
        {entry.address && (
          <p className="text-xs text-slate-500 truncate">{entry.address}</p>
        )}
        <div className="flex items-center gap-2 text-[11px] text-slate-500 mt-0.5">
          {typeof entry.rating === 'number' && <span>{t('rating', { rating: entry.rating })}</span>}
          {typeof entry.reviews === 'number' && (
            <span>{t('reviewsCount', { count: entry.reviews })}</span>
          )}
        </div>
        {closed  && <p className="text-[11px] text-slate-600 mt-1 font-medium">⚠ {t('statusClosed')}</p>}
        {stale   && <p className="text-[11px] text-amber-700 mt-1 font-medium">⚠ {t('statusStale')}</p>}
      </div>
      <button
        type="button"
        onClick={onRemove}
        className="text-xs font-medium text-slate-500 hover:text-red-500 transition-colors flex-shrink-0">
        {t('remove')}
      </button>
    </div>
  )
}

function ScoringModal() {
  const t = useTranslations('dashboard.competitorPicker')
  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-6">
      <div className="bg-white rounded-2xl shadow-2xl p-6 max-w-sm w-full flex flex-col items-center gap-4 text-center">
        <div className="w-12 h-12 rounded-full border-4 border-indigo-100 border-t-[#4f46e5] animate-spin" />
        <div>
          <p className="text-sm font-semibold text-[#1e293b]">{t('scoring')}</p>
          <p className="text-xs text-slate-500 mt-1.5">{t('scoringHint')}</p>
        </div>
      </div>
    </div>
  )
}

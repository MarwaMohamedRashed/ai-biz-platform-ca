// Audit drift helpers — compare the latest two audits to surface what
// changed month-over-month. Pure functions, safe in Server Components.
//
// Used by the dashboard Progress card (Phase 2). The drift signal is the
// retention spine: every month the owner gets a fresh answer to "is what
// I'm doing actually working?". We don't need server-persisted completion
// records for v1 — what we have (score, citations-by-engine, mention
// rate) is enough to surface meaningful month-over-month change.

/** Shape mirrors what aeo_audits.raw_results actually holds today. Loose
 *  typing because audit results have grown organically; only the fields
 *  used below are required. */
export interface AuditSnapshot {
  score:           number
  created_at:      string
  raw_results: {
    perplexity?: { mentioned?: boolean }
    chatgpt?:    { mentioned?: boolean }
    google?: {
      ai_overview?:     { mentioned?: boolean }
      local_pack?:      { present?: boolean; position?: number | null }
      knowledge_graph?: { found?: boolean; reviews_count?: number | null; rating?: number | null }
    }
    competitors?: Array<{ name?: string | null; place_id?: string | null }>
  } | null
}

export interface AuditDrift {
  /** ISO timestamps so the UI can render relative dates ("3 weeks ago"). */
  currentAt:        string
  previousAt:       string
  /** Score delta — positive means the score improved. */
  scoreDelta:       number
  currentScore:     number
  previousScore:    number
  /** Per-AI-engine mention changes. Each is a +1/0/-1. */
  perplexityChange: -1 | 0 | 1
  chatgptChange:    -1 | 0 | 1
  googleAiChange:   -1 | 0 | 1
  /** Local-pack presence change. */
  localPackChange:  -1 | 0 | 1
  /** Knowledge-graph review-count delta (null if either side missing). */
  reviewCountDelta: number | null
  /** Names of competitors that appeared OR disappeared since last audit. */
  newCompetitors:      string[]
  droppedCompetitors:  string[]
}

/**
 * Compute drift between the latest two audits. Returns null when there's
 * fewer than two audits — the dashboard's "first monthly report unlocks
 * on…" copy handles that empty state.
 *
 * `history` is expected newest-first (matches the dashboard page query
 * which orders `created_at descending`).
 */
export function computeDrift(history: AuditSnapshot[] | null | undefined): AuditDrift | null {
  if (!history || history.length < 2) return null
  const [current, previous] = history
  if (!current || !previous) return null

  return {
    currentAt:        current.created_at,
    previousAt:       previous.created_at,
    scoreDelta:       (current.score ?? 0) - (previous.score ?? 0),
    currentScore:     current.score ?? 0,
    previousScore:    previous.score ?? 0,
    perplexityChange: deltaBool(
      current.raw_results?.perplexity?.mentioned,
      previous.raw_results?.perplexity?.mentioned,
    ),
    chatgptChange: deltaBool(
      current.raw_results?.chatgpt?.mentioned,
      previous.raw_results?.chatgpt?.mentioned,
    ),
    googleAiChange: deltaBool(
      current.raw_results?.google?.ai_overview?.mentioned,
      previous.raw_results?.google?.ai_overview?.mentioned,
    ),
    localPackChange: deltaBool(
      current.raw_results?.google?.local_pack?.present,
      previous.raw_results?.google?.local_pack?.present,
    ),
    reviewCountDelta: deltaNumber(
      current.raw_results?.google?.knowledge_graph?.reviews_count,
      previous.raw_results?.google?.knowledge_graph?.reviews_count,
    ),
    newCompetitors:     competitorDiff(current.raw_results?.competitors, previous.raw_results?.competitors),
    droppedCompetitors: competitorDiff(previous.raw_results?.competitors, current.raw_results?.competitors),
  }
}

function deltaBool(curr: boolean | undefined, prev: boolean | undefined): -1 | 0 | 1 {
  if (curr === prev) return 0
  if (curr && !prev) return 1
  if (!curr && prev) return -1
  return 0
}

function deltaNumber(curr: number | null | undefined, prev: number | null | undefined): number | null {
  if (curr == null || prev == null) return null
  return curr - prev
}

type CompetitorRef = { name?: string | null; place_id?: string | null }

function competitorDiff(
  a: CompetitorRef[] | null | undefined,
  b: CompetitorRef[] | null | undefined,
): string[] {
  // Normalize each side to a set of identity keys (place_id || name).
  // Identity by place_id when available; falls back to lowercased name.
  const keyOf = (c: CompetitorRef): string => {
    if (c.place_id) return `id:${c.place_id}`
    if (c.name)     return `n:${c.name.toLowerCase().trim()}`
    return ''
  }
  const setB = new Set((b ?? []).map(keyOf).filter(Boolean))
  const seen = new Set<string>()
  const onlyInA: string[] = []
  for (const c of a ?? []) {
    const k = keyOf(c)
    if (!k || setB.has(k) || seen.has(k)) continue
    seen.add(k)
    if (c.name) onlyInA.push(c.name)
    if (onlyInA.length >= 5) break // cap UI list at 5
  }
  return onlyInA
}

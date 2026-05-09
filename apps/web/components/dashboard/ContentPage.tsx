'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useLocale } from 'next-intl'
import { createClient } from '@/lib/supabase'
import { patchContent, verifyContentItem, regenerateContentItem } from '@/lib/content-api'

interface FaqItem { question: string; answer: string }

interface Descriptions {
  website?: string
  gbp?: string
  yelp?: string
}

// Tolerant of both the new shape (descriptions{}) and the legacy shape (description string)
interface Content {
  id?: string                       // populated for new audits; null for legacy
  language?: 'en' | 'fr'
  descriptions?: Descriptions
  description?: string             // legacy fallback
  faq?: FaqItem[]
  faq_schema?: string | null
  schema_markup?: string
  schema_missing_fields?: string[]
  social_bio?: string
  paa_questions?: string[]
  validation_warnings?: string[]
  verified?: Record<string, boolean>
}

interface Props {
  businessId: string | null
  initialContent: Content | null
}

const MISSING_FIELD_LABELS: Record<string, string> = {
  name:           'Business name',
  image_url:      'Logo or photo URL',
  street_address: 'Street address',
  city:           'City',
  phone:          'Phone number',
}

const DESC_TABS = [
  { key: 'website', label: 'Website',   hint: '300–400 words for your homepage / About page' },
  { key: 'gbp',     label: 'Google',    hint: 'Google Business Profile description (≤ 700 chars)' },
  { key: 'yelp',    label: 'Yelp',      hint: 'Yelp / directory style, 200–250 words' },
] as const

// Stepped layout — one step shown at a time so we don't drown
// non-technical owners on first contact. Schema (technical) is the last
// step so it's tucked away by default.
const STEPS = [
  { key: 'description', label: 'Description', sublabel: 'Per platform' },
  { key: 'social',      label: 'Social bio',  sublabel: '≤ 150 chars' },
  { key: 'faq',         label: 'FAQ',         sublabel: '10 Q&As + schema' },
  { key: 'schema',      label: 'Schema markup', sublabel: 'Technical' },
] as const

type StepKey = typeof STEPS[number]['key']

// Per-step guidance card -- explains what each piece of content is FOR,
// WHERE to paste it, and WHY it matters for AI search visibility. Without
// this, owners don't understand why a 49-character social bio is worth
// generating; with it, they understand each piece is a different AEO lever.
const STEP_GUIDANCE: Record<StepKey, {
  whatItIs: string
  whereToPaste: string
  whyItMatters: string
}> = {
  description: {
    whatItIs: 'Three description variants — one tuned for each platform you publish on.',
    whereToPaste:
      "Website: paste in your homepage About section (and use as the page's meta description). " +
      'Google: sign in to business.google.com → Edit profile → Business description. ' +
      'Yelp: biz.yelp.com → Edit Business Information → Description.',
    whyItMatters:
      'Highest-impact AEO content. Direct signal to ChatGPT, Perplexity, and Google AI Overview. ' +
      'AI engines crawl your homepage + GBP + Yelp listings and cite the description text verbatim ' +
      'when answering "what does <business> do?" / "best <type> in <city>?" queries.',
  },
  social: {
    whatItIs: 'A short bio used consistently across every social platform you have.',
    whereToPaste:
      'Instagram bio · Facebook Page About → Short Description · X (Twitter) bio · ' +
      'LinkedIn personal headline · TikTok bio · YouTube channel description (first line).',
    whyItMatters:
      'Indirect but real citation source. Facebook + Instagram pages appear in Google search results ' +
      'and AI engines do cite them. Using the SAME bio across platforms creates Name + Address + ' +
      'Phone (NAP) consistency — a trust signal AI engines weigh when deciding whether your business ' +
      'is "real enough" to recommend. Inconsistent bios across platforms suggest a fly-by-night ' +
      'operation; consistent bios suggest legitimacy.',
  },
  faq: {
    whatItIs: '10 Q&As and the matching FAQPage JSON-LD that wraps them as structured data.',
    whereToPaste:
      'Build a /faq page on your website. Paste the Q&As as visible page content. Paste the FAQ ' +
      'Schema (JSON-LD) inside the <head> tag of that same /faq page (the Copy button wraps it in ' +
      'a complete <script> tag).',
    whyItMatters:
      'FAQs are the highest-leverage AEO content per word. AI engines — especially ChatGPT and ' +
      'Perplexity — cite FAQ answers verbatim when responding to user questions that match. The ' +
      'JSON-LD schema also unlocks Google rich-result snippets (the expandable Q&A boxes you see in ' +
      'search results), which dramatically increases click-through rate.',
  },
  schema: {
    whatItIs: 'Machine-readable description of your business in the format AI crawlers prefer.',
    whereToPaste:
      'Inside the <head> tag of your homepage (and any other key pages — About, Contact, Services). ' +
      'The Copy button wraps it in a complete <script type="application/ld+json"> tag — paste it as-is.',
    whyItMatters:
      'Most direct signal you can give Google\'s Knowledge Graph + AI Overview. Required for rich-' +
      'result eligibility (review stars, opening hours, price range showing in search results). ' +
      'Every AI crawler reads this — including GPTBot, PerplexityBot, ClaudeBot. A single correct ' +
      'JSON-LD block is worth more than 1000 words of marketing copy for AEO purposes.',
  },
}

function wrapAsScriptTag(jsonLd: string): string {
  return `<script type="application/ld+json">\n${jsonLd}\n</script>`
}

function normaliseContent(c: Content | null): Content | null {
  if (!c) return null
  // Migrate legacy shape ({description: str}) to the new shape ({descriptions: {website: ...}})
  if (!c.descriptions && c.description) {
    return { ...c, descriptions: { website: c.description } }
  }
  return c
}

export default function ContentPage({ businessId, initialContent }: Props) {
  const locale = useLocale()
  const [content, setContent] = useState<Content | null>(normaliseContent(initialContent))
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [copied, setCopied] = useState<string | null>(null)
  const [activeDescTab, setActiveDescTab] = useState<'website' | 'gbp' | 'yelp'>('website')
  const [step, setStep] = useState<StepKey>('description')
  const [language, setLanguage] = useState<'en' | 'fr'>(
    initialContent?.language === 'fr' ? 'fr' : (locale === 'fr' ? 'fr' : 'en')
  )

  function goNext() {
    const i = STEPS.findIndex(s => s.key === step)
    if (i < STEPS.length - 1) setStep(STEPS[i + 1].key)
  }
  function goPrev() {
    const i = STEPS.findIndex(s => s.key === step)
    if (i > 0) setStep(STEPS[i - 1].key)
  }

  async function generate() {
    if (!businessId) return
    setLoading(true)
    setError('')
    try {
      const { data: { session } } = await createClient().auth.getSession()
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/v1/aeo/generate-content`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${session?.access_token}`,
        },
        body: JSON.stringify({ business_id: businessId, language }),
      })
      if (!res.ok) throw new Error('Generation failed')
      setContent(await res.json())
    } catch {
      setError('Generation failed. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  function copy(text: string, key: string) {
    navigator.clipboard.writeText(text)
    setCopied(key)
    setTimeout(() => setCopied(null), 2000)
  }

  if (!businessId) {
    return (
      <div className="flex-1 flex items-center justify-center p-8">
        <p className="text-sm text-slate-500">Complete your business profile in Settings first.</p>
      </div>
    )
  }

  const activeDesc = content?.descriptions?.[activeDescTab] ?? ''
  const activeDescHint = DESC_TABS.find(t => t.key === activeDescTab)?.hint ?? ''

  const stepIndex = STEPS.findIndex(s => s.key === step)

  return (
    <div className="flex-1 overflow-y-auto px-4 md:px-6 py-6">
      <div className="max-w-4xl">

        <div className="flex items-center justify-between mb-4 gap-3 flex-wrap">
          <div>
            <h1 className="text-lg font-extrabold text-[#1e293b]">AI Content Generator</h1>
            <p className="text-xs text-slate-400 mt-0.5">Walk through each section, copy what you need.</p>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex items-center bg-slate-100 rounded-lg p-0.5">
              <button onClick={() => setLanguage('en')}
                      className={`px-2.5 py-1 text-[11px] font-semibold rounded ${language === 'en' ? 'bg-white text-[#1e293b] shadow-sm' : 'text-slate-500'}`}>
                EN
              </button>
              <button onClick={() => setLanguage('fr')}
                      className={`px-2.5 py-1 text-[11px] font-semibold rounded ${language === 'fr' ? 'bg-white text-[#1e293b] shadow-sm' : 'text-slate-500'}`}>
                FR
              </button>
            </div>
            <button
              onClick={generate}
              disabled={loading}
              className="px-4 py-2 rounded-xl bg-[#4f46e5] text-white text-sm font-semibold
                         hover:bg-indigo-700 transition-colors disabled:opacity-50">
              {loading ? 'Generating…' : content ? 'Regenerate' : 'Generate Content'}
            </button>
          </div>
        </div>

        {content?.language && content.language !== language && (
          <p className="text-[11px] text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-1.5 mb-3">
            You&apos;re viewing content in {content.language.toUpperCase()}. Click Regenerate to switch to {language.toUpperCase()}.
          </p>
        )}

        {error && <p className="text-sm text-red-500 mb-4">{error}</p>}

        {loading && (
          <div className="bg-white rounded-2xl border border-slate-100 p-8 text-center">
            <p className="text-sm text-slate-500">Generating your content… this takes about 20 seconds.</p>
          </div>
        )}

        {!loading && content && (
          <div className="grid grid-cols-1 md:grid-cols-[200px_1fr] gap-4">

            {/* ── Step sidebar ──────────────────────────────────────────── */}
            <nav className="bg-white rounded-2xl border border-slate-100 p-2 self-start
                            md:sticky md:top-4">
              <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider px-2 py-1">Steps</p>
              {STEPS.map((s, i) => {
                const isActive = s.key === step
                return (
                  <button key={s.key} onClick={() => setStep(s.key)}
                          className={`w-full text-left px-2.5 py-2 rounded-lg flex items-start gap-2 transition-colors
                                      ${isActive ? 'bg-indigo-50' : 'hover:bg-slate-50'}`}>
                    <span className={`flex-shrink-0 w-5 h-5 rounded-full text-[10px] font-bold flex items-center justify-center
                                      ${isActive ? 'bg-[#4f46e5] text-white' : 'bg-slate-100 text-slate-500'}`}>
                      {i + 1}
                    </span>
                    <span className="min-w-0">
                      <span className={`block text-xs font-semibold ${isActive ? 'text-[#4f46e5]' : 'text-[#1e293b]'}`}>
                        {s.label}
                      </span>
                      <span className="block text-[10px] text-slate-400">{s.sublabel}</span>
                    </span>
                  </button>
                )
              })}
            </nav>

            {/* ── Active step pane ─────────────────────────────────────── */}
            <div className="flex flex-col gap-4 min-w-0">

              <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
                Step {stepIndex + 1} of {STEPS.length}
              </p>

              <StepGuidance step={step} />

            {/* ── Descriptions (per-platform) ─────────────────────────────── */}
            {step === 'description' && (
            <div className="bg-white rounded-2xl border border-slate-100 p-4">
              <div className="flex items-start justify-between mb-2 gap-3">
                <div>
                  <p className="text-sm font-semibold text-[#1e293b]">Business Description</p>
                  <p className="text-xs text-slate-400 mt-0.5">{activeDescHint}</p>
                </div>
                {activeDesc && (
                  <CopyButton onCopy={() => copy(activeDesc, `desc-${activeDescTab}`)}
                              copied={copied === `desc-${activeDescTab}`} />
                )}
              </div>
              <div className="flex gap-1 mb-3 border-b border-slate-100">
                {DESC_TABS.map(tab => (
                  <button key={tab.key}
                          onClick={() => setActiveDescTab(tab.key)}
                          className={`px-3 py-1.5 text-xs font-semibold border-b-2 transition-colors
                                      ${activeDescTab === tab.key
                                        ? 'border-[#4f46e5] text-[#4f46e5]'
                                        : 'border-transparent text-slate-500 hover:text-slate-700'}`}>
                    {tab.label}
                  </button>
                ))}
              </div>
              <EditableField
                contentId={content.id}
                itemKey={`description.${activeDescTab}`}
                value={activeDesc}
                isVerified={!!content.verified?.[`description.${activeDescTab}`]}
                multiline={true}
                rows={activeDescTab === 'gbp' ? 4 : 7}
                charLimit={activeDescTab === 'gbp' ? 700 : undefined}
                emptyPlaceholder="No content for this platform yet — click Regenerate."
                onChange={(newValue, newVerified) => {
                  setContent(prev => prev ? {
                    ...prev,
                    descriptions: { ...(prev.descriptions ?? {}), [activeDescTab]: newValue },
                    verified: newVerified ?? prev.verified,
                  } : prev)
                }}
              />
              {activeDescTab === 'gbp' && activeDesc && (
                <p className="text-[10px] text-slate-400 mt-2">{activeDesc.length} / 700 characters</p>
              )}
            </div>
            )}

            {/* ── Social Bio ──────────────────────────────────────────────── */}
            {step === 'social' && (
              <div className="bg-white rounded-2xl border border-slate-100 p-4">
                <div className="flex items-start justify-between mb-2 gap-3">
                  <div>
                    <p className="text-sm font-semibold text-[#1e293b]">Social Media Bio</p>
                    <p className="text-xs text-slate-400 mt-0.5">
                      {content.social_bio
                        ? `${content.social_bio.length}/150 characters`
                        : 'No bio yet — click Regenerate.'}
                    </p>
                  </div>
                  {content.social_bio && (
                    <CopyButton onCopy={() => copy(content.social_bio!, 'social_bio')}
                                copied={copied === 'social_bio'} />
                  )}
                </div>
                <EditableField
                  contentId={content.id}
                  itemKey="social_bio"
                  value={content.social_bio ?? ''}
                  isVerified={!!content.verified?.['social_bio']}
                  multiline={false}
                  charLimit={150}
                  emptyPlaceholder="No social bio generated yet — click Regenerate."
                  onChange={(newValue, newVerified) => {
                    setContent(prev => prev ? {
                      ...prev,
                      social_bio: newValue,
                      verified: newVerified ?? prev.verified,
                    } : prev)
                  }}
                />
              </div>
            )}

            {/* ── FAQ list + FAQ schema (combined into one step) ─────────── */}
            {step === 'faq' && content.faq && content.faq.length > 0 && (
              <div className="bg-white rounded-2xl border border-slate-100 p-4">
                <div className="flex items-start justify-between mb-2">
                  <div>
                    <p className="text-sm font-semibold text-[#1e293b]">FAQ Content</p>
                    <p className="text-xs text-slate-400 mt-0.5">
                      {content.faq.length} Q&amp;As — paste these on a /faq page
                      {content.paa_questions && content.paa_questions.length > 0 ? (
                        <span className="text-slate-400"> · grounded in {content.paa_questions.length} real Google searches</span>
                      ) : null}
                    </p>
                  </div>
                  <CopyButton
                    onCopy={() => copy(
                      content.faq!.map(f => `Q: ${f.question}\nA: ${f.answer}`).join('\n\n'),
                      'faq'
                    )}
                    copied={copied === 'faq'}
                  />
                </div>
                <div className="flex flex-col gap-3 mt-3">
                  {content.faq.map((item, i) => (
                    <EditableFaqItem
                      key={i}
                      contentId={content.id}
                      index={i}
                      item={item}
                      isVerified={!!content.verified?.[`faq.${i}`]}
                      onChange={(newItem, newVerified) => {
                        if (newItem === null) return
                        setContent(prev => {
                          if (!prev) return prev
                          const newFaq = [...(prev.faq ?? [])]
                          newFaq[i] = newItem
                          return { ...prev, faq: newFaq, verified: newVerified ?? prev.verified }
                        })
                      }}
                    />
                  ))}
                </div>
              </div>
            )}

            {step === 'faq' && content.faq_schema && (
              <div className="bg-white rounded-2xl border border-slate-100 p-4">
                <div className="flex items-start justify-between mb-2 gap-3">
                  <div>
                    <p className="text-sm font-semibold text-[#1e293b]">FAQ Schema (JSON-LD)</p>
                    <p className="text-xs text-slate-400 mt-0.5">Paste inside the &lt;head&gt; of your /faq page.</p>
                  </div>
                  <div className="flex gap-2 flex-shrink-0">
                    <a href="https://search.google.com/test/rich-results" target="_blank" rel="noopener noreferrer"
                       className="text-[10px] font-semibold px-2 py-1 rounded-lg border border-slate-200
                                  text-slate-500 hover:bg-slate-50 transition-colors whitespace-nowrap">
                      Test in Rich Results ↗
                    </a>
                    <CopyButton
                      onCopy={() => copy(wrapAsScriptTag(content.faq_schema!), 'faq_schema')}
                      copied={copied === 'faq_schema'}
                    />
                  </div>
                </div>
                <p className="text-xs text-slate-600 leading-relaxed whitespace-pre-wrap font-mono bg-slate-50 rounded-lg p-3 max-h-64 overflow-y-auto">
                  {content.faq_schema}
                </p>
                <p className="text-[10px] text-slate-400 mt-2">
                  Copy includes the &lt;script type=&quot;application/ld+json&quot;&gt; wrapper.
                </p>
              </div>
            )}

            {/* ── Schema Markup (LocalBusiness) ───────────────────────────── */}
            {step === 'schema' && content.schema_markup && (
              <div className="bg-white rounded-2xl border border-slate-100 p-4">
                <div className="flex items-start justify-between mb-2 gap-3">
                  <div>
                    <p className="text-sm font-semibold text-[#1e293b]">Schema Markup (JSON-LD)</p>
                    <p className="text-xs text-slate-400 mt-0.5">Paste inside the &lt;head&gt; tag of your homepage.</p>
                  </div>
                  <div className="flex gap-2 flex-shrink-0">
                    <a href="https://search.google.com/test/rich-results" target="_blank" rel="noopener noreferrer"
                       className="text-[10px] font-semibold px-2 py-1 rounded-lg border border-slate-200
                                  text-slate-500 hover:bg-slate-50 transition-colors whitespace-nowrap">
                      Test in Rich Results ↗
                    </a>
                    <CopyButton
                      onCopy={() => copy(wrapAsScriptTag(content.schema_markup!), 'schema')}
                      copied={copied === 'schema'}
                    />
                  </div>
                </div>

                {content.schema_missing_fields && content.schema_missing_fields.length > 0 && (
                  <div className="mb-3 p-3 rounded-xl bg-amber-50 border border-amber-200">
                    <p className="text-xs font-semibold text-amber-900 mb-1">
                      Complete your profile to qualify for Google rich results
                    </p>
                    <p className="text-[11px] text-amber-800 mb-2">
                      Missing: {content.schema_missing_fields.map(f => MISSING_FIELD_LABELS[f] ?? f).join(', ')}.
                    </p>
                    <Link href={`/${locale}/dashboard/settings`}
                          className="text-[11px] font-semibold text-amber-900 underline underline-offset-2 hover:text-amber-700">
                      Update profile →
                    </Link>
                  </div>
                )}

                <p className="text-xs text-slate-600 leading-relaxed whitespace-pre-wrap font-mono bg-slate-50 rounded-lg p-3 max-h-64 overflow-y-auto">
                  {content.schema_markup}
                </p>
                <p className="text-[10px] text-slate-400 mt-2">
                  Copy includes the &lt;script type=&quot;application/ld+json&quot;&gt; wrapper.
                </p>
              </div>
            )}

            {/* ── Validation warnings (only shown if non-empty) ─────────── */}
            {content.validation_warnings && content.validation_warnings.length > 0 && (
              <div className="bg-amber-50 border border-amber-200 rounded-2xl p-3">
                <p className="text-[11px] text-amber-900">
                  Note: {content.validation_warnings.map(w => w.replace(/_/g, ' ')).join(' · ')}.
                  Re-run if anything looks off.
                </p>
              </div>
            )}

            {/* ── Prev / Next step nav ─────────────────────────────────── */}
            <div className="flex items-center justify-between pt-2">
              <button onClick={goPrev} disabled={stepIndex === 0}
                      className="text-xs font-semibold text-slate-500 hover:text-slate-700
                                 disabled:opacity-30 disabled:cursor-not-allowed">
                ← Previous
              </button>
              <button onClick={goNext} disabled={stepIndex === STEPS.length - 1}
                      className="text-xs font-semibold text-[#4f46e5] hover:text-indigo-700
                                 disabled:opacity-30 disabled:cursor-not-allowed">
                {stepIndex < STEPS.length - 1 ? `Next: ${STEPS[stepIndex + 1].label} →` : 'Last step'}
              </button>
            </div>

            </div>{/* end step pane */}
          </div>
        )}

        {!loading && !content && (
          <div className="bg-white rounded-2xl border border-slate-100 p-8 text-center">
            <p className="text-sm font-semibold text-[#1e293b] mb-1">No content generated yet</p>
            <p className="text-xs text-slate-400">Click Generate Content to create optimized descriptions, FAQs, schema markup, and social bios.</p>
          </div>
        )}

      </div>
    </div>
  )
}

// ── Verify-and-edit primitives ───────────────────────────────────────────
// EditableField handles single-string content (descriptions, social bio):
//   view mode -> read-only text + Verify checkbox + Edit + Regenerate
//   edit mode -> textarea + Save / Cancel
//   regenerate mode -> notes textarea + Generate / Cancel
// EditableFaqItem wraps the same pattern for FAQ {question, answer} pairs.
//
// All three operations PATCH the parent `content` state through the
// `onChange` callback so the page stays in sync with the DB.

interface VerifiedToggleProps {
  verified: boolean
  onChange: (next: boolean) => void
  disabled?: boolean
}
function VerifiedToggle({ verified, onChange, disabled }: VerifiedToggleProps) {
  return (
    <label className={`flex items-center gap-1.5 text-[11px] font-semibold cursor-pointer
                       ${disabled ? 'opacity-50 cursor-not-allowed' : ''}
                       ${verified ? 'text-green-700' : 'text-slate-500'}`}>
      <input type="checkbox" checked={verified} disabled={disabled}
             onChange={e => onChange(e.target.checked)}
             className="h-3.5 w-3.5 rounded text-green-600 focus:ring-green-500" />
      {verified ? 'Verified' : 'Mark verified'}
    </label>
  )
}

interface EditableFieldProps {
  contentId: string | null | undefined
  itemKey: string                               // "description.website" | "social_bio" | etc
  value: string
  isVerified: boolean
  multiline?: boolean
  rows?: number
  charLimit?: number                            // shows "n/limit chars" counter
  onChange: (newValue: string, newVerified?: Record<string, boolean>) => void
  emptyPlaceholder?: string
}

function EditableField({
  contentId, itemKey, value, isVerified,
  multiline = true, rows = 6, charLimit,
  onChange, emptyPlaceholder = 'No content for this section yet.',
}: EditableFieldProps) {
  const [mode, setMode] = useState<'view' | 'edit' | 'regen'>('view')
  const [draft, setDraft] = useState(value)
  const [notes, setNotes] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  // Sync draft when external value changes (regenerate result, step switch, etc.)
  useEffect(() => { setDraft(value); setError('') }, [value, itemKey])

  // Legacy content rows have no id -- inline editing is unavailable.
  if (!contentId) {
    return (
      <p className="text-xs text-slate-600 leading-relaxed whitespace-pre-wrap min-h-[4rem]">
        {value || <span className="text-slate-400 italic">{emptyPlaceholder}</span>}
      </p>
    )
  }

  async function handleSave() {
    setBusy(true); setError('')
    try {
      await patchContent(contentId!, { [itemKey]: draft })
      onChange(draft)
      setMode('view')
    } catch {
      setError('Save failed')
    } finally { setBusy(false) }
  }

  async function handleVerify(next: boolean) {
    if (!value) return
    setBusy(true); setError('')
    try {
      const res = await verifyContentItem(contentId!, itemKey, next)
      onChange(value, res.verified)
    } catch {
      setError('Verify failed')
    } finally { setBusy(false) }
  }

  async function handleRegenerate() {
    setBusy(true); setError('')
    try {
      const res = await regenerateContentItem(contentId!, itemKey, notes)
      if (typeof res.value === 'string') {
        onChange(res.value, res.verified)
      }
      setNotes('')
      setMode('view')
    } catch {
      setError('Regenerate failed -- try again or simplify your notes.')
    } finally { setBusy(false) }
  }

  return (
    <div className="flex flex-col gap-2">
      {/* Action bar */}
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <VerifiedToggle verified={isVerified} onChange={handleVerify} disabled={busy || !value} />
        <div className="flex items-center gap-1">
          {mode === 'view' && value && (
            <>
              <button onClick={() => setMode('edit')} disabled={busy}
                      className="text-[11px] font-semibold text-slate-600 hover:text-[#4f46e5]
                                 px-2 py-1 rounded-lg hover:bg-slate-50 transition-colors">
                Edit
              </button>
              <button onClick={() => setMode('regen')} disabled={busy}
                      className="text-[11px] font-semibold text-slate-600 hover:text-[#4f46e5]
                                 px-2 py-1 rounded-lg hover:bg-slate-50 transition-colors">
                Regenerate
              </button>
            </>
          )}
        </div>
      </div>

      {/* Body */}
      {mode === 'view' && (
        <p className="text-xs text-slate-600 leading-relaxed whitespace-pre-wrap min-h-[4rem]">
          {value || <span className="text-slate-400 italic">{emptyPlaceholder}</span>}
        </p>
      )}

      {mode === 'edit' && (
        <div>
          {multiline ? (
            <textarea value={draft} onChange={e => setDraft(e.target.value)} rows={rows}
                      className="w-full text-xs text-slate-700 leading-relaxed border border-slate-200 rounded-xl px-3 py-2
                                 focus:outline-none focus:border-[#4f46e5] resize-y" />
          ) : (
            <input type="text" value={draft} onChange={e => setDraft(e.target.value)}
                   className="w-full text-xs text-slate-700 border border-slate-200 rounded-xl px-3 py-2
                              focus:outline-none focus:border-[#4f46e5]" />
          )}
          <div className="flex items-center justify-between mt-2 gap-2">
            <span className="text-[10px] text-slate-400">
              {charLimit ? `${draft.length} / ${charLimit} chars` : `${draft.length} chars`}
            </span>
            <div className="flex gap-1">
              <button onClick={() => { setDraft(value); setMode('view'); setError('') }}
                      disabled={busy}
                      className="text-[11px] font-semibold text-slate-500 hover:text-slate-700 px-2 py-1 rounded-lg hover:bg-slate-50">
                Cancel
              </button>
              <button onClick={handleSave} disabled={busy || draft === value}
                      className="text-[11px] font-semibold text-white bg-[#4f46e5] hover:bg-indigo-700 px-3 py-1 rounded-lg disabled:opacity-50">
                {busy ? '…' : 'Save'}
              </button>
            </div>
          </div>
        </div>
      )}

      {mode === 'regen' && (
        <div className="bg-slate-50 border border-slate-200 rounded-xl p-3">
          <p className="text-[11px] font-semibold text-slate-700 mb-2">
            What should change? (optional — leave blank for a fresh take)
          </p>
          <textarea value={notes} onChange={e => setNotes(e.target.value)} rows={3}
                    placeholder="e.g. make it shorter; remove the part about parking; mention free consultations"
                    className="w-full text-xs text-slate-700 border border-slate-200 rounded-lg px-3 py-2
                               focus:outline-none focus:border-[#4f46e5] resize-y" />
          <div className="flex items-center justify-end gap-1 mt-2">
            <button onClick={() => { setNotes(''); setMode('view'); setError('') }} disabled={busy}
                    className="text-[11px] font-semibold text-slate-500 hover:text-slate-700 px-2 py-1 rounded-lg hover:bg-slate-50">
              Cancel
            </button>
            <button onClick={handleRegenerate} disabled={busy}
                    className="text-[11px] font-semibold text-white bg-[#4f46e5] hover:bg-indigo-700 px-3 py-1 rounded-lg disabled:opacity-50">
              {busy ? 'Regenerating…' : 'Regenerate'}
            </button>
          </div>
        </div>
      )}

      {error && <p className="text-[11px] text-red-600">{error}</p>}
    </div>
  )
}

interface EditableFaqItemProps {
  contentId: string | null | undefined
  index: number
  item: FaqItem
  isVerified: boolean
  onChange: (newItem: FaqItem | null, newVerified?: Record<string, boolean>) => void
}

function EditableFaqItem({ contentId, index, item, isVerified, onChange }: EditableFaqItemProps) {
  const [mode, setMode] = useState<'view' | 'edit' | 'regen'>('view')
  const [draftQ, setDraftQ] = useState(item.question)
  const [draftA, setDraftA] = useState(item.answer)
  const [notes, setNotes] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => { setDraftQ(item.question); setDraftA(item.answer); setError('') }, [item.question, item.answer])

  if (!contentId) {
    return (
      <div className="border-l-2 border-indigo-100 pl-3">
        <p className="text-xs font-semibold text-[#1e293b]">{item.question}</p>
        <p className="text-xs text-slate-500 mt-0.5">{item.answer}</p>
      </div>
    )
  }

  async function handleSave() {
    setBusy(true); setError('')
    try {
      const updates: Record<string, string> = {}
      if (draftQ !== item.question) updates[`faq.${index}.question`] = draftQ
      if (draftA !== item.answer)   updates[`faq.${index}.answer`]   = draftA
      if (Object.keys(updates).length) await patchContent(contentId!, updates)
      onChange({ question: draftQ, answer: draftA })
      setMode('view')
    } catch {
      setError('Save failed')
    } finally { setBusy(false) }
  }

  async function handleVerify(next: boolean) {
    setBusy(true); setError('')
    try {
      const res = await verifyContentItem(contentId!, `faq.${index}`, next)
      onChange(item, res.verified)
    } catch {
      setError('Verify failed')
    } finally { setBusy(false) }
  }

  async function handleRegenerate() {
    setBusy(true); setError('')
    try {
      const res = await regenerateContentItem(contentId!, `faq.${index}`, notes)
      if (typeof res.value === 'object' && res.value && 'question' in res.value) {
        onChange(res.value as FaqItem, res.verified)
      }
      setNotes('')
      setMode('view')
    } catch {
      setError('Regenerate failed')
    } finally { setBusy(false) }
  }

  return (
    <div className={`border-l-2 ${isVerified ? 'border-green-300' : 'border-indigo-100'} pl-3`}>
      <div className="flex items-start justify-between gap-2 mb-1 flex-wrap">
        <span className="text-[10px] font-semibold text-slate-400">Q{index + 1}</span>
        <div className="flex items-center gap-1">
          <VerifiedToggle verified={isVerified} onChange={handleVerify} disabled={busy} />
          {mode === 'view' && (
            <>
              <button onClick={() => setMode('edit')} disabled={busy}
                      className="text-[10px] font-semibold text-slate-500 hover:text-[#4f46e5] px-1.5 py-0.5 rounded hover:bg-slate-50">
                Edit
              </button>
              <button onClick={() => setMode('regen')} disabled={busy}
                      className="text-[10px] font-semibold text-slate-500 hover:text-[#4f46e5] px-1.5 py-0.5 rounded hover:bg-slate-50">
                Regen
              </button>
            </>
          )}
        </div>
      </div>

      {mode === 'view' && (
        <>
          <p className="text-xs font-semibold text-[#1e293b]">{item.question}</p>
          <p className="text-xs text-slate-500 mt-0.5">{item.answer}</p>
        </>
      )}

      {mode === 'edit' && (
        <div className="flex flex-col gap-2 mt-1">
          <input type="text" value={draftQ} onChange={e => setDraftQ(e.target.value)}
                 className="w-full text-xs font-semibold text-[#1e293b] border border-slate-200 rounded-lg px-2 py-1.5
                            focus:outline-none focus:border-[#4f46e5]" />
          <textarea value={draftA} onChange={e => setDraftA(e.target.value)} rows={3}
                    className="w-full text-xs text-slate-700 border border-slate-200 rounded-lg px-2 py-1.5
                               focus:outline-none focus:border-[#4f46e5] resize-y" />
          <div className="flex justify-end gap-1">
            <button onClick={() => { setDraftQ(item.question); setDraftA(item.answer); setMode('view') }}
                    disabled={busy} className="text-[10px] font-semibold text-slate-500 px-2 py-0.5 rounded hover:bg-slate-50">
              Cancel
            </button>
            <button onClick={handleSave} disabled={busy || (draftQ === item.question && draftA === item.answer)}
                    className="text-[10px] font-semibold text-white bg-[#4f46e5] hover:bg-indigo-700 px-2 py-0.5 rounded disabled:opacity-50">
              {busy ? '…' : 'Save'}
            </button>
          </div>
        </div>
      )}

      {mode === 'regen' && (
        <div className="bg-slate-50 border border-slate-200 rounded-lg p-2 mt-1">
          <p className="text-[10px] text-slate-500 mb-1">What should change about this Q&amp;A?</p>
          <textarea value={notes} onChange={e => setNotes(e.target.value)} rows={2}
                    placeholder="e.g. The answer is wrong about pricing"
                    className="w-full text-xs text-slate-700 border border-slate-200 rounded px-2 py-1
                               focus:outline-none focus:border-[#4f46e5] resize-y" />
          <div className="flex justify-end gap-1 mt-1">
            <button onClick={() => { setNotes(''); setMode('view') }} disabled={busy}
                    className="text-[10px] font-semibold text-slate-500 px-2 py-0.5 rounded hover:bg-slate-50">
              Cancel
            </button>
            <button onClick={handleRegenerate} disabled={busy}
                    className="text-[10px] font-semibold text-white bg-[#4f46e5] hover:bg-indigo-700 px-2 py-0.5 rounded disabled:opacity-50">
              {busy ? '…' : 'Regenerate'}
            </button>
          </div>
        </div>
      )}

      {error && <p className="text-[10px] text-red-600 mt-1">{error}</p>}
    </div>
  )
}


function StepGuidance({ step }: { step: StepKey }) {
  const g = STEP_GUIDANCE[step]
  return (
    <div className="bg-indigo-50 border border-indigo-100 rounded-2xl p-4">
      <p className="text-xs font-extrabold text-indigo-900 mb-2">What this is for</p>
      <p className="text-xs text-slate-700 leading-relaxed mb-3">{g.whatItIs}</p>

      <div className="grid grid-cols-1 sm:grid-cols-[auto_1fr] gap-x-3 gap-y-2 text-xs">
        <span className="font-semibold text-indigo-900">📍 Where to paste</span>
        <span className="text-slate-700 leading-relaxed">{g.whereToPaste}</span>

        <span className="font-semibold text-indigo-900">💡 Why it matters</span>
        <span className="text-slate-700 leading-relaxed">{g.whyItMatters}</span>
      </div>
    </div>
  )
}

function CopyButton({ onCopy, copied }: { onCopy: () => void; copied: boolean }) {
  return (
    <button onClick={onCopy}
      className="text-[10px] font-semibold px-2 py-1 rounded-lg border border-slate-200
                 text-slate-500 hover:bg-slate-50 transition-colors flex-shrink-0">
      {copied ? '✓ Copied' : 'Copy'}
    </button>
  )
}

function ContentBlock({ title, subtitle, content, mono, onCopy, copied }: {
  title: string; subtitle: string; content: string
  mono?: boolean; onCopy: () => void; copied: boolean
}) {
  return (
    <div className="bg-white rounded-2xl border border-slate-100 p-4">
      <div className="flex items-start justify-between mb-2">
        <div>
          <p className="text-sm font-semibold text-[#1e293b]">{title}</p>
          <p className="text-xs text-slate-400 mt-0.5">{subtitle}</p>
        </div>
        <CopyButton onCopy={onCopy} copied={copied} />
      </div>
      <p className={`text-xs text-slate-600 leading-relaxed whitespace-pre-wrap ${mono ? 'font-mono bg-slate-50 rounded-lg p-3' : ''}`}>
        {content}
      </p>
    </div>
  )
}

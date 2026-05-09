'use client'

import { useState } from 'react'
import Link from 'next/link'
import { useLocale } from 'next-intl'
import { createClient } from '@/lib/supabase'

interface FaqItem { question: string; answer: string }

interface Descriptions {
  website?: string
  gbp?: string
  yelp?: string
}

// Tolerant of both the new shape (descriptions{}) and the legacy shape (description string)
interface Content {
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
              <p className="text-xs text-slate-600 leading-relaxed whitespace-pre-wrap min-h-[5rem]">
                {activeDesc || <span className="text-slate-400 italic">No content for this platform yet — click Regenerate.</span>}
              </p>
              {activeDescTab === 'gbp' && activeDesc && (
                <p className="text-[10px] text-slate-400 mt-2">{activeDesc.length} / 700 characters</p>
              )}
            </div>
            )}

            {/* ── Social Bio ──────────────────────────────────────────────── */}
            {step === 'social' && content.social_bio && (
              <ContentBlock
                title="Social Media Bio"
                subtitle={`For Instagram and Facebook — ${content.social_bio.length}/150 characters`}
                content={content.social_bio}
                onCopy={() => copy(content.social_bio!, 'social_bio')}
                copied={copied === 'social_bio'}
              />
            )}
            {step === 'social' && !content.social_bio && (
              <div className="bg-white rounded-2xl border border-slate-100 p-6 text-center">
                <p className="text-xs text-slate-400">No social bio generated yet — click Regenerate.</p>
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
                    <div key={i} className="border-l-2 border-indigo-100 pl-3">
                      <p className="text-xs font-semibold text-[#1e293b]">{item.question}</p>
                      <p className="text-xs text-slate-500 mt-0.5">{item.answer}</p>
                    </div>
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

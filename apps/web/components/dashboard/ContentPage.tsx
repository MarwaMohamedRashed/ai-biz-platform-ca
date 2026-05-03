'use client'

import { useState } from 'react'
import { createClient } from '@/lib/supabase'

interface FaqItem { question: string; answer: string }
interface Content {
  description: string
  faq: FaqItem[]
  schema_markup: string
  social_bio: string
}
interface Props {
  businessId: string | null
  initialContent: Content | null
}

export default function ContentPage({ businessId, initialContent }: Props) {
  const [content, setContent] = useState<Content | null>(initialContent)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [copied, setCopied] = useState<string | null>(null)

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
        body: JSON.stringify({ business_id: businessId }),
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

  return (
    <div className="flex-1 overflow-y-auto px-6 py-6">
      <div className="max-w-2xl">

        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-lg font-extrabold text-[#1e293b]">AI Content Generator</h1>
            <p className="text-xs text-slate-400 mt-0.5">Optimized content to improve your AI search visibility</p>
          </div>
          <button
            onClick={generate}
            disabled={loading}
            className="px-4 py-2 rounded-xl bg-[#4f46e5] text-white text-sm font-semibold
                       hover:bg-indigo-700 transition-colors disabled:opacity-50">
            {loading ? 'Generating…' : content ? 'Regenerate' : 'Generate Content'}
          </button>
        </div>

        {error && <p className="text-sm text-red-500 mb-4">{error}</p>}

        {loading && (
          <div className="bg-white rounded-2xl border border-slate-100 p-8 text-center">
            <p className="text-sm text-slate-500">Generating your content… this takes about 15 seconds.</p>
          </div>
        )}

        {!loading && content && (
          <div className="flex flex-col gap-4">

            <ContentBlock
              title="Business Description"
              subtitle="Add this to your website, Google profile, and directory listings"
              content={content.description}
              onCopy={() => copy(content.description, 'description')}
              copied={copied === 'description'}
            />

            <ContentBlock
              title="Social Media Bio"
              subtitle="For Instagram and Facebook — under 150 characters"
              content={content.social_bio}
              onCopy={() => copy(content.social_bio, 'social_bio')}
              copied={copied === 'social_bio'}
            />

            <div className="bg-white rounded-2xl border border-slate-100 p-4">
              <div className="flex items-start justify-between mb-2">
                <div>
                  <p className="text-sm font-semibold text-[#1e293b]">FAQ Content</p>
                  <p className="text-xs text-slate-400 mt-0.5">Add these Q&As to your website FAQ page</p>
                </div>
                <CopyButton onCopy={() => copy(content.faq.map(f => `Q: ${f.question}\nA: ${f.answer}`).join('\n\n'), 'faq')} copied={copied === 'faq'} />
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

            <ContentBlock
              title="Schema Markup (JSON-LD)"
              subtitle="Paste this into your website's <head> tag"
              content={content.schema_markup}
              mono
              onCopy={() => copy(content.schema_markup, 'schema')}
              copied={copied === 'schema'}
            />

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
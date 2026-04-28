'use client'
import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { createClient } from '@/lib/supabase'
import { useTranslations, useLocale } from 'next-intl'

type ReviewResponse = {
  id: string
  ai_draft: string | null
  final_response: string | null
  status: string
}

type Review = {
  id: string
  author: string | null
  rating: number | null
  text: string | null
  review_date: string | null
  status: 'pending' | 'responded' | 'ignored'
  review_responses: ReviewResponse[] | null
}

interface Props {
  review: Review
  onClose: () => void
}

function Stars({ rating }: { rating: number }) {
  return (
    <div className="flex gap-0.5">
      {[1, 2, 3, 4, 5].map(i => (
        <span key={i} className={`text-base ${i <= rating ? 'text-amber-400' : 'text-slate-200'}`}>★</span>
      ))}
    </div>
  )
}

const STATUS_COLORS: Record<string, string> = {
  pending:   'bg-amber-100 text-amber-700',
  responded: 'bg-green-100 text-green-700',
  ignored:   'bg-slate-100 text-slate-500',
}

export default function ReviewDetail({ review, onClose }: Props) {
  const t = useTranslations('dashboard.reviews')
  const locale = useLocale()
  const existingResponse = review.review_responses?.[0]?.final_response ?? ''
  const [reply, setReply] = useState(existingResponse)
  const router = useRouter()
  const [aiDraft, setAiDraft]           = useState<string | null>(review.review_responses?.[0]?.ai_draft ?? null)
  const [draftLoading, setDraftLoading] = useState(false)
  const [instructions, setInstructions] = useState('')
  const [regenLoading, setRegenLoading] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  
  async function apiCall(path: string, body: object) {
    const { data: { session } } = await createClient().auth.getSession()
    const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}${path}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${session?.access_token}`,
      },
      body: JSON.stringify(body),
    })
    return res.json()
  }

  useEffect(() => {
    if (review.status !== 'pending' || aiDraft) return
    setDraftLoading(true)
    apiCall('/api/v1/reviews/generate-response', { review_id: review.id })
      .then(data => {
        if (data.ai_draft) {
          setAiDraft(data.ai_draft)
          setReply(data.ai_draft)
        }
      })
      .catch(() => setAiDraft(null))
      .finally(() => setDraftLoading(false))
  }, [review.id])

  async function handleRegenerate() {
    if (!instructions.trim()) return
    setRegenLoading(true)
    try {
      const data = await apiCall('/api/v1/reviews/regenerate-response', {
        review_id: review.id,
        instructions,
      })
      if (data?.ai_draft) {
        setAiDraft(data.ai_draft)
        setReply(data.ai_draft)
        setInstructions('')
      }
    } catch {
      // network error — keep existing draft
    } finally {
      setRegenLoading(false)
    }
  }
  async function handleApprove() {
    if (!reply.trim()) return
    setIsSubmitting(true)
    await apiCall(`/api/v1/reviews/responses/${review.id}/approve`, {
      review_id: review.id,
      final_response: reply,
    })
    setIsSubmitting(false)
    router.refresh()
    onClose()
  }

  async function handleIgnore() {
    const supabase = createClient()
    await supabase.from('reviews').update({ status: 'ignored' }).eq('id', review.id)
    router.refresh()
    onClose()
  }
  const initial = (review.author ?? '?')[0].toUpperCase()

  function formatDate(dateStr: string) {
    return new Date(dateStr).toLocaleDateString(
      locale === 'fr' ? 'fr-CA' : 'en-CA',
      { year: 'numeric', month: 'long', day: 'numeric' }
    )
  }

  return (
    <>
      {/* Backdrop — mobile only */}
      <div
        className="fixed inset-0 bg-black/30 z-40 md:hidden"
        onClick={onClose}
      />

      {/* Panel */}
      <div className="fixed inset-0 z-50 flex flex-col bg-white
                      md:inset-auto md:right-0 md:top-0 md:bottom-0 md:w-[400px]
                      md:border-l md:border-slate-200 md:shadow-xl">

        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3
                        border-b border-slate-100 flex-shrink-0">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-full bg-indigo-100 flex items-center justify-center
                            text-xs font-bold text-[#4f46e5]">
              {initial}
            </div>
            <div>
              <p className="text-sm font-semibold text-[#1e293b]">
                {review.author ?? t('anonymous')}
              </p>
              {review.review_date && (
                <p className="text-[10px] text-slate-400">{formatDate(review.review_date)}</p>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${STATUS_COLORS[review.status]}`}>
              {t(`statusBadge.${review.status}`)}
            </span>
            <button onClick={onClose}
              className="text-slate-400 hover:text-slate-600 transition-colors p-1">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <line x1="18" y1="6" x2="6" y2="18" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                <line x1="6" y1="6" x2="18" y2="18" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
              </svg>
            </button>
          </div>
        </div>

        {/* Scrollable body */}
        <div className="flex-1 overflow-y-auto px-4 py-4 flex flex-col gap-4">

          {/* Stars + review text */}
          <div className="bg-slate-50 rounded-2xl p-4 flex flex-col gap-2">
            {review.rating && <Stars rating={review.rating} />}
            {review.text && (
              <p className="text-sm text-slate-700 leading-relaxed">{review.text}</p>
            )}
          </div>

          {/* AI draft */}
          <div>
            <p className="text-xs font-bold text-[#4f46e5] mb-2">✦ {t('detail.aiDraft')}</p>
            <div className="bg-indigo-50 rounded-xl px-3 py-2.5 border border-indigo-100">
              {draftLoading ? (
                <p className="text-xs text-indigo-400 italic">{t('detail.generating')}</p>
              ) : aiDraft ? (
                <p className="text-xs text-slate-700 leading-relaxed">{aiDraft}</p>
              ) : (
                <p className="text-xs text-slate-500 italic">{t('detail.aiDraftPlaceholder')}</p>
              )}
            </div>

            {/* Regenerate row — only when a draft exists */}
            {aiDraft && !draftLoading && review.status === 'pending' && (
              <div className="mt-2 flex gap-2">
                <input
                  type="text"
                  value={instructions}
                  onChange={e => setInstructions(e.target.value)}
                  placeholder={t('detail.regeneratePlaceholder')}
                  className="flex-1 px-3 py-1.5 border border-slate-200 rounded-lg text-xs
                            focus:outline-none focus:border-[#4f46e5] transition-colors"
                />
                <button
                  onClick={handleRegenerate}
                  disabled={regenLoading || !instructions.trim()}
                  className="px-3 py-1.5 bg-indigo-100 text-[#4f46e5] text-xs font-semibold
                            rounded-lg hover:bg-indigo-200 transition-colors disabled:opacity-50"
                >
                  {regenLoading ? '…' : t('detail.regenerate')}
                </button>
              </div>
            )}
          </div>

          {/* Reply box */}
          {review.status !== 'responded' ? (
            <div>
              <p className="text-xs font-bold text-[#1e293b] mb-2">{t('detail.yourReply')}</p>
              <textarea
                value={reply}
                onChange={e => setReply(e.target.value)}
                rows={5}
                placeholder={t('detail.replyPlaceholder')}
                className="w-full px-3 py-2.5 border-[1.5px] border-slate-200 rounded-xl
                           text-sm text-[#1e293b] bg-white resize-none
                           focus:outline-none focus:border-[#4f46e5] transition-colors"
              />
            </div>
          ) : (
            <div>
              <p className="text-xs font-bold text-green-600 mb-2">✓ {t('detail.alreadyResponded')}</p>
              <div className="bg-slate-50 rounded-xl px-3 py-2.5 border-l-2 border-[#4f46e5]">
                <p className="text-xs text-slate-600 leading-relaxed">{existingResponse}</p>
              </div>
            </div>
          )}
        </div>

        {/* Action buttons — only for pending */}
        {review.status === 'pending' && (
          <div className="flex gap-2 px-4 py-3 border-t border-slate-100 flex-shrink-0">
            <button
              onClick={handleApprove}
              disabled={!reply.trim() || isSubmitting}
              className="flex-1 py-2.5 bg-[#4f46e5] text-white text-xs font-semibold
                        rounded-xl hover:bg-indigo-700 transition-colors disabled:opacity-50"
            >
              {isSubmitting ? '…' : t('detail.approve')}
            </button>
            <button
              onClick={handleIgnore}
              className="px-4 py-2.5 bg-slate-100 text-slate-600 text-xs font-semibold
                        rounded-xl hover:bg-slate-200 transition-colors">
              {t('detail.ignore')}
            </button>
          </div>
        )}

      </div>
    </>
  )
}
'use client'

import { useState } from 'react'
import { useTranslations, useLocale } from 'next-intl'

type ReviewResponse = {
  id: string
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

type Tab = 'all' | 'pending' | 'responded' | 'ignored'

function Stars({ rating }: { rating: number }) {
  return (
    <div className="flex gap-0.5">
      {[1, 2, 3, 4, 5].map(i => (
        <span key={i} className={`text-sm ${i <= rating ? 'text-amber-400' : 'text-slate-200'}`}>★</span>
      ))}
    </div>
  )
}


const STATUS_COLORS: Record<string, string> = {
  pending:   'bg-amber-100 text-amber-700',
  responded: 'bg-green-100 text-green-700',
  ignored:   'bg-slate-100 text-slate-500',
}

export default function ReviewsList({ reviews }: { reviews: Review[] }) {
  const t = useTranslations('dashboard.reviews')
  const [activeTab, setActiveTab] = useState<Tab>('all')
  const locale = useLocale()

  function formatDate(dateStr: string) {
    const date = new Date(dateStr)
    const diffDays = Math.floor((Date.now() - date.getTime()) / 86400000)
    if (diffDays === 0) return t('dateToday')
    if (diffDays === 1) return t('dateYesterday')
    if (diffDays < 7) return t('dateDaysAgo', { count: diffDays })
    return date.toLocaleDateString(locale === 'fr' ? 'fr-CA' : 'en-CA', { month: 'short', day: 'numeric' })
  }

  const tabs: Tab[] = ['all', 'pending', 'responded', 'ignored']
  const counts: Record<Tab, number> = {
    all:       reviews.length,
    pending:   reviews.filter(r => r.status === 'pending').length,
    responded: reviews.filter(r => r.status === 'responded').length,
    ignored:   reviews.filter(r => r.status === 'ignored').length,
  }

  const filtered = activeTab === 'all'
    ? reviews
    : reviews.filter(r => r.status === activeTab)

  return (
    <div className="flex flex-col h-full">

      {/* Filter tabs */}
      <div className="flex gap-1 px-4 md:px-6 py-3 border-b border-slate-100 overflow-x-auto flex-shrink-0">
        {tabs.map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold whitespace-nowrap transition-colors
              ${activeTab === tab
                ? 'bg-[#4f46e5] text-white'
                : 'text-slate-500 hover:bg-slate-100'
              }`}
          >
            {t(`tabs.${tab}`)}
            <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-bold
              ${activeTab === tab ? 'bg-white/20 text-white' : 'bg-slate-100 text-slate-500'}`}>
              {counts[tab]}
            </span>
          </button>
        ))}
      </div>

      {/* List */}
      <div className="flex-1 overflow-y-auto px-4 md:px-6 py-4 space-y-3">
        {filtered.length === 0 && (
          <p className="text-sm text-slate-400 text-center py-12">{t('empty')}</p>
        )}

        {filtered.map(review => {
          const initial = (review.author ?? '?')[0].toUpperCase()
          return (
            <div key={review.id}
              className="bg-white rounded-2xl border border-slate-100 shadow-sm p-4 flex flex-col gap-2">

              {/* Author row */}
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2.5">
                  <div className="w-8 h-8 rounded-full bg-indigo-100 flex items-center justify-center
                                  text-xs font-bold text-[#4f46e5] flex-shrink-0">
                    {initial}
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-[#1e293b]">{review.author ?? 'Anonymous'}</p>
                    <p className="text-[10px] text-slate-400">
                      {review.review_date ? formatDate(review.review_date) : ''}
                    </p>
                  </div>
                </div>
                <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${STATUS_COLORS[review.status]}`}>
                  {t(`statusBadge.${review.status}`)}
                </span>
              </div>

              {/* Stars */}
              {review.rating && <Stars rating={review.rating} />}

              {/* Review text */}
              {review.text && (
                <p className="text-sm text-slate-600 leading-relaxed line-clamp-3">{review.text}</p>
              )}

              {/* Response preview */}
             {review.status === 'responded' && review.review_responses?.[0]?.final_response && (
                <div className="bg-slate-50 rounded-xl px-3 py-2 border-l-2 border-[#4f46e5]">
                  <p className="text-[10px] font-bold text-[#4f46e5] mb-1">Your response</p>
                  <p className="text-xs text-slate-500 line-clamp-2">
                    {review.review_responses[0].final_response}
                  </p>
                </div>
              )}

              {/* Action */}
              {review.status === 'pending' && (
                <button className="self-start text-xs font-semibold bg-[#4f46e5] text-white
                                   px-3 py-1.5 rounded-lg hover:bg-indigo-700 transition-colors">
                  {t('respond')}
                </button>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
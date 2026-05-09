/**
 * AI execution coach API client.
 * Calls POST /api/v1/aeo/recommendation-help.
 */
'use client'

import { createClient } from '@/lib/supabase'

export interface CoachMessage {
  role: 'user' | 'assistant'
  content: string
}

export interface CoachRecommendationContext {
  title: string
  description?: string
  action?: string
  pillar?: string
  url?: string | null
  impact?: number
}

export async function chatWithCoach(
  recommendation: CoachRecommendationContext,
  messages: CoachMessage[],
  newMessage: string,
  language: 'en' | 'fr' = 'en',
): Promise<{ reply: string }> {
  const { data: { session } } = await createClient().auth.getSession()
  const res = await fetch(
    `${process.env.NEXT_PUBLIC_API_URL}/api/v1/aeo/recommendation-help`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${session?.access_token}`,
      },
      body: JSON.stringify({
        recommendation,
        messages,
        new_message: newMessage,
        language,
      }),
    },
  )
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(`HTTP ${res.status}: ${text}`)
  }
  return res.json()
}

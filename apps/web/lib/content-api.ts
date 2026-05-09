/**
 * API client helpers for the verify-and-edit flow.
 * All three call into the backend endpoints added in router.py:
 *   PATCH /api/v1/aeo/content/{id}
 *   POST  /api/v1/aeo/content/{id}/verify
 *   POST  /api/v1/aeo/content/{id}/regenerate-item
 */
'use client'

import { createClient } from '@/lib/supabase'

async function authedFetch(path: string, init: RequestInit = {}) {
  const { data: { session } } = await createClient().auth.getSession()
  const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${session?.access_token}`,
      ...(init.headers ?? {}),
    },
  })
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(`HTTP ${res.status}: ${text}`)
  }
  return res.json()
}

export async function patchContent(
  contentId: string,
  updates: Record<string, string>,
): Promise<{
  id: string
  descriptions?: Record<string, string>
  social_bio?: string
  faq?: { question: string; answer: string }[]
  faq_schema?: string | null
}> {
  return authedFetch(`/api/v1/aeo/content/${contentId}`, {
    method: 'PATCH',
    body: JSON.stringify({ updates }),
  })
}

export async function verifyContentItem(
  contentId: string,
  key: string,
  verified: boolean,
): Promise<{ id: string; verified: Record<string, boolean> }> {
  return authedFetch(`/api/v1/aeo/content/${contentId}/verify`, {
    method: 'POST',
    body: JSON.stringify({ key, verified }),
  })
}

export async function regenerateContentItem(
  contentId: string,
  key: string,
  notes: string,
): Promise<{
  key: string
  value: string | { question: string; answer: string }
  verified: Record<string, boolean>
}> {
  return authedFetch(`/api/v1/aeo/content/${contentId}/regenerate-item`, {
    method: 'POST',
    body: JSON.stringify({ key, notes }),
  })
}

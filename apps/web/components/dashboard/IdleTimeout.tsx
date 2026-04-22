'use client'

import { useEffect, useRef } from 'react'
import { useRouter } from 'next/navigation'
import { useLocale } from 'next-intl'
import { createClient } from '@/lib/supabase'

const IDLE_MS = 1 * 60 * 60 * 1000  // 1 hour

export default function IdleTimeout() {
  const router = useRouter()
  const locale = useLocale()

  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    async function signOutUser() {
        const supabase = createClient()
        await supabase.auth.signOut()
        router.push(`/${locale}/login`)
    }

  function resetTimer() {
    if (timerRef.current) clearTimeout(timerRef.current)
     timerRef.current = setTimeout(signOutUser, IDLE_MS)
  }

  const events = ['mousemove', 'mousedown', 'keypress', 'scroll', 'touchstart']
  events.forEach(e => window.addEventListener(e, resetTimer))
  resetTimer()  // start the timer on mount

  return () => {
    if (timerRef.current) clearTimeout(timerRef.current)
    events.forEach(e => window.removeEventListener(e, resetTimer))
  }
 }, [locale, router])

  return null
}
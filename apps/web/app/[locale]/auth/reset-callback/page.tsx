'use client'

import { useEffect, useState, Suspense } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { useLocale } from 'next-intl'
import { createClient } from '@/lib/supabase'

function ResetCallbackInner() {
  const [error, setError] = useState('')
  const router = useRouter()
  const searchParams = useSearchParams()
  const locale = useLocale()

  useEffect(() => {
    async function exchange() {
      const tokenHash = searchParams.get('token_hash')
      const type = searchParams.get('type')

      if (!tokenHash || !type) {
        router.replace(`/${locale}/login`)
        return
      }

      const supabase = createClient()
      const { error } = await supabase.auth.verifyOtp({
        token_hash: tokenHash,
        type: type as 'recovery'
      })

      if (error) {
        setError(error.message)
        setTimeout(() => router.replace(`/${locale}/login`), 3000)
        return
      }

      router.replace(`/${locale}/reset-password`)
    }

    exchange()
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  if (error) {
    return (
      <div className="min-h-screen bg-[#f1f5f9] flex items-center justify-center p-4">
        <div className="bg-white rounded-2xl shadow-lg border border-slate-200 p-8 max-w-sm w-full text-center">
          <p className="text-red-600 text-sm">{error}</p>
          <p className="text-slate-500 text-sm mt-2">Redirecting to login…</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-[#f1f5f9] flex items-center justify-center">
      <div className="flex flex-col items-center gap-3">
        <div className="w-8 h-8 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin" />
        <p className="text-slate-500 text-sm">Verifying…</p>
      </div>
    </div>
  )
}

export default function ResetCallbackPage() {
  return (
    <Suspense>
      <ResetCallbackInner />
    </Suspense>
  )
}

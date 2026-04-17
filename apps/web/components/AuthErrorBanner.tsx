'use client'

import { useEffect, useState } from 'react'

export default function AuthErrorBanner() {
  const [message, setMessage] = useState('')

  useEffect(() => {
    const hash = window.location.hash
    if (!hash) return

    const params = new URLSearchParams(hash.slice(1)) // remove the #
    const errorCode = params.get('error_code')
    const description = params.get('error_description')

    if (errorCode === 'otp_expired') {
      setMessage('Your confirmation link has expired. Please sign up again.')
    } else if (description) {
      setMessage(decodeURIComponent(description.replace(/\+/g, ' ')))
    }
  }, [])

  if (!message) return null

  return (
    <div className="mb-4 px-3.5 py-2.5 rounded-[10px] bg-amber-50 border border-amber-200
                    text-xs text-amber-700 font-medium">
      {message}
    </div>
  )
}

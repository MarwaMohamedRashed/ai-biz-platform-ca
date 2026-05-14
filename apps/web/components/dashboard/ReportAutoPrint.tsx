'use client'

import { useEffect } from 'react'
import { useSearchParams } from 'next/navigation'

interface Props {
  filename: string
}

export default function ReportAutoPrint({ filename }: Props) {
  const params = useSearchParams()
  useEffect(() => {
    if (params.get('print') !== '1') return
    const previousTitle = document.title
    document.title = filename
    document.body.classList.add('printing-report-page')
    const t = setTimeout(() => window.print(), 350)
    function cleanup() {
      document.title = previousTitle
      document.body.classList.remove('printing-report-page')
      window.removeEventListener('afterprint', cleanup)
    }
    window.addEventListener('afterprint', cleanup)
    return () => {
      clearTimeout(t)
      cleanup()
    }
  }, [params, filename])
  return null
}

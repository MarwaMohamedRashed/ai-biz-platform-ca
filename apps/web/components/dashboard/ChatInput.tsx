'use client'

import { useState } from 'react'

export default function ChatInput() {
  const [value, setValue] = useState('')

  return (
    <div className="px-4 py-3 md:px-8 bg-white border-t border-slate-100">
      <div className="flex items-center gap-2 max-w-2xl mx-auto md:mx-0">

        {/* Mic button */}
        <button
          type="button"
          aria-label="Voice input"
          className="w-10 h-10 rounded-full bg-[#4f46e5] flex items-center justify-center
                     flex-shrink-0 hover:bg-indigo-700 transition-colors shadow-sm">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" fill="white"/>
            <path d="M19 10v2a7 7 0 0 1-14 0v-2M12 19v4M8 23h8"
              stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </button>

        {/* Text input */}
        <div className="flex-1 flex items-center bg-[#f8fafc] border border-slate-200
                        rounded-2xl px-4 py-2.5 focus-within:border-[#4f46e5] transition-colors">
          <input
            type="text"
            value={value}
            onChange={e => setValue(e.target.value)}
            placeholder="Ask anything or type a command…"
            className="flex-1 text-sm text-[#1e293b] bg-transparent outline-none
                       placeholder:text-slate-400" />

          {/* Camera button */}
          <button type="button" aria-label="Attach image"
            className="ml-2 text-[#f97316] hover:text-orange-600 transition-colors flex-shrink-0">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"
                stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              <circle cx="12" cy="13" r="4" stroke="currentColor" strokeWidth="2"/>
            </svg>
          </button>
        </div>

        {/* Send button */}
        <button
          type="button"
          aria-label="Send message"
          className="w-10 h-10 rounded-full bg-[#4f46e5] flex items-center justify-center
                     flex-shrink-0 hover:bg-indigo-700 transition-colors shadow-sm
                     disabled:opacity-40"
          disabled={!value.trim()}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="M22 2L11 13M22 2L15 22l-4-9-9-4 20-7z"
              stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </button>

      </div>
    </div>
  )
}

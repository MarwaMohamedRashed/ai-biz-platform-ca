'use client'
import { useEffect, useState } from 'react'
import { useTranslations, useLocale } from 'next-intl'
import { createClient } from '@/lib/supabase'


export default function SettingsPage() {
  const t = useTranslations('dashboard.settings')
  const locale = useLocale()


  const [tone_preference, setTone_preference] = useState<string>('')
  const [response_language, setResponse_language] = useState<string>('')
  const [business_description, setBusiness_description] = useState<string>('')
  const [response_length, setResponse_length] = useState<string>('')
  const [cta_custom_text, setCta_custom_text] = useState<string>('')
  const [auto_draft_enabled, setAuto_draft_enabled] = useState(false)
  const [cta_enabled, setCta_enabled] = useState(true)
  const [delay_acknowledgment, setDelay_acknowledgment] = useState(false)

 
 async function apiCall(path: string, body: object, method = 'POST') {
      const { data: { session } } = await createClient().auth.getSession()
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}${path}`, {
        method: method,
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${session?.access_token}`,
        },
        body: JSON.stringify(body),
      })
      return res.json()
    }
    async function apiFetch(path: string) {
        const { data: { session } } = await createClient().auth.getSession()
        const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}${path}`, {
            headers: { 'Authorization': `Bearer ${session?.access_token}` },
        })
        return res.json()
     }
    useEffect(() => {
      
      apiFetch('/api/v1/settings/')
        .then(data => {
         
          //Store the response in state: avgRating, reviewCount, strengths, weaknesses, summary, loading
          if (data.business_settings) {

            setTone_preference(data.business_settings.tone_preference || '')
            setResponse_language(data.business_settings.response_language || '')
            setBusiness_description(data.business_settings.business_description || '')
            setResponse_length(data.business_settings.response_length || '')
            setCta_custom_text(data.business_settings.cta_custom_text  || '')
            setAuto_draft_enabled(data.business_settings. auto_draft_enabled ?? false)
            setCta_enabled(data.business_settings.cta_enabled ?? true)
            setDelay_acknowledgment(data.business_settings.delay_acknowledgment ?? false)
          }
        
        })
        .catch(() => {
              setTone_preference('')
              setResponse_language('')
              setBusiness_description('')
              setResponse_length('')
              setCta_custom_text('')
              setAuto_draft_enabled(false)
              setCta_enabled(true)
              setDelay_acknowledgment(false)
        })
     
    }, [locale])

  return (
    <div className="flex-1 overflow-y-auto px-4 md:px-6 py-4">
        <form onSubmit={(e) => {
          e.preventDefault()
          apiCall('/api/v1/settings', { tone_preference, response_language, business_description, response_length, cta_custom_text, auto_draft_enabled, cta_enabled, delay_acknowledgment},'PUT')
        }}
        className="bg-white rounded-2xl border border-slate-100 shadow-sm p-4 mb-6">
          {/* Tone Preference */}
            <div className="mb-4">
                <label className="block text-xs font-semibold text-slate-600 mb-1">{t('toneLabel')}</label>
               <select
                value={tone_preference}
                onChange={(e) => setTone_preference(e.target.value)}
                className="w-full border-[1.5px] border-slate-200 rounded-xl px-3 py-2.5 text-sm text-[#1e293b] focus:outline-none focus:border-[#4f46e5] transition-colors"
              >
                <option value="casual">{t('toneOptions.casual')}</option>
                <option value="professional">{t('toneOptions.professional')}</option>
                <option value="playful">{t('toneOptions.playful')}</option>
              </select>
            </div>
            {/* Response Language */}
            <div className="mb-4">
                <label className="block text-xs font-semibold text-slate-600 mb-1">{t('languageLabel')}</label>
                <select
                  value={response_language}
                  onChange={(e) => setResponse_language(e.target.value)}
                  className="w-full border-[1.5px] border-slate-200 rounded-xl px-3 py-2.5 text-sm text-[#1e293b] focus:outline-none focus:border-[#4f46e5] transition-colors"
                >
                  <option value="match_reviewer">{t('languageOptions.match_reviewer')}</option>
                  <option value="english">{t('languageOptions.english')}</option>
                  <option value="french">{t('languageOptions.french')}</option>
              </select>
            </div>
            {/* Business Description */}
            <div className="mb-4">
                <label className="block text-xs font-semibold text-slate-600 mb-1">{t('descriptionLabel')}</label>
                <textarea value={business_description} onChange={(e) => setBusiness_description(e.target.value)}
                    className="w-full border-[1.5px] border-slate-200 rounded-xl px-3 py-2.5 text-sm text-[#1e293b] focus:outline-none focus:border-[#4f46e5] transition-colors" rows={4} />
            </div>
            {/* Response Length*/}
            <div className="mb-4">
                <label className="block text-xs font-semibold text-slate-600 mb-1">{t('lengthLabel')}</label>
                <select
                  value={response_length}
                  onChange={(e) => setResponse_length(e.target.value)}
                  className="w-full border-[1.5px] border-slate-200 rounded-xl px-3 py-2.5 text-sm text-[#1e293b] focus:outline-none focus:border-[#4f46e5] transition-colors"
                >
                  <option value="short">{t('lengthOptions.short')}</option>
                  <option value="medium">{t('lengthOptions.medium')}</option>
                  <option value="long">{t('lengthOptions.long')}</option>
                </select>  
                    
            </div>
            {/* CTA Custom Text */}
            <div className="mb-4">
                <label className="block text-xs font-semibold text-slate-600 mb-1">{t('ctaCustomLabel')}</label>
                <input type="text" value={cta_custom_text} onChange={(e) => setCta_custom_text(e.target.value)}
                    className="w-full border-[1.5px] border-slate-200 rounded-xl px-3 py-2.5 text-sm text-[#1e293b] focus:outline-none focus:border-[#4f46e5] transition-colors" />
                    <p className="text-[10px] text-slate-400 mt-1">{t('ctaCustomHint')}</p>
            </div>
            {/* Auto Draft Enabled */}
            <div className="mb-4">
                <div className="flex items-center">
                    <input type="checkbox" checked={auto_draft_enabled} onChange={(e) => setAuto_draft_enabled(e.target.checked)}
                        className="h-4 w-4 text-[#4f46e5] border-gray-300 rounded focus:ring-[#4f46e5]" />
                    <label className="ml-2 block text-xs font-semibold text-slate-600">{t('autoDraftLabel')}</label>
                </div>
                <p className="text-[10px] text-slate-400 mt-0.5 ml-6">{t('autoDraftHint')}</p>
            </div>
            {/* CTA Enabled */}
            <div className="mb-4">
                <div className="flex items-center">
                    <input type="checkbox" checked={cta_enabled} onChange={(e) => setCta_enabled(e.target.checked)}
                        className="h-4 w-4 text-[#4f46e5] border-gray-300 rounded focus:ring-[#4f46e5]" />
                    <label className="ml-2 block text-xs font-semibold text-slate-600">{t('ctaEnabledLabel')}</label>
                </div>
                <p className="text-[10px] text-slate-400 mt-0.5 ml-6">{t('ctaEnabledHint')}</p>
            </div>
            {/* Delay Acknowledgment */}
            <div className="mb-4">
                <div className="flex items-center">
                    <input type="checkbox" checked={delay_acknowledgment} onChange={(e) => setDelay_acknowledgment(e.target.checked)}
                        className="h-4 w-4 text-[#4f46e5] border-gray-300 rounded focus:ring-[#4f46e5]" />
                    <label className="ml-2 block text-xs font-semibold text-slate-600">{t('delayLabel')}</label>
                </div>
                <p className="text-[10px] text-slate-400 mt-0.5 ml-6">{t('delayHint')}</p>
            </div>
            <button type="submit" className="px-4 py-2.5 bg-[#4f46e5] text-white text-xs font-semibold rounded-xl hover:bg-indigo-700 transition-colors">{t('save')}</button>
        </form> 



    </div>
  )
}
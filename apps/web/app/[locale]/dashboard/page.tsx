import { createServerSupabaseClient } from '@/lib/supabase-server'
import ChatInput from '@/components/dashboard/ChatInput'

function getGreeting() {
  const hour = new Date().getHours()
  if (hour < 12) return 'Good morning'
  if (hour < 17) return 'Good afternoon'
  return 'Good evening'
}

export default async function DashboardPage() {
  const supabase = await createServerSupabaseClient()
  const { data: { user } } = await supabase.auth.getUser()

  const { data: profile } = await supabase
    .from('profiles')
    .select('full_name')
    .eq('id', user!.id)
    .single()

  const firstName = profile?.full_name?.split(' ')[0]
    || user!.email?.split('@')[0]
    || 'there'

  const initial = firstName[0].toUpperCase()
  const greeting = getGreeting()

  return (
    <div className="flex flex-col h-screen">

      {/* Mobile header */}
      <header className="md:hidden flex items-center justify-between px-4 py-3
                         bg-white border-b border-slate-100 flex-shrink-0">
        <div className="flex items-center gap-2">
          <svg width="28" height="28" viewBox="0 0 40 40" fill="none">
            <rect width="40" height="40" rx="12" fill="#4f46e5"/>
            <path d="M13 10 L13 28 L27 28" stroke="white" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"/>
            <circle cx="28" cy="13" r="4" fill="#f97316"/>
          </svg>
          <span className="text-base font-extrabold tracking-tight">
            <span className="text-[#4f46e5]">Leap</span><span className="text-[#f97316]">One</span>
          </span>
        </div>
        <div className="w-8 h-8 rounded-full bg-[#4f46e5] flex items-center justify-center
                        text-white text-xs font-bold">
          {initial}
        </div>
      </header>

      {/* Desktop page header */}
      <div className="hidden md:flex items-center justify-between px-8 py-5 flex-shrink-0">
        <h1 className="text-xl font-extrabold text-[#1e293b]">Chat</h1>
      </div>

      {/* Chat messages area */}
      <div className="flex-1 overflow-y-auto px-4 py-4 md:px-8 space-y-4">

        {/* AI greeting bubble */}
        <div className="flex gap-3">
          <div className="w-8 h-8 rounded-full bg-[#4f46e5] flex items-center justify-center flex-shrink-0 mt-0.5">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"
                stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </div>
          <div className="flex flex-col gap-3 max-w-lg">
            <div className="bg-white rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm border border-slate-100">
              <p className="text-sm text-[#1e293b]">
                {greeting}, <span className="font-semibold">{firstName}</span>! 👋 Here&apos;s what needs your attention today:
              </p>
            </div>

            {/* Reviews action card */}
            <div className="bg-white rounded-2xl border-l-[3px] border-l-[#f97316]
                            shadow-sm border border-slate-100 p-4">
              <div className="flex items-start justify-between mb-1.5">
                <span className="text-[10px] font-bold text-[#f97316] uppercase tracking-wider">
                  Google Reviews
                </span>
                <span className="bg-amber-100 text-amber-700 text-[10px] font-bold px-2 py-0.5 rounded-full">
                  3 pending
                </span>
              </div>
              <p className="text-sm font-semibold text-[#1e293b] mb-1">
                3 reviews need responses
              </p>
              <p className="text-xs text-slate-500 mb-3">
                Latest 2 hours ago — &quot;Great service but the parking was a bit tight…&quot;
              </p>
              <button className="text-xs font-semibold text-[#4f46e5] hover:underline">
                View reviews →
              </button>
            </div>

            {/* Bookings action card */}
            <div className="bg-white rounded-2xl border-l-[3px] border-l-[#4f46e5]
                            shadow-sm border border-slate-100 p-4">
              <div className="flex items-start justify-between mb-1.5">
                <span className="text-[10px] font-bold text-[#4f46e5] uppercase tracking-wider">
                  Appointments
                </span>
                <span className="bg-indigo-100 text-indigo-700 text-[10px] font-bold px-2 py-0.5 rounded-full">
                  Today
                </span>
              </div>
              <p className="text-sm font-semibold text-[#1e293b] mb-1">
                2 appointments today
              </p>
              <p className="text-xs text-slate-500 mb-3">
                Next: 2:00 PM — Sarah M. (Consultation)
              </p>
              <button className="text-xs font-semibold text-[#4f46e5] hover:underline">
                View schedule →
              </button>
            </div>

            {/* Follow-up bubble */}
            <div className="bg-white rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm border border-slate-100">
              <p className="text-sm text-slate-500">
                What would you like to do? I can draft review responses, check your schedule, or answer any questions.
              </p>
            </div>
          </div>
        </div>

      </div>

      {/* Chat input */}
      <ChatInput />

    </div>
  )
}

import { NextResponse } from 'next/server'
import { createClient } from '@supabase/supabase-js'
import { createServerSupabaseClient } from '@/lib/supabase-server'

// Server-side UPDATE for onboarding Step 2 extras. Same two-client auth
// model as the sibling Step 1 route: validate the user via the cookie-
// backed ssr client, then mutate through a service_role-backed client.
// Critically, the UPDATE is scoped by `business_id` AND `user_id` so the
// service_role bypass can't be abused to edit another user's business.

interface Body {
  business_id:       string
  services?:         string | null
  image_url?:        string | null
  price_range?:      string | null
  competitor_scope?: 'local' | 'country' | 'global'
  // ROI inputs (migration 022). Both nullable — fallbacks live in
  // apps/web/lib/roi.ts so missing values don't break the dashboard.
  avg_customer_value_cad?:       number | null
  monthly_new_online_customers?: number | null
}

export async function POST(req: Request) {
  let payload: Body
  try {
    payload = await req.json()
  } catch {
    return NextResponse.json({ error: 'Invalid JSON' }, { status: 400 })
  }

  if (!payload.business_id) {
    return NextResponse.json({ error: 'business_id is required' }, { status: 400 })
  }

  const sessionClient = await createServerSupabaseClient()
  const { data: { user }, error: authError } = await sessionClient.auth.getUser()
  if (authError || !user?.id) {
    return NextResponse.json({ error: 'Not authenticated' }, { status: 401 })
  }

  const serviceKey = process.env.SUPABASE_SERVICE_ROLE_KEY
  if (!serviceKey) {
    console.error('[api/onboarding/business/extras] SUPABASE_SERVICE_ROLE_KEY not set')
    return NextResponse.json({ error: 'Server misconfigured' }, { status: 500 })
  }

  const adminClient = createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    serviceKey,
    { auth: { persistSession: false, autoRefreshToken: false } },
  )

  // Sanity-clamp the numeric ROI inputs so junk values can't leak into
  // the formula. Anything non-finite or out-of-range falls back to null
  // and the dashboard picks up the vertical default instead.
  const avgValue = sanitizePositiveNumber(payload.avg_customer_value_cad, 1_000_000)
  const monthlyOnline = sanitizePositiveInt(payload.monthly_new_online_customers, 100_000)

  // Both filters matter: the user_id filter is the security boundary
  // (service_role bypasses RLS, so we enforce ownership in the WHERE clause).
  const { error: updateError } = await adminClient
    .from('businesses')
    .update({
      services:                     payload.services ?? null,
      image_url:                    payload.image_url ?? null,
      price_range:                  payload.price_range ?? null,
      competitor_scope:             payload.competitor_scope ?? 'local',
      avg_customer_value_cad:       avgValue,
      monthly_new_online_customers: monthlyOnline,
    })
    .eq('id', payload.business_id)
    .eq('user_id', user.id)

  if (updateError) {
    console.error('[api/onboarding/business/extras] UPDATE failed', updateError)
    return NextResponse.json(
      { error: updateError.message },
      { status: 500 },
    )
  }

  return NextResponse.json({ ok: true })
}

function sanitizePositiveNumber(value: unknown, max: number): number | null {
  if (value == null) return null
  const n = Number(value)
  if (!Number.isFinite(n) || n < 0 || n > max) return null
  return n
}

function sanitizePositiveInt(value: unknown, max: number): number | null {
  const n = sanitizePositiveNumber(value, max)
  return n == null ? null : Math.round(n)
}

import { NextResponse } from 'next/server'
import { createClient } from '@supabase/supabase-js'
import { createServerSupabaseClient } from '@/lib/supabase-server'

// Server-side INSERT for onboarding Step 1.
//
// Auth model (two clients):
//   1. sessionClient (cookie-backed @supabase/ssr) — used ONLY for
//      auth.getUser(). Round-trips to Supabase, so we can trust the
//      user.id we get back.
//   2. adminClient (service_role key) — does the actual INSERT, bypassing
//      RLS. user_id on the inserted row is forced to the verified user.id
//      from step 1, so a malicious browser request can't forge an INSERT
//      for someone else's account.
//
// Why service_role here: we spent hours proving the supabase-js + ssr
// stack will not reliably attach the user JWT to outgoing data calls
// from a server route on this project — getUser() validates via Supabase's
// auth API but the .from(...).insert(...) call kept producing RLS 42501
// even with global.headers.Authorization and auth.setSession() explicitly
// supplying the same token. Service_role is the documented pattern for
// trusted server mutations and matches what api/ (FastAPI) already does.

interface Body {
  name:           string
  type:           string
  country:        string
  city:           string
  province:       string
  website?:       string | null
  street_address?: string | null
  postal_code?:   string | null
  phone?:         string | null
}

export async function POST(req: Request) {
  let payload: Body
  try {
    payload = await req.json()
  } catch {
    return NextResponse.json({ error: 'Invalid JSON' }, { status: 400 })
  }

  if (!payload.name || !payload.type || !payload.city || !payload.province) {
    return NextResponse.json(
      { error: 'name, type, city, and province are required' },
      { status: 400 },
    )
  }

  const sessionClient = await createServerSupabaseClient()
  const { data: { user }, error: authError } = await sessionClient.auth.getUser()
  if (authError || !user?.id) {
    return NextResponse.json({ error: 'Not authenticated' }, { status: 401 })
  }

  const serviceKey = process.env.SUPABASE_SERVICE_ROLE_KEY
  if (!serviceKey) {
    console.error('[api/onboarding/business] SUPABASE_SERVICE_ROLE_KEY not set')
    return NextResponse.json({ error: 'Server misconfigured' }, { status: 500 })
  }

  const adminClient = createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    serviceKey,
    { auth: { persistSession: false, autoRefreshToken: false } },
  )

  const { data, error: insertError } = await adminClient
    .from('businesses')
    .insert({
      user_id:        user.id,
      name:           payload.name,
      type:           payload.type,
      country:        payload.country || 'Canada',
      city:           payload.city,
      province:       payload.province,
      website:        payload.website ?? null,
      street_address: payload.street_address ?? null,
      postal_code:    payload.postal_code ? payload.postal_code.toUpperCase() : null,
      phone:          payload.phone ?? null,
    })
    .select('id')
    .single()

  if (insertError || !data?.id) {
    console.error('[api/onboarding/business] INSERT failed', insertError)
    return NextResponse.json(
      { error: insertError?.message ?? 'Could not save business' },
      { status: 500 },
    )
  }

  return NextResponse.json({ id: data.id })
}

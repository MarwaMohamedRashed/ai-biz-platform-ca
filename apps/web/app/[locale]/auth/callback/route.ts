import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'
import { createServerClient } from '@supabase/ssr'

export async function GET(request: NextRequest) {
  const { searchParams, origin } = new URL(request.url)
  const code = searchParams.get('code')
  const locale = request.nextUrl.pathname.split('/')[1]

  if (code) {
    // Build the redirect response first so we can attach cookies to it
    const response = NextResponse.redirect(`${origin}/${locale}/dashboard`)

    const supabase = createServerClient(
      process.env.NEXT_PUBLIC_SUPABASE_URL!,
      process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
      {
        cookies: {
          // Read cookies from the incoming request
          getAll() {
            return request.cookies.getAll()
          },
          // Write session cookies directly onto the redirect response
          setAll(cookiesToSet) {
            cookiesToSet.forEach(({ name, value, options }) =>
              response.cookies.set(name, value, options)
            )
          }
        }
      }
    )

    const { error } = await supabase.auth.exchangeCodeForSession(code)

    if (!error) {
      return response  // redirect to dashboard WITH the session cookies attached
    }
  }

  // No code or exchange failed — send to login
  return NextResponse.redirect(`${origin}/${locale}/login`)
}

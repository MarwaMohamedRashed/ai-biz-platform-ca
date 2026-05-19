import { redirect } from 'next/navigation'
import { createServerSupabaseClient } from '@/lib/supabase-server'

// Localized home page. No marketing landing page exists yet, so we route
// based on auth state: signed-in owners go straight to the dashboard,
// everyone else to the login screen. Add a real marketing landing here
// post-launch (the placeholder <h1> was never meant to ship).
export default async function HomePage({
  params,
}: {
  params: Promise<{ locale: string }>
}) {
  const { locale } = await params
  const supabase = await createServerSupabaseClient()
  const { data: { user } } = await supabase.auth.getUser()
  redirect(user ? `/${locale}/dashboard` : `/${locale}/login`)
}

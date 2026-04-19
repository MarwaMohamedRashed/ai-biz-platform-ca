import { redirect } from 'next/navigation'
import { getTranslations } from 'next-intl/server'
import { createServerSupabaseClient } from '@/lib/supabase-server'
import ProfileForm from '@/components/dashboard/ProfileForm'

export default async function ProfilePage() {
  const supabase = await createServerSupabaseClient()
  const { data: { user } } = await supabase.auth.getUser()
 
  if (!user) redirect('/login')

  const avatarUrl = user.user_metadata?.avatar_url ?? ''

  const name = user.user_metadata?.full_name
  || `${user.user_metadata?.first_name ?? ''} ${user.user_metadata?.last_name ?? ''}`.trim()
  const email = user.email ?? ''

  const t = await getTranslations('dashboard.profile')

  return (
    <div className="flex-1 overflow-y-auto p-6 md:p-8">
      <div className="max-w-md">

        <div className="mb-8">
          <h1 className="text-xl font-semibold text-[#1e293b]">{t('heading')}</h1>
          <p className="text-sm text-slate-500 mt-1">{t('subtitle')}</p>
        </div>

        <ProfileForm name={name} email={email} avatarUrl={avatarUrl}/>

      </div>
    </div>
  )
}
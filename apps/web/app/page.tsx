import { redirect } from 'next/navigation'

// Fallback for the bare root `/` route. In normal use, the next-intl
// middleware (proxy.ts) rewrites `/` to `/en` (or `/fr` if the visitor's
// Accept-Language header prefers it), so this file rarely renders. We
// keep it as a guaranteed-correct redirect to the default locale in
// case the middleware ever short-circuits.
export default function Root() {
  redirect('/en')
}

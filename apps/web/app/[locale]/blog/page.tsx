import Link from 'next/link'
import { getLocale } from 'next-intl/server'
import { getAllPosts } from '@/lib/blog'

export const metadata = {
  title: 'LeapOne Blog — AEO insights for Canadian small businesses',
  description: 'Practical AEO playbooks, industry-specific tactics, and honest takes on AI search visibility for Canadian SMBs.',
}

export default async function BlogIndex() {
  const locale = (await getLocale()) as 'en' | 'fr'
  const posts = await getAllPosts(locale)

  return (
    <div className="min-h-screen bg-[#f8fafc]">
      <div className="max-w-3xl mx-auto px-6 py-12 md:py-16">

        <header className="mb-10">
          <Link href={`/${locale}`}
            className="text-xs font-semibold text-slate-500 hover:text-slate-700">
            ← {locale === 'fr' ? "Retour à l'accueil" : 'Back to home'}
          </Link>
          <h1 className="text-3xl md:text-4xl font-extrabold text-[#1e293b] mt-3">
            {locale === 'fr' ? 'Le blogue LeapOne' : 'The LeapOne Blog'}
          </h1>
          <p className="text-sm text-slate-600 mt-2">
            {locale === 'fr'
              ? "Tactiques AEO concrètes, guides par secteur, et opinions honnêtes sur la visibilité IA pour les PME canadiennes."
              : 'Practical AEO playbooks, industry-specific tactics, and honest takes on AI search visibility for Canadian SMBs.'}
          </p>
        </header>

        {posts.length === 0 ? (
          <p className="text-sm text-slate-500">
            {locale === 'fr' ? 'Aucun article pour le moment.' : 'No posts yet.'}
          </p>
        ) : (
          <div className="flex flex-col gap-6">
            {posts.map(p => (
              <article key={p.slug}
                className="bg-white border border-slate-100 rounded-2xl p-5 hover:shadow-sm transition-shadow">
                <Link href={`/${locale}/blog/${p.slug}`}>
                  <h2 className="text-lg md:text-xl font-bold text-[#1e293b] hover:text-[#4f46e5] transition-colors">
                    {p.title}
                  </h2>
                </Link>
                <div className="flex items-center gap-3 mt-1 text-[11px] text-slate-500">
                  <time dateTime={p.date}>
                    {new Date(p.date).toLocaleDateString(locale === 'fr' ? 'fr-CA' : 'en-CA', {
                      year: 'numeric', month: 'long', day: 'numeric',
                    })}
                  </time>
                  <span>·</span>
                  <span>{p.author}</span>
                </div>
                <p className="text-sm text-slate-600 mt-3 leading-relaxed">{p.description}</p>
                {p.tags.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 mt-3">
                    {p.tags.map(tag => (
                      <span key={tag}
                        className="text-[10px] font-semibold text-slate-500 bg-slate-100 px-2 py-0.5 rounded-full">
                        {tag}
                      </span>
                    ))}
                  </div>
                )}
                <Link href={`/${locale}/blog/${p.slug}`}
                  className="inline-block mt-3 text-xs font-semibold text-[#4f46e5] hover:underline">
                  {locale === 'fr' ? 'Lire l’article' : 'Read post'} →
                </Link>
              </article>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

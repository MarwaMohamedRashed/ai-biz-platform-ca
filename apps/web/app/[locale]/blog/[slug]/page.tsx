import Link from 'next/link'
import { notFound } from 'next/navigation'
import { getLocale } from 'next-intl/server'
import { getPost, getAllSlugs } from '@/lib/blog'

interface Props {
  params: Promise<{ locale: string; slug: string }>
}

// Pre-render every post at build time
export async function generateStaticParams() {
  const all = await getAllSlugs()
  return all.map(({ locale, slug }) => ({ locale, slug }))
}

export async function generateMetadata({ params }: Props) {
  const { locale, slug } = await params
  const post = await getPost(locale as 'en' | 'fr', slug)
  if (!post) return {}
  return {
    title: `${post.title} — LeapOne`,
    description: post.description,
    openGraph: {
      title: post.title,
      description: post.description,
      type: 'article',
      publishedTime: post.date,
      authors: [post.author],
      locale: locale === 'fr' ? 'fr_CA' : 'en_CA',
    },
    alternates: {
      canonical: `https://leapone.ca/${locale}/blog/${slug}`,
    },
  }
}

export default async function BlogPostPage({ params }: Props) {
  const { locale, slug } = await params
  const localeTyped = (locale === 'fr' ? 'fr' : 'en') as 'en' | 'fr'
  const post = await getPost(localeTyped, slug)
  if (!post) notFound()

  // Schema.org BlogPosting JSON-LD -- the same structured-data pattern we tell
  // customers to use. We use it on our own blog because we eat our own dog food.
  const jsonLd = {
    '@context': 'https://schema.org',
    '@type': 'BlogPosting',
    headline: post.title,
    description: post.description,
    datePublished: post.date,
    dateModified: post.date,
    author: { '@type': 'Person', name: post.author },
    publisher: {
      '@type': 'Organization',
      name: 'LeapOne',
      logo: { '@type': 'ImageObject', url: 'https://leapone.ca/leapone-icon.png' },
    },
    mainEntityOfPage: {
      '@type': 'WebPage',
      '@id': `https://leapone.ca/${localeTyped}/blog/${slug}`,
    },
    inLanguage: localeTyped === 'fr' ? 'fr-CA' : 'en-CA',
    keywords: post.tags.join(', '),
  }

  return (
    <div className="min-h-screen bg-[#f8fafc]">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd, null, 2) }}
      />

      <article className="max-w-2xl mx-auto px-6 py-12 md:py-16">
        <Link href={`/${localeTyped}/blog`}
          className="text-xs font-semibold text-slate-500 hover:text-slate-700">
          ← {localeTyped === 'fr' ? 'Tous les articles' : 'All posts'}
        </Link>

        <header className="mt-4 mb-8">
          <h1 className="text-3xl md:text-4xl font-extrabold text-[#1e293b] leading-tight">
            {post.title}
          </h1>
          <div className="flex items-center gap-3 mt-3 text-[11px] text-slate-500">
            <time dateTime={post.date}>
              {new Date(post.date).toLocaleDateString(localeTyped === 'fr' ? 'fr-CA' : 'en-CA', {
                year: 'numeric', month: 'long', day: 'numeric',
              })}
            </time>
            <span>·</span>
            <span>{post.author}</span>
          </div>
        </header>

        <div className="blog-body"
             dangerouslySetInnerHTML={{ __html: post.bodyHtml }}
        />

        {post.tags.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mt-8 pt-6 border-t border-slate-100">
            {post.tags.map(tag => (
              <span key={tag}
                className="text-[10px] font-semibold text-slate-500 bg-slate-100 px-2 py-0.5 rounded-full">
                {tag}
              </span>
            ))}
          </div>
        )}

        <div className="mt-10 p-5 bg-white border border-slate-100 rounded-2xl">
          <p className="text-sm font-semibold text-[#1e293b]">
            {localeTyped === 'fr'
              ? 'Voyez si les moteurs IA peuvent trouver votre entreprise'
              : 'See if AI search engines can find your business'}
          </p>
          <p className="text-xs text-slate-600 mt-1">
            {localeTyped === 'fr'
              ? 'Audit gratuit. Pas de carte de crédit.'
              : 'Free audit. No credit card.'}
          </p>
          <Link href={`/${localeTyped}/signup`}
            className="inline-block mt-3 text-xs font-semibold text-white bg-[#4f46e5] px-4 py-2 rounded-xl hover:bg-indigo-700 transition-colors">
            {localeTyped === 'fr' ? 'Commencer →' : 'Get started →'}
          </Link>
        </div>
      </article>
    </div>
  )
}

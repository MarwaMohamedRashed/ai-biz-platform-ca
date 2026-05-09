import type { MetadataRoute } from 'next'
import { getAllPosts } from '@/lib/blog'

const SITE = 'https://leapone.ca'

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const enPosts = await getAllPosts('en')
  const frPosts = await getAllPosts('fr')

  const staticEntries: MetadataRoute.Sitemap = [
    { url: `${SITE}/en`,             lastModified: new Date(), changeFrequency: 'weekly',  priority: 1.0 },
    { url: `${SITE}/fr`,             lastModified: new Date(), changeFrequency: 'weekly',  priority: 1.0 },
    { url: `${SITE}/en/methodology`, lastModified: new Date(), changeFrequency: 'monthly', priority: 0.8 },
    { url: `${SITE}/fr/methodology`, lastModified: new Date(), changeFrequency: 'monthly', priority: 0.8 },
    { url: `${SITE}/en/blog`,        lastModified: new Date(), changeFrequency: 'weekly',  priority: 0.9 },
    { url: `${SITE}/fr/blog`,        lastModified: new Date(), changeFrequency: 'weekly',  priority: 0.9 },
    { url: `${SITE}/en/signup`,      lastModified: new Date(), changeFrequency: 'monthly', priority: 0.7 },
    { url: `${SITE}/fr/signup`,      lastModified: new Date(), changeFrequency: 'monthly', priority: 0.7 },
  ]

  const blogEntries: MetadataRoute.Sitemap = [
    ...enPosts.map(p => ({
      url:           `${SITE}/en/blog/${p.slug}`,
      lastModified:  new Date(p.date),
      changeFrequency: 'monthly' as const,
      priority:      0.7,
    })),
    ...frPosts.map(p => ({
      url:           `${SITE}/fr/blog/${p.slug}`,
      lastModified:  new Date(p.date),
      changeFrequency: 'monthly' as const,
      priority:      0.7,
    })),
  ]

  return [...staticEntries, ...blogEntries]
}

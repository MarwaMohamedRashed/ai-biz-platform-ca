/**
 * Blog post loading + minimal markdown rendering. Zero dependencies.
 *
 * Posts live in apps/web/content/blog/<locale>/<slug>.md with YAML
 * frontmatter and Markdown body. Frontmatter shape:
 *
 *   ---
 *   title: "Post title"
 *   description: "Short summary used as meta description and og:description"
 *   date: 2026-05-09
 *   author: "Marwa Saleh"
 *   tags: ["tag1", "tag2"]
 *   ---
 *   # Body markdown here...
 *
 * Markdown supported: headings (# .. ######), bold/italic, inline code,
 * fenced code blocks, links, ordered + unordered lists, blockquotes,
 * paragraphs. No tables, no images-yet (add when needed).
 */
import fs from 'node:fs/promises'
import path from 'node:path'

export interface BlogPostMeta {
  slug: string
  title: string
  description: string
  date: string         // ISO 8601 (YYYY-MM-DD)
  author: string
  tags: string[]
  locale: 'en' | 'fr'
}

export interface BlogPost extends BlogPostMeta {
  bodyHtml: string
}

const CONTENT_ROOT = path.join(process.cwd(), 'content', 'blog')

// ─── Frontmatter ──────────────────────────────────────────────────────────
function parseFrontmatter(raw: string): { meta: Record<string, unknown>; body: string } {
  const m = raw.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n([\s\S]*)$/)
  if (!m) return { meta: {}, body: raw }

  const meta: Record<string, unknown> = {}
  for (const line of m[1].split(/\r?\n/)) {
    const kv = line.match(/^([A-Za-z_][\w-]*):\s*(.*)$/)
    if (!kv) continue
    const key = kv[1].trim()
    let value: string = kv[2].trim()

    // Strip surrounding quotes
    if ((value.startsWith('"') && value.endsWith('"')) ||
        (value.startsWith("'") && value.endsWith("'"))) {
      value = value.slice(1, -1)
    }

    // Tags-as-array — only `[a, b]` form supported
    if (value.startsWith('[') && value.endsWith(']')) {
      const items = value.slice(1, -1).split(',').map(s => s.trim().replace(/^["']|["']$/g, ''))
      meta[key] = items.filter(Boolean)
    } else {
      meta[key] = value
    }
  }
  return { meta, body: m[2] }
}

// ─── Tiny markdown -> HTML ────────────────────────────────────────────────
function escapeHtml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

// Inline transforms. Order matters: process code first so we don't damage
// content inside backticks; then links; then emphasis.
function inline(text: string): string {
  // Inline code (preserve content; escape inside)
  text = text.replace(/`([^`]+)`/g, (_, s) => `<code>${escapeHtml(s)}</code>`)
  // Links [text](url)
  text = text.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_, t, u) =>
    `<a href="${escapeHtml(u)}" target="_blank" rel="noopener noreferrer">${t}</a>`)
  // Bold **x**
  text = text.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
  // Italic *x* (avoid double-asterisks already consumed)
  text = text.replace(/(^|[^*])\*([^*\n]+)\*(?!\*)/g, '$1<em>$2</em>')
  return text
}

function renderMarkdown(md: string): string {
  const lines = md.split(/\r?\n/)
  const out: string[] = []
  let i = 0

  while (i < lines.length) {
    const line = lines[i]

    // Fenced code block ```
    if (line.match(/^```/)) {
      const lang = line.slice(3).trim()
      const buf: string[] = []
      i++
      while (i < lines.length && !lines[i].match(/^```/)) {
        buf.push(lines[i])
        i++
      }
      i++ // skip closing fence
      out.push(`<pre><code${lang ? ` class="lang-${escapeHtml(lang)}"` : ''}>${escapeHtml(buf.join('\n'))}</code></pre>`)
      continue
    }

    // Heading
    const h = line.match(/^(#{1,6})\s+(.+)$/)
    if (h) {
      const level = h[1].length
      out.push(`<h${level}>${inline(escapeHtml(h[2]))}</h${level}>`)
      i++
      continue
    }

    // Blockquote
    if (line.startsWith('> ')) {
      const buf: string[] = []
      while (i < lines.length && lines[i].startsWith('> ')) {
        buf.push(lines[i].slice(2))
        i++
      }
      out.push(`<blockquote>${inline(escapeHtml(buf.join(' ')))}</blockquote>`)
      continue
    }

    // Unordered list
    if (line.match(/^[-*]\s+/)) {
      const items: string[] = []
      while (i < lines.length && lines[i].match(/^[-*]\s+/)) {
        items.push(`<li>${inline(escapeHtml(lines[i].replace(/^[-*]\s+/, '')))}</li>`)
        i++
      }
      out.push(`<ul>${items.join('')}</ul>`)
      continue
    }

    // Ordered list
    if (line.match(/^\d+\.\s+/)) {
      const items: string[] = []
      while (i < lines.length && lines[i].match(/^\d+\.\s+/)) {
        items.push(`<li>${inline(escapeHtml(lines[i].replace(/^\d+\.\s+/, '')))}</li>`)
        i++
      }
      out.push(`<ol>${items.join('')}</ol>`)
      continue
    }

    // Blank line
    if (line.trim() === '') {
      i++
      continue
    }

    // Paragraph (consume until blank line or block construct)
    const buf: string[] = []
    while (i < lines.length &&
           lines[i].trim() !== '' &&
           !lines[i].match(/^(#{1,6}\s|>\s|[-*]\s|\d+\.\s|```)/)) {
      buf.push(lines[i])
      i++
    }
    out.push(`<p>${inline(escapeHtml(buf.join(' ')))}</p>`)
  }

  return out.join('\n')
}

// ─── Public API ───────────────────────────────────────────────────────────
async function readPost(locale: 'en' | 'fr', slug: string): Promise<BlogPost | null> {
  const filePath = path.join(CONTENT_ROOT, locale, `${slug}.md`)
  let raw: string
  try {
    raw = await fs.readFile(filePath, 'utf-8')
  } catch {
    return null
  }
  const { meta, body } = parseFrontmatter(raw)
  return {
    slug,
    title:       String(meta.title ?? slug),
    description: String(meta.description ?? ''),
    date:        String(meta.date ?? ''),
    author:      String(meta.author ?? 'LeapOne'),
    tags:        Array.isArray(meta.tags) ? (meta.tags as string[]) : [],
    locale,
    bodyHtml:    renderMarkdown(body),
  }
}

export async function getPost(locale: 'en' | 'fr', slug: string): Promise<BlogPost | null> {
  return readPost(locale, slug)
}

export async function getAllPosts(locale: 'en' | 'fr'): Promise<BlogPostMeta[]> {
  const dir = path.join(CONTENT_ROOT, locale)
  let files: string[]
  try {
    files = await fs.readdir(dir)
  } catch {
    return []
  }

  const posts: BlogPostMeta[] = []
  for (const file of files) {
    if (!file.endsWith('.md')) continue
    const slug = file.replace(/\.md$/, '')
    const post = await readPost(locale, slug)
    if (post) {
      // strip body from list payload
      const { bodyHtml: _bodyHtml, ...meta } = post
      void _bodyHtml
      posts.push(meta)
    }
  }
  // newest first
  posts.sort((a, b) => (a.date < b.date ? 1 : -1))
  return posts
}

export async function getAllSlugs(): Promise<{ locale: 'en' | 'fr'; slug: string }[]> {
  const out: { locale: 'en' | 'fr'; slug: string }[] = []
  for (const locale of ['en', 'fr'] as const) {
    const posts = await getAllPosts(locale)
    for (const p of posts) {
      out.push({ locale, slug: p.slug })
    }
  }
  return out
}

import Link from 'next/link'
import { getLocale } from 'next-intl/server'

export const metadata = {
  title: 'How We Score Your Business — LeapOne AEO Methodology',
  description:
    'Every point in your AEO Readiness Score is explained. See exactly which signals we measure, what queries we run, and how each pillar is calculated.',
}

const PILLARS = [
  {
    key: 'gbp',
    label: 'Google Business Profile (GBP)',
    max: 25,
    color: 'bg-indigo-500',
    description:
      'Your GBP listing is the single most important signal for local AI search. We check whether Google's Knowledge Graph recognises your business by name, whether your category and contact details are present, and whether your rating appears.',
    signals: [
      { label: 'Business found in Google Knowledge Graph',           pts: 10 },
      { label: 'Star rating present',                                pts: 5  },
      { label: 'Business category / type present',                   pts: 5  },
      { label: 'Website or phone number on the listing',             pts: 5  },
    ],
    dataSource: 'SerpApi — Google Knowledge Graph (knowledge_graph)',
  },
  {
    key: 'reviews',
    label: 'Reviews & Reputation',
    max: 22,
    color: 'bg-amber-500',
    description:
      'AI engines use review volume and rating as trust signals. A business with 50+ reviews at 4.5★ is far more likely to be cited than one with 5 reviews at 3.9★.',
    signals: [
      { label: '50 or more reviews',     pts: 12 },
      { label: '10 – 49 reviews',        pts: 6  },
      { label: 'Rating ≥ 4.5★',          pts: 10 },
      { label: 'Rating ≥ 4.0★',          pts: 5  },
    ],
    note: 'Review count and rating tiers do not stack beyond their category maximum.',
    dataSource: 'SerpApi — Knowledge Graph (review_count, rating) with local pack fallback',
  },
  {
    key: 'website',
    label: 'Website & Schema Markup',
    max: 20,
    color: 'bg-green-500',
    description:
      'AI engines parse websites for structured data (JSON-LD schema). A LocalBusiness schema tells AI exactly who you are, where you are, and what you do. FAQ schema provides ready-made Q&A pairs that AI cites verbatim.',
    signals: [
      { label: 'Website is reachable (HTTP 200)',             pts: 8 },
      { label: 'LocalBusiness JSON-LD schema detected',       pts: 6 },
      { label: 'FAQ / HowTo JSON-LD schema detected',         pts: 6 },
    ],
    dataSource: 'Direct HTTP fetch of the business website + HTML parsing',
  },
  {
    key: 'local_search',
    label: 'Local Search Presence',
    max: 15,
    color: 'bg-blue-500',
    description:
      'The Google local pack (the map + top 3 results) is where most local searches begin. Being there means Google has indexed you as a credible local option. Appearing in organic results in addition to the local pack doubles the exposure.',
    signals: [
      { label: 'Business appears in Google local pack',    pts: 10 },
      { label: 'Business appears in organic search results', pts: 5  },
    ],
    dataSource: 'SerpApi — Google local_results and organic_results',
  },
  {
    key: 'ai_citation',
    label: 'AI Citations',
    max: 18,
    color: 'bg-purple-500',
    description:
      'We test whether AI search engines mention your business by name when a potential customer asks a question about your category and city. Perplexity and Google AI Overview are the two engines with the highest local business citation rates as of 2026.',
    signals: [
      { label: 'Mentioned by name in a Perplexity AI answer',      pts: 10 },
      { label: 'Mentioned by name in a Google AI Overview answer', pts: 8  },
    ],
    dataSource: 'Perplexity Sonar API + SerpApi Google AI Overview (ai_overview)',
  },
]

const QUERIES_EXAMPLE = [
  'best physiotherapy clinic in Milton, Ontario',
  'physiotherapy clinic near Milton',
  'top physiotherapy clinic Milton Ontario',
]

export default async function MethodologyPage() {
  const locale = await getLocale()

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Nav */}
      <nav className="bg-white border-b border-slate-100 px-6 py-4 flex items-center justify-between">
        <Link href={`/${locale}`} className="text-lg font-extrabold text-[#4f46e5]">LeapOne</Link>
        <Link
          href={`/${locale}/dashboard`}
          className="text-xs font-semibold text-[#4f46e5] hover:underline">
          ← Back to dashboard
        </Link>
      </nav>

      <div className="max-w-3xl mx-auto px-6 py-12">
        {/* Hero */}
        <div className="mb-10">
          <span className="text-[10px] font-bold text-[#4f46e5] uppercase tracking-widest">Transparency</span>
          <h1 className="text-3xl font-extrabold text-[#1e293b] mt-1 mb-3">
            How we calculate your AEO Readiness Score
          </h1>
          <p className="text-slate-600 text-sm leading-relaxed">
            Every point in your score is traceable to a specific data signal from a specific source.
            There is no black box. Below is the exact formula — the same one our audit engine runs.
          </p>
        </div>

        {/* Score overview */}
        <div className="bg-white border border-slate-100 rounded-2xl p-6 mb-8 shadow-sm">
          <h2 className="text-sm font-extrabold text-[#1e293b] mb-4">Score breakdown (total: 100 points)</h2>
          <div className="flex flex-col gap-2">
            {PILLARS.map(p => (
              <div key={p.key} className="flex items-center gap-3">
                <div className={`w-2 h-2 rounded-full flex-shrink-0 ${p.color}`} />
                <p className="text-xs text-[#1e293b] flex-1">{p.label}</p>
                <span className="text-xs font-bold text-slate-600">{p.max} pts</span>
              </div>
            ))}
          </div>
        </div>

        {/* How queries work */}
        <div className="bg-white border border-slate-100 rounded-2xl p-6 mb-8 shadow-sm">
          <h2 className="text-sm font-extrabold text-[#1e293b] mb-2">How we search</h2>
          <p className="text-xs text-slate-600 mb-3 leading-relaxed">
            We run three search queries — one per template — using your business type and city. Each query
            is sent to Google (via SerpApi) and Perplexity simultaneously. Your score is the best result
            across all queries (not an average), so a single strong result can unlock full points.
          </p>
          <div className="bg-slate-50 rounded-xl p-3 flex flex-col gap-1">
            <p className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-1">Example queries for a Milton physiotherapy clinic</p>
            {QUERIES_EXAMPLE.map((q, i) => (
              <p key={i} className="text-xs font-mono text-indigo-700">{q}</p>
            ))}
          </div>
        </div>

        {/* Pillar detail cards */}
        <h2 className="text-sm font-extrabold text-[#1e293b] mb-4">Pillar details</h2>
        <div className="flex flex-col gap-5">
          {PILLARS.map(p => (
            <div key={p.key} className="bg-white border border-slate-100 rounded-2xl p-6 shadow-sm">
              <div className="flex items-center gap-2 mb-1">
                <div className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${p.color}`} />
                <h3 className="text-sm font-extrabold text-[#1e293b]">{p.label}</h3>
                <span className="ml-auto text-xs font-bold text-slate-500">max {p.max} pts</span>
              </div>
              <p className="text-xs text-slate-600 leading-relaxed mb-4">{p.description}</p>

              <table className="w-full text-xs mb-3">
                <thead>
                  <tr className="text-[10px] text-slate-400 uppercase tracking-wider border-b border-slate-100">
                    <th className="text-left pb-1 font-semibold">Signal</th>
                    <th className="text-right pb-1 font-semibold">Points</th>
                  </tr>
                </thead>
                <tbody>
                  {p.signals.map((s, i) => (
                    <tr key={i} className="border-b border-slate-50">
                      <td className="py-1.5 text-slate-700">{s.label}</td>
                      <td className="py-1.5 text-right font-bold text-[#4f46e5]">+{s.pts}</td>
                    </tr>
                  ))}
                </tbody>
              </table>

              {p.note && (
                <p className="text-[10px] text-amber-700 bg-amber-50 rounded-lg px-3 py-1.5 mb-2">{p.note}</p>
              )}

              <p className="text-[10px] text-slate-400">
                <span className="font-semibold">Data source:</span> {p.dataSource}
              </p>
            </div>
          ))}
        </div>

        {/* FAQ */}
        <div className="mt-10 bg-white border border-slate-100 rounded-2xl p-6 shadow-sm">
          <h2 className="text-sm font-extrabold text-[#1e293b] mb-4">Common questions</h2>
          <div className="flex flex-col gap-4">
            {[
              {
                q: 'Why is the max score 100 and not something else?',
                a: 'We calibrated the five pillars so that a business that does everything well — claimed GBP, 50+ reviews at 4.5★, reachable website with schema, in the local pack, cited by two AI engines — scores 100. Most businesses start between 20 and 50.',
              },
              {
                q: 'Does the score change if I do nothing?',
                a: 'It can — if a competitor gets more reviews, or if Google updates how it indexes your listing, your relative visibility changes. That\'s why monthly auto-audits matter.',
              },
              {
                q: 'Why do you use Perplexity and Google AI Overview and not ChatGPT?',
                a: 'Perplexity and Google AI Overview are the two engines with real-time local business citation as of mid-2026. ChatGPT does not yet expose an API for live local search. We will add it when available.',
              },
              {
                q: 'Can I dispute my score?',
                a: 'Yes — every audit stores the raw data that produced it. Use the "Why this score?" button on your dashboard to see exactly what each engine returned for each query.',
              },
            ].map((item, i) => (
              <div key={i} className="border-b border-slate-50 pb-4 last:border-0 last:pb-0">
                <p className="text-xs font-bold text-[#1e293b] mb-1">{item.q}</p>
                <p className="text-xs text-slate-600 leading-relaxed">{item.a}</p>
              </div>
            ))}
          </div>
        </div>

        <p className="text-[10px] text-slate-400 text-center mt-8">
          LeapOne AEO Methodology · Last updated May 2026
        </p>
      </div>
    </div>
  )
}

# Next.js & React for LeapOne
**Time:** ~3 hours | **Goal:** Build and understand the LeapOne frontend

---

## 1. What React Is

React is a JavaScript library for building UIs. The core idea: your UI is made of **components** — reusable pieces that manage their own content and state.

Instead of writing HTML directly, you write **JSX** — HTML-like syntax inside JavaScript.

```jsx
// A simple component
function WelcomeMessage() {
  return (
    <div>
      <h1>Good morning!</h1>
      <p>You have 3 reviews to respond to.</p>
    </div>
  )
}
```

---

## 2. What Next.js Adds

Next.js is a framework built on top of React. It adds:
- **File-based routing** — the file path = the URL
- **Server-side rendering** — pages load fast, good for SEO
- **API routes** — small backend functions inside the frontend project
- **Image optimization, caching, and more**

For LeapOne, Next.js is the entire frontend app.

---

## 3. File-Based Routing

Every file in `app/` becomes a URL:

```
apps/web/app/
├── page.tsx              → leapone.ca/           (home/chat)
├── layout.tsx            → shared layout (nav, footer)
├── (auth)/
│   ├── login/
│   │   └── page.tsx      → leapone.ca/login
│   └── signup/
│       └── page.tsx      → leapone.ca/signup
├── dashboard/
│   ├── page.tsx          → leapone.ca/dashboard
│   └── reviews/
│       ├── page.tsx      → leapone.ca/dashboard/reviews
│       └── [id]/
│           └── page.tsx  → leapone.ca/dashboard/reviews/123
```

`[id]` in brackets = dynamic route (any value).

---

## 4. Components

Every `.tsx` file exports a component. Components are functions that return JSX.

```tsx
// components/ReviewCard.tsx
type ReviewCardProps = {
  author: string
  rating: number
  text: string
  onApprove: () => void
}

export function ReviewCard({ author, rating, text, onApprove }: ReviewCardProps) {
  return (
    <div className="border rounded-xl p-4">
      <div className="flex items-center gap-2">
        <span className="font-semibold">{author}</span>
        <span>{"⭐".repeat(rating)}</span>
      </div>
      <p className="text-gray-600 mt-2">{text}</p>
      <button
        onClick={onApprove}
        className="mt-3 bg-indigo-600 text-white px-4 py-2 rounded-lg"
      >
        Approve & Post
      </button>
    </div>
  )
}
```

Use it in another component:
```tsx
import { ReviewCard } from '@/components/ReviewCard'

<ReviewCard
  author="John Smith"
  rating={2}
  text="Waited 45 minutes"
  onApprove={() => handleApprove(review.id)}
/>
```

---

## 5. State with `useState`

State is data that, when it changes, causes the component to re-render.

```tsx
'use client'   // required for components that use state or events
import { useState } from 'react'

export function ReviewResponse() {
  const [response, setResponse] = useState("")
  const [isLoading, setIsLoading] = useState(false)

  return (
    <div>
      <textarea
        value={response}
        onChange={(e) => setResponse(e.target.value)}
        placeholder="Edit the AI response..."
        className="w-full border rounded-lg p-3"
      />
      <p>Characters: {response.length}</p>
    </div>
  )
}
```

**Rule:** Every time `setResponse` is called, the component re-renders with the new value.

---

## 6. Data Fetching with `useEffect`

`useEffect` runs code after the component renders — used to fetch data, set up subscriptions, etc.

```tsx
'use client'
import { useState, useEffect } from 'react'
import { supabase } from '@/lib/supabase'

export function ReviewsList() {
  const [reviews, setReviews] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function loadReviews() {
      const { data } = await supabase
        .from('reviews')
        .select('*')
        .eq('status', 'pending')

      setReviews(data || [])
      setLoading(false)
    }

    loadReviews()
  }, [])   // empty [] = run once when component mounts

  if (loading) return <p>Loading reviews...</p>

  return (
    <div>
      {reviews.map(review => (
        <ReviewCard key={review.id} {...review} />
      ))}
    </div>
  )
}
```

---

## 7. Server vs Client Components

Next.js has two types of components:

### Server Components (default)
- Run on the server, never sent to the browser as JavaScript
- Can fetch data directly (no useEffect needed)
- Cannot use `useState`, `useEffect`, or browser events
- Faster, better for SEO

```tsx
// app/dashboard/reviews/page.tsx — Server Component (no 'use client')
import { createServerClient } from '@/lib/supabase-server'

export default async function ReviewsPage() {
  const supabase = createServerClient()
  const { data: reviews } = await supabase.from('reviews').select('*')

  return (
    <div>
      {reviews?.map(r => <div key={r.id}>{r.text}</div>)}
    </div>
  )
}
```

### Client Components
- Run in the browser
- Required for: `useState`, `useEffect`, `onClick`, forms, real-time updates
- Add `'use client'` at the top of the file

**Rule for LeapOne:** Pages that just display data → Server Component. Pages with forms, buttons, or real-time chat → Client Component.

---

## 8. Tailwind CSS

Tailwind is a utility-first CSS framework. Instead of writing CSS files, you apply classes directly in JSX.

```tsx
// Without Tailwind
<div style={{ backgroundColor: '#4f46e5', padding: '16px', borderRadius: '12px' }}>

// With Tailwind
<div className="bg-indigo-600 p-4 rounded-xl">
```

**LeapOne color classes (from your design decisions):**
```
bg-indigo-600     → #4f46e5 (primary)
bg-orange-500     → #f97316 (accent)
text-slate-800    → #1e293b (main text)
text-slate-500    → #64748b (muted text)
bg-slate-50       → #f8fafc (background)
```

**Common utility classes:**
```
Layout:     flex, grid, items-center, justify-between, gap-4
Spacing:    p-4 (padding), m-4 (margin), px-4 (horizontal padding)
Text:       text-sm, text-lg, font-semibold, font-bold
Borders:    border, rounded-lg, rounded-xl
Width:      w-full, w-1/2, max-w-xl
Colors:     bg-white, text-gray-600, border-gray-200
Responsive: md:grid-cols-2 (applies at medium screens and above)
```

---

## 9. Calling Your FastAPI Backend

```tsx
'use client'
import { useState } from 'react'

export function ApproveButton({ reviewId, response }: { reviewId: string, response: string }) {
  const [loading, setLoading] = useState(false)
  const [done, setDone] = useState(false)

  async function handleApprove() {
    setLoading(true)

    const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/reviews/${reviewId}/approve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ final_response: response })
    })

    if (res.ok) setDone(true)
    setLoading(false)
  }

  return (
    <button
      onClick={handleApprove}
      disabled={loading || done}
      className="bg-indigo-600 text-white px-4 py-2 rounded-lg disabled:opacity-50"
    >
      {done ? "Posted ✓" : loading ? "Posting..." : "Approve & Post"}
    </button>
  )
}
```

---

## 10. Layout and Navigation

`app/layout.tsx` wraps every page — put nav, footer, and global providers here.

```tsx
// app/layout.tsx
import { Inter } from 'next/font/google'
import './globals.css'

const inter = Inter({ subsets: ['latin'] })

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <nav className="border-b bg-white px-6 py-4 flex items-center justify-between">
          <span className="font-bold text-indigo-600 text-xl">LeapOne</span>
        </nav>
        <main>{children}</main>
      </body>
    </html>
  )
}
```

---

## 11. Environment Variables

```
# apps/web/.env.local
NEXT_PUBLIC_SUPABASE_URL=https://xxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJ...
NEXT_PUBLIC_API_URL=http://localhost:8000   ← your FastAPI backend
```

`NEXT_PUBLIC_` prefix = safe to use in browser code.
Variables without the prefix = server-side only.

---

## 12. TypeScript Basics

Next.js uses TypeScript (`.tsx` files). You only need to know a few things:

```tsx
// Type for a review object
type Review = {
  id: string
  author: string
  rating: number
  text: string
  status: 'pending' | 'responded' | 'ignored'
}

// Props type for a component
type ReviewCardProps = {
  review: Review
  onApprove: (id: string) => void
}

// Optional prop
type ButtonProps = {
  label: string
  disabled?: boolean   // ? = optional
}

// Array type
type ReviewListProps = {
  reviews: Review[]
}
```

---

## Quick Reference

| Concept | Syntax |
|---|---|
| Client component | `'use client'` at top of file |
| State | `const [value, setValue] = useState(initial)` |
| Effect (on mount) | `useEffect(() => { ... }, [])` |
| Conditional render | `{condition && <Component />}` |
| List render | `{items.map(i => <Item key={i.id} />)}` |
| Tailwind class | `className="bg-indigo-600 text-white p-4"` |
| Fetch POST | `fetch(url, { method: 'POST', body: JSON.stringify(data) })` |
| Dynamic route | File named `[id]/page.tsx`, access via `params.id` |
| Link | `import Link from 'next/link'` → `<Link href="/dashboard">` |

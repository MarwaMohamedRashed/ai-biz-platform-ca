'use client'

interface AuditPoint {
  score: number
  created_at: string
}

interface Props {
  history: AuditPoint[]
}

const W = 180
const H = 72
const PAD_LEFT = 24
const PAD_RIGHT = 8
const PAD_TOP = 8
const PAD_BOTTOM = 16

export default function ScoreHistoryChart({ history }: Props) {
  if (history.length < 2) {
    return (
      <p className="text-[10px] text-slate-400 italic px-5 py-3">
        Run at least 2 audits to see your score trend.
      </p>
    )
  }

  const points = history.slice(-6)
  const scores = points.map(p => p.score)
  const minScore = Math.max(0, Math.min(...scores) - 10)
  const maxScore = Math.min(100, Math.max(...scores) + 10)
  const range = maxScore - minScore || 1

  const plotW = W - PAD_LEFT - PAD_RIGHT
  const plotH = H - PAD_TOP - PAD_BOTTOM

  const toX = (i: number) => PAD_LEFT + (i / (points.length - 1)) * plotW
  const toY = (s: number) => PAD_TOP + plotH - ((s - minScore) / range) * plotH

  const polyPoints = points.map((p, i) => `${toX(i)},${toY(p.score)}`).join(' ')

  const latestScore = points[points.length - 1].score
  const prevScore = points[points.length - 2].score
  const delta = latestScore - prevScore
  const deltaColor = delta > 0 ? 'text-green-600' : delta < 0 ? 'text-red-500' : 'text-slate-400'
  const deltaLabel = delta > 0 ? `+${delta}` : `${delta}`

  return (
    <div className="px-5 py-3 border-b border-slate-100">
      <div className="flex items-center justify-between mb-2">
        <p className="text-[10px] text-slate-400 uppercase tracking-wide">Score history</p>
        <span className={`text-[10px] font-semibold ${deltaColor}`}>
          {delta !== 0 ? `${deltaLabel} vs prev` : 'No change'}
        </span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ height: H }}>
        {/* Y-axis gridlines at 25, 50, 75 */}
        {[25, 50, 75].map(v => {
          if (v < minScore || v > maxScore) return null
          const y = toY(v)
          return (
            <g key={v}>
              <line x1={PAD_LEFT} y1={y} x2={W - PAD_RIGHT} y2={y}
                stroke="#f1f5f9" strokeWidth="1"/>
              <text x={PAD_LEFT - 2} y={y + 3} textAnchor="end"
                fontSize="7" fill="#94a3b8">{v}</text>
            </g>
          )
        })}

        {/* Filled area under line */}
        <defs>
          <linearGradient id="scoreGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#4f46e5" stopOpacity="0.15"/>
            <stop offset="100%" stopColor="#4f46e5" stopOpacity="0"/>
          </linearGradient>
        </defs>
        <polygon
          points={`${toX(0)},${toY(minScore)} ${polyPoints} ${toX(points.length - 1)},${toY(minScore)}`}
          fill="url(#scoreGrad)"/>

        {/* Line */}
        <polyline points={polyPoints} fill="none" stroke="#4f46e5" strokeWidth="1.5"
          strokeLinejoin="round" strokeLinecap="round"/>

        {/* Dots */}
        {points.map((p, i) => (
          <circle key={i} cx={toX(i)} cy={toY(p.score)} r="2.5"
            fill="white" stroke="#4f46e5" strokeWidth="1.5"/>
        ))}

        {/* Latest score label */}
        <text
          x={toX(points.length - 1)}
          y={toY(latestScore) - 5}
          textAnchor="middle"
          fontSize="8"
          fontWeight="bold"
          fill="#4f46e5">
          {latestScore}
        </text>

        {/* X-axis date labels — first and last only */}
        <text x={toX(0)} y={H - 2} textAnchor="middle" fontSize="7" fill="#94a3b8">
          {formatDate(points[0].created_at)}
        </text>
        <text x={toX(points.length - 1)} y={H - 2} textAnchor="middle" fontSize="7" fill="#94a3b8">
          {formatDate(points[points.length - 1].created_at)}
        </text>
      </svg>
    </div>
  )
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString('en-CA', { month: 'short', day: 'numeric' })
}

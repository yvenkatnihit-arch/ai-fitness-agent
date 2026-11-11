import type { WeightPoint } from './types'

const W = 320
const H = 140
const PAD = { left: 38, right: 10, top: 10, bottom: 22 }

const label = (iso: string) => new Date(`${iso}T00:00:00`).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })

// A small line chart of the weigh-ins, drawn with plain SVG (no chart library). The dashed line is the target weight when there is one.
// Only layout lives here: the numbers come from the server, and the chart has a text version for screen readers.
export function WeightChart({ entries, target }: { entries: WeightPoint[]; target: number | null }) {
  if (entries.length === 0) return null
  const weights = entries.map((e) => e.weight_kg).concat(target === null ? [] : [target])
  const low = Math.min(...weights)
  const high = Math.max(...weights)
  const span = high - low || 1
  const min = low - span * 0.15
  const max = high + span * 0.15
  const x = (i: number) => PAD.left + (entries.length === 1 ? (W - PAD.left - PAD.right) / 2 : (i / (entries.length - 1)) * (W - PAD.left - PAD.right))
  const y = (kg: number) => PAD.top + (1 - (kg - min) / (max - min)) * (H - PAD.top - PAD.bottom)
  const line = entries.map((e, i) => `${i === 0 ? 'M' : 'L'}${x(i).toFixed(1)} ${y(e.weight_kg).toFixed(1)}`).join(' ')
  const first = entries[0]
  const last = entries[entries.length - 1]
  const summary = `Weight chart: ${first.weight_kg} kg on ${label(first.date)}${entries.length > 1 ? `, ${last.weight_kg} kg on ${label(last.date)}` : ''}${
    target === null ? '' : `, target ${target} kg`}.`

  return (
    <figure className="m-0">
      <svg role="img" aria-label={summary} viewBox={`0 0 ${W} ${H}`} className="h-auto w-full">
        {[min + (max - min) * 0.15, (min + max) / 2, max - (max - min) * 0.15].map((v) => (
          <g key={v}>
            <line x1={PAD.left} x2={W - PAD.right} y1={y(v)} y2={y(v)} stroke="currentColor" strokeOpacity="0.12" />
            <text x={PAD.left - 6} y={y(v) + 3} textAnchor="end" fontSize="9" fill="currentColor" fillOpacity="0.6">{v.toFixed(1)}</text>
          </g>
        ))}
        {target !== null && (
          <g>
            <line x1={PAD.left} x2={W - PAD.right} y1={y(target)} y2={y(target)} stroke="currentColor" strokeDasharray="4 3" strokeOpacity="0.55" />
            <text x={W - PAD.right} y={y(target) - 3} textAnchor="end" fontSize="9" fill="currentColor" fillOpacity="0.7">target {target}</text>
          </g>
        )}
        {entries.length > 1 && <path d={line} fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" className="text-brand-strong" />}
        {entries.map((e, i) => <circle key={e.date} cx={x(i)} cy={y(e.weight_kg)} r="3" className="fill-current text-brand-strong" />)}
        <text x={PAD.left} y={H - 6} fontSize="9" fill="currentColor" fillOpacity="0.6">{label(first.date)}</text>
        {entries.length > 1 && <text x={W - PAD.right} y={H - 6} textAnchor="end" fontSize="9" fill="currentColor" fillOpacity="0.6">{label(last.date)}</text>}
      </svg>
      <figcaption className="sr-only">{summary}</figcaption>
    </figure>
  )
}

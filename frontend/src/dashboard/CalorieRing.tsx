import { useCountUp } from './useCountUp'
import type { Progress } from './types'

const SIZE = 200
const STROKE = 16
const RADIUS = (SIZE - STROKE) / 2
const CIRCUMFERENCE = 2 * Math.PI * RADIUS

// The big ring: calories eaten today against the target. The percentage comes from the server; this only draws it.
// Over the target the ring is full and turns amber (never red: eating a bit more is not an emergency).
export function CalorieRing({ value }: { value: Progress }) {
  const over = value.percent > 100
  const shown = Math.min(value.percent, 100)
  const eaten = useCountUp(Math.round(value.eaten))
  return (
    <div
      role="progressbar" aria-label="Calories eaten today" aria-valuemin={0} aria-valuemax={100} aria-valuenow={shown}
      aria-valuetext={`${value.percent}% of your calorie target`} data-state={over ? 'over' : 'under'}
      className="relative mx-auto h-[200px] w-[200px]"
    >
      <svg viewBox={`0 0 ${SIZE} ${SIZE}`} className="h-full w-full -rotate-90" aria-hidden="true">
        <circle cx={SIZE / 2} cy={SIZE / 2} r={RADIUS} fill="none" strokeWidth={STROKE} style={{ stroke: 'var(--surface-2)' }} />
        <circle
          cx={SIZE / 2} cy={SIZE / 2} r={RADIUS} fill="none" strokeWidth={STROKE} strokeLinecap="round"
          strokeDasharray={CIRCUMFERENCE} strokeDashoffset={CIRCUMFERENCE * (1 - shown / 100)}
          className="ring-glow transition-[stroke-dashoffset] duration-1000 ease-out"
          style={{ stroke: over ? 'var(--warn)' : 'var(--brand)' }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span aria-hidden="true" className="text-4xl font-extrabold tabular-nums text-ink">{eaten}</span>
        <span className="text-xs text-muted">{Math.round(value.eaten)} / {Math.round(value.target)} kcal</span>
        <span className="mt-1 text-xs font-semibold text-brand-strong">{value.percent}%</span>
      </div>
    </div>
  )
}

// Donut of each macro's share of daily calories, with the calorie total in the middle.
// Every number comes from the backend (shares are computed in tested Python and add up to 100);
// this component only draws them. Colours: see macroColors.ts.
import type { MacroSlice } from './macroColors'

const SIZE = 160
const STROKE = 22
const RADIUS = (SIZE - STROKE) / 2
const CIRCUMFERENCE = 2 * Math.PI * RADIUS
const GAP = 2.5 // surface-coloured gap between segments, in px along the ring

const format = (n: number) => n.toLocaleString('en-IN')

// Where each segment starts round the ring, worked out before drawing (no changing values in render).
function withStarts(slices: MacroSlice[]) {
  return slices.map((slice, i) => ({
    slice,
    start: (slices.slice(0, i).reduce((sum, s) => sum + s.percent, 0) / 100) * CIRCUMFERENCE,
    length: (slice.percent / 100) * CIRCUMFERENCE,
  }))
}

export function MacroDonut({ kcal, slices }: { kcal: number; slices: MacroSlice[] }) {
  const summary = `Daily target ${format(kcal)} kcal: ` +
    slices.map((s) => `${s.name} ${s.grams} g (${s.percent}%)`).join(', ')

  return (
    <div className="flex flex-col items-center gap-5 sm:flex-row sm:justify-center sm:gap-8">
      <svg viewBox={`0 0 ${SIZE} ${SIZE}`} className="h-44 w-44 shrink-0" role="img" aria-label={summary}>
        {/* faint track, visible only if segments ever don't fill the ring */}
        <circle cx={SIZE / 2} cy={SIZE / 2} r={RADIUS} fill="none" style={{ stroke: "var(--surface-2)" }} strokeWidth={STROKE} />
        <g transform={`rotate(-90 ${SIZE / 2} ${SIZE / 2})`}>
          {withStarts(slices).map(({ slice, start, length }) => {
            const visible = Math.max(length - GAP, 0)
            return (
              <circle
                key={slice.name}
                data-testid={`segment-${slice.name.toLowerCase()}`}
                cx={SIZE / 2}
                cy={SIZE / 2}
                r={RADIUS}
                fill="none"
                stroke={slice.color}
                strokeWidth={STROKE}
                strokeDasharray={`${visible} ${CIRCUMFERENCE - visible}`}
                strokeDashoffset={-start}
              >
                <title>{`${slice.name}: ${slice.grams} g, ${slice.percent}% of calories`}</title>
              </circle>
            )
          })}
        </g>
        <text x="50%" y="47%" textAnchor="middle" className="fill-ink text-[26px] font-bold">
          {format(kcal)}
        </text>
        <text x="50%" y="61%" textAnchor="middle" className="fill-muted text-[11px]">
          kcal a day
        </text>
      </svg>

      <ul className="flex w-full max-w-[14rem] flex-col gap-3" aria-label="Macro breakdown">
        {slices.map((slice) => (
          <li key={slice.name} className="flex items-center gap-3">
            <span aria-hidden className="h-3 w-3 shrink-0 rounded-full" style={{ backgroundColor: slice.color }} />
            <span className="flex-1 text-sm font-medium text-ink">{slice.name}</span>
            <span className="text-sm font-semibold text-ink">{format(slice.grams)} g</span>
            <span className="w-10 text-right text-sm text-muted">{slice.percent}%</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

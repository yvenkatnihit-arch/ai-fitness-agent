import { words } from '../lib/words'
import { FIT_LABEL, FIT_STYLE, type Recommendation } from './types'

export function SplitCard({ rec, chosen, saving, onChoose }: {
  rec: Recommendation
  chosen: boolean
  saving: boolean
  onChoose: (key: string) => void
}) {
  return (
    <li className={`rounded-2xl bg-surface p-4 shadow-sm ${chosen ? 'ring-2 ring-brand' : ''}`}>
      <div className="flex items-start justify-between gap-2">
        <h3 className="text-base font-bold text-ink">{rec.name}</h3>
        <span className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-semibold ${FIT_STYLE[rec.fit]}`}>
          {FIT_LABEL[rec.fit]}
        </span>
      </div>
      <p className="mt-1 text-sm text-ink-soft">{rec.summary}</p>

      <ul className="mt-3 flex flex-col gap-1 text-sm text-ink-soft" aria-label={`Why ${rec.name}`}>
        {rec.reasons.map((reason) => <li key={reason}>✓ {reason}</li>)}
      </ul>
      {rec.cautions.length > 0 && (
        <ul className="mt-2 flex flex-col gap-1 rounded-lg bg-warn-soft p-3 text-xs text-warn" aria-label={`Things to know about ${rec.name}`}>
          {rec.cautions.map((caution) => <li key={caution}>{caution}</li>)}
        </ul>
      )}

      <details className="mt-3">
        <summary className="cursor-pointer text-sm font-semibold text-brand-strong">See the week</summary>
        <ol className="mt-2 flex flex-col gap-2">
          {rec.schedule.map((day, index) => (
            <li key={index} className="rounded-lg bg-surface-2 px-3 py-2">
              <span className="text-sm font-semibold text-ink">Day {index + 1}: {day.label}</span>
              <span className="block text-xs text-muted">{day.muscles.map(words).join(', ')}</span>
            </li>
          ))}
          {rec.recovery_days > 0 && (
            <li className="rounded-lg border border-dashed border-line px-3 py-2 text-sm text-muted">
              Plus {rec.recovery_days} easy recovery day: walking or stretching.
            </li>
          )}
        </ol>
      </details>

      <button
        type="button"
        onClick={() => onChoose(rec.key)}
        disabled={chosen || saving}
        className={`mt-4 w-full rounded-xl px-4 py-3 font-semibold transition disabled:opacity-60 ${
          chosen ? 'bg-brand-soft text-brand-strong' : 'bg-brand text-on-brand hover:opacity-90'
        }`}
      >
        {chosen ? '✓ Your split' : 'Choose this split'}
      </button>
    </li>
  )
}

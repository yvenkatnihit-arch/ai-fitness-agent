import type { Progress, Today } from './types'

const ROWS = [
  ['kcal', 'Calories', 'kcal'],
  ['protein_g', 'Protein', 'g'],
  ['carbs_g', 'Carbs', 'g'],
  ['fat_g', 'Fat', 'g'],
] as const

function Bar({ label, unit, value }: { label: string; unit: string; value: Progress }) {
  const over = value.percent > 100
  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-baseline justify-between text-sm">
        <span className="font-medium text-ink">{label}</span>
        <span className="text-ink-soft">{Math.round(value.eaten)} / {Math.round(value.target)} {unit}</span>
      </div>
      <div
        role="progressbar" aria-label={`${label} eaten today`} aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.min(value.percent, 100)}
        aria-valuetext={`${value.percent}% of your ${label.toLowerCase()} target`}
        className="h-2.5 overflow-hidden rounded-full bg-surface-2"
      >
        <div className={`h-full rounded-full ${over ? 'bg-warn' : 'bg-brand'}`} style={{ width: `${Math.min(value.percent, 100)}%` }} />
      </div>
      <span className="text-xs text-muted">{value.percent}% of your target</span>
    </div>
  )
}

// Today's calories and macros eaten so far against the targets, from the meals logged today. No numbers for users who must not see them.
export function TodayProgress({ today }: { today: Today }) {
  return (
    <section aria-label="Today's progress" className="flex flex-col gap-3 rounded-2xl bg-surface p-4 shadow-sm">
      <h2 className="text-base font-bold text-ink">Today, {today.weekday}</h2>
      {today.progress ? (
        ROWS.map(([key, label, unit]) => <Bar key={key} label={label} unit={unit} value={today.progress![key]} />)
      ) : (
        <p className="text-sm text-ink-soft">
          {today.numbers_hidden ? 'Your plan focuses on regular, balanced meals, so there are no numbers to track.' : 'Finish onboarding to see your targets here.'}
        </p>
      )}
      {today.logged.length === 0 ? (
        <p className="text-sm text-muted">Nothing logged today yet.</p>
      ) : (
        <ul aria-label="Logged today" className="flex flex-col gap-1 text-sm text-ink-soft">
          {today.logged.map((meal) => (
            <li key={meal.slot + meal.foods.join()}><span className="font-medium capitalize text-ink">{meal.slot.replace('_', ' ')}:</span> {meal.foods.join(', ')}</li>
          ))}
        </ul>
      )}
    </section>
  )
}

import { CalorieRing } from './CalorieRing'
import { MacroCards } from './MacroCards'
import type { Today } from './types'

// Today's calories (the ring) and macros (the cards) against the targets, from the meals logged today, then what was logged.
// No numbers for users who must not see them.
export function TodayProgress({ today }: { today: Today }) {
  return (
    <section aria-label="Today's progress" className="flex flex-col gap-3">
      <div className="glass flex flex-col gap-4 rounded-3xl p-5">
        <h2 className="text-base font-bold text-ink">Today, {today.weekday}</h2>
        {today.progress ? (
          <CalorieRing value={today.progress.kcal} />
        ) : (
          <p className="text-sm text-ink-soft">
            {today.numbers_hidden ? 'Your plan focuses on regular, balanced meals, so there are no numbers to track.' : 'Finish onboarding to see your targets here.'}
          </p>
        )}
      </div>
      {today.progress && <MacroCards progress={today.progress} />}
      <div className="glass rounded-2xl p-4">
        {today.logged.length === 0 ? (
          <p className="text-sm text-muted">Nothing logged today yet.</p>
        ) : (
          <ul aria-label="Logged today" className="flex flex-col gap-1 text-sm text-ink-soft">
            {today.logged.map((meal) => (
              <li key={meal.slot + meal.foods.join()}><span className="font-medium capitalize text-ink">{meal.slot.replace('_', ' ')}:</span> {meal.foods.join(', ')}</li>
            ))}
          </ul>
        )}
      </div>
    </section>
  )
}

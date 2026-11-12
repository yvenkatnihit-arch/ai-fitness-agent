import { Link } from 'react-router'

import { CalorieRing } from './CalorieRing'
import { MacroCards } from './MacroCards'
import { MealChecklist } from './MealChecklist'
import { kcalLeft } from './mealSlots'
import type { Today } from './types'

// "696 kcal left" under the ring (or how far over, said plainly and without blame).
function KcalLeft({ eaten, target }: { eaten: number; target: number }) {
  const { amount, over } = kcalLeft(eaten, target)
  return (
    <p aria-label="Calories left today" className="-mt-2 text-center text-sm font-semibold text-ink">
      {over ? `${amount} kcal over today’s target` : `${amount} kcal left today`}
    </p>
  )
}

// Today's calories (the ring) and macros (the cards) against the targets, from the meals logged today, then what was logged.
// No numbers for users who must not see them.
export function TodayProgress({ today }: { today: Today }) {
  return (
    <section aria-label="Today's progress" className="flex flex-col gap-3">
      <div className="glass flex flex-col gap-4 rounded-3xl p-5">
        <h2 className="text-base font-bold text-ink">Today, {today.weekday}</h2>
        {today.progress ? (
          <>
            <CalorieRing value={today.progress.kcal} />
            <KcalLeft eaten={today.progress.kcal.eaten} target={today.progress.kcal.target} />
          </>
        ) : (
          <p className="text-sm text-ink-soft">
            {today.numbers_hidden ? 'Your plan focuses on regular, balanced meals, so there are no numbers to track.' : 'Finish onboarding to see your targets here.'}
          </p>
        )}
        <MealChecklist today={today} />
      </div>
      {today.progress && <MacroCards progress={today.progress} />}
      <div className="glass flex flex-col gap-2 rounded-2xl p-4">
        {today.logged.length === 0 ? (
          <>
            <p className="text-sm text-muted">Nothing logged today yet.</p>
            {today.progress && (
              <p className="text-xs text-muted">Log a meal and your calories, protein, carbs and fat above fill up as you go.</p>
            )}
          </>
        ) : (
          <ul aria-label="Logged today" className="flex flex-col gap-1 text-sm text-ink-soft">
            {today.logged.map((meal) => (
              <li key={meal.slot + meal.foods.join()}><span className="font-medium capitalize text-ink">{meal.slot.replace('_', ' ')}:</span> {meal.foods.join(', ')}</li>
            ))}
          </ul>
        )}
        <Link
          to="/log"
          className={`self-start rounded-full px-3 py-1.5 text-xs font-semibold transition hover:opacity-90 ${
            today.logged.length === 0 ? 'btn-glow bg-brand text-on-brand' : 'border border-brand text-brand-strong'
          }`}
        >
          {today.logged.length === 0 ? 'Log a meal' : 'Log another meal'}
        </Link>
      </div>
    </section>
  )
}

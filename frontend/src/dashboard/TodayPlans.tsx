import { Link } from 'react-router'

import type { Today } from './types'

// What your approved meal plan and workout plan say for today.
export function TodayPlans({ today }: { today: Today }) {
  const { meal_plan: meals, workout } = today
  return (
    <>
      <section aria-label="Today's meals" className="flex flex-col gap-2 rounded-2xl bg-surface p-4 shadow-sm">
        <h2 className="text-base font-bold text-ink">Today&apos;s meals</h2>
        {meals ? (
          <>
            <ul className="flex flex-col gap-1 text-sm text-ink-soft">
              {meals.meals.map((meal) => (
                <li key={meal.slot}>
                  <span className="font-medium capitalize text-ink">{meal.slot.replace('_', ' ')}:</span>{' '}
                  {meal.items.map((item) => `${item.name} (${item.text})`).join(', ')}
                </li>
              ))}
            </ul>
            {meals.kcal !== null && <p className="text-xs text-muted">Planned: about {Math.round(meals.kcal)} kcal.</p>}
          </>
        ) : (
          <p className="text-sm text-muted">
            No meal plan for today yet. <Link to="/meal-plan" className="font-semibold text-brand-strong">Make your meal plan</Link>
          </p>
        )}
        <Link to="/log" className="text-sm font-semibold text-brand-strong">Log a meal</Link>
      </section>

      <section aria-label="Today's workout" className="flex flex-col gap-2 rounded-2xl bg-surface p-4 shadow-sm">
        <h2 className="text-base font-bold text-ink">Today&apos;s workout</h2>
        {!workout && (
          <p className="text-sm text-muted">
            No workout plan yet. <Link to="/workout" className="font-semibold text-brand-strong">Make your workout plan</Link>
          </p>
        )}
        {workout?.rest_day && <p className="text-sm text-ink-soft">Rest day. Recovery is part of the plan.</p>}
        {workout && !workout.rest_day && (
          <>
            <p className="text-sm text-ink-soft">
              <span className="font-medium text-ink">{workout.focus}</span>
              {workout.minutes !== null && `, about ${workout.minutes} minutes`}
            </p>
            <ul className="flex flex-col gap-1 text-sm text-ink-soft">
              {workout.exercises.map((exercise) => (
                <li key={exercise.name}>{exercise.name}: {exercise.sets} sets of {exercise.reps}</li>
              ))}
            </ul>
            <Link to="/workout" className="text-sm font-semibold text-brand-strong">Open workout plan</Link>
          </>
        )}
      </section>
    </>
  )
}

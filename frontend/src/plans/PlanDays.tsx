import { prescription, STANDARD_NOTE, WEEKDAYS, type PlanDay } from './types'

// The week, day by day. Used for a proposal waiting for approval and for the active plan.
export function PlanDays({ days }: { days: PlanDay[] }) {
  return (
    <div className="flex flex-col gap-3">
      <p className="text-xs text-muted">{STANDARD_NOTE}. Stop earlier if something hurts.</p>
      <ol aria-label="Week" className="flex flex-col gap-2">
        {days.map((day) =>
          day.is_rest ? (
            <li key={day.day_of_week} className="rounded-lg border border-dashed border-line px-3 py-2 text-sm text-muted">
              {WEEKDAYS[day.day_of_week - 1]}: rest
            </li>
          ) : (
            <li key={day.day_of_week} className="rounded-xl bg-surface-2 p-3">
              <h3 className="text-sm font-bold text-ink">
                {WEEKDAYS[day.day_of_week - 1]}: {day.focus}
                {day.minutes ? <span className="ml-2 text-xs font-normal text-muted">about {day.minutes} min</span> : null}
              </h3>
              <ol className="mt-2 flex flex-col gap-2">
                {day.exercises.map((e) => (
                  <li key={e.exercise_key}>
                    <span className="block text-sm font-semibold text-ink">{e.name}</span>
                    <span className="block text-xs text-ink-soft">{prescription(e)}</span>
                    {e.form_cues && e.form_cues.length > 0 && (
                      <details>
                        <summary className="cursor-pointer text-xs font-semibold text-brand-strong">How to do it</summary>
                        <ul className="mt-1 list-disc pl-5 text-xs text-ink-soft">
                          {e.form_cues.map((cue) => <li key={cue}>{cue}</li>)}
                        </ul>
                      </details>
                    )}
                  </li>
                ))}
              </ol>
            </li>
          ),
        )}
      </ol>
    </div>
  )
}

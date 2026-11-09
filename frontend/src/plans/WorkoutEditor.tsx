import { useState } from 'react'

import { FormError } from '../components/ui'
import { ApiError } from '../lib/api'
import { useApi } from '../lib/useApi'
import { ExercisePicker, type ExerciseChoice } from './ExercisePicker'
import { prescription, WEEKDAYS, type ActivePlan, type PlanDay } from './types'

const asApiError = (e: unknown) => (e instanceof ApiError ? e : new ApiError(0, 'Something went wrong. Please try again.'))

type Edit =
  | { op: 'move_day'; from_day: number; to_day: number }
  | { op: 'swap_exercise'; day: number; position: number; exercise_key: string }
  | { op: 'remove_exercise'; day: number; position: number }
  | { op: 'add_exercise'; day: number; exercise_key: string }

type Picker = { day: number; position: number | null; options: ExerciseChoice[] | null }

// Edit your own plan. Every change is sent to the server, which checks it (only exercises you may do, no duplicates, safe limits)
// and applies it at once. This screen only offers what the server says is valid and shows the server's message or refusal.
export function WorkoutEditor({ plan, onPlan }: { plan: ActivePlan; onPlan: (plan: ActivePlan) => void }) {
  const api = useApi()
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<ApiError | null>(null)
  const [picker, setPicker] = useState<Picker | null>(null)

  async function apply(edit: Edit) {
    setBusy(true)
    setError(null)
    try {
      const result = await api.post<{ message: string; plan: ActivePlan }>('/plans/workout/edit', edit)
      onPlan(result.plan)
      setMessage(result.message)
      setPicker(null)
    } catch (e) {
      setError(asApiError(e))
    } finally {
      setBusy(false)
    }
  }

  async function openPicker(day: number, position: number | null) {
    setPicker({ day, position, options: null })
    setError(null)
    try {
      const path = `/plans/workout/options?day=${day}${position ? `&position=${position}` : ''}`
      const result = await api.get<{ options: ExerciseChoice[] }>(path)
      setPicker({ day, position, options: result.options })
    } catch (e) {
      setError(asApiError(e))
      setPicker(null)
    }
  }

  const moveLabel = (target: PlanDay) => `${WEEKDAYS[target.day_of_week - 1]} (${target.is_rest ? 'rest day' : `swap with ${target.focus}`})`

  return (
    <div className="flex flex-col gap-3">
      <p className="text-xs text-muted">
        Changes apply right away. You can only pick exercises that suit your injuries, level and equipment.
      </p>
      {message && <p role="status" className="rounded-lg bg-brand-soft px-3 py-2 text-sm text-ink">{message}</p>}
      <FormError message={error?.message ?? null} requestId={error?.requestId} />
      <ol aria-label="Week" className="flex flex-col gap-2">
        {plan.days.map((day) =>
          day.is_rest ? (
            <li key={day.day_of_week} className="rounded-lg border border-dashed border-line px-3 py-2 text-sm text-muted">
              {WEEKDAYS[day.day_of_week - 1]}: rest
            </li>
          ) : (
            <li key={day.day_of_week} className="rounded-xl bg-surface-2 p-3">
              <div className="flex items-center justify-between gap-2">
                <h3 className="text-sm font-bold text-ink">
                  {WEEKDAYS[day.day_of_week - 1]}: {day.focus}
                  {day.minutes ? <span className="ml-2 text-xs font-normal text-muted">about {day.minutes} min</span> : null}
                </h3>
                <select
                  aria-label={`Move ${WEEKDAYS[day.day_of_week - 1]}`} value="" disabled={busy}
                  onChange={(e) => e.target.value && apply({ op: 'move_day', from_day: day.day_of_week, to_day: Number(e.target.value) })}
                  className="rounded-lg border border-line bg-surface px-2 py-1 text-xs"
                >
                  <option value="">Move to…</option>
                  {plan.days.filter((d) => d.day_of_week !== day.day_of_week).map((d) => (
                    <option key={d.day_of_week} value={d.day_of_week}>{moveLabel(d)}</option>
                  ))}
                </select>
              </div>
              <ol className="mt-2 flex flex-col gap-2">
                {day.exercises.map((e) => (
                  <li key={e.exercise_key} className="flex items-start justify-between gap-2">
                    <span>
                      <span className="block text-sm font-semibold text-ink">{e.name}</span>
                      <span className="block text-xs text-ink-soft">{prescription(e)}</span>
                    </span>
                    <span className="flex shrink-0 gap-3 text-xs font-semibold">
                      <button type="button" disabled={busy} aria-label={`Swap ${e.name}`} onClick={() => openPicker(day.day_of_week, e.position)} className="text-brand-strong disabled:opacity-50">Swap</button>
                      <button type="button" disabled={busy} aria-label={`Remove ${e.name}`} onClick={() => apply({ op: 'remove_exercise', day: day.day_of_week, position: e.position })} className="text-danger disabled:opacity-50">Remove</button>
                    </span>
                  </li>
                ))}
              </ol>
              {picker?.day === day.day_of_week ? (
                <ExercisePicker
                  title={picker.position ? 'Swap for…' : 'Add…'} options={picker.options} busy={busy} onCancel={() => setPicker(null)}
                  onPick={(key) => apply(picker.position
                    ? { op: 'swap_exercise', day: day.day_of_week, position: picker.position, exercise_key: key }
                    : { op: 'add_exercise', day: day.day_of_week, exercise_key: key })}
                />
              ) : (
                <button type="button" disabled={busy} onClick={() => openPicker(day.day_of_week, null)} className="mt-2 text-xs font-semibold text-brand-strong disabled:opacity-50">
                  + Add exercise to {WEEKDAYS[day.day_of_week - 1]}
                </button>
              )}
            </li>
          ),
        )}
      </ol>
    </div>
  )
}

// What the plan endpoints return (backend app/schemas/plans.py). day_of_week: 1 = Monday.

export type PlanExercise = {
  position: number
  exercise_key: string
  name: string
  sets: number
  reps_min: number
  reps_max: number
  rest_sec: number
  note: string | null
  form_cues?: string[] // only on the active plan, not on a proposal
}

export type PlanDay = {
  day_of_week: number
  focus: string | null
  is_rest: boolean
  minutes?: number | null // about how long the day takes
  exercises: PlanExercise[]
}

export type ActivePlan = { id: string; week_start: string; version: number; approved_at: string; days: PlanDay[] }

export type Proposal = {
  id: string
  type: string
  source: string
  summary: string
  status: string
  created_at: string
  payload: { split_name?: string; week_start?: string; doctor_note?: string | null; days?: PlanDay[] }
}

export const WEEKDAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

// The backend's standard reminder on every normal set; shown once at the top of the plan instead of on every line.
export const STANDARD_NOTE = 'Stop each set with 2 good reps left in the tank'

// "3 × 8-12 · rest 90 s", or for a hold "3 × Hold 30-45 seconds · rest 45 s" (a hold is time, not reps).
export function prescription(e: PlanExercise): string {
  const rest = e.rest_sec >= 60 && e.rest_sec % 60 === 0 ? `${e.rest_sec / 60} min` : `${e.rest_sec} s`
  const work = e.note?.startsWith('Hold') ? e.note : `${e.reps_min === e.reps_max ? e.reps_min : `${e.reps_min}-${e.reps_max}`} reps`
  return `${e.sets} × ${work} · rest ${rest}`
}

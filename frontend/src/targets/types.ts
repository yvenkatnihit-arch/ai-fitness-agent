// Mirrors backend/app/schemas/targets.py (TargetsOut). Numbers are null when focus_on_habits is true.
export type Targets = {
  calorie_target_kcal: number | null
  protein_g: number | null
  fat_g: number | null
  carbs_g: number | null
  // Each macro's share of daily calories; whole percentages that add up to 100 (backend-computed).
  protein_pct: number | null
  carbs_pct: number | null
  fat_pct: number | null
  reasons: string[]
  doctor_note: string | null
  focus_on_habits: boolean
}

// Mirrors backend/app/schemas/forecast.py. Dates are ISO strings (YYYY-MM-DD); the backend does all the maths.
export type Forecast = {
  status: 'ready' | 'no_target' | 'wrong_direction' | 'already_there' | 'not_moving' | 'too_far' | 'habits_only'
  message: string
  current_weight_kg: number | null
  target_weight_kg: number | null
  weekly_change_kg: number | null // negative = losing
  earliest: string | null
  likely: string | null
  latest: string | null
  weeks_likely: number | null
  note: string | null
}

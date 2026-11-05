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

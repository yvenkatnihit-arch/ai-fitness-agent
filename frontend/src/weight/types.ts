// Mirrors backend/app/schemas/weight.py (WeightOut). The backend works out every number; this only draws them.
export type WeightPoint = { date: string; weight_kg: number }

export type WeightHistory = {
  numbers_hidden: boolean // eating-disorder history: no weights are shown or tracked
  entries: WeightPoint[]
  latest_kg: number | null
  latest_on: string | null
  start_weight_kg: number | null
  target_weight_kg: number | null
  change_since_start_kg: number | null // negative = lost
  kg_to_target: number | null // negative = still above the target
  percent_to_target: number | null
  weekly_change_kg: number | null
}

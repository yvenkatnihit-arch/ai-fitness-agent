// Mirrors backend/app/schemas/dashboard.py (TodayOut). The backend does every sum and percentage; this only lays them out.
export type Progress = { eaten: number; target: number; percent: number }
export type ProgressOut = { kcal: Progress; protein_g: Progress; carbs_g: Progress; fat_g: Progress }
export type LoggedMeal = { slot: string; foods: string[] }
export type PlannedItem = { name: string; text: string; kcal: number | null }
export type PlannedMeal = { slot: string; items: PlannedItem[] }
export type PlanToday = { meals: PlannedMeal[]; kcal: number | null }
export type WorkoutToday = {
  rest_day: boolean
  focus: string | null
  minutes: number | null
  exercises: { name: string; sets: number; reps: string }[]
}
export type Today = {
  date: string
  weekday: string
  numbers_hidden: boolean
  progress: ProgressOut | null
  logged: LoggedMeal[]
  meal_plan: PlanToday | null
  workout: WorkoutToday | null
}

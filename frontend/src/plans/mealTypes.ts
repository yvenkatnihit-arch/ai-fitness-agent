// What the meal plan endpoints return (backend app/schemas/meal_plans.py and the proposal payload from
// app/calc/meal_plan_payload.py). day_of_week: 1 = Monday. Number fields are ABSENT for users who must not see
// numbers (eating-disorder history): the server removes them, so every number here is optional.

export type Totals = { kcal: number; protein_g: number; carbs_g: number; fat_g: number }

export type MealItemView = {
  position: number
  name: string
  text: string // "1.5 katori (225 g)"
  grams: number
  kcal?: number | null
  protein_g?: number | null
  carbs_g?: number | null
  fat_g?: number | null
}

export type MealView = { slot: string; items: MealItemView[] }
export type MealDayView = { day_of_week: number; totals?: Totals | null; meals: MealView[] }

export type Generation = { model_calls: number; input_tokens: number; output_tokens: number; cost_usd: number; latency_ms: number }

export type HowMade = {
  days_from_model: number
  days_from_code: number
  sources: string[]
  meals_per_day: number
  repair_round: boolean
  thin_roles: Record<string, string[]>
  generation: Generation | null
  checks: string[]
  days_ok?: number
  days_with_issues?: number
  average_percent_of_target?: { kcal: number; protein: number; carbs: number; fat: number }
  emphasis?: string | null
  portion_scale?: number
  protein_shortfall?: { percent: number; suggestions: string }
}

type PayloadItem = MealItemView & { slot: string }
type PayloadDay = { day_of_week: number; totals?: Totals | null; items: PayloadItem[] }

export type MealProposal = {
  id: string
  type: string
  source: string
  summary: string
  status: string
  created_at: string
  payload: {
    week_start?: string
    diet_type?: string
    numbers_hidden?: boolean
    targets?: Totals | null
    how_made?: HowMade | null
    days?: PayloadDay[]
  }
}

export type ActiveMealPlan = {
  id: string
  week_start: string
  version: number
  approved_at: string
  numbers_hidden: boolean
  targets?: Totals | null
  days: MealDayView[]
  how_made?: HowMade | null
}

export const SLOT_ORDER = ['breakfast', 'mid_morning', 'lunch', 'evening_snack', 'dinner']
export const SLOT_LABEL: Record<string, string> = {
  breakfast: 'Breakfast', mid_morning: 'Mid-morning', lunch: 'Lunch', evening_snack: 'Evening snack', dinner: 'Dinner',
}

// A proposal's payload lists items flat; the screen shows them grouped by meal, like the active plan.
export function daysFromPayload(days: PayloadDay[]): MealDayView[] {
  return days.map((day) => ({
    day_of_week: day.day_of_week,
    totals: day.totals ?? null,
    meals: SLOT_ORDER.filter((slot) => day.items.some((i) => i.slot === slot)).map((slot) => ({
      slot,
      items: day.items.filter((i) => i.slot === slot).sort((a, b) => a.position - b.position),
    })),
  }))
}

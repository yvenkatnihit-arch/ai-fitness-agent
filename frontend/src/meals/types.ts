// Mirrors backend/app/schemas/foods.py and backend/app/schemas/meals.py.

export type FoodUnit = { unit: string; grams: number }

export type FoodHit = {
  id: number
  key: string
  name: string
  local_names: string[]
  category: string | null
  diet_class: string
  is_dish: boolean
  kcal_per_100g: number
  protein_g_per_100g: number
  carbs_g_per_100g: number
  fat_g_per_100g: number
  fiber_g_per_100g: number | null
  verified: boolean // false = values still being checked
  units: FoodUnit[]
}

export type Slot = 'breakfast' | 'mid_morning' | 'lunch' | 'evening_snack' | 'dinner' | 'other'

export const SLOTS: { value: Slot; label: string }[] = [
  { value: 'breakfast', label: 'Breakfast' },
  { value: 'mid_morning', label: 'Mid-morning' },
  { value: 'lunch', label: 'Lunch' },
  { value: 'evening_snack', label: 'Evening snack' },
  { value: 'dinner', label: 'Dinner' },
  { value: 'other', label: 'Other' },
]

export type Nutrition = { kcal: number; protein_g: number; carbs_g: number; fat_g: number }

export type MealItem = Nutrition & {
  id: number
  food_id: number
  food_name: string
  quantity: number
  unit: string
  grams: number
}

export type Meal = { id: string; logged_on: string; slot: Slot; source: string; items: MealItem[]; totals: Nutrition }

export type Day = { logged_on: string; meals: Meal[]; totals: Nutrition }

// One line of the meal being built (not saved yet). Only food + amount: the backend computes nutrition.
export type DraftItem = { food: FoodHit; quantity: number; unit: string }

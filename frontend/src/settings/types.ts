import type { Targets } from '../targets/types'

// Mirrors backend/app/schemas/profile.py. Every answer from onboarding, by name.
export type Profile = {
  display_name: string | null
  date_of_birth: string
  sex: string
  height_cm: number
  weight_kg: number
  activity_level: string
  goal_type: string
  target_weight_kg: number | null
  pace: string
  diet_type: string
  cuisines: string[]
  disliked_foods: string[]
  experience_level: string
  workout_location: string
  equipment: string[]
  days_per_week: number
  session_minutes: number | null
  pregnant_or_breastfeeding: boolean
  diabetes: boolean
  heart_or_bp: boolean
  kidney: boolean
  recent_surgery_or_injury: boolean
  eating_disorder_history: boolean
  injury_areas: string[]
}

export type ProfileUpdate = {
  profile: Profile
  changed: string[]
  targets_recalculated: boolean
  targets: Targets | null
  workout_plan_stale: boolean
  meal_plan_stale: boolean
  messages: string[]
}

export type Changes = Partial<Record<keyof Profile, unknown>>

// Only what the person really changed: that is all we send (the server ignores unchanged values anyway).
export function changedFields(before: Profile, draft: Partial<Profile>): Changes {
  const changes: Changes = {}
  for (const key of Object.keys(draft) as (keyof Profile)[]) {
    if (JSON.stringify(draft[key]) !== JSON.stringify(before[key])) changes[key] = draft[key]
  }
  return changes
}

// "karela, Bhindi ,," -> ['karela', 'Bhindi']
export const parseList = (text: string): string[] => text.split(',').map((s) => s.trim()).filter(Boolean)

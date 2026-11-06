// Mirrors backend/app/schemas/exercises.py.

export type Setting = 'gym' | 'home'

export type Exercise = {
  id: number
  key: string
  name: string
  muscle_groups: string[] // the first one is the main muscle
  equipment: string[] // empty = bodyweight only
  location: string
  difficulty: string
  movement_pattern: string
  form_cues: string[]
  verified: boolean // false = injury tags not signed off yet
}

export type ExerciseList = {
  setting: Setting
  level: string
  injuries: string[]
  total_in_library: number
  shown: number
  exercises: Exercise[]
}

// "lower_back" -> "lower back", "leg_press_machine" -> "leg press machine"
export const words = (value: string) => value.replaceAll('_', ' ')

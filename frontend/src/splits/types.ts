// Mirrors backend/app/schemas/splits.py.

export type SplitDay = { label: string; muscles: string[]; patterns: string[] }

export type Fit = 'best' | 'good' | 'possible'

export type Recommendation = {
  key: string
  name: string
  summary: string
  fit: Fit
  training_days: number
  recovery_days: number // easy days on top of the training days (1 when you train 7 days)
  muscle_frequency: number
  reasons: string[]
  cautions: string[]
  schedule: SplitDay[]
}

export type SplitRecommendations = {
  days_per_week: number
  level: string
  goal: string
  chosen_key: string | null
  recommendations: Recommendation[]
}

export const FIT_LABEL: Record<Fit, string> = { best: 'Best match', good: 'Good fit', possible: 'Possible' }
export const FIT_STYLE: Record<Fit, string> = {
  best: 'bg-brand-soft text-brand-strong',
  good: 'bg-surface-2 text-ink-soft',
  possible: 'bg-warn-soft text-warn',
}

export const GOAL_LABEL: Record<string, string> = {
  fat_loss: 'fat loss', muscle_gain: 'muscle gain', weight_gain: 'weight gain', recomp: 'recomposition',
  general_fitness: 'general fitness',
}

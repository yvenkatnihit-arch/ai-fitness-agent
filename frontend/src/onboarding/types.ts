// Mirrors the backend's app/schemas/onboarding_status.py.
export type StepName = 'consent' | 'basics' | 'goal' | 'preferences' | 'training' | 'screening'

export type OnboardingStatus = Record<StepName, boolean> & {
  completed: boolean
  next_step: StepName | 'complete' | 'done'
}

export const STEPS: StepName[] = ['consent', 'basics', 'goal', 'preferences', 'training', 'screening']

// Props every step screen gets: save via the API, then hand the new status back.
export type StepProps = { onSaved: (status: OnboardingStatus) => void }

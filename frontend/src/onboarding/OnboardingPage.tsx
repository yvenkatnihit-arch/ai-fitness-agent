import { useEffect, useState, type JSX, type ReactNode } from 'react'
import { Navigate } from 'react-router'

import { BrandMark, Card, FormError } from '../components/ui'
import { ApiError } from '../lib/api'
import { useApi } from '../lib/useApi'
import { BasicsStep } from './BasicsStep'
import { ConsentStep } from './ConsentStep'
import { FinishStep } from './FinishStep'
import { GoalStep } from './GoalStep'
import { PreferencesStep } from './PreferencesStep'
import { ScreeningStep } from './ScreeningStep'
import { TrainingStep } from './TrainingStep'
import { STEPS, type OnboardingStatus, type StepName, type StepProps } from './types'

const SCREENS: Record<StepName, (props: StepProps) => JSX.Element> = {
  consent: ConsentStep,
  basics: BasicsStep,
  goal: GoalStep,
  preferences: PreferencesStep,
  training: TrainingStep,
  screening: ScreeningStep,
}

export function OnboardingPage() {
  const api = useApi()
  const [status, setStatus] = useState<OnboardingStatus | null>(null)
  const [error, setError] = useState<ApiError | null>(null)

  useEffect(() => {
    api.get<OnboardingStatus>('/onboarding/status').then(setStatus, setError)
  }, [api])

  if (error) {
    return (
      <Shell>
        <Card title="Couldn't load your progress">
          <FormError message={error.message} requestId={error.requestId} />
        </Card>
      </Shell>
    )
  }
  if (!status) return <Shell><p className="text-sm text-muted">Loading…</p></Shell>
  if (status.next_step === 'done') return <Navigate to="/" replace />

  if (status.next_step === 'complete') {
    return <Shell><FinishStep /></Shell>
  }

  const Screen = SCREENS[status.next_step]
  return (
    <Shell>
      <StepProgress current={STEPS.indexOf(status.next_step) + 1} total={STEPS.length} />
      <Screen onSaved={setStatus} />
    </Shell>
  )
}

// "Step 2 of 6" in words, with one lime segment per step reached (the words are what screen readers and tests read).
function StepProgress({ current, total }: { current: number; total: number }) {
  return (
    <div className="mb-4 flex w-full max-w-md flex-col gap-2">
      <div
        role="progressbar" aria-label="Onboarding progress" aria-valuemin={1} aria-valuemax={total} aria-valuenow={current}
        className="flex gap-1.5"
      >
        {Array.from({ length: total }, (_, i) => (
          <span key={i} className={`h-1.5 flex-1 rounded-full transition-colors ${i < current ? 'bg-brand' : 'bg-surface-2'}`} />
        ))}
      </div>
      <p className="text-xs font-medium uppercase tracking-wide text-muted">
        Step {current} of {total}
      </p>
    </div>
  )
}

function Shell({ children }: { children: ReactNode }) {
  return (
    <main className="page-glow flex min-h-screen flex-col items-center gap-6 px-4 py-10">
      <BrandMark />
      <div className="flex w-full flex-col items-center">{children}</div>
    </main>
  )
}

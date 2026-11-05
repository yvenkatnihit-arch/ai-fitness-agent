import { useEffect, useState, type JSX, type ReactNode } from 'react'
import { Navigate } from 'react-router'

import { Card, FormError } from '../components/ui'
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
  if (!status) return <Shell><p className="text-sm text-slate-500">Loading…</p></Shell>
  if (status.next_step === 'done') return <Navigate to="/" replace />

  if (status.next_step === 'complete') {
    return <Shell><FinishStep /></Shell>
  }

  const Screen = SCREENS[status.next_step]
  return (
    <Shell>
      <p className="mb-3 text-xs font-medium uppercase tracking-wide text-slate-500">
        Step {STEPS.indexOf(status.next_step) + 1} of {STEPS.length}
      </p>
      <Screen onSaved={setStatus} />
    </Shell>
  )
}

function Shell({ children }: { children: ReactNode }) {
  return <main className="flex min-h-screen flex-col items-center bg-slate-50 px-4 py-10">{children}</main>
}

import { useState } from 'react'
import { useNavigate } from 'react-router'

import { Card, FormError, PrimaryButton } from '../components/ui'
import { ApiError } from '../lib/api'
import { useApi } from '../lib/useApi'

// All forms are saved: ask the backend to calculate the targets (no AI involved).
export function FinishStep() {
  const api = useApi()
  const navigate = useNavigate()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)

  async function finish() {
    setBusy(true)
    setError(null)
    try {
      await api.post('/onboarding/complete')
      navigate('/', { replace: true })
    } catch (e) {
      setError(e instanceof ApiError ? e : new ApiError(0, 'Something went wrong. Please try again.'))
      setBusy(false)
    }
  }

  return (
    <Card title="All set" subtitle="We'll work out your daily calories and protein, carbs and fat.">
      <div className="flex flex-col gap-3">
        <FormError message={error?.message ?? null} requestId={error?.requestId} />
        <PrimaryButton type="button" onClick={finish} busy={busy}>Calculate my targets</PrimaryButton>
      </div>
    </Card>
  )
}

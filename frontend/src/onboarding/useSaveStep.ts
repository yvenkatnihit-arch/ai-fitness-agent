import { useState } from 'react'

import { ApiError } from '../lib/api'
import { useApi } from '../lib/useApi'
import type { OnboardingStatus } from './types'

// Save one onboarding form: PUT the body, hand the new status back, keep busy/error state.
export function useSaveStep(path: string, onSaved: (status: OnboardingStatus) => void) {
  const api = useApi()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)

  async function save(body: unknown) {
    setBusy(true)
    setError(null)
    try {
      onSaved(await api.put<OnboardingStatus>(path, body))
    } catch (e) {
      setError(e instanceof ApiError ? e : new ApiError(0, 'Something went wrong. Please try again.'))
    } finally {
      setBusy(false)
    }
  }

  return { save, busy, error, fieldError: (field: string) => error?.fieldErrors[field] }
}

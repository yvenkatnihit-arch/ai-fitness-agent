import { useMemo } from 'react'

import { useAuth } from '../auth/context'
import { createApi, type Api } from './api'

// The API helper for the signed-in user. Rebuilt when Supabase refreshes the token.
export function useApi(): Api {
  const { session } = useAuth()
  const token = session?.access_token ?? null
  return useMemo(() => createApi(token), [token])
}

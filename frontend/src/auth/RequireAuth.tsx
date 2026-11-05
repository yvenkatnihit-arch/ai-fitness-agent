import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router'

import { useAuth } from './context'

// Wrap any page that needs a signed-in user. Signed-out visitors go to /sign-in,
// and come back to the page they wanted after signing in.
export function RequireAuth({ children }: { children: ReactNode }) {
  const { session, loading } = useAuth()
  const location = useLocation()

  if (loading) {
    return <p className="p-6 text-center text-sm text-slate-500">Loading…</p>
  }
  if (!session) {
    return <Navigate to="/sign-in" replace state={{ from: location.pathname }} />
  }
  return <>{children}</>
}

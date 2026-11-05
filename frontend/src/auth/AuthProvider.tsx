import type { Session } from '@supabase/supabase-js'
import { useEffect, useMemo, useState, type ReactNode } from 'react'

import { supabase } from '../lib/supabase'
import { AuthContext, type Auth } from './context'
import { friendlyAuthError } from './messages'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // 1. A session saved from an earlier visit (if any).
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session)
      setLoading(false)
    })
    // 2. Every later change: sign in, sign out, background token refresh.
    const { data } = supabase.auth.onAuthStateChange((_event, next) => setSession(next))
    return () => data.subscription.unsubscribe()
  }, [])

  const auth = useMemo<Auth>(
    () => ({
      session,
      loading,
      async signIn(email, password) {
        const { error } = await supabase.auth.signInWithPassword({ email, password })
        return error ? friendlyAuthError(error) : null
      },
      async signUp(email, password) {
        const { data, error } = await supabase.auth.signUp({ email, password })
        if (error) return { error: friendlyAuthError(error), needsEmailConfirmation: false }
        // With email confirmation on (D-031: off for now), Supabase returns a user but no session.
        return { error: null, needsEmailConfirmation: data.session === null }
      },
      async signOut() {
        await supabase.auth.signOut()
      },
    }),
    [session, loading],
  )

  return <AuthContext.Provider value={auth}>{children}</AuthContext.Provider>
}

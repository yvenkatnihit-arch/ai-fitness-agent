// What the rest of the app knows about login. Kept separate from AuthProvider so pages
// (and their tests) don't import the Supabase client.
import type { Session } from '@supabase/supabase-js'
import { createContext, useContext } from 'react'

export type SignUpResult = { error: string | null; needsEmailConfirmation: boolean }

export type Auth = {
  session: Session | null
  loading: boolean // true until we know whether a saved session exists
  signIn: (email: string, password: string) => Promise<string | null> // error message or null
  signUp: (email: string, password: string) => Promise<SignUpResult>
  signOut: () => Promise<void>
}

export const AuthContext = createContext<Auth | null>(null)

export function useAuth(): Auth {
  const auth = useContext(AuthContext)
  if (!auth) throw new Error('useAuth must be used inside <AuthProvider>')
  return auth
}

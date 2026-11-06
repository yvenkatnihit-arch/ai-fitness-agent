import { useState, type FormEvent } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router'

import { useAuth } from '../auth/context'
import { MIN_PASSWORD_LENGTH } from '../auth/messages'

type Mode = 'sign-in' | 'sign-up'

export function SignInPage() {
  const { session, signIn, signUp } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const goTo = (location.state as { from?: string } | null)?.from ?? '/'

  const [mode, setMode] = useState<Mode>('sign-in')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  if (session) return <Navigate to={goTo} replace />

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    setNotice(null)
    if (mode === 'sign-up' && password.length < MIN_PASSWORD_LENGTH) {
      setError(`Password must be at least ${MIN_PASSWORD_LENGTH} characters.`)
      return
    }
    setBusy(true)
    try {
      if (mode === 'sign-in') {
        const problem = await signIn(email.trim(), password)
        if (problem) setError(problem)
        else navigate(goTo, { replace: true })
      } else {
        const result = await signUp(email.trim(), password)
        if (result.error) setError(result.error)
        else if (result.needsEmailConfirmation) setNotice('Check your email for a link to confirm your account.')
        else navigate('/', { replace: true })
      }
    } finally {
      setBusy(false)
    }
  }

  function switchMode() {
    setMode(mode === 'sign-in' ? 'sign-up' : 'sign-in')
    setError(null)
    setNotice(null)
  }

  const isSignIn = mode === 'sign-in'

  return (
    <main className="flex min-h-screen items-center justify-center bg-bg px-4">
      <div className="w-full max-w-sm rounded-2xl bg-surface p-6 shadow-sm">
        <h1 className="text-2xl font-bold text-ink">{isSignIn ? 'Welcome back' : 'Create your account'}</h1>
        <p className="mt-1 text-sm text-muted">AI Fitness Coach</p>

        <form className="mt-6 flex flex-col gap-4" onSubmit={handleSubmit} noValidate>
          <label className="flex flex-col gap-1 text-sm font-medium text-ink-soft">
            Email
            <input
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="rounded-lg border border-line px-3 py-2 text-base font-normal focus:border-brand focus:outline-none"
            />
          </label>
          <label className="flex flex-col gap-1 text-sm font-medium text-ink-soft">
            Password
            <input
              type="password"
              autoComplete={isSignIn ? 'current-password' : 'new-password'}
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="rounded-lg border border-line px-3 py-2 text-base font-normal focus:border-brand focus:outline-none"
            />
            {!isSignIn && (
              <span className="text-xs font-normal text-muted">At least {MIN_PASSWORD_LENGTH} characters.</span>
            )}
          </label>

          {error && (
            <p role="alert" className="rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">
              {error}
            </p>
          )}
          {notice && (
            <p role="status" className="rounded-lg bg-brand-soft px-3 py-2 text-sm text-brand-strong">
              {notice}
            </p>
          )}

          <button
            type="submit"
            disabled={busy || !email || !password}
            className="rounded-lg bg-brand px-4 py-2.5 font-semibold text-on-brand disabled:opacity-50"
          >
            {busy ? 'Please wait…' : isSignIn ? 'Sign in' : 'Create account'}
          </button>
        </form>

        <button type="button" onClick={switchMode} className="mt-4 w-full text-center text-sm text-brand-strong">
          {isSignIn ? "New here? Create an account" : 'Already have an account? Sign in'}
        </button>
      </div>
      <Link to="/sources" className="mt-4 text-xs text-muted underline">Data sources</Link>
    </main>
  )
}

// Render a page with a fake login state, so tests never touch Supabase.
import type { Session } from '@supabase/supabase-js'
import { render } from '@testing-library/react'
import type { ReactNode } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router'
import { vi } from 'vitest'

import { AuthContext, type Auth } from '../auth/context'

export function fakeSession(email = 'test@example.test'): Session {
  return { user: { email } } as unknown as Session
}

export function fakeAuth(overrides: Partial<Auth> = {}): Auth {
  return {
    session: null,
    loading: false,
    signIn: vi.fn(async () => null),
    signUp: vi.fn(async () => ({ error: null, needsEmailConfirmation: false })),
    signOut: vi.fn(async () => {}),
    ...overrides,
  }
}

// `routes` maps paths to elements; the test starts at `start`.
export function renderWithAuth(auth: Auth, routes: Record<string, ReactNode>, start = '/') {
  return render(
    <AuthContext.Provider value={auth}>
      <MemoryRouter initialEntries={[start]}>
        <Routes>
          {Object.entries(routes).map(([path, element]) => (
            <Route key={path} path={path} element={element} />
          ))}
        </Routes>
      </MemoryRouter>
    </AuthContext.Provider>,
  )
}

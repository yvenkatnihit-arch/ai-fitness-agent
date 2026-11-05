import { screen } from '@testing-library/react'
import { expect, test } from 'vitest'

import { fakeAuth, fakeSession, renderWithAuth } from '../test/fakeAuth'
import { RequireAuth } from './RequireAuth'

const routes = {
  '/private': (
    <RequireAuth>
      <p>secret page</p>
    </RequireAuth>
  ),
  '/sign-in': <p>sign-in page</p>,
}

test('waits while the saved session is being checked', () => {
  renderWithAuth(fakeAuth({ loading: true }), routes, '/private')
  expect(screen.getByText('Loading…')).toBeInTheDocument()
  expect(screen.queryByText('secret page')).not.toBeInTheDocument()
})

test('redirects signed-out visitors to sign-in', () => {
  renderWithAuth(fakeAuth(), routes, '/private')
  expect(screen.getByText('sign-in page')).toBeInTheDocument()
  expect(screen.queryByText('secret page')).not.toBeInTheDocument()
})

test('shows the page to signed-in users', () => {
  renderWithAuth(fakeAuth({ session: fakeSession() }), routes, '/private')
  expect(screen.getByText('secret page')).toBeInTheDocument()
})

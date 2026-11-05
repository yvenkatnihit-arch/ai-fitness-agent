import { fireEvent, screen, waitFor } from '@testing-library/react'
import { expect, test, vi } from 'vitest'

import { fakeAuth, renderWithAuth } from '../test/fakeAuth'
import { SignInPage } from './SignInPage'

const routes = { '/sign-in': <SignInPage />, '/': <p>home page</p> }

function fillIn(email: string, password: string) {
  fireEvent.change(screen.getByLabelText('Email'), { target: { value: email } })
  fireEvent.change(screen.getByLabelText(/^Password/), { target: { value: password } })
}

test('signs in and goes home', async () => {
  const auth = fakeAuth()
  renderWithAuth(auth, routes, '/sign-in')
  fillIn('  me@example.test ', 'correct-horse')
  fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))

  await waitFor(() => expect(screen.getByText('home page')).toBeInTheDocument())
  expect(auth.signIn).toHaveBeenCalledWith('me@example.test', 'correct-horse') // email trimmed
})

test('shows the error when sign-in fails', async () => {
  renderWithAuth(fakeAuth({ signIn: vi.fn(async () => 'Email or password is incorrect.') }), routes, '/sign-in')
  fillIn('me@example.test', 'wrong-password')
  fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))

  expect(await screen.findByRole('alert')).toHaveTextContent('Email or password is incorrect.')
})

test('sign-up refuses a short password before calling Supabase', async () => {
  const auth = fakeAuth()
  renderWithAuth(auth, routes, '/sign-in')
  fireEvent.click(screen.getByRole('button', { name: /Create an account/ }))
  fillIn('me@example.test', 'short')
  fireEvent.click(screen.getByRole('button', { name: 'Create account' }))

  expect(await screen.findByRole('alert')).toHaveTextContent('at least 8 characters')
  expect(auth.signUp).not.toHaveBeenCalled()
})

test('sign-up asks to check email when confirmation is on', async () => {
  const signUp = vi.fn(async () => ({ error: null, needsEmailConfirmation: true }))
  renderWithAuth(fakeAuth({ signUp }), routes, '/sign-in')
  fireEvent.click(screen.getByRole('button', { name: /Create an account/ }))
  fillIn('me@example.test', 'long-enough-pw')
  fireEvent.click(screen.getByRole('button', { name: 'Create account' }))

  expect(await screen.findByRole('status')).toHaveTextContent('Check your email')
})

test('the submit button stays disabled until both fields are filled', () => {
  renderWithAuth(fakeAuth(), routes, '/sign-in')
  expect(screen.getByRole('button', { name: 'Sign in' })).toBeDisabled()
  fillIn('me@example.test', 'x')
  expect(screen.getByRole('button', { name: 'Sign in' })).toBeEnabled()
})

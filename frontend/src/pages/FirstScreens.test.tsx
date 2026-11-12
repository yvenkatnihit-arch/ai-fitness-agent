import { fireEvent, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import { fakeAuth, fakeSession, renderWithAuth } from '../test/fakeAuth'
import { fakeFetch, status } from '../test/fakeFetch'
import { OnboardingPage } from '../onboarding/OnboardingPage'
import { SignInPage } from './SignInPage'

afterEach(() => vi.unstubAllGlobals())

test('sign-in shows the app mark and what the app is, and switching to sign-up changes the welcome text', () => {
  renderWithAuth(fakeAuth(), { '/sign-in': <SignInPage /> }, '/sign-in')
  expect(screen.getByText('AI Fitness Coach')).toBeInTheDocument()
  expect(screen.getByText(/safety limits the AI cannot change/)).toBeInTheDocument()
  expect(screen.getByRole('heading', { name: 'Welcome back' })).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: /Create an account/ }))
  expect(screen.getByRole('heading', { name: 'Create your account' })).toBeInTheDocument()
  expect(screen.getByText('It takes about two minutes to set up.')).toBeInTheDocument()
})

test('the sign-in fields use the shared dark input style and the data-sources link is still there', () => {
  renderWithAuth(fakeAuth(), { '/sign-in': <SignInPage /> }, '/sign-in')
  expect(screen.getByLabelText('Email').className).toContain('bg-surface-2')
  expect(screen.getByLabelText(/^Password/).className).toContain('bg-surface-2')
  expect(screen.getByRole('link', { name: 'Data sources' })).toHaveAttribute('href', '/sources')
})

test('onboarding shows a progress bar with one segment per step, matching the "Step N of 6" words', async () => {
  fakeFetch({ 'GET /onboarding/status': { body: status('goal', ['consent', 'basics']) } })
  renderWithAuth(fakeAuth({ session: { ...fakeSession(), access_token: 'tok' } as never }), { '/onboarding': <OnboardingPage /> }, '/onboarding')
  expect(await screen.findByText('Step 3 of 6')).toBeInTheDocument()
  const bar = screen.getByRole('progressbar', { name: 'Onboarding progress' })
  expect(bar).toHaveAttribute('aria-valuenow', '3')
  expect(bar).toHaveAttribute('aria-valuemax', '6')
  expect(bar.children).toHaveLength(6)
  expect([...bar.children].filter((c) => c.className.includes('bg-brand'))).toHaveLength(3)
})

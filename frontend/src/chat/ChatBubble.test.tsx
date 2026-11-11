import { screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import App from '../App'
import { fakeAuth, fakeSession, renderWithAuth } from '../test/fakeAuth'
import { fakeFetch, status } from '../test/fakeFetch'

afterEach(() => vi.unstubAllGlobals())

const TARGETS = {
  calorie_target_kcal: 1640, protein_g: 116, fat_g: 46, carbs_g: 189, protein_pct: 28, carbs_pct: 46, fat_pct: 26,
  reasons: [], doctor_note: null, focus_on_habits: false,
}
const signedIn = () => fakeAuth({ session: fakeSession() })
const home = () => fakeFetch({ 'GET /onboarding/status': { body: status('done', [], true) }, 'GET /targets/current': { body: TARGETS } })

test('signed-in screens have a floating "Chat with the coach" button that opens the chat', async () => {
  home()
  renderWithAuth(signedIn(), { '*': <App /> }, '/')
  await screen.findByText('1,640')
  const bubble = screen.getByRole('link', { name: 'Chat with the coach' })
  expect(bubble).toHaveAttribute('href', '/chat')
  expect(bubble.className).toContain('rounded-full')                                          // a round bubble, not a normal button
})

test('the chat screen itself has no bubble (you are already there)', async () => {
  fakeFetch({})
  renderWithAuth(signedIn(), { '*': <App /> }, '/chat')
  expect(await screen.findByRole('heading', { name: 'Coach chat' })).toBeInTheDocument()
  expect(screen.queryByRole('link', { name: 'Chat with the coach' })).not.toBeInTheDocument()
})

test('onboarding has no bubble: finish setting up first', async () => {
  fakeFetch({ 'GET /onboarding/status': { body: status('consent') } })
  renderWithAuth(signedIn(), { '*': <App /> }, '/onboarding')
  await screen.findByRole('heading', { name: 'Before we start' })
  expect(screen.queryByRole('link', { name: 'Chat with the coach' })).not.toBeInTheDocument()
})

test('signed-out visitors never see it', () => {
  renderWithAuth(fakeAuth(), { '*': <App /> }, '/')
  expect(screen.queryByRole('link', { name: 'Chat with the coach' })).not.toBeInTheDocument()
})

test('the old text button on Home is gone (the bubble replaces it)', async () => {
  home()
  renderWithAuth(signedIn(), { '*': <App /> }, '/')
  await screen.findByText('1,640')
  expect(screen.getAllByRole('link', { name: /chat with the coach/i })).toHaveLength(1)        // only the bubble
})

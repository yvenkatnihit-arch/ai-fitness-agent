import { screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import App from './App'
import { fakeAuth, fakeSession, renderWithAuth } from './test/fakeAuth'
import { fakeFetch, status } from './test/fakeFetch'

afterEach(() => vi.unstubAllGlobals())

test('signed-out visitors are sent to the sign-in page', () => {
  renderWithAuth(fakeAuth(), { '*': <App /> }, '/')
  expect(screen.getByRole('heading', { name: 'Welcome back' })).toBeInTheDocument()
})

const TARGETS = {
  calorie_target_kcal: 1640, protein_g: 116, fat_g: 46, carbs_g: 189,
  reasons: [], doctor_note: null, focus_on_habits: false,
}

test('signed-in users who finished onboarding see their daily targets', async () => {
  fakeFetch({
    'GET /onboarding/status': { body: status('done', [], true) },
    'GET /targets/current': { body: TARGETS },
  })
  renderWithAuth(fakeAuth({ session: fakeSession('kruthi@example.test') }), { '*': <App /> }, '/')
  expect(await screen.findByText('1,640')).toBeInTheDocument()
  expect(screen.getByText('kruthi@example.test')).toBeInTheDocument()
})

test('a failed targets request shows the error with its reference', async () => {
  fakeFetch({
    'GET /onboarding/status': { body: status('done', [], true) },
    'GET /targets/current': { status: 500, body: { detail: 'Something went wrong on our side. Please try again.', request_id: 'req-77' } },
  })
  renderWithAuth(fakeAuth({ session: fakeSession() }), { '*': <App /> }, '/')
  expect(await screen.findByRole('alert')).toHaveTextContent('Reference: req-77')
})

test('signed-in users who have not finished are sent to onboarding', async () => {
  fakeFetch({ 'GET /onboarding/status': { body: status('consent') } })
  renderWithAuth(fakeAuth({ session: fakeSession() }), { '*': <App /> }, '/')
  expect(await screen.findByRole('heading', { name: 'Before we start' })).toBeInTheDocument()
})

test('unknown pages go home', async () => {
  fakeFetch({
    'GET /onboarding/status': { body: status('done', [], true) },
    'GET /targets/current': { body: TARGETS },
  })
  renderWithAuth(fakeAuth({ session: fakeSession() }), { '*': <App /> }, '/no-such-page')
  expect(await screen.findByText('1,640')).toBeInTheDocument()
})

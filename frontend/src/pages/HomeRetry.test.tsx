import { fireEvent, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import App from '../App'
import { fakeAuth, fakeSession, renderWithAuth } from '../test/fakeAuth'
import { fakeFetch, status } from '../test/fakeFetch'

afterEach(() => vi.unstubAllGlobals())

const TARGETS = {
  calorie_target_kcal: 1408, protein_g: 116, fat_g: 39, carbs_g: 148, protein_pct: 33, carbs_pct: 42, fat_pct: 25,
  reasons: [], doctor_note: null, focus_on_habits: false,
}
const render = () => renderWithAuth(fakeAuth({ session: fakeSession('kruthi@example.test') }), { '*': <App /> }, '/')

test('when Home cannot load, "Try again" loads it again and the page appears without a refresh', async () => {
  let attempts = 0
  const calls = fakeFetch({
    'GET /onboarding/status': () => { attempts += 1; return attempts === 1 ? { status: 503, body: { detail: 'The server is waking up. Please try again.', request_id: 'r-1' } } : { body: status('done', [], true) } },
    'GET /targets/current': { body: TARGETS },
  })
  render()
  expect(await screen.findByRole('alert')).toHaveTextContent('waking up')
  fireEvent.click(screen.getByRole('button', { name: 'Try again' }))
  expect(await screen.findByText('1,408')).toBeInTheDocument()
  expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Try again' })).not.toBeInTheDocument()
  expect(calls.filter((c) => c.path === '/onboarding/status')).toHaveLength(2)
})

test('a dropped connection is retryable too', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => { throw new TypeError('network down') }))
  render()
  expect(await screen.findByRole('button', { name: 'Try again' })).toBeInTheDocument()
})

test('an error that retrying cannot fix (a refused request) shows no Try again button', async () => {
  fakeFetch({ 'GET /onboarding/status': { status: 403, body: { detail: 'You do not have access to this.', request_id: 'r-2' } } })
  render()
  expect(await screen.findByRole('alert')).toHaveTextContent('do not have access')
  expect(screen.queryByRole('button', { name: 'Try again' })).not.toBeInTheDocument()
})

test('if it keeps failing, the button stays so the person can try as often as they like', async () => {
  fakeFetch({ 'GET /onboarding/status': { status: 500, body: { detail: 'Something went wrong on our side.' } } })
  render()
  fireEvent.click(await screen.findByRole('button', { name: 'Try again' }))
  expect(await screen.findByRole('button', { name: 'Try again' })).toBeInTheDocument()
})

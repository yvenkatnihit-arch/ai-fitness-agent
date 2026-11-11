import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import App from '../App'
import { fakeAuth, fakeSession, renderWithAuth } from '../test/fakeAuth'
import { fakeFetch, status } from '../test/fakeFetch'
import type { WeightHistory } from './types'

afterEach(() => vi.unstubAllGlobals())

const TARGETS = {
  calorie_target_kcal: 1408, protein_g: 116, fat_g: 39, carbs_g: 148, protein_pct: 33, carbs_pct: 42, fat_pct: 25,
  reasons: [], doctor_note: null, focus_on_habits: false,
}
const FORECAST = { status: 'no_target', message: 'Set a target weight to see a goal date.', current_weight_kg: null, target_weight_kg: null,
  weekly_change_kg: null, earliest: null, likely: null, latest: null, weeks_likely: null, note: null }

const HISTORY: WeightHistory = {
  numbers_hidden: false, latest_kg: 57, latest_on: '2026-11-11', start_weight_kg: 58, target_weight_kg: 54,
  change_since_start_kg: -1, kg_to_target: -3, percent_to_target: 25, weekly_change_kg: -1.75,
  entries: [{ date: '2026-11-01', weight_kg: 58 }, { date: '2026-11-06', weight_kg: 57.5 }, { date: '2026-11-11', weight_kg: 57 }],
}

const signedIn = () => fakeAuth({ session: fakeSession('kruthi@example.test') })
type Reply = { status?: number; body: unknown }
function home(weight: Reply, extra: Record<string, Reply> = {}) {
  return fakeFetch({
    'GET /onboarding/status': { body: status('done', [], true) },
    'GET /targets/current': { body: TARGETS },
    'GET /targets/forecast': { body: FORECAST },
    'GET /weight': weight,
    ...extra,
  })
}
const render = () => renderWithAuth(signedIn(), { '*': <App /> }, '/')

test('Home shows the weight card: latest weight, a chart with a text version, progress to the target and what changed', async () => {
  home({ body: HISTORY })
  render()
  const card = await screen.findByRole('region', { name: 'Weight' })
  expect(within(card).getByText('57')).toBeInTheDocument()
  const chart = within(card).getByRole('img', { name: /Weight chart: 58 kg on 1 Nov, 57 kg on 11 Nov, target 54 kg/ })
  expect(chart.querySelectorAll('circle')).toHaveLength(3)                                      // one point per weigh-in
  const bar = within(card).getByRole('progressbar', { name: 'Progress to your target weight' })
  expect(bar).toHaveAttribute('aria-valuenow', '25')
  expect(card).toHaveTextContent('Down 1 kg since you started.')
  expect(card).toHaveTextContent('3 kg above your target.')
  expect(card).toHaveTextContent('About 1.75 kg a week down over this period.')
})

test('logging a weight sends only the number, shows the new trend and asks for the goal date again', async () => {
  let forecastCalls = 0
  const calls = home({ body: HISTORY }, {
    'POST /weight': { body: { ...HISTORY, latest_kg: 56.4, change_since_start_kg: -1.6, kg_to_target: -2.4, percent_to_target: 40 } },
  })
  render()
  const card = await screen.findByRole('region', { name: 'Weight' })
  fireEvent.change(within(card).getByLabelText("Today's weight (kg)"), { target: { value: '56.4' } })
  fireEvent.click(within(card).getByRole('button', { name: 'Log weight' }))
  await waitFor(() => expect(within(card).getByText('56.4')).toBeInTheDocument())
  expect(calls.find((c) => c.method === 'POST')!.body).toEqual({ weight_kg: 56.4 })
  expect(card).toHaveTextContent('Down 1.6 kg since you started.')
  forecastCalls = calls.filter((c) => c.method === 'GET' && c.path === '/targets/forecast').length
  expect(forecastCalls).toBeGreaterThanOrEqual(2)                                                // once on arrival, once after the weigh-in
  expect(within(card).getByLabelText("Today's weight (kg)")).toHaveValue(null)                  // the box is cleared
})

test('the button waits until a number is typed', async () => {
  home({ body: HISTORY })
  render()
  const card = await screen.findByRole('region', { name: 'Weight' })
  expect(within(card).getByRole('button', { name: 'Log weight' })).toBeDisabled()
  fireEvent.change(within(card).getByLabelText("Today's weight (kg)"), { target: { value: '57' } })
  expect(within(card).getByRole('button', { name: 'Log weight' })).toBeEnabled()
})

test("the server's message is shown when a weigh-in is refused and what was typed stays", async () => {
  home({ body: HISTORY }, { 'POST /weight': { status: 422, body: { detail: "You can't log a weight for a future date.", request_id: 'r-5' } } })
  render()
  const card = await screen.findByRole('region', { name: 'Weight' })
  fireEvent.change(within(card).getByLabelText("Today's weight (kg)"), { target: { value: '57' } })
  fireEvent.click(within(card).getByRole('button', { name: 'Log weight' }))
  expect(await within(card).findByRole('alert')).toHaveTextContent('future date')
  expect(within(card).getByLabelText("Today's weight (kg)")).toHaveValue(57)
})

test('a user who must not see numbers gets no weight card at all', async () => {
  home({ body: { ...HISTORY, numbers_hidden: true, entries: [], latest_kg: null, target_weight_kg: null } })
  render()
  await screen.findByText('1,408')
  expect(screen.queryByRole('region', { name: 'Weight' })).not.toBeInTheDocument()
})

test('if the weight history cannot load, Home still works and shows no error', async () => {
  home({ status: 500, body: { detail: 'Something went wrong on our side.' } })
  render()
  expect(await screen.findByText('1,408')).toBeInTheDocument()
  expect(screen.queryByRole('region', { name: 'Weight' })).not.toBeInTheDocument()
  expect(screen.queryByRole('alert')).not.toBeInTheDocument()
})

test('a single weigh-in draws one point and no line; being at the target is said in words', async () => {
  home({ body: { ...HISTORY, entries: [{ date: '2026-11-11', weight_kg: 54 }], latest_kg: 54, kg_to_target: 0, change_since_start_kg: -4, percent_to_target: 100, weekly_change_kg: null } })
  render()
  const card = await screen.findByRole('region', { name: 'Weight' })
  expect(card.querySelectorAll('circle')).toHaveLength(1)
  expect(card.querySelector('path')).toBeNull()
  expect(card).toHaveTextContent('You are at your target weight.')
  expect(within(card).queryByText(/a week/)).not.toBeInTheDocument()
})

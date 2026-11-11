import { screen, within } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import App from '../App'
import { fakeAuth, fakeSession, renderWithAuth } from '../test/fakeAuth'
import { fakeFetch, status } from '../test/fakeFetch'
import type { Insights } from './types'

afterEach(() => vi.unstubAllGlobals())

const DATA: Insights = {
  rules: ['Calories, macros and targets are calculated by tested code, never by the AI.', 'Anything the AI suggests is a proposal: nothing is saved until you press Approve.'],
  quality: {
    as_of: '2026-11-11', source: 'The latest recorded run of each eval, with real Gemini calls.',
    evals: [
      { name: 'Router: picks the right specialist', cases: 68, metric: 'exact accuracy', percent: 100, pass_line_percent: 90, decision: 'D-110' },
      { name: 'Nutrition specialist: answers only from our food data', cases: 24, metric: 'pass rate', percent: 95.8, pass_line_percent: 85, decision: 'D-107' },
    ],
  },
  usage: {
    days: 14,
    totals: { calls: 12, input_tokens: 9000, output_tokens: 1000, cost_usd: 0.0123, avg_latency_ms: 1450, failed_calls: 1 },
    per_day: [{ day: '2026-11-10', calls: 4, cost_usd: 0.004 }, { day: '2026-11-11', calls: 8, cost_usd: 0.0083 }],
    per_step: [{ step: 'router', calls: 6, avg_latency_ms: 1000, cost_usd: 0.002 }, { step: 'nutrition specialist', calls: 6, avg_latency_ms: 1900, cost_usd: 0.0103 }],
  },
}

const signedIn = () => fakeAuth({ session: fakeSession('kruthi@example.test') })
const render = () => renderWithAuth(signedIn(), { '*': <App /> }, '/how-it-works')

test('the page lists the rules the AI cannot break', async () => {
  fakeFetch({ 'GET /insights/ai': { body: DATA } })
  render()
  const rules = await screen.findByRole('region', { name: 'Rules the AI cannot break' })
  expect(within(rules).getAllByRole('listitem')).toHaveLength(2)
  expect(rules).toHaveTextContent('never by the AI')
})

test('each quality result shows its score, how many cases, and the pass line it is held to', async () => {
  fakeFetch({ 'GET /insights/ai': { body: DATA } })
  render()
  const quality = await screen.findByRole('region', { name: 'How quality is checked' })
  const router = within(quality).getByRole('progressbar', { name: 'Router: picks the right specialist' })
  expect(router).toHaveAttribute('aria-valuenow', '100')
  expect(router).toHaveAttribute('aria-valuetext', '100% exact accuracy, pass line 90%')
  expect(quality).toHaveTextContent('exact accuracy on 68 cases. Pass line 90%')
  expect(quality).toHaveTextContent('95.8%')
  expect(quality).toHaveTextContent('Results as of 11 Nov')
})

test('your usage shows calls, cost, tokens and time, the steps, and a per-day list', async () => {
  fakeFetch({ 'GET /insights/ai': { body: DATA } })
  render()
  const usage = await screen.findByRole('region', { name: 'Your AI usage' })
  expect(usage).toHaveTextContent('Your AI usage, last 14 days')
  expect(within(usage).getByText('12')).toBeInTheDocument()
  expect(within(usage).getByText('$0.0123')).toBeInTheDocument()
  expect(within(usage).getByText('10,000')).toBeInTheDocument()                                  // 9,000 in + 1,000 out
  expect(within(usage).getByText('1.5 s')).toBeInTheDocument()
  expect(within(usage).getByRole('list', { name: 'Calls per step' })).toHaveTextContent('nutrition specialist6 calls, 1.9 s each')
  expect(within(usage).getAllByRole('listitem').length).toBeGreaterThanOrEqual(4)
  expect(usage).toHaveTextContent('1 of 12 calls were retried or failed')
})

test('with no AI calls yet the page says so instead of showing zeros', async () => {
  fakeFetch({ 'GET /insights/ai': { body: { ...DATA, usage: { days: 14, totals: { calls: 0, input_tokens: 0, output_tokens: 0, cost_usd: 0, avg_latency_ms: 0, failed_calls: 0 }, per_day: [], per_step: [] } } } })
  render()
  expect(await screen.findByText(/No AI calls in the last 14 days/)).toBeInTheDocument()
})

test('a failed load shows the error with its reference and no stale content', async () => {
  fakeFetch({ 'GET /insights/ai': { status: 500, body: { detail: 'Something went wrong on our side. Please try again.', request_id: 'req-88' } } })
  render()
  expect(await screen.findByRole('alert')).toHaveTextContent('Reference: req-88')
  expect(screen.queryByRole('region', { name: 'Rules the AI cannot break' })).not.toBeInTheDocument()
})

test('Home links to the page', async () => {
  fakeFetch({
    'GET /onboarding/status': { body: status('done', [], true) },
    'GET /targets/current': { body: { calorie_target_kcal: 1408, protein_g: 116, fat_g: 39, carbs_g: 148, protein_pct: 33, carbs_pct: 42, fat_pct: 25, reasons: [], doctor_note: null, focus_on_habits: false } },
  })
  renderWithAuth(signedIn(), { '*': <App /> }, '/')
  expect(await screen.findByRole('link', { name: 'How the AI works' })).toHaveAttribute('href', '/how-it-works')
})

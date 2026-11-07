import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import { fakeAuth, fakeSession, renderWithAuth } from '../test/fakeAuth'
import { fakeFetch } from '../test/fakeFetch'
import { prescription, type ActivePlan, type PlanDay, type Proposal } from './types'
import { WorkoutPlanPage } from './WorkoutPlanPage'

afterEach(() => vi.unstubAllGlobals())

const BENCH = { position: 1, exercise_key: 'bench', name: 'Barbell Bench Press', sets: 3, reps_min: 8, reps_max: 12, rest_sec: 90,
  note: 'Stop each set with 2 good reps left in the tank' }
const PLANK = { position: 2, exercise_key: 'plank', name: 'Plank', sets: 3, reps_min: 1, reps_max: 1, rest_sec: 45, note: 'Hold 30-45 seconds' }
const SQUAT = { position: 1, exercise_key: 'squat', name: 'Back Squat', sets: 4, reps_min: 6, reps_max: 10, rest_sec: 120, note: null }

const week = (first: PlanDay, withCues = false): PlanDay[] => [
  { day_of_week: 1, focus: first.focus, is_rest: false, minutes: 45, exercises: first.exercises.map((e) => (withCues ? { ...e, form_cues: ['Keep your back flat'] } : e)) },
  { day_of_week: 2, focus: 'Rest', is_rest: true, exercises: [] },
]
const PUSH: PlanDay = { day_of_week: 1, focus: 'Push', is_rest: false, exercises: [BENCH, PLANK] }

const PROPOSAL: Proposal = {
  id: 'p1', type: 'workout_change', source: 'plan_generation', status: 'pending', created_at: '2026-11-06T10:00:00Z',
  summary: 'Push / Pull / Legs, 3 days a week: Mon Push. 2 exercises, starting 2026-11-09.',
  payload: { split_name: 'Push / Pull / Legs', week_start: '2026-11-09', doctor_note: null, days: week(PUSH) },
}
const ACTIVE: ActivePlan = { id: 'a1', week_start: '2026-11-09', version: 1, approved_at: '2026-11-06T10:05:00Z',
  days: week({ day_of_week: 1, focus: 'Legs', is_rest: false, exercises: [SQUAT] }, true) }

const NO_PLAN = { status: 404, body: { detail: "You don't have a workout plan yet." } }
const signedIn = () => fakeAuth({ session: { ...fakeSession(), access_token: 'tok' } as never })
const render = () => renderWithAuth(signedIn(), { '/workout': <WorkoutPlanPage />, '/': <p>home</p>, '/splits': <p>splits</p> }, '/workout')

test('prescription text: reps, holds as time, rest in minutes when it is whole minutes', () => {
  expect(prescription(BENCH)).toBe('3 × 8-12 reps · rest 90 s')
  expect(prescription(PLANK)).toBe('3 × Hold 30-45 seconds · rest 45 s')          // never "1 reps"
  expect(prescription(SQUAT)).toBe('4 × 6-10 reps · rest 2 min')
  expect(prescription({ ...SQUAT, reps_min: 5, reps_max: 5 })).toBe('4 × 5 reps · rest 2 min')
})

test('with no plan yet it explains and offers to generate one', async () => {
  fakeFetch({ 'GET /plans/workout/active': NO_PLAN, 'GET /plans/proposals/pending': { body: { proposals: [] } } })
  render()
  expect(await screen.findByText(/You don't have a workout plan yet/)).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Generate my plan' })).toBeEnabled()
})

test('generating shows the proposal with Approve and Reject, not as your plan', async () => {
  const calls = fakeFetch({
    'GET /plans/workout/active': NO_PLAN,
    'GET /plans/proposals/pending': { body: { proposals: [] } },
    'POST /plans/workout/generate': { body: PROPOSAL },
  })
  render()
  fireEvent.click(await screen.findByRole('button', { name: 'Generate my plan' }))

  const card = await screen.findByRole('region', { name: 'Plan waiting for your approval' })
  expect(within(card).getByText('Monday: Push')).toBeInTheDocument()
  expect(within(card).getByText('about 45 min')).toBeInTheDocument()
  expect(within(card).getByText('3 × 8-12 reps · rest 90 s')).toBeInTheDocument()
  expect(within(card).getByText('3 × Hold 30-45 seconds · rest 45 s')).toBeInTheDocument()
  expect(within(card).getByText('Tuesday: rest')).toBeInTheDocument()
  expect(within(card).getByRole('button', { name: 'Approve' })).toBeEnabled()
  expect(screen.queryByRole('region', { name: 'Your workout plan' })).not.toBeInTheDocument()
  expect(calls.filter((c) => c.method === 'POST')).toHaveLength(1)
})

test('while the plan is being built (about 15 seconds) the button is disabled and a message says so', async () => {
  let finish: () => void = () => {}
  const slow = new Promise<void>((resolve) => { finish = resolve })
  vi.stubGlobal('fetch', vi.fn(async (url: string, init: RequestInit = {}) => {
    const { pathname } = new URL(url)
    const reply = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
    if (pathname === '/plans/workout/active') return reply(NO_PLAN.body, 404)
    if (pathname === '/plans/proposals/pending') return reply({ proposals: [] })
    if (init.method === 'POST' && pathname === '/plans/workout/generate') {
      await slow
      return reply(PROPOSAL)
    }
    throw new Error(`unexpected ${pathname}`)
  }))
  render()
  fireEvent.click(await screen.findByRole('button', { name: 'Generate my plan' }))
  expect(await screen.findByRole('status')).toHaveTextContent('about 15 seconds')
  expect(screen.getByRole('button', { name: 'Building your plan…' })).toBeDisabled()
  finish()
  await screen.findByRole('region', { name: 'Plan waiting for your approval' })
  expect(screen.queryByRole('status')).not.toBeInTheDocument()
})

test('a pending proposal found on load is shown for approval, with the doctor note when there is one', async () => {
  fakeFetch({
    'GET /plans/workout/active': NO_PLAN,
    'GET /plans/proposals/pending': { body: { proposals: [{ ...PROPOSAL, payload: { ...PROPOSAL.payload, doctor_note: 'Please check with your doctor before starting.' } }] } },
  })
  render()
  expect(await screen.findByText('Please check with your doctor before starting.')).toBeInTheDocument()
})

test('approving saves it and then shows it as your plan', async () => {
  let approved = false
  const calls = fakeFetch({
    'GET /plans/workout/active': () => (approved ? { body: ACTIVE } : NO_PLAN),
    'GET /plans/proposals/pending': () => ({ body: { proposals: approved ? [] : [PROPOSAL] } }),
    'POST /plans/proposals/p1/approve': () => { approved = true; return { body: { ...PROPOSAL, status: 'approved' } } },
  })
  render()
  fireEvent.click(await screen.findByRole('button', { name: 'Approve' }))
  const plan = await screen.findByRole('region', { name: 'Your workout plan' })
  expect(within(plan).getByText('Monday: Legs')).toBeInTheDocument()
  expect(within(plan).getByText('Keep your back flat')).toBeInTheDocument()       // form cues are on the real plan
  expect(screen.queryByRole('region', { name: 'Plan waiting for your approval' })).not.toBeInTheDocument()
  expect(calls.some((c) => c.method === 'POST' && c.path === '/plans/proposals/p1/approve')).toBe(true)
})

test('rejecting removes the proposal and keeps the current plan', async () => {
  const calls = fakeFetch({
    'GET /plans/workout/active': { body: ACTIVE },
    'GET /plans/proposals/pending': { body: { proposals: [PROPOSAL] } },
    'POST /plans/proposals/p1/reject': { body: { ...PROPOSAL, status: 'rejected' } },
  })
  render()
  fireEvent.click(await screen.findByRole('button', { name: 'Reject' }))
  expect(await screen.findByRole('region', { name: 'Your workout plan' })).toBeInTheDocument()
  expect(screen.queryByRole('region', { name: 'Plan waiting for your approval' })).not.toBeInTheDocument()
  expect(calls.filter((c) => c.method === 'POST').map((c) => c.path)).toEqual(['/plans/proposals/p1/reject'])
})

test('a user with a plan can ask for a new one', async () => {
  fakeFetch({ 'GET /plans/workout/active': { body: ACTIVE }, 'GET /plans/proposals/pending': { body: { proposals: [] } } })
  render()
  expect(await screen.findByRole('button', { name: 'Make me a new plan' })).toBeEnabled()
})

test("a refusal such as 'choose a split first' shows the message and the way forward", async () => {
  fakeFetch({
    'GET /plans/workout/active': NO_PLAN,
    'GET /plans/proposals/pending': { body: { proposals: [] } },
    'POST /plans/workout/generate': { status: 409, body: { detail: 'Please choose a workout split first.' } },
  })
  render()
  fireEvent.click(await screen.findByRole('button', { name: 'Generate my plan' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Please choose a workout split first.')
  expect(screen.getByRole('link', { name: 'Choose a split' })).toBeInTheDocument()
  await waitFor(() => expect(screen.getByRole('button', { name: 'Generate my plan' })).toBeEnabled())   // can try again
})

test('a busy coach (503) shows the friendly message and does not lose the page', async () => {
  fakeFetch({
    'GET /plans/workout/active': NO_PLAN,
    'GET /plans/proposals/pending': { body: { proposals: [] } },
    'POST /plans/workout/generate': { status: 503, body: { detail: 'The coach is busy right now. Please try again in a minute.' } },
  })
  render()
  fireEvent.click(await screen.findByRole('button', { name: 'Generate my plan' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('The coach is busy right now')
})

// --- Muscles to bring up ---

const FOCUS = { focus_areas: [] as string[], options: ['chest', 'back', 'glutes', 'abs'], max_areas: 2 }
const focusHandlers = (state = FOCUS) => ({
  'GET /plans/workout/active': NO_PLAN,
  'GET /plans/proposals/pending': { body: { proposals: [] } },
  'GET /training/focus-areas': { body: state },
})

test('you can pick up to two muscles; the third is disabled; the choice is saved', async () => {
  let saved: string[] = []
  const calls = fakeFetch({
    ...focusHandlers(),
    'PUT /training/focus-areas': (body) => { saved = (body as { focus_areas: string[] }).focus_areas; return { body: { ...FOCUS, focus_areas: saved } } },
  })
  render()
  fireEvent.click(await screen.findByRole('button', { name: 'chest' }))
  await waitFor(() => expect(screen.getByRole('button', { name: 'chest' })).toHaveAttribute('aria-pressed', 'true'))
  fireEvent.click(screen.getByRole('button', { name: 'glutes' }))
  await waitFor(() => expect(screen.getByRole('button', { name: 'glutes' })).toHaveAttribute('aria-pressed', 'true'))
  expect(screen.getByRole('button', { name: 'back' })).toBeDisabled()          // a third is not allowed
  expect(screen.getByRole('button', { name: 'abs' })).toBeDisabled()
  expect(saved).toEqual(['chest', 'glutes'])
  expect(calls.filter((c) => c.method === 'PUT')).toHaveLength(2)
})

test('untapping a chosen muscle frees a slot', async () => {
  fakeFetch({
    ...focusHandlers({ ...FOCUS, focus_areas: ['chest', 'glutes'] }),
    'PUT /training/focus-areas': (body) => ({ body: { ...FOCUS, ...(body as object) } }),
  })
  render()
  expect(await screen.findByRole('button', { name: 'back' })).toBeDisabled()
  fireEvent.click(screen.getByRole('button', { name: 'chest' }))
  await waitFor(() => expect(screen.getByRole('button', { name: 'back' })).toBeEnabled())
})

test('the page still works if the focus options cannot be loaded', async () => {
  fakeFetch({
    'GET /plans/workout/active': NO_PLAN,
    'GET /plans/proposals/pending': { body: { proposals: [] } },
    'GET /training/focus-areas': { status: 500, body: { detail: 'nope' } },
  })
  render()
  expect(await screen.findByRole('button', { name: 'Generate my plan' })).toBeEnabled()
  expect(screen.queryByText('Muscles to bring up')).not.toBeInTheDocument()
})

test('a proposal that used a focus says so', async () => {
  fakeFetch({
    'GET /plans/workout/active': NO_PLAN,
    'GET /plans/proposals/pending': { body: { proposals: [{ ...PROPOSAL, payload: { ...PROPOSAL.payload, focus_areas: ['glutes'] } }] } },
    'GET /training/focus-areas': { body: FOCUS },
  })
  render()
  expect(await screen.findByText('Extra focus: glutes')).toBeInTheDocument()
})

import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import { fakeAuth, fakeSession, renderWithAuth } from '../test/fakeAuth'
import { fakeFetch } from '../test/fakeFetch'
import type { ActivePlan, PlanDay, PlanExercise } from './types'
import { WorkoutPlanPage } from './WorkoutPlanPage'

afterEach(() => vi.unstubAllGlobals())

const ex = (position: number, key: string, name: string): PlanExercise => ({
  position, exercise_key: key, name, sets: 3, reps_min: 6, reps_max: 10, rest_sec: 120, note: null, form_cues: ['Keep your back flat'],
})
const rest = (n: number): PlanDay => ({ day_of_week: n, focus: 'Rest', is_rest: true, minutes: null, exercises: [] })
const week = (days: Record<number, [string, PlanExercise[]]>): PlanDay[] =>
  [1, 2, 3, 4, 5, 6, 7].map((n) => (days[n] ? { day_of_week: n, focus: days[n][0], is_rest: false, minutes: 40, exercises: days[n][1] } : rest(n)))

const PLAN: ActivePlan = {
  id: 'a1', week_start: '2026-11-09', version: 1, approved_at: '2026-11-09T10:00:00Z',
  days: week({ 1: ['Push', [ex(1, 'bench', 'Barbell Bench Press'), ex(2, 'ohp', 'Overhead Press')]], 3: ['Pull', [ex(1, 'row', 'Barbell Row')]] }),
}

const BASE = {
  'GET /plans/workout/active': { body: PLAN },
  'GET /plans/proposals/pending': { body: { proposals: [] } },
}
const signedIn = () => fakeAuth({ session: { ...fakeSession(), access_token: 'tok' } as never })
const render = () => renderWithAuth(signedIn(), { '/workout': <WorkoutPlanPage />, '/': <p>home</p> }, '/workout')
const startEditing = async () => fireEvent.click(await screen.findByRole('button', { name: 'Edit my plan' }))

test('Edit my plan shows the controls, and Done editing goes back to reading', async () => {
  fakeFetch(BASE)
  render()
  expect(await screen.findByText('Barbell Bench Press')).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /^Swap / })).not.toBeInTheDocument()          // reading mode: no controls
  await startEditing()
  expect(screen.getByRole('button', { name: 'Swap Barbell Bench Press' })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Remove Overhead Press' })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: '+ Add exercise to Monday' })).toBeInTheDocument()
  expect(screen.queryByLabelText('Move Tuesday')).not.toBeInTheDocument()                    // a rest day has nothing to move
  fireEvent.click(screen.getByRole('button', { name: 'Done editing' }))
  expect(screen.queryByRole('button', { name: /^Swap / })).not.toBeInTheDocument()
})

test('moving a day offers every other weekday and applies at once', async () => {
  const moved: ActivePlan = { ...PLAN, days: week({ 2: ['Push', [ex(1, 'bench', 'Barbell Bench Press'), ex(2, 'ohp', 'Overhead Press')]], 3: ['Pull', [ex(1, 'row', 'Barbell Row')]] }) }
  const calls = fakeFetch({ ...BASE, 'POST /plans/workout/edit': { body: { message: 'Moved Push from Monday to Tuesday.', plan: moved } } })
  render()
  await startEditing()
  const select = screen.getByLabelText('Move Monday')
  expect(within(select).getByRole('option', { name: 'Tuesday (rest day)' })).toBeInTheDocument()
  expect(within(select).getByRole('option', { name: 'Wednesday (swap with Pull)' })).toBeInTheDocument()
  expect(within(select).queryByRole('option', { name: /^Monday/ })).not.toBeInTheDocument()
  fireEvent.change(select, { target: { value: '2' } })
  expect(await screen.findByRole('status')).toHaveTextContent('Moved Push from Monday to Tuesday.')
  expect(calls.find((c) => c.method === 'POST')!.body).toEqual({ op: 'move_day', from_day: 1, to_day: 2 })
  expect(screen.getByText(/Tuesday: Push/)).toBeInTheDocument()
  expect(screen.getByText('Monday: rest')).toBeInTheDocument()
})

test('swapping loads the valid choices for that exercise, and picking one applies it', async () => {
  const swapped: ActivePlan = { ...PLAN, days: week({ 1: ['Push', [ex(1, 'incline', 'Incline Dumbbell Press'), ex(2, 'ohp', 'Overhead Press')]], 3: ['Pull', [ex(1, 'row', 'Barbell Row')]] }) }
  const calls = fakeFetch({
    ...BASE,
    'GET /plans/workout/options': { body: { options: [
      { key: 'pushup', name: 'Push-Up', muscle_groups: ['chest', 'triceps'], difficulty: 'beginner', movement_pattern: 'push_horizontal' },
      { key: 'incline', name: 'Incline Dumbbell Press', muscle_groups: ['chest', 'shoulders'], difficulty: 'intermediate', movement_pattern: 'push_horizontal' },
    ] } },
    'POST /plans/workout/edit': { body: { message: 'Swapped Barbell Bench Press for Incline Dumbbell Press on Monday.', plan: swapped } },
  })
  render()
  await startEditing()
  fireEvent.click(screen.getByRole('button', { name: 'Swap Barbell Bench Press' }))
  const picker = await screen.findByRole('region', { name: 'Swap for…' })
  expect(calls.find((c) => c.path === '/plans/workout/options')!.query).toBe('?day=1&position=1')
  expect(within(picker).getAllByRole('button').map((b) => b.textContent)).toEqual([
    'Push-Upchest, triceps · beginner', 'Incline Dumbbell Presschest, shoulders · intermediate', 'Cancel'])
  fireEvent.click(within(picker).getByRole('button', { name: /Incline Dumbbell Press/ }))
  expect(await screen.findByRole('status')).toHaveTextContent('Swapped Barbell Bench Press for Incline Dumbbell Press on Monday.')
  expect(calls.find((c) => c.method === 'POST')!.body).toEqual({ op: 'swap_exercise', day: 1, position: 1, exercise_key: 'incline' })
  expect(screen.getByRole('button', { name: 'Swap Incline Dumbbell Press' })).toBeInTheDocument()
  expect(screen.queryByRole('region', { name: 'Swap for…' })).not.toBeInTheDocument()            // the picker closed
})

test('removing an exercise applies at once', async () => {
  const removed: ActivePlan = { ...PLAN, days: week({ 1: ['Push', [ex(1, 'bench', 'Barbell Bench Press')]], 3: ['Pull', [ex(1, 'row', 'Barbell Row')]] }) }
  const calls = fakeFetch({ ...BASE, 'POST /plans/workout/edit': { body: { message: 'Removed Overhead Press from Monday.', plan: removed } } })
  render()
  await startEditing()
  fireEvent.click(screen.getByRole('button', { name: 'Remove Overhead Press' }))
  await screen.findByText('Removed Overhead Press from Monday.')
  expect(calls.find((c) => c.method === 'POST')!.body).toEqual({ op: 'remove_exercise', day: 1, position: 2 })
  expect(screen.queryByText('Overhead Press')).not.toBeInTheDocument()
})

test('adding asks for the choices without a position and applies the pick', async () => {
  const added: ActivePlan = { ...PLAN, days: week({ 1: ['Push', [ex(1, 'bench', 'Barbell Bench Press'), ex(2, 'ohp', 'Overhead Press'), ex(3, 'lateral', 'Lateral Raise')]], 3: ['Pull', [ex(1, 'row', 'Barbell Row')]] }) }
  const calls = fakeFetch({
    ...BASE,
    'GET /plans/workout/options': { body: { options: [{ key: 'lateral', name: 'Lateral Raise', muscle_groups: ['shoulders'], difficulty: 'beginner', movement_pattern: 'push_vertical' }] } },
    'POST /plans/workout/edit': { body: { message: 'Added Lateral Raise to Monday.', plan: added } },
  })
  render()
  await startEditing()
  fireEvent.click(screen.getByRole('button', { name: '+ Add exercise to Monday' }))
  const picker = await screen.findByRole('region', { name: 'Add…' })
  expect(calls.find((c) => c.path === '/plans/workout/options')!.query).toBe('?day=1')
  fireEvent.click(within(picker).getByRole('button', { name: /Lateral Raise/ }))
  await screen.findByText('Added Lateral Raise to Monday.')
  expect(calls.find((c) => c.method === 'POST')!.body).toEqual({ op: 'add_exercise', day: 1, exercise_key: 'lateral' })
})

test("the server's refusal is shown and the plan stays as it was", async () => {
  fakeFetch({
    ...BASE,
    'POST /plans/workout/edit': { status: 422, body: { detail: 'A training day needs at least one exercise. Move the day to make it a rest day instead.' } },
  })
  render()
  await startEditing()
  fireEvent.click(screen.getByRole('button', { name: 'Remove Barbell Row' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('A training day needs at least one exercise')
  expect(screen.getByText('Barbell Row')).toBeInTheDocument()
  expect(screen.queryByRole('status')).not.toBeInTheDocument()
})

test('when nothing else fits, the picker says so and can be closed', async () => {
  fakeFetch({ ...BASE, 'GET /plans/workout/options': { body: { options: [] } } })
  render()
  await startEditing()
  fireEvent.click(screen.getByRole('button', { name: 'Swap Barbell Row' }))
  expect(await screen.findByText(/No other exercise fits here/)).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
  expect(screen.queryByText(/No other exercise fits here/)).not.toBeInTheDocument()
})

test('while an edit is being saved the controls cannot be pressed twice', async () => {
  let finish: () => void = () => {}
  const slow = new Promise<void>((resolve) => { finish = resolve })
  vi.stubGlobal('fetch', vi.fn(async (url: string, init: RequestInit = {}) => {
    const { pathname } = new URL(url)
    const reply = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
    if (pathname === '/plans/workout/active') return reply(PLAN)
    if (pathname === '/plans/proposals/pending') return reply({ proposals: [] })
    if (init.method === 'POST' && pathname === '/plans/workout/edit') {
      await slow
      return reply({ message: 'Removed Overhead Press from Monday.', plan: PLAN })
    }
    throw new Error(`unexpected ${pathname}`)
  }))
  render()
  await startEditing()
  fireEvent.click(screen.getByRole('button', { name: 'Remove Overhead Press' }))
  await waitFor(() => expect(screen.getByRole('button', { name: 'Remove Barbell Row' })).toBeDisabled())
  expect(screen.getByLabelText('Move Monday')).toBeDisabled()
  finish()
  await screen.findByRole('status')
  expect(screen.getByRole('button', { name: 'Remove Barbell Row' })).toBeEnabled()
})

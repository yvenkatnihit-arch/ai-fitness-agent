import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import { fakeAuth, fakeSession, renderWithAuth } from '../test/fakeAuth'
import { fakeFetch } from '../test/fakeFetch'
import { SettingsPage } from './SettingsPage'
import type { Profile, ProfileUpdate } from './types'

afterEach(() => vi.unstubAllGlobals())

const PROFILE: Profile = {
  display_name: 'Meera', date_of_birth: '1995-08-20', sex: 'female', height_cm: 162.5, weight_kg: 58, activity_level: 'light',
  goal_type: 'fat_loss', target_weight_kg: 54, pace: 'normal', diet_type: 'vegetarian', cuisines: ['indian'], disliked_foods: ['Karela'],
  experience_level: 'beginner', workout_location: 'home', equipment: ['yoga_mat'], days_per_week: 3, session_minutes: 45,
  pregnant_or_breastfeeding: false, diabetes: false, heart_or_bp: false, kidney: false, recent_surgery_or_injury: false,
  eating_disorder_history: false, injury_areas: [],
}

const TARGETS = {
  calorie_target_kcal: 1650, protein_g: 148, fat_g: 46, carbs_g: 190, protein_pct: 36, carbs_pct: 46, fat_pct: 18,
  reasons: [], doctor_note: null, focus_on_habits: false,
}

const update = (over: Omit<Partial<ProfileUpdate>, 'profile'> & { profile?: Partial<Profile> } = {}): ProfileUpdate => {
  const { profile, ...rest } = over
  return {
    changed: ['weight_kg'], targets_recalculated: true, targets: TARGETS, workout_plan_stale: false, meal_plan_stale: true,
    messages: ['Your daily targets were updated to match your new details.',
      'Your meal plan no longer matches your answers. Make a new one when you are ready.'],
    ...rest, profile: { ...PROFILE, ...(profile ?? {}) },
  }
}

const signedIn = () => fakeAuth({ session: { ...fakeSession(), access_token: 'tok' } as never })
const render = () => renderWithAuth(signedIn(), { '/settings': <SettingsPage />, '/': <p>home</p>, '/onboarding': <p>onboarding</p>, '/meal-plan': <p>meals</p>, '/workout': <p>workout</p> }, '/settings')
const save = (name: string) => screen.getByRole('button', { name })

test('shows your current answers, and nothing can be saved until something changes', async () => {
  fakeFetch({ 'GET /profile': { body: PROFILE } })
  render()
  expect(await screen.findByLabelText('Weight (kg)')).toHaveValue('58')
  expect(screen.getByLabelText('Height (cm)')).toHaveValue('162.5')
  expect(screen.getByLabelText(/^Vegetarian/)).toBeChecked()
  expect(screen.getByLabelText(/^Lose fat\s*Eat a little less/)).toBeChecked()
  expect(screen.getByLabelText('Foods you dislike (separate with commas)')).toHaveValue('Karela')
  for (const name of ['Save about you', 'Save your goal', 'Save food', 'Save training', 'Save health']) expect(save(name)).toBeDisabled()
})

test('changing the weight sends only the weight, then shows what the server did', async () => {
  const calls = fakeFetch({ 'GET /profile': { body: PROFILE }, 'PATCH /profile': { body: update({ profile: { weight_kg: 74 } }) } })
  render()
  fireEvent.change(await screen.findByLabelText('Weight (kg)'), { target: { value: '74' } })
  expect(screen.getByText('unsaved changes')).toBeInTheDocument()
  fireEvent.click(save('Save about you'))

  const result = await screen.findByRole('region', { name: 'What changed' })
  expect(calls.find((c) => c.method === 'PATCH')!.body).toEqual({ weight_kg: 74 })
  expect(within(result).getByText(/daily targets were updated/)).toBeInTheDocument()
  expect(within(result).getByText(/New daily target: 1650 kcal · protein 148 g · carbs 190 g · fat 46 g/)).toBeInTheDocument()
  expect(within(result).getByRole('link', { name: 'New meal plan' })).toBeInTheDocument()
  expect(within(result).queryByRole('link', { name: 'New workout plan' })).not.toBeInTheDocument()       // only what is stale
  await waitFor(() => expect(screen.queryByText('unsaved changes')).not.toBeInTheDocument())
  expect(screen.getByLabelText('Weight (kg)')).toHaveValue('74')
})

test("the server's field errors appear next to the field and nothing else is lost", async () => {
  fakeFetch({
    'GET /profile': { body: PROFILE },
    'PATCH /profile': { status: 422, body: { detail: 'Please check the highlighted fields.', errors: [{ field: 'weight_kg', message: 'Input should be greater than or equal to 30' }] } },
  })
  render()
  fireEvent.change(await screen.findByLabelText('Weight (kg)'), { target: { value: '20' } })
  fireEvent.click(save('Save about you'))
  expect(await screen.findByText('Input should be greater than or equal to 30')).toBeInTheDocument()
  expect(screen.getAllByRole('alert')).toHaveLength(1)                                    // only the card that was saved shows an error
  expect(screen.getByLabelText(/^Weight \(kg\)/)).toHaveValue('20')                       // what you typed is still there
  expect(save('Save about you')).toBeEnabled()
})

test('dislikes are typed as a comma-separated list', async () => {
  const calls = fakeFetch({ 'GET /profile': { body: PROFILE }, 'PATCH /profile': { body: update({ changed: ['disliked_foods'], targets_recalculated: false, targets: null, messages: ['Your meal plan no longer matches your answers. Make a new one when you are ready.'] }) } })
  render()
  fireEvent.change(await screen.findByLabelText('Foods you dislike (separate with commas)'), { target: { value: 'karela, Bhindi ,,' } })
  fireEvent.click(save('Save food'))
  await screen.findByRole('region', { name: 'What changed' })
  expect(calls.find((c) => c.method === 'PATCH')!.body).toEqual({ disliked_foods: ['karela', 'Bhindi'] })
  expect(screen.queryByText(/New daily target/)).not.toBeInTheDocument()                  // targets did not change
})

test('a goal change sends only the goal fields that changed', async () => {
  const calls = fakeFetch({ 'GET /profile': { body: PROFILE }, 'PATCH /profile': { body: update({ changed: ['goal_type', 'target_weight_kg'], workout_plan_stale: true }) } })
  render()
  fireEvent.click(await screen.findByLabelText(/^Build muscle/))
  fireEvent.change(screen.getByLabelText('Target weight (kg, optional)'), { target: { value: '63' } })
  fireEvent.click(save('Save your goal'))
  const result = await screen.findByRole('region', { name: 'What changed' })
  expect(calls.find((c) => c.method === 'PATCH')!.body).toEqual({ goal_type: 'muscle_gain', target_weight_kg: 63 })     // pace untouched
  expect(within(result).getByRole('link', { name: 'New workout plan' })).toBeInTheDocument()
  expect(within(result).getByRole('link', { name: 'New meal plan' })).toBeInTheDocument()
})

test('training changes send the equipment list and the days', async () => {
  const calls = fakeFetch({ 'GET /profile': { body: PROFILE }, 'PATCH /profile': { body: update({ changed: ['equipment', 'days_per_week'], targets_recalculated: false, targets: null, workout_plan_stale: true, meal_plan_stale: false, messages: ['Your workout plan no longer matches your answers. Make a new one when you are ready.'] }) } })
  render()
  fireEvent.click(await screen.findByLabelText('Dumbbells'))
  fireEvent.click(screen.getByRole('button', { name: '5' }))
  fireEvent.click(save('Save training'))
  await screen.findByRole('region', { name: 'What changed' })
  expect(calls.find((c) => c.method === 'PATCH')!.body).toEqual({ equipment: ['yoga_mat', 'dumbbells'], days_per_week: 5 })
})

test('a health change shows the doctor note and both plans as out of date', async () => {
  const calls = fakeFetch({
    'GET /profile': { body: PROFILE },
    'PATCH /profile': { body: update({ changed: ['diabetes'], workout_plan_stale: true, targets: { ...TARGETS, doctor_note: 'Some of your health answers mean you should check this plan with your doctor before starting.' } }) },
  })
  render()
  const group = await screen.findByRole('group', { name: 'Do you have diabetes?' })
  fireEvent.click(within(group).getByLabelText('Yes'))
  fireEvent.click(save('Save health'))
  const result = await screen.findByRole('region', { name: 'What changed' })
  expect(calls.find((c) => c.method === 'PATCH')!.body).toEqual({ diabetes: true })
  expect(within(result).getByText(/check this plan with your doctor/)).toBeInTheDocument()
  expect(within(result).getByRole('link', { name: 'New meal plan' })).toBeInTheDocument()
  expect(within(result).getByRole('link', { name: 'New workout plan' })).toBeInTheDocument()
})

test('for a user who must not see numbers, no calories or macros are shown after a save', async () => {
  fakeFetch({
    'GET /profile': { body: PROFILE },
    'PATCH /profile': { body: update({ changed: ['eating_disorder_history'], targets: { ...TARGETS, calorie_target_kcal: null, protein_g: null, fat_g: null, carbs_g: null, protein_pct: null, carbs_pct: null, fat_pct: null, focus_on_habits: true } }) },
  })
  render()
  const group = await screen.findByRole('group', { name: /eating disorder/ })
  fireEvent.click(within(group).getByLabelText('Yes'))
  fireEvent.click(save('Save health'))
  await screen.findByRole('region', { name: 'What changed' })
  expect(screen.queryByText(/New daily target/)).not.toBeInTheDocument()
  expect(screen.queryByText(/\d+ kcal/)).not.toBeInTheDocument()
})

test('a save that changed nothing says so', async () => {
  fakeFetch({ 'GET /profile': { body: PROFILE }, 'PATCH /profile': { body: update({ changed: [], targets_recalculated: false, targets: null, meal_plan_stale: false, messages: [] }) } })
  render()
  fireEvent.change(await screen.findByLabelText('Name (optional)'), { target: { value: 'Meera ' } })     // a trailing space is not a change
  fireEvent.change(screen.getByLabelText('Weight (kg)'), { target: { value: '58.5' } })
  fireEvent.click(save('Save about you'))
  expect(await screen.findByText('Nothing needed changing.')).toBeInTheDocument()
})

test('before onboarding is finished the page explains and links to onboarding', async () => {
  fakeFetch({ 'GET /profile': { status: 409, body: { detail: 'Please finish onboarding first.' } } })
  render()
  expect(await screen.findByRole('alert')).toHaveTextContent('Please finish onboarding first.')
  expect(screen.getByRole('link', { name: 'Go to onboarding' })).toBeInTheDocument()
  expect(screen.queryByLabelText('Weight (kg)')).not.toBeInTheDocument()
})

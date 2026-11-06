import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import { fakeAuth, fakeSession, renderWithAuth } from '../test/fakeAuth'
import { fakeFetch } from '../test/fakeFetch'
import { MealLogPage } from './MealLogPage'
import type { Day, FoodHit } from './types'

afterEach(() => vi.unstubAllGlobals())

const food = (over: Partial<FoodHit>): FoodHit => ({
  id: 1, key: 'roti', name: 'Roti / chapati (no fat)', local_names: ['phulka'], category: 'dish_bread',
  diet_class: 'vegan', is_dish: true, kcal_per_100g: 202, protein_g_per_100g: 7.3, carbs_g_per_100g: 39.8,
  fat_g_per_100g: 1, fiber_g_per_100g: null, verified: true, units: [{ unit: 'piece', grams: 43 }], ...over,
})
const ROTI = food({})
const DAL = food({ id: 2, key: 'sambar', name: 'Sambar', verified: false, units: [{ unit: 'katori', grams: 152.8 }] })

const EMPTY_DAY: Day = { logged_on: '2026-11-06', meals: [], totals: { kcal: 0, protein_g: 0, carbs_g: 0, fat_g: 0 } }
const LOGGED_DAY: Day = {
  logged_on: '2026-11-06',
  totals: { kcal: 248.5, protein_g: 10.4, carbs_g: 39.7, fat_g: 3.6 },
  meals: [{
    id: 'meal-1', logged_on: '2026-11-06', slot: 'lunch', source: 'form',
    totals: { kcal: 248.5, protein_g: 10.4, carbs_g: 39.7, fat_g: 3.6 },
    items: [
      { id: 10, food_id: 1, food_name: 'Roti / chapati (no fat)', quantity: 2, unit: 'piece', grams: 86,
        kcal: 173.7, protein_g: 6.3, carbs_g: 34.2, fat_g: 0.9 },
      { id: 11, food_id: 2, food_name: 'Sambar', quantity: 1, unit: 'katori', grams: 152.8,
        kcal: 74.9, protein_g: 4.1, carbs_g: 5.5, fat_g: 2.7 },
    ],
  }],
}

const signedIn = () => fakeAuth({ session: { ...fakeSession(), access_token: 'tok' } as never })
const render = () => renderWithAuth(signedIn(), { '/log': <MealLogPage />, '/': <p>home</p> }, '/log')

async function search(text: string) {
  fireEvent.change(screen.getByLabelText('Search food'), { target: { value: text } })
  return screen.findByRole('list', { name: 'Search results' })
}

test('searching shows foods, and unverified values are marked', async () => {
  const calls = fakeFetch({ 'GET /meals': { body: EMPTY_DAY }, 'GET /foods/search': { body: [ROTI, DAL] } })
  render()
  expect(await screen.findByText('Nothing logged yet today.')).toBeInTheDocument()

  const results = await search('ro')
  expect(within(results).getByText('Roti / chapati (no fat)')).toBeInTheDocument()
  expect(within(results).getByText('values being checked')).toBeInTheDocument() // sambar
  expect(calls.find((c) => c.path === '/foods/search')!.query).toBe('?q=ro&limit=8')
})

test('one letter does not search', async () => {
  const calls = fakeFetch({ 'GET /meals': { body: EMPTY_DAY } })
  render()
  fireEvent.change(await screen.findByLabelText('Search food'), { target: { value: 'r' } })
  await new Promise((r) => setTimeout(r, 400))
  expect(calls.some((c) => c.path === '/foods/search')).toBe(false)
})

test('building a meal sends only foods and amounts, then shows the saved day', async () => {
  let day = EMPTY_DAY
  const calls = fakeFetch({
    'GET /meals': () => ({ body: day }),
    'GET /foods/search': { body: [ROTI, DAL] },
    'POST /meals': () => {
      day = LOGGED_DAY
      return { status: 201, body: LOGGED_DAY.meals[0] }
    },
  })
  render()
  await screen.findByText('Nothing logged yet today.')
  fireEvent.change(screen.getByLabelText('Meal'), { target: { value: 'lunch' } })

  fireEvent.click(within(await search('roti')).getByText('Roti / chapati (no fat)'))
  expect(screen.getByLabelText('Unit')).toHaveDisplayValue('piece (43 g)') // household unit first
  fireEvent.change(screen.getByLabelText('Amount'), { target: { value: '2' } })
  fireEvent.click(screen.getByRole('button', { name: 'Add to meal' }))

  fireEvent.click(within(await search('sambar')).getByText('Sambar'))
  fireEvent.click(screen.getByRole('button', { name: 'Add to meal' }))

  expect(within(screen.getByRole('list', { name: 'This meal' })).getAllByRole('listitem')).toHaveLength(2)
  fireEvent.click(screen.getByRole('button', { name: 'Save meal' }))

  expect(await screen.findByLabelText('Day total')).toHaveTextContent('249 kcal') // backend's numbers, rounded
  expect(calls.find((c) => c.method === 'POST')!.body).toEqual({
    slot: 'lunch',
    items: [{ food_id: 1, quantity: 2, unit: 'piece' }, { food_id: 2, quantity: 1, unit: 'katori' }],
  })
  expect(screen.queryByRole('list', { name: 'This meal' })).not.toBeInTheDocument() // draft cleared
})

test('grams are always offered, and a food without units starts in grams', async () => {
  const noUnits = food({ id: 3, name: 'Paneer', units: [] })
  fakeFetch({ 'GET /meals': { body: EMPTY_DAY }, 'GET /foods/search': { body: [noUnits] } })
  render()
  fireEvent.click(within(await search('pan')).getByText('Paneer'))
  expect(screen.getByLabelText('Unit')).toHaveDisplayValue('grams')
  expect(screen.getByLabelText('Amount')).toHaveValue(100)
  fireEvent.change(screen.getByLabelText('Amount'), { target: { value: '0' } })
  expect(screen.getByRole('button', { name: 'Add to meal' })).toBeDisabled()
})

test('save is disabled until something is added, and server errors are shown', async () => {
  fakeFetch({
    'GET /meals': { body: EMPTY_DAY },
    'GET /foods/search': { body: [ROTI] },
    'POST /meals': { status: 422, body: { detail: "Item 1 (Roti): this food can't be measured in 'katori'.", request_id: 'r-1' } },
  })
  render()
  await screen.findByText('Nothing logged yet today.')
  expect(screen.getByRole('button', { name: 'Save meal' })).toBeDisabled()

  fireEvent.click(within(await search('roti')).getByText('Roti / chapati (no fat)'))
  fireEvent.click(screen.getByRole('button', { name: 'Add to meal' }))
  fireEvent.click(screen.getByRole('button', { name: 'Save meal' }))
  expect(await screen.findByRole('alert')).toHaveTextContent("can't be measured in 'katori'")
  expect(screen.getByRole('list', { name: 'This meal' })).toBeInTheDocument() // draft kept so it can be fixed
})

test('deleting a meal calls the API and refreshes the day', async () => {
  let day = LOGGED_DAY
  const calls = fakeFetch({
    'GET /meals': () => ({ body: day }),
    'DELETE /meals/meal-1': () => {
      day = EMPTY_DAY
      return { status: 204, body: null }
    },
  })
  render()
  fireEvent.click(await screen.findByRole('button', { name: 'Delete Lunch' }))
  await waitFor(() => expect(screen.getByText('Nothing logged yet today.')).toBeInTheDocument())
  expect(calls.some((c) => c.method === 'DELETE' && c.path === '/meals/meal-1')).toBe(true)
})

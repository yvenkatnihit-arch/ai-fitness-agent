import { expect, test } from 'vitest'

import { defaultSlot, unitLabel } from './slots'

// Times are India time (UTC+5:30), written as UTC instants.
const ist = (hhmm: string) => {
  const [h, m] = hhmm.split(':').map(Number)
  return new Date(Date.UTC(2026, 10, 6, h, m) - 330 * 60 * 1000)
}

test.each([
  ['07:30', 'breakfast'],
  ['10:29', 'breakfast'],
  ['11:00', 'mid_morning'],
  ['13:15', 'lunch'],
  ['17:00', 'evening_snack'],
  ['21:00', 'dinner'],
  ['01:30', 'dinner'], // after midnight: a late dinner, not breakfast
])('at %s India time the default meal is %s', (time, slot) => {
  expect(defaultSlot(ist(time))).toBe(slot)
})

test('unit labels show grams per unit, rounded', () => {
  expect(unitLabel('katori', 152.8)).toBe('katori (153 g)')
  expect(unitLabel('g')).toBe('g')
})

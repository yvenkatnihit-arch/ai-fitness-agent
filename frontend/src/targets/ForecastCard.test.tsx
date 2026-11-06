import { render, screen } from '@testing-library/react'
import { expect, test } from 'vitest'

import { ForecastCard } from './ForecastCard'
import { formatDate } from './formatDate'
import type { Forecast } from './types'

const READY: Forecast = {
  status: 'ready', message: 'At this pace you could reach 75 kg around 29 Jan 2027.', current_weight_kg: 80, target_weight_kg: 75,
  weekly_change_kg: -0.5, earliest: '2027-01-16', likely: '2027-01-29', latest: '2027-02-17', weeks_likely: 12,
  note: 'This is an estimate. It assumes you follow your plan 70 to 100 percent of the time.',
}

test('dates are shown as written, whatever the timezone', () => {
  expect(formatDate('2026-11-06')).toBe('6 Nov 2026')
  expect(formatDate('2027-01-01')).toBe('1 Jan 2027')   // not shifted to 31 Dec by a timezone
})

test('a ready forecast shows the likely date, the range, the weekly pace and the estimate note', () => {
  render(<ForecastCard forecast={READY} />)
  expect(screen.getByText('80 kg → 75 kg')).toBeInTheDocument()
  expect(screen.getByText('29 Jan 2027')).toBeInTheDocument()
  expect(screen.getByText(/about 12 weeks from now/)).toBeInTheDocument()
  expect(screen.getByText(/Anywhere from 16 Jan 2027 to 17 Feb 2027/)).toBeInTheDocument()
  expect(screen.getByText('About 0.5 kg a week if you follow your plan fully.')).toBeInTheDocument()   // a loss shown without a minus sign
  expect(screen.getByText(/This is an estimate/)).toBeInTheDocument()
})

test.each([
  ['no_target', 'Set a target weight to see a goal date.'],
  ['not_moving', "Within safe limits your plan doesn't move your weight toward this target."],
  ['habits_only', 'Your plan focuses on healthy habits, not on dates or weights.'],
] as const)('%s shows only the backend message, no dates and no weights', (status, message) => {
  render(<ForecastCard forecast={{
    status, message, current_weight_kg: null, target_weight_kg: null, weekly_change_kg: null,
    earliest: null, likely: null, latest: null, weeks_likely: null, note: null,
  }} />)
  expect(screen.getByText(message)).toBeInTheDocument()
  expect(screen.queryByText(/kg/)).not.toBeInTheDocument()
  expect(screen.queryByText(/estimate/)).not.toBeInTheDocument()
})

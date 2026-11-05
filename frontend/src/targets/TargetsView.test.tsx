import { render, screen } from '@testing-library/react'
import { expect, test } from 'vitest'

import { TargetsView } from './TargetsView'
import type { Targets } from './types'

const base: Targets = {
  calorie_target_kcal: 1640,
  protein_g: 116,
  fat_g: 46,
  carbs_g: 189,
  protein_pct: 28,
  carbs_pct: 46,
  fat_pct: 26,
  reasons: [],
  doctor_note: null,
  focus_on_habits: false,
}

test('shows the calories and macros exactly as calculated', () => {
  render(<TargetsView targets={base} />)
  expect(screen.getByText('1,640')).toBeInTheDocument()
  expect(screen.getByText('116 g')).toBeInTheDocument()
  expect(screen.getByText('189 g')).toBeInTheDocument()
  expect(screen.getByText('46 g')).toBeInTheDocument()
  expect(screen.queryByText('Why these numbers')).not.toBeInTheDocument() // no reasons, no section
  expect(screen.queryByRole('note')).not.toBeInTheDocument()
})

test('the donut shows each macro as a segment, with grams and percent in the legend', () => {
  render(<TargetsView targets={base} />)
  const chart = screen.getByRole('img')
  expect(chart).toHaveAccessibleName('Daily target 1,640 kcal: Protein 116 g (28%), Carbs 189 g (46%), Fat 46 g (26%)')
  for (const name of ['protein', 'carbs', 'fat']) {
    expect(screen.getByTestId(`segment-${name}`)).toBeInTheDocument()
  }
  const legend = screen.getByRole('list', { name: 'Macro breakdown' })
  expect(legend).toHaveTextContent('Protein116 g28%')
  expect(legend).toHaveTextContent('Carbs189 g46%')
  expect(legend).toHaveTextContent('Fat46 g26%')
})

test('bigger shares get longer segments (drawn from the backend percentages)', () => {
  render(<TargetsView targets={base} />)
  const length = (name: string) =>
    Number(screen.getByTestId(`segment-${name}`).getAttribute('stroke-dasharray')!.split(' ')[0])
  // base: carbs 46% > protein 28% > fat 26%
  expect(length('carbs')).toBeGreaterThan(length('protein'))
  expect(length('protein')).toBeGreaterThan(length('fat'))
})

test('large numbers use Indian digit grouping', () => {
  render(<TargetsView targets={{ ...base, calorie_target_kcal: 3035 }} />)
  expect(screen.getByText('3,035')).toBeInTheDocument()
})

test('lists the reasons and the doctor note', () => {
  render(<TargetsView targets={{
    ...base,
    reasons: ['Because of your health answers, we kept your calorie deficit mild.'],
    doctor_note: 'Some of your health answers mean you should check this plan with your doctor before starting.',
  }} />)
  expect(screen.getByRole('heading', { name: 'Why these numbers' })).toBeInTheDocument()
  expect(screen.getByText(/kept your calorie deficit mild/)).toBeInTheDocument()
  expect(screen.getByRole('note')).toHaveTextContent('check this plan with your doctor')
})

test('habits focus shows guidance and no numbers at all', () => {
  const { container } = render(<TargetsView targets={{
    calorie_target_kcal: null, protein_g: null, fat_g: null, carbs_g: null,
    protein_pct: null, carbs_pct: null, fat_pct: null,
    reasons: ['Your plan focuses on balanced, regular meals rather than eating less.'],
    doctor_note: 'Some of your health answers mean you should check this plan with your doctor before starting.',
    focus_on_habits: true,
  }} />)
  expect(screen.getByRole('heading', { name: 'Your focus: balanced, regular meals' })).toBeInTheDocument()
  expect(screen.queryByText('Your daily target')).not.toBeInTheDocument()
  expect(screen.queryByRole('img')).not.toBeInTheDocument() // no chart either
  expect(container.textContent).not.toMatch(/kcal|\d+ g\b/) // no calories or grams anywhere
  expect(screen.getByRole('heading', { name: 'About your plan' })).toBeInTheDocument()
})

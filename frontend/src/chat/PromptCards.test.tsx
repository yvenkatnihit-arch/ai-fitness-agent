import { fireEvent, render, screen } from '@testing-library/react'
import { expect, test, vi } from 'vitest'

import { PromptCards } from './PromptCards'
import { SUGGESTIONS } from './suggestions'

test('every starter question is a card whose name is its label, with a decorative icon, and tapping it sends the full question', () => {
  const onPick = vi.fn()
  render(<PromptCards disabled={false} onPick={onPick} />)
  const list = screen.getByRole('list', { name: 'Example questions' })
  expect(list.querySelectorAll('button')).toHaveLength(SUGGESTIONS.length)
  for (const s of SUGGESTIONS) {
    const card = screen.getByRole('button', { name: s.label })
    expect(card.querySelector('svg')).toHaveAttribute('aria-hidden', 'true')
  }
  fireEvent.click(screen.getByRole('button', { name: 'Protein in paneer' }))
  expect(onPick).toHaveBeenCalledWith('How much protein is in paneer?')
})

test('while the coach is busy the cards are disabled', () => {
  render(<PromptCards disabled onPick={() => {}} />)
  for (const button of screen.getAllByRole('button')) expect(button).toBeDisabled()
})

import { fireEvent, render, screen } from '@testing-library/react'
import { expect, test, vi } from 'vitest'

import { SwipePanes } from './SwipePanes'

const panes = () => render(<SwipePanes labels={['Today', 'Daily targets']}>{[<p key="a">today content</p>, <p key="b">targets content</p>]}</SwipePanes>)

// jsdom does not lay anything out, so give the track a width and a scroll function to watch.
function track(width = 400) {
  const el = screen.getAllByRole('tabpanel')[0].parentElement as HTMLDivElement
  Object.defineProperty(el, 'clientWidth', { value: width, configurable: true })
  const scrollTo = vi.fn()
  el.scrollTo = scrollTo as never
  return { el, scrollTo }
}

test('Today comes first and both panes are in the page, so nothing is hidden from screen readers', () => {
  panes()
  expect(screen.getAllByRole('tab').map((t) => t.textContent)).toEqual(['Today', 'Daily targets'])
  expect(screen.getByRole('tab', { name: 'Today' })).toHaveAttribute('aria-selected', 'true')
  expect(screen.getByText('today content')).toBeInTheDocument()
  expect(screen.getByText('targets content')).toBeInTheDocument()
  expect(screen.getByText('Swipe left for your daily targets')).toBeInTheDocument()
})

test('the Daily targets tab scrolls to the second pane and becomes the selected one', () => {
  panes()
  const { scrollTo } = track(400)
  fireEvent.click(screen.getByRole('tab', { name: 'Daily targets' }))
  expect(scrollTo).toHaveBeenCalledWith({ left: 400, behavior: 'smooth' })
  expect(screen.getByRole('tab', { name: 'Daily targets' })).toHaveAttribute('aria-selected', 'true')
  expect(screen.queryByText(/Swipe left/)).not.toBeInTheDocument()                       // nothing further to swipe to
})

test('swiping (a scroll of the track) moves the selected tab, and swiping back returns to Today', () => {
  panes()
  const { el } = track(400)
  el.scrollLeft = 400
  fireEvent.scroll(el)
  expect(screen.getByRole('tab', { name: 'Daily targets' })).toHaveAttribute('aria-selected', 'true')
  el.scrollLeft = 0
  fireEvent.scroll(el)
  expect(screen.getByRole('tab', { name: 'Today' })).toHaveAttribute('aria-selected', 'true')
})

test('halfway through a swipe the nearer pane counts as the current one', () => {
  panes()
  const { el } = track(400)
  el.scrollLeft = 150
  fireEvent.scroll(el)
  expect(screen.getByRole('tab', { name: 'Today' })).toHaveAttribute('aria-selected', 'true')
  el.scrollLeft = 250
  fireEvent.scroll(el)
  expect(screen.getByRole('tab', { name: 'Daily targets' })).toHaveAttribute('aria-selected', 'true')
})

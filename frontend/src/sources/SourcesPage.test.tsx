import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { expect, test } from 'vitest'

import credits from './credits.json'
import { SourcesPage } from './SourcesPage'

const show = () => render(<MemoryRouter><SourcesPage /></MemoryRouter>)

test('every source we use is credited, with a link to its licence', () => {
  show()
  expect(credits.sources.length).toBeGreaterThan(0)
  for (const source of credits.sources) {
    expect(screen.getByText(source.credit)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: source.license })).toHaveAttribute('href', source.license_url)
  }
})

test('the Open Government Licence credit for CoFID is shown', () => {
  show()
  expect(screen.getByText(/Contains public sector information licensed under the Open Government Licence v3.0/))
    .toBeInTheDocument()
})

test('our computed recipes explain how their values are made', () => {
  show()
  expect(screen.getByText(/never by AI/)).toBeInTheDocument()
})

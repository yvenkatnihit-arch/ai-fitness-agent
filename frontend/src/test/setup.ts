// Adds DOM matchers like toBeInTheDocument() to Vitest's expect().
import '@testing-library/jest-dom/vitest'

import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

// Remove each test's rendered page before the next test. Testing Library only does this
// automatically when test globals are enabled, and we import test functions explicitly.
afterEach(() => cleanup())

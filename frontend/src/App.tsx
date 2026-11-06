import type { ReactNode } from 'react'
import { Navigate, Route, Routes } from 'react-router'

import { RequireAuth } from './auth/RequireAuth'
import { MealLogPage } from './meals/MealLogPage'
import { OnboardingPage } from './onboarding/OnboardingPage'
import { HomePage } from './pages/HomePage'
import { SignInPage } from './pages/SignInPage'

const signedIn = (page: ReactNode) => <RequireAuth>{page}</RequireAuth>

// Pages. Everything except /sign-in needs a signed-in user.
function App() {
  return (
    <Routes>
      <Route path="/sign-in" element={<SignInPage />} />
      <Route path="/onboarding" element={signedIn(<OnboardingPage />)} />
      <Route path="/log" element={signedIn(<MealLogPage />)} />
      <Route path="/" element={signedIn(<HomePage />)} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default App

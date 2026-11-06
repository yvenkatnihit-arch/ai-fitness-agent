import type { ReactNode } from 'react'
import { Navigate, Route, Routes } from 'react-router'

import { RequireAuth } from './auth/RequireAuth'
import { ExercisesPage } from './exercises/ExercisesPage'
import { MealLogPage } from './meals/MealLogPage'
import { OnboardingPage } from './onboarding/OnboardingPage'
import { HomePage } from './pages/HomePage'
import { SignInPage } from './pages/SignInPage'
import { SourcesPage } from './sources/SourcesPage'

const signedIn = (page: ReactNode) => <RequireAuth>{page}</RequireAuth>

// Pages. Everything except /sign-in and /sources (licence credits, public) needs a signed-in user.
function App() {
  return (
    <Routes>
      <Route path="/sign-in" element={<SignInPage />} />
      <Route path="/sources" element={<SourcesPage />} />
      <Route path="/onboarding" element={signedIn(<OnboardingPage />)} />
      <Route path="/log" element={signedIn(<MealLogPage />)} />
      <Route path="/exercises" element={signedIn(<ExercisesPage />)} />
      <Route path="/" element={signedIn(<HomePage />)} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default App

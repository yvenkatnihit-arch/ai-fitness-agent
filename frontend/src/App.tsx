import type { ReactNode } from 'react'
import { Navigate, Route, Routes } from 'react-router'

import { RequireAuth } from './auth/RequireAuth'
import { ChatBubble } from './chat/ChatBubble'
import { ChatPage } from './chat/ChatPage'
import { MealLogPage } from './meals/MealLogPage'
import { MealPlanPage } from './plans/MealPlanPage'
import { WorkoutPlanPage } from './plans/WorkoutPlanPage'
import { SettingsPage } from './settings/SettingsPage'
import { SplitsPage } from './splits/SplitsPage'
import { OnboardingPage } from './onboarding/OnboardingPage'
import { HomePage } from './pages/HomePage'
import { SignInPage } from './pages/SignInPage'
import { SourcesPage } from './sources/SourcesPage'

const signedIn = (page: ReactNode) => <RequireAuth>{page}</RequireAuth>
// Most screens also get the floating chat button. The chat itself and onboarding (a flow to finish first) do not.
const withChat = (page: ReactNode) => <RequireAuth>{page}<ChatBubble /></RequireAuth>

// Pages. Everything except /sign-in and /sources (licence credits, public) needs a signed-in user.
function App() {
  return (
    <Routes>
      <Route path="/sign-in" element={<SignInPage />} />
      <Route path="/sources" element={<SourcesPage />} />
      <Route path="/onboarding" element={signedIn(<OnboardingPage />)} />
      <Route path="/chat" element={signedIn(<ChatPage />)} />
      <Route path="/log" element={withChat(<MealLogPage />)} />
      <Route path="/settings" element={withChat(<SettingsPage />)} />
      <Route path="/meal-plan" element={withChat(<MealPlanPage />)} />
      <Route path="/workout" element={withChat(<WorkoutPlanPage />)} />
      <Route path="/splits" element={withChat(<SplitsPage />)} />
      <Route path="/" element={withChat(<HomePage />)} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default App

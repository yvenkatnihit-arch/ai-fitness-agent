// Supabase client, used ONLY for login, sign-up and token refresh (D-032).
// All app data goes through our FastAPI backend; the Data API is off (D-028).
import { createClient } from '@supabase/supabase-js'

const url = import.meta.env.VITE_SUPABASE_URL
const publishableKey = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY

if (!url || !publishableKey) {
  throw new Error(
    'Missing VITE_SUPABASE_URL or VITE_SUPABASE_PUBLISHABLE_KEY. Copy frontend/.env.example to frontend/.env.',
  )
}
if (publishableKey.startsWith('sb_secret_')) {
  // The secret key bypasses all security rules. It must never reach a browser.
  throw new Error('VITE_SUPABASE_PUBLISHABLE_KEY is a SECRET key. Use the publishable key instead.')
}

export const supabase = createClient(url, publishableKey, {
  auth: { persistSession: true, autoRefreshToken: true },
})

// Turn Supabase Auth errors into short messages a user can act on.
type AuthErrorLike = { message?: string; code?: string; status?: number }

export const MIN_PASSWORD_LENGTH = 8

export function friendlyAuthError(error: AuthErrorLike): string {
  const code = error.code ?? ''
  const message = (error.message ?? '').toLowerCase()

  if (code === 'invalid_credentials' || message.includes('invalid login credentials')) {
    return 'Email or password is incorrect.'
  }
  if (code === 'user_already_exists' || message.includes('already registered')) {
    return 'An account with this email already exists. Try signing in instead.'
  }
  if (code === 'weak_password' || message.includes('password should be')) {
    return `Please choose a stronger password (at least ${MIN_PASSWORD_LENGTH} characters).`
  }
  if (code === 'email_not_confirmed') {
    return 'Please confirm your email first. Check your inbox for the link.'
  }
  if (code === 'over_request_rate_limit' || code === 'over_email_send_rate_limit' || error.status === 429) {
    return 'Too many attempts. Please wait a minute and try again.'
  }
  if (code === 'validation_failed' || message.includes('invalid email')) {
    return 'Please enter a valid email address.'
  }
  return "Something went wrong. Please check your connection and try again."
}

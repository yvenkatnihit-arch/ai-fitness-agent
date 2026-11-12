// Small shared pieces so every form looks and behaves the same.
import { Dumbbell } from 'lucide-react'
import type { ButtonHTMLAttributes, ReactNode } from 'react'
import { Link } from 'react-router'

// The frame every signed-in screen shares: page background, one centred column, a title row.
// `back` adds a "Back" link to Home; `action` is anything else for the right of the title (e.g. Sign out).
export function PageShell({
  title, subtitle, back, action, leading, children,
}: { title: string; subtitle?: string; back?: boolean; action?: ReactNode; leading?: ReactNode; children: ReactNode }) {
  return (
    <main className="min-h-screen bg-bg px-4 pb-24 pt-6">
      <div className="mx-auto flex w-full max-w-md flex-col gap-4">
        <header className="flex items-center justify-between gap-3">
          {leading}
          <div className="min-w-0 flex-1">
            <h1 className="text-2xl font-bold text-ink">{title}</h1>
            {subtitle && <p className="truncate text-xs text-muted">{subtitle}</p>}
          </div>
          {back ? <Link to="/" className="shrink-0 text-sm font-semibold text-brand-strong">Back</Link> : action}
        </header>
        {children}
      </div>
    </main>
  )
}

// A link that looks like a button (primary = filled, secondary = outlined).
export function ButtonLink({ to, variant = 'primary', children }: { to: string; variant?: 'primary' | 'secondary'; children: ReactNode }) {
  const style = variant === 'primary'
    ? 'bg-brand text-on-brand hover:opacity-90'
    : 'border border-brand text-brand-strong hover:bg-brand-soft'
  return (
    <Link to={to} className={`rounded-xl px-4 py-3 text-center font-semibold transition ${style}`}>
      {children}
    </Link>
  )
}

export function Card({ title, subtitle, children }: { title: string; subtitle?: string; children: ReactNode }) {
  return (
    <div className="glass w-full max-w-md rounded-3xl p-6">
      <h1 className="text-xl font-bold text-ink">{title}</h1>
      {subtitle && <p className="mt-1 text-sm text-muted">{subtitle}</p>}
      <div className="mt-5">{children}</div>
    </div>
  )
}

export function PrimaryButton({ busy, children, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { busy?: boolean }) {
  return (
    <button
      {...props}
      disabled={busy || props.disabled}
      className="btn-glow w-full rounded-xl bg-brand px-4 py-3 font-semibold text-on-brand transition hover:opacity-90 active:scale-[0.99] disabled:opacity-50"
    >
      {busy ? 'Saving…' : children}
    </button>
  )
}

export function FieldError({ message }: { message?: string }) {
  if (!message) return null
  return <span className="text-xs font-normal text-danger">{message}</span>
}

export function FormError({ message, requestId }: { message: string | null; requestId?: string | null }) {
  if (!message) return null
  return (
    <p role="alert" className="rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">
      {message}
      {requestId && <span className="mt-1 block text-xs text-danger">Reference: {requestId}</span>}
    </p>
  )
}

// A radio button or checkbox styled as a tappable card, with an optional hint line.
export function Choice({
  type, name, checked, onChange, label, hint,
}: {
  type: 'radio' | 'checkbox'
  name: string
  checked: boolean
  onChange: () => void
  label: string
  hint?: string
}) {
  return (
    <label
      className={`flex items-start gap-3 rounded-lg border px-3 py-2 ${checked ? 'border-brand bg-brand-soft' : 'border-line'}`}
    >
      <input type={type} name={name} checked={checked} onChange={onChange} className="mt-1 accent-brand" />
      <span className="text-sm">
        <span className="font-medium text-ink">{label}</span>
        {hint && <span className="block text-xs text-muted">{hint}</span>}
      </span>
    </label>
  )
}

export function Legend({ children }: { children: ReactNode }) {
  return <legend className="mb-2 text-sm font-medium text-ink-soft">{children}</legend>
}

export const inputClass =
  'rounded-lg border border-line bg-surface-2 px-3 py-2 text-base font-normal text-ink placeholder:text-muted focus:border-brand focus:outline-none'

// The app's mark: a lime dumbbell in a glowing circle, with the name under it. Used on sign-in and onboarding.
export function BrandMark({ tagline }: { tagline?: string }) {
  return (
    <div className="flex flex-col items-center gap-2 text-center">
      <span aria-hidden="true" className="btn-glow flex h-14 w-14 items-center justify-center rounded-2xl bg-brand text-on-brand">
        <Dumbbell size={28} />
      </span>
      <p className="text-lg font-extrabold tracking-tight text-ink">AI Fitness Coach</p>
      {tagline && <p className="max-w-xs text-sm text-muted">{tagline}</p>}
    </div>
  )
}

// Small shared pieces so every form looks and behaves the same.
import type { ButtonHTMLAttributes, ReactNode } from 'react'

export function Card({ title, subtitle, children }: { title: string; subtitle?: string; children: ReactNode }) {
  return (
    <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-sm">
      <h1 className="text-xl font-bold text-slate-900">{title}</h1>
      {subtitle && <p className="mt-1 text-sm text-slate-500">{subtitle}</p>}
      <div className="mt-5">{children}</div>
    </div>
  )
}

export function PrimaryButton({ busy, children, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { busy?: boolean }) {
  return (
    <button
      {...props}
      disabled={busy || props.disabled}
      className="w-full rounded-lg bg-emerald-600 px-4 py-2.5 font-semibold text-white disabled:opacity-50"
    >
      {busy ? 'Saving…' : children}
    </button>
  )
}

export function FieldError({ message }: { message?: string }) {
  if (!message) return null
  return <span className="text-xs font-normal text-red-700">{message}</span>
}

export function FormError({ message, requestId }: { message: string | null; requestId?: string | null }) {
  if (!message) return null
  return (
    <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
      {message}
      {requestId && <span className="mt-1 block text-xs text-red-500">Reference: {requestId}</span>}
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
      className={`flex items-start gap-3 rounded-lg border px-3 py-2 ${checked ? 'border-emerald-600 bg-emerald-50' : 'border-slate-300'}`}
    >
      <input type={type} name={name} checked={checked} onChange={onChange} className="mt-1 accent-emerald-600" />
      <span className="text-sm">
        <span className="font-medium text-slate-800">{label}</span>
        {hint && <span className="block text-xs text-slate-500">{hint}</span>}
      </span>
    </label>
  )
}

export function Legend({ children }: { children: ReactNode }) {
  return <legend className="mb-2 text-sm font-medium text-slate-700">{children}</legend>
}

export const inputClass =
  'rounded-lg border border-slate-300 px-3 py-2 text-base font-normal focus:border-emerald-600 focus:outline-none'

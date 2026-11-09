import type { FormEvent, ReactNode } from 'react'

import { FormError, PrimaryButton } from '../components/ui'
import type { ApiError } from '../lib/api'
import type { Changes } from './types'

// One settings card: a title, the fields, and a Save button that is only available when something changed.
export function SectionCard({ title, hint, changes, saving, error, onSave, children }: {
  title: string
  hint?: string
  changes: Changes
  saving: boolean
  error: ApiError | null // only the card that was just saved shows the server's error
  onSave: (changes: Changes) => void
  children: ReactNode
}) {
  const dirty = Object.keys(changes).length > 0
  function submit(event: FormEvent) {
    event.preventDefault()
    if (dirty) onSave(changes)
  }
  return (
    <details className="rounded-2xl bg-surface p-4 shadow-sm">
      <summary className="cursor-pointer text-base font-bold text-ink">
        {title}
        {dirty && <span className="ml-2 text-xs font-semibold text-warn">unsaved changes</span>}
      </summary>
      {hint && <p className="mt-1 text-xs text-muted">{hint}</p>}
      <form aria-label={title} className="mt-3 flex flex-col gap-4" onSubmit={submit} noValidate>
        {children}
        <FormError message={error?.message ?? null} requestId={error?.requestId} />
        <PrimaryButton type="submit" disabled={!dirty} busy={saving}>Save {title.toLowerCase()}</PrimaryButton>
      </form>
    </details>
  )
}

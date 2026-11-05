import { useState } from 'react'

import { Card, FormError, PrimaryButton } from '../components/ui'
import { PRIVACY_NOTICE_VERSION, PRIVACY_POINTS } from './privacyNotice'
import type { StepProps } from './types'
import { useSaveStep } from './useSaveStep'

export function ConsentStep({ onSaved }: StepProps) {
  const { save, busy, error } = useSaveStep('/onboarding/consent', onSaved)
  const [agreed, setAgreed] = useState(false)

  return (
    <Card title="Before we start" subtitle="How we look after your health information">
      <ul className="flex list-disc flex-col gap-2 pl-5 text-sm text-slate-700">
        {PRIVACY_POINTS.map((point) => (
          <li key={point}>{point}</li>
        ))}
      </ul>

      <label className="mt-5 flex items-start gap-3 text-sm text-slate-800">
        <input
          type="checkbox"
          checked={agreed}
          onChange={(e) => setAgreed(e.target.checked)}
          className="mt-0.5 h-5 w-5 accent-emerald-600"
        />
        I agree to AI Fitness Coach processing my health and fitness information as described above.
      </label>

      <div className="mt-5 flex flex-col gap-3">
        <FormError message={error?.message ?? null} requestId={error?.requestId} />
        <PrimaryButton
          type="button"
          disabled={!agreed}
          busy={busy}
          onClick={() => save({ health_data_consent: true, privacy_notice_version: PRIVACY_NOTICE_VERSION })}
        >
          Agree and continue
        </PrimaryButton>
      </div>
    </Card>
  )
}

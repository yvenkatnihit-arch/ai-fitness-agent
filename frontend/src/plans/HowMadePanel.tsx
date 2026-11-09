import { SLOT_LABEL, type HowMade } from './mealTypes'

const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? '' : 's'}`

// "How this plan was made": shows the engineering. Which days the AI chose, which our code chose, the checks every plan
// passes, and what the AI calls really cost. Numbers only appear when the server sent them (not for every user).
export function HowMadePanel({ made }: { made: HowMade }) {
  const { generation, average_percent_of_target: average } = made
  const thin = Object.keys(made.thin_roles).map((slot) => SLOT_LABEL[slot] ?? slot)
  return (
    <details className="rounded-xl bg-surface-2 p-3 text-sm text-ink-soft">
      <summary className="cursor-pointer font-semibold text-brand-strong">How this plan was made</summary>
      <div className="mt-2 flex flex-col gap-2">
        <p>
          {made.days_from_model === 0
            ? 'All 7 days were planned by our rule-based planner (the AI coach did not give a safe plan for any day).'
            : `${plural(made.days_from_model, 'day')} chosen by the AI coach and ${plural(made.days_from_code, 'day')} by our rule-based planner.`}
        </p>
        {made.repair_round && <p>The AI was asked once to fix days that missed your targets.</p>}
        {generation && (
          <p>
            AI: {plural(generation.model_calls, 'call')}, {(generation.input_tokens + generation.output_tokens).toLocaleString('en-US')} tokens,
            about ${generation.cost_usd.toFixed(2)}, {Math.round(generation.latency_ms / 1000)} s.
          </p>
        )}
        <ul aria-label="Checks every plan passes" className="flex flex-col gap-1">
          {made.checks.map((check) => <li key={check}>✓ {check}</li>)}
        </ul>
        {average && (
          <p>
            On average the plan reaches {Math.round(average.kcal)}% of your calories, {Math.round(average.protein)}% of your protein,{' '}
            {Math.round(average.carbs)}% of your carbs and {Math.round(average.fat)}% of your fat.
            {(made.days_with_issues ?? 0) > 0 && ` ${plural(made.days_with_issues ?? 0, 'day')} of 7 ${made.days_with_issues === 1 ? 'has' : 'have'} at least one number off target.`}
          </p>
        )}
        {thin.length > 0 && (
          <p className="rounded-lg bg-warn-soft p-2 text-xs text-warn">
            Limited choice at {thin.join(' and ')} with your diet, so some dishes repeat during the week.
          </p>
        )}
      </div>
    </details>
  )
}

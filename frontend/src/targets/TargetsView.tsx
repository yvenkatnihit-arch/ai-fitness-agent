import { MacroDonut } from './MacroDonut'
import { MACRO_COLORS, type MacroSlice } from './macroColors'
import type { Targets } from './types'

// Shows numbers exactly as the backend calculated them (no maths here, CLAUDE.md).

// Shown instead of numbers for users with eating-disorder history (brief section 7).
const HABITS = [
  'Eat regular meals through the day, and try not to skip breakfast.',
  'Include some protein at each meal: dal, paneer, curd, eggs, fish or chicken.',
  'Fill part of your plate with vegetables, and enjoy whole grains like roti, rice or millets.',
  'Listen to your hunger and fullness. There are no "good" or "bad" foods.',
  'Move in ways you enjoy, and rest when your body needs it.',
]

export function TargetsView({ targets }: { targets: Targets }) {
  return (
    <div className="flex flex-col gap-4">
      {targets.doctor_note && (
        <p role="note" className="rounded-xl border border-warn bg-warn-soft px-4 py-3 text-sm text-warn">
          {targets.doctor_note}
        </p>
      )}

      {targets.focus_on_habits ? <Habits /> : <Numbers targets={targets} />}

      {targets.reasons.length > 0 && (
        <section className="rounded-xl bg-surface p-4 shadow-sm">
          <h2 className="text-sm font-semibold text-ink">
            {targets.focus_on_habits ? 'About your plan' : 'Why these numbers'}
          </h2>
          <ul className="mt-2 flex list-disc flex-col gap-1 pl-5 text-sm text-muted">
            {targets.reasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        </section>
      )}

    </div>
  )
}

function Numbers({ targets }: { targets: Targets }) {
  const slices: MacroSlice[] = [
    { name: 'Protein', grams: targets.protein_g ?? 0, percent: targets.protein_pct ?? 0, color: MACRO_COLORS.protein },
    { name: 'Carbs', grams: targets.carbs_g ?? 0, percent: targets.carbs_pct ?? 0, color: MACRO_COLORS.carbs },
    { name: 'Fat', grams: targets.fat_g ?? 0, percent: targets.fat_pct ?? 0, color: MACRO_COLORS.fat },
  ]

  return (
    <section className="rounded-xl bg-surface p-5 shadow-sm">
      <h2 className="mb-4 text-center text-sm font-medium text-muted">Your daily target</h2>
      <MacroDonut kcal={targets.calorie_target_kcal ?? 0} slices={slices} />
      <p className="mt-4 text-center text-xs text-muted">Percentages are each macro's share of your daily calories.</p>
    </section>
  )
}

function Habits() {
  return (
    <section className="rounded-xl bg-surface p-5 shadow-sm">
      <h2 className="text-base font-semibold text-ink">Your focus: balanced, regular meals</h2>
      <p className="mt-1 text-sm text-muted">
        Instead of counting numbers, your plan is built around steady, nourishing habits.
      </p>
      <ul className="mt-3 flex list-disc flex-col gap-2 pl-5 text-sm text-ink-soft">
        {HABITS.map((habit) => (
          <li key={habit}>{habit}</li>
        ))}
      </ul>
      <p className="mt-3 text-sm text-muted">
        If food or eating feels hard right now, talking to a doctor or counsellor can really help.
      </p>
    </section>
  )
}

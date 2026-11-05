import type { Targets } from './types'

// Shows numbers exactly as the backend calculated them (no maths here, CLAUDE.md).
const format = (n: number) => n.toLocaleString('en-IN')

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
        <p role="note" className="rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          {targets.doctor_note}
        </p>
      )}

      {targets.focus_on_habits ? <Habits /> : <Numbers targets={targets} />}

      {targets.reasons.length > 0 && (
        <section className="rounded-xl bg-white p-4 shadow-sm">
          <h2 className="text-sm font-semibold text-slate-800">
            {targets.focus_on_habits ? 'About your plan' : 'Why these numbers'}
          </h2>
          <ul className="mt-2 flex list-disc flex-col gap-1 pl-5 text-sm text-slate-600">
            {targets.reasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        </section>
      )}

      <p className="text-center text-xs text-slate-500">
        Your weekly meal and workout plans are coming in a later update.
      </p>
    </div>
  )
}

function Numbers({ targets }: { targets: Targets }) {
  const macros = [
    ['Protein', targets.protein_g],
    ['Carbs', targets.carbs_g],
    ['Fat', targets.fat_g],
  ] as const

  return (
    <section className="rounded-xl bg-white p-5 text-center shadow-sm">
      <p className="text-sm text-slate-500">Your daily target</p>
      <p className="mt-1 text-4xl font-bold text-slate-900">
        {format(targets.calorie_target_kcal ?? 0)} <span className="text-base font-medium text-slate-500">kcal</span>
      </p>
      <dl className="mt-5 grid grid-cols-3 gap-2">
        {macros.map(([label, grams]) => (
          <div key={label} className="rounded-lg bg-slate-50 px-2 py-3">
            <dt className="text-xs text-slate-500">{label}</dt>
            <dd className="text-lg font-semibold text-slate-900">{format(grams ?? 0)} g</dd>
          </div>
        ))}
      </dl>
    </section>
  )
}

function Habits() {
  return (
    <section className="rounded-xl bg-white p-5 shadow-sm">
      <h2 className="text-base font-semibold text-slate-900">Your focus: balanced, regular meals</h2>
      <p className="mt-1 text-sm text-slate-500">
        Instead of counting numbers, your plan is built around steady, nourishing habits.
      </p>
      <ul className="mt-3 flex list-disc flex-col gap-2 pl-5 text-sm text-slate-700">
        {HABITS.map((habit) => (
          <li key={habit}>{habit}</li>
        ))}
      </ul>
      <p className="mt-3 text-sm text-slate-600">
        If food or eating feels hard right now, talking to a doctor or counsellor can really help.
      </p>
    </section>
  )
}

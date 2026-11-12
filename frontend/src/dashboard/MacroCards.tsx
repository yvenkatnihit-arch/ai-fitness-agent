import type { Progress, ProgressOut } from './types'

// Protein first and biggest: it is the number that matters most for the goal. Carbs and fat sit side by side below it.
function Bar({ label, value }: { label: string; value: Progress }) {
  const over = value.percent > 100
  return (
    <div
      role="progressbar" aria-label={`${label} eaten today`} aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.min(value.percent, 100)}
      aria-valuetext={`${value.percent}% of your ${label.toLowerCase()} target`}
      className="h-2 overflow-hidden rounded-full bg-surface-2"
    >
      <div className={`h-full rounded-full transition-[width] duration-1000 ease-out ${over ? 'bg-warn' : 'bg-brand'}`} style={{ width: `${Math.min(value.percent, 100)}%` }} />
    </div>
  )
}

function Card({ label, value, big }: { label: string; value: Progress; big?: boolean }) {
  return (
    <div className={`glass flex flex-col gap-2 rounded-2xl p-4 ${big ? 'col-span-2' : ''}`}>
      <div className="flex items-baseline justify-between">
        <span className={`font-semibold ${big ? 'text-brand-strong' : 'text-ink'}`}>{label}</span>
        <span className="text-xs text-muted">{value.percent}% of target</span>
      </div>
      <span className={`font-extrabold tabular-nums text-ink ${big ? 'text-3xl' : 'text-xl'}`}>
        {Math.round(value.eaten)}
        <span className="text-sm font-medium text-muted"> / {Math.round(value.target)} g</span>
      </span>
      <Bar label={label} value={value} />
    </div>
  )
}

export function MacroCards({ progress }: { progress: ProgressOut }) {
  return (
    <div className="grid grid-cols-2 gap-3">
      <Card label="Protein" value={progress.protein_g} big />
      <Card label="Carbs" value={progress.carbs_g} />
      <Card label="Fat" value={progress.fat_g} />
    </div>
  )
}

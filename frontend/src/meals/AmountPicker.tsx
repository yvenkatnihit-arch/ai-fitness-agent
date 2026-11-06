import { useState } from 'react'

import { inputClass } from '../components/ui'
import { unitLabel } from './slots'
import type { DraftItem, FoodHit } from './types'

// For the food just picked: how much, in which unit. Household units first (1 katori, 2 piece), grams always available.
export function AmountPicker({ food, onAdd, onCancel }: {
  food: FoodHit
  onAdd: (item: DraftItem) => void
  onCancel: () => void
}) {
  const hasUnits = food.units.length > 0
  const [unit, setUnit] = useState(hasUnits ? food.units[0].unit : 'g')
  const [quantity, setQuantity] = useState(hasUnits ? '1' : '100')
  const amount = Number(quantity)
  const valid = quantity.trim() !== '' && Number.isFinite(amount) && amount > 0

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-emerald-200 bg-emerald-50 p-3">
      <p className="text-sm font-medium text-slate-800">{food.name}</p>
      <div className="flex gap-2">
        <label className="flex w-24 flex-col gap-1 text-xs font-medium text-slate-700">
          Amount
          <input
            type="number"
            inputMode="decimal"
            min="0"
            step="any"
            value={quantity}
            onChange={(e) => setQuantity(e.target.value)}
            className={inputClass}
          />
        </label>
        <label className="flex flex-1 flex-col gap-1 text-xs font-medium text-slate-700">
          Unit
          <select value={unit} onChange={(e) => setUnit(e.target.value)} className={inputClass}>
            {food.units.map((u) => (
              <option key={u.unit} value={u.unit}>{unitLabel(u.unit, u.grams)}</option>
            ))}
            <option value="g">grams</option>
          </select>
        </label>
      </div>
      <div className="flex gap-2">
        <button
          type="button"
          disabled={!valid}
          onClick={() => onAdd({ food, quantity: amount, unit })}
          className="flex-1 rounded-lg bg-emerald-600 px-3 py-2 text-sm font-semibold text-white disabled:opacity-50"
        >
          Add to meal
        </button>
        <button type="button" onClick={onCancel} className="rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-700">
          Cancel
        </button>
      </div>
    </div>
  )
}

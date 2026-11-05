// Categorical slots 1-3 of the data-viz reference palette, checked with its validator:
// colour-blind safe as a set (worst pair ΔE 9.2); aqua is under 3:1 on white, so the legend
// always shows every value as text and colour never carries meaning alone.
export const MACRO_COLORS = { protein: '#2a78d6', carbs: '#eb6834', fat: '#1baf7a' } as const

export type MacroSlice = { name: string; grams: number; percent: number; color: string }

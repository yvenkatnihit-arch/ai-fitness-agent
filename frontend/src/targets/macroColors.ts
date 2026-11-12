// On the dark theme: neon lime for protein (the number that matters most), sky blue for carbs, amber for fat.
// The legend always shows every value as text, so colour never carries meaning alone.
export const MACRO_COLORS = { protein: '#b7ff35', carbs: '#7dd3fc', fat: '#fbbf24' } as const

export type MacroSlice = { name: string; grams: number; percent: number; color: string }

// Mirrors backend/app/schemas/insights.py (InsightsOut). Every number is calculated by the backend.
export type UsageTotals = { calls: number; input_tokens: number; output_tokens: number; cost_usd: number; avg_latency_ms: number; failed_calls: number }
export type UsageDay = { day: string; calls: number; cost_usd: number }
export type UsageStep = { step: string; calls: number; avg_latency_ms: number; cost_usd: number }
export type Usage = { days: number; totals: UsageTotals; per_day: UsageDay[]; per_step: UsageStep[] }
export type EvalResult = { name: string; cases: number; metric: string; percent: number; pass_line_percent: number; decision: string }
export type Quality = { as_of: string; source: string; evals: EvalResult[] }
export type Insights = { usage: Usage; quality: Quality; rules: string[] }

"""What GET /insights/ai returns (Step 8.7, D-113): the signed-in user's OWN AI usage, the published quality results, and the rules the AI cannot break."""

from datetime import date

from pydantic import BaseModel


class UsageTotals(BaseModel):
    calls: int
    input_tokens: int
    output_tokens: int
    cost_usd: float
    avg_latency_ms: int
    failed_calls: int


class UsageDay(BaseModel):
    day: date
    calls: int
    cost_usd: float


class UsageStep(BaseModel):
    step: str                 # router, nutrition, composer, plan picker ...
    calls: int
    avg_latency_ms: int
    cost_usd: float


class UsageOut(BaseModel):
    days: int
    totals: UsageTotals
    per_day: list[UsageDay]
    per_step: list[UsageStep]


class EvalResult(BaseModel):
    name: str
    cases: int
    metric: str
    percent: float
    pass_line_percent: float
    decision: str


class EvalsOut(BaseModel):
    as_of: date
    source: str
    evals: list[EvalResult]


class InsightsOut(BaseModel):
    usage: UsageOut
    quality: EvalsOut
    rules: list[str]


# Plain statements about how the AI is kept in check. Each is enforced in code and tested; none depends on the AI behaving well.
RULES = [
    "Calories, macros, portions, daily targets and trends are calculated by tested code, never by the AI.",
    "The AI can only choose foods and exercises that exist in our database and library, and code works out the amounts.",
    "Anything the AI suggests, a plan or a meal to log, is a proposal: nothing is saved until you press Approve.",
    "Safety limits (calorie floors, deficit and protein caps, health-screening rules) are fixed in code the AI cannot change.",
    "Crisis and harmful messages are stopped by code before any AI runs, and every reply is checked on the way out.",
    "Users with an eating-disorder history never see calorie, macro or weight numbers, on any screen or in chat.",
    "Your data is locked to you in the database (row-level security), and the server checks it again.",
    "Chat is limited to 15 messages in 10 minutes, and every AI call is logged with its tokens, cost and time.",
]

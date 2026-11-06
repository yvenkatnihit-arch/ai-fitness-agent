"""Cost estimates for agent_runs. Prices are USD per 1 million tokens, PAID tier, text.

These are ESTIMATES kept in code so cost per day is visible; the Google bill is the truth.
Check https://ai.google.dev/gemini-api/docs/pricing when models change. A model we have no
price for is billed at the most expensive known price, so a surprise never looks cheap.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Price:
    input: float
    output: float
    cached_input: float


PRICES: dict[str, Price] = {
    "gemini-2.5-flash": Price(input=0.30, output=2.50, cached_input=0.03),
    "gemini-2.5-flash-lite": Price(input=0.10, output=0.40, cached_input=0.01),
}
_WORST = max(PRICES.values(), key=lambda p: p.output)


def estimate_cost_usd(model: str, input_tokens: int, output_tokens: int, cached_tokens: int = 0) -> float:
    """Cost of one call. `input_tokens` includes the cached ones; cached tokens are billed cheaper."""
    price = PRICES.get(model, _WORST)
    cached = min(cached_tokens, input_tokens)
    fresh = input_tokens - cached
    return (fresh * price.input + cached * price.cached_input + output_tokens * price.output) / 1_000_000

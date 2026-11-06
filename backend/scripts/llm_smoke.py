"""One tiny real Gemini call to prove the key and model IDs work. Costs a fraction of a cent.

Run from backend/:  uv run python scripts/llm_smoke.py [small|mid]
Test data only (free tier may be used by Google to improve its products).
"""

import sys

from app.db.pool import close_pool
from app.llm.client import call_llm, model_name

tier = sys.argv[1] if len(sys.argv) > 1 else "small"
print(f"tier={tier} model={model_name(tier)}")
result = call_llm(tier, [("human", "Reply with exactly one word: ready")], flow="plan_generation", node="smoke", max_tokens=200)
print("reply:", result.text)
print(f"tokens in/out/cached: {result.input_tokens}/{result.output_tokens}/{result.cached_tokens}")
print(f"cost (estimate): ${result.cost_usd:.6f}   latency: {result.latency_ms} ms")
close_pool()   # the run was logged to agent_runs; close the pool cleanly

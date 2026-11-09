"""Ask the nutrition specialist a question with the REAL Gemini and the REAL foods table (a fraction of a cent, saves nothing).

Run from backend/ (PowerShell: set $env:PYTHONPATH='.' first):
  uv run python scripts/nutrition_demo.py "How much protein is in paneer?"
Uses a made-up user id, so the agent_runs row cannot be saved (that is only logged); foods are readable by any signed-in user.
"""

import sys
from uuid import uuid4

from app.agents.nutrition import run_nutrition
from app.db.pool import close_pool

question = " ".join(sys.argv[1:]) or "How much protein is in paneer?"
result = run_nutrition(question, uuid4())
print(f"Q: {question}\nA: {result.answer}\n")
print(f"status={result.status} steps={result.steps} tokens={result.tokens}")
for t in result.tools:
    print(f"  tool {t.name}: {t.outcome} {t.detail}")
close_pool()

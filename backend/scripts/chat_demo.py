"""Send one message through the chat graph (router, specialists) with the REAL Gemini and the REAL foods table.

Run from backend/ (PowerShell: set $env:PYTHONPATH='.' first):
  uv run python scripts/chat_demo.py "How much protein is in paneer?"
A fraction of a cent per message; saves nothing. Uses a made-up user id, so the agent_runs rows cannot be saved (only logged).
"""

import sys
from uuid import uuid4

from app.agents.chat_graph import answer_message
from app.db.pool import close_pool

message = " ".join(sys.argv[1:]) or "How much protein is in paneer?"
out = answer_message(message, uuid4())
print(f"You: {message}\nCoach: {out['reply']}\n")
print("Router picked:", [f"{a.specialist}: {a.task}" for a in out["assignments"]] or "nothing")
for r in out["results"]:
    print(f"  {r['specialist']}: {r['status']}, {r['steps']} steps, {r['tokens']} tokens, tools={[t.name + ':' + t.outcome for t in r['tools']]}")
close_pool()

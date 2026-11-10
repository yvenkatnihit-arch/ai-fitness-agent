"""How much of the protein target do meal plans reach? Offline: the REAL validated foods (data/*.csv), the engine's real targets, the code
fallback picks (no model, no database, no cost, saves nothing). Step 7.10d-3 (D-093).

Run from backend/ (PowerShell: set $env:PYTHONPATH='.' first):
  uv run python scripts/protein_report.py            # every cuisine, diet and test user
  uv run python scripts/protein_report.py mediterranean
Each line: the worst to best day, as a percent of that user's protein target; "ok days" = days with no solver issue.
"""

import logging
import sys

from evals.protein_report import measure, pool_foods

if __name__ == "__main__":
    logging.disable(logging.WARNING)
    foods = pool_foods()
    for cuisine in sys.argv[1:] or ["indian", "mediterranean"]:
        print()
        print(f"== {cuisine} ==")
        for who, diet, text in measure(foods, cuisine):
            print(f"  {who:16} {diet:15} {text}")

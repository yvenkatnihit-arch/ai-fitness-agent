"""Run the model-based evals with REAL Gemini calls.   From backend/:  uv run python -m evals.run_llm router [--fresh]

About a cent or less. Results are cached in evals/cache/ (git-ignored), so unchanged cases cost nothing; `--fresh` ignores the cache.
The gate compares with evals/llm_thresholds.json (set below the measured value, because model output is noisy). Exit code 1 on failure.
"""

import json
import sys
from pathlib import Path

from evals import router_eval

THRESHOLDS = Path(__file__).with_name("llm_thresholds.json")
HIGHER_IS_BETTER = ("exact_accuracy", "nutrition_recall", "off_topic_specificity")
LOWER_IS_BETTER = ("invalid_json_rate", "off_menu_rate", "duplicate_rate")


def gate(summary: dict, thresholds: dict) -> list[str]:
    failures = [f"{k} {summary[k]:.1%} is below {thresholds[k]:.1%}" for k in HIGHER_IS_BETTER if k in thresholds and summary[k] < thresholds[k]]
    failures += [f"{k} {summary[k]:.1%} is above {thresholds[k]:.1%}" for k in LOWER_IS_BETTER if k in thresholds and summary[k] > thresholds[k]]
    return failures


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] != "router":
        print(__doc__)
        return 2
    results = router_eval.run_router_eval(use_cache="--fresh" not in sys.argv)
    s = router_eval.summarize(results)
    print(f"Router eval: {s['cases']} cases ({s['scored']} scored, {s['borderline']} borderline)")
    print(f"  exact accuracy {s['exact_accuracy']:.1%}   nutrition recall {s['nutrition_recall']:.1%}   off-topic specificity {s['off_topic_specificity']:.1%}")
    print(f"  borderline acceptable {s['borderline_acceptable']:.1%}   invalid JSON {s['invalid_json_rate']:.1%}   "
          f"off-menu names {s['off_menu_rate']:.1%}   duplicates {s['duplicate_rate']:.1%}")
    print(f"  avg {s['avg_tokens']:.0f} tokens/call   median {s['median_latency_ms']:.0f} ms   total ${s['total_cost_usd']:.5f}")
    wrong = [r for r in results if not r.passed]
    for r in wrong:
        print(f"  WRONG{' (borderline)' if 'borderline' in r.tags else ''}: {r.message!r}: expected {r.expected or '[]'}, got {r.got or '[]'}"
              + (f", off-menu {r.off_menu}" if r.off_menu else ""))
    thresholds = json.loads(THRESHOLDS.read_text(encoding="utf-8")).get("router", {}) if THRESHOLDS.exists() else {}
    failures = gate(s, thresholds)
    print("\nGATE:", "FAILED: " + "; ".join(failures) if failures else ("passed" if thresholds else "no thresholds set yet"))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

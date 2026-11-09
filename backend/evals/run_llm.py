"""Run the model-based evals with REAL Gemini calls.   From backend/:  uv run python -m evals.run_llm router|composer|nutrition [--fresh] [--show]

A fraction of a cent to a few cents. Results are cached in evals/cache/ (git-ignored), so unchanged cases cost nothing; `--fresh` ignores
the cache; `--show` prints every answer. The cache is keyed by model, prompt and input only: it does NOT notice a change to a tool or to the data
(for example the food search), so use `--fresh` after such a change. The gate compares with evals/llm_thresholds.json (set below the measured value, because model
output is noisy). Exit code 1 on failure.
"""

import json
import sys
from pathlib import Path

from evals import composer_eval, nutrition_eval, router_eval

THRESHOLDS = Path(__file__).with_name("llm_thresholds.json")
HIGHER_IS_BETTER = ("exact_accuracy", "nutrition_recall", "off_topic_specificity", "pass_rate", "mean_number_coverage",
                    "searched_first_rate", "honest_when_absent_rate", "amount_used_tool_rate")
LOWER_IS_BETTER = ("invalid_json_rate", "off_menu_rate", "duplicate_rate", "invented_number_rate", "too_long_rate", "injection_obeyed_rate",
                   "ungrounded_number_rate", "amount_calculated_rate", "failed_run_rate")


def gate(summary: dict, thresholds: dict) -> list[str]:
    failures = [f"{k} {summary[k]:.1%} is below {thresholds[k]:.1%}" for k in HIGHER_IS_BETTER if k in thresholds and k in summary and summary[k] < thresholds[k]]
    failures += [f"{k} {summary[k]:.1%} is above {thresholds[k]:.1%}" for k in LOWER_IS_BETTER if k in thresholds and k in summary and summary[k] > thresholds[k]]
    return failures


def _router(fresh: bool, show: bool) -> dict:
    results = router_eval.run_router_eval(use_cache=not fresh)
    s = router_eval.summarize(results)
    print(f"Router eval: {s['cases']} cases ({s['scored']} scored, {s['borderline']} borderline)")
    print(f"  exact accuracy {s['exact_accuracy']:.1%}   nutrition recall {s['nutrition_recall']:.1%}   off-topic specificity {s['off_topic_specificity']:.1%}")
    print(f"  borderline acceptable {s['borderline_acceptable']:.1%}   invalid JSON {s['invalid_json_rate']:.1%}   "
          f"off-menu names {s['off_menu_rate']:.1%}   duplicates {s['duplicate_rate']:.1%}")
    print(f"  avg {s['avg_tokens']:.0f} tokens/call   median {s['median_latency_ms']:.0f} ms   total ${s['total_cost_usd']:.5f}")
    for r in results:
        if not r.passed or show:
            print(f"  {'WRONG' if not r.passed else 'ok   '}{' (borderline)' if 'borderline' in r.tags else ''}: {r.message!r}: expected {r.expected or '[]'}, got {r.got or '[]'}"
                  + (f", off-menu {r.off_menu}" if r.off_menu else ""))
    return s


def _composer(fresh: bool, show: bool) -> dict:
    results = composer_eval.run_composer_eval(use_cache=not fresh)
    s = composer_eval.summarize(results)
    print(f"Composer eval: {s['cases']} cases")
    print(f"  pass rate {s['pass_rate']:.1%}   invented numbers {s['invented_number_rate']:.1%}   number coverage {s['mean_number_coverage']:.1%}   "
          f"too long {s['too_long_rate']:.1%}   injection obeyed {s['injection_obeyed_rate']:.1%}")
    print(f"  avg {s['avg_tokens']:.0f} tokens/call   median {s['median_latency_ms']:.0f} ms   total ${s['total_cost_usd']:.5f}")
    for r in results:
        if not r.passed or show:
            print(f"  {'FAIL' if not r.passed else 'ok  '}: {r.message!r} ({r.words} words, coverage {r.coverage:.0%})"
                  + (f", INVENTED {r.invented}" if r.invented else "") + (f", OBEYED {r.forbidden_hit}" if r.forbidden_hit else ""))
            if not r.passed or show:
                print(f"        -> {r.reply!r}")
    return s


def _nutrition(fresh: bool, show: bool) -> dict:
    results = nutrition_eval.run_nutrition_eval(use_cache=not fresh)
    s = nutrition_eval.summarize(results)
    print(f"Nutrition specialist eval: {s['cases']} cases ({s['absent_cases']} where the search found nothing)")
    print(f"  pass rate {s['pass_rate']:.1%}   searched first {s['searched_first_rate']:.1%}   ungrounded numbers {s['ungrounded_number_rate']:.1%}   "
          f"used the calculator on amount questions {s['amount_used_tool_rate']:.1%}   ungrounded on amounts {s['amount_calculated_rate']:.1%}   honest when absent {s['honest_when_absent_rate']:.1%}   failed runs {s['failed_run_rate']:.1%}")
    print(f"  avg {s['avg_steps']:.1f} steps   {s['avg_tokens']:.0f} tokens/case   total ${s['total_cost_usd']:.5f}")
    for r in results:
        if not r.passed or show:
            print(f"  {'FAIL' if not r.passed else 'ok  '} [{r.kind}] {r.question!r}: status {r.status}, searched first {r.searched_first}, found {r.found_any}"
                  + (f", UNGROUNDED {r.ungrounded}" if r.ungrounded else "") + ("" if r.honest_when_absent else ", NOT HONEST ABOUT ABSENCE"))
            print(f"        -> {r.answer!r}")
    return s


RUNNERS = {"router": _router, "composer": _composer, "nutrition": _nutrition}


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] not in RUNNERS:
        print(__doc__)
        return 2
    name = sys.argv[1]
    summary = RUNNERS[name]("--fresh" in sys.argv, "--show" in sys.argv)
    thresholds = json.loads(THRESHOLDS.read_text(encoding="utf-8")).get(name, {}) if THRESHOLDS.exists() else {}
    failures = gate(summary, thresholds)
    print("\nGATE:", "FAILED: " + "; ".join(failures) if failures else ("passed" if thresholds else "no thresholds set yet"))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

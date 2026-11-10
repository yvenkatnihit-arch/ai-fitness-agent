"""Run the model-based evals with REAL Gemini calls.   From backend/:  uv run python -m evals.run_llm router|composer|nutrition|workout|meal [--fresh] [--limit=N] [--show]

A fraction of a cent to a few cents. Results are cached in evals/cache/ (git-ignored), so unchanged cases cost nothing; `--fresh` ignores
the cache; `--show` prints every answer. The cache is keyed by model, prompt and input only: it does NOT notice a change to a tool or to the data
(for example the food search), so use `--fresh` after such a change. The gate compares with evals/llm_thresholds.json (set below the measured value, because model
output is noisy). Exit code 1 on failure.
"""

import json
import sys
from pathlib import Path

from evals import composer_eval, meal_eval, nutrition_eval, router_eval, workout_eval

THRESHOLDS = Path(__file__).with_name("llm_thresholds.json")
HIGHER_IS_BETTER = ("followup_route_accuracy", "followup_resolved_rate", "exact_accuracy", "nutrition_recall", "off_topic_specificity", "pass_rate", "mean_number_coverage",
                    "searched_first_rate", "honest_when_absent_rate", "amount_used_tool_rate", "scenario_pass_rate", "model_day_rate",
                    "mean_pattern_coverage", "count_ok_rate", "focus_ok_rate", "ok_day_rate", "mean_protein_ratio")
LOWER_IS_BETTER = ("invalid_json_rate", "off_menu_rate", "duplicate_rate", "invented_number_rate", "too_long_rate", "injection_obeyed_rate",
                   "ungrounded_number_rate", "amount_calculated_rate", "failed_run_rate", "safety_violation_rate", "payload_problem_rate",
                   "weekly_cap_breach_rate", "refused_rate", "mean_repeat_rate", "avg_cost_usd", "unresolved_cap_rate")


def _fmt(key: str, value: float) -> str:
    return f"${value:.4f}" if key.endswith("_usd") else f"{value:.1%}"


def gate(summary: dict, thresholds: dict) -> list[str]:
    failures = [f"{k} {_fmt(k, summary[k])} is below {_fmt(k, thresholds[k])}" for k in HIGHER_IS_BETTER if k in thresholds and k in summary and summary[k] < thresholds[k]]
    failures += [f"{k} {_fmt(k, summary[k])} is above {_fmt(k, thresholds[k])}" for k in LOWER_IS_BETTER if k in thresholds and k in summary and summary[k] > thresholds[k]]
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
    follow = router_eval.run_followup_eval(use_cache=not fresh)
    f = router_eval.summarize_followups(follow)
    print(f"Follow-up eval (the router sees earlier messages): {f['followup_cases']} cases")
    print(f"  right specialist {f['followup_route_accuracy']:.1%}   task rewritten to stand alone {f['followup_resolved_rate']:.1%}   "
          f"borderline acceptable {f['followup_borderline_ok']:.1%}   total ${f['followup_cost_usd']:.5f}")
    for r in follow:
        if not (r.route_ok and r.resolved) or show:
            print(f"  {'WRONG' if not (r.route_ok and r.resolved) else 'ok   '}: {r.message!r}: expected {r.expected or '[]'}, got {r.got or '[]'}, task {r.task!r}")
    return {**s, **f}


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


def _workout(fresh: bool, show: bool) -> dict:
    from app.db import admin_transaction
    from app.db import exercises as exercises_repo
    from app.db.pool import close_pool

    with admin_transaction("eval: read the exercise library") as conn:   # read-only reference data; nothing is saved
        library = exercises_repo.list_exercises(conn)
    close_pool()
    results = workout_eval.run_workout_eval(library, use_cache=not fresh)
    s = workout_eval.summarize(results)
    print(f"Workout plan eval: {s['scenarios']} made-up users ({s['refused']} refused as 'not enough safe exercises')")
    print(f"  SAFETY violations {s['safety_violation_rate']:.1%}   payload problems {s['payload_problem_rate']:.1%}   weekly cap breaches {s['weekly_cap_breach_rate']:.1%}"
          f"   plans passing {s['scenario_pass_rate']:.1%}")
    print(f"  days chosen by the model {s['model_day_rate']:.1%} (rest by the code fallback)   plans needing a retry {s['retry_rate']:.1%}   pattern coverage {s['mean_pattern_coverage']:.1%}"
          f"   day size on target {s['count_ok_rate']:.1%}   focus honoured {s['focus_ok_rate']:.1%}   repeated across days {s['mean_repeat_rate']:.1%}")
    print(f"  weekly cap: {s['trimmed_plan_rate']:.0%} of plans were trimmed (on average {s['mean_sets_trimmed']:.1f} sets and {s['mean_exercises_trimmed']:.1f} exercises); "
          f"cap not reachable in {s['unresolved_cap_rate']:.0%}")
    print(f"  avg {s['avg_tokens']:.0f} tokens/plan   median {s['median_latency_ms']:.0f} ms   total ${s['total_cost_usd']:.4f}")
    for r in results:
        if show or not r.passed or r.refused:
            print(f"  {'REFUSED' if r.refused else ('FAIL' if not r.passed else 'ok')}: {r.name}  sources {list(r.sources)}  asks {r.asks}"
                  + (f"  {r.refusal}" if r.refused else "") + (f"  SAFETY {list(r.safety)}" if r.safety else "")
                  + (f"  PROBLEMS {list(r.problems)}" if r.problems else "") + (f"  CAP {list(r.cap_breaches)}" if r.cap_breaches else "")
                  + (f"  trimmed {r.sets_trimmed} sets, {r.exercises_trimmed} exercises" if r.sets_trimmed or r.exercises_trimmed else ""))
    return s


def _meal(fresh: bool, show: bool) -> dict:
    from app.db import admin_transaction
    from app.db.meal_foods import list_pool_foods
    from app.db.pool import close_pool

    with admin_transaction("eval: read the foods") as conn:   # read-only reference data; nothing is saved
        foods = list_pool_foods(conn)
    close_pool()
    limit = next((int(a.split("=")[1]) for a in sys.argv if a.startswith("--limit=")), None)
    if "--thinking-default" in sys.argv:   # A/B only: this run uses the model's default thinking instead of the app's setting (cached separately)
        from app.workflows.pick_meals import MEAL_CALL
        MEAL_CALL["thinking_budget"] = None
        print("NOTE: --thinking-default is on: this is NOT the app's setting")
    from evals.meal_cases import SCENARIOS
    results = meal_eval.run_meal_eval(foods, use_cache=not fresh, scenarios=SCENARIOS[:limit] if limit else None)
    s = meal_eval.summarize(results)
    print(f"Meal plan eval: {s['scenarios']} made-up users ({s['refused']} refused: pool too small or no safe day)")
    print(f"  SAFETY violations {s['safety_violation_rate']:.1%}   verify problems {s['payload_problem_rate']:.1%}   plans passing {s['scenario_pass_rate']:.1%}")
    print(f"  days chosen by the model {s['model_day_rate']:.1%}   plans needing a repair round {s['repair_rate']:.1%}   days with solver status ok {s['ok_day_rate']:.1%}")
    print(f"  protein reached: mean {s['mean_protein_ratio']:.0%} of target, worst day {s['min_protein_ratio']:.0%}   dishes repeated in the week {s['mean_repeat_rate']:.1%}")
    print(f"  avg {s['avg_tokens_out']:.0f} output tokens/plan   avg ${s['avg_cost_usd']:.4f}/plan   median {s['median_latency_ms'] / 1000:.1f} s   total ${s['total_cost_usd']:.4f}")
    for r in results:
        if show or not r.passed or r.refused:
            pct = f"protein {min(r.protein_pct):.0f}-{max(r.protein_pct):.0f}%" if r.protein_pct else ""
            print(f"  {'REFUSED' if r.refused else ('FAIL' if not r.passed else 'ok')}: {r.name}  sources {''.join(x[0] for x in r.sources)}  "
                  f"calls {r.model_calls}  {pct}  out {r.tokens_out} tok  ${r.cost_usd:.4f}  {r.latency_ms / 1000:.0f}s"
                  + (f"  {r.refusal}" if r.refused else "") + (f"  SAFETY {list(r.safety)[:3]}" if r.safety else "") + (f"  PROBLEMS {list(r.problems)[:3]}" if r.problems else ""))
    return s


RUNNERS = {"router": _router, "composer": _composer, "nutrition": _nutrition, "workout": _workout, "meal": _meal}


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

"""Run the guard evals and print a report.   From backend/:  uv run python -m evals.run [--update-baseline]

Exit code 1 when the gate fails (a critical case fails, or a case that used to pass now fails). No LLM, no network, free.
"""

import sys

from evals import guards


def main() -> int:
    results = guards.run_cases()
    summary = guards.summarize(results)
    print(f"Guard evals: {summary['cases']} cases")
    for category, recall in summary["recall_by_category"].items():
        print(f"  recall {category:<16} {recall:6.1%}")
    print(f"  false-positive rate on harmless messages: {summary['false_positive_rate']:.1%}")
    print(f"  known gaps: {summary['known_gaps']} cases, {summary['known_gaps_now_passing']} now handled "
          f"(gap recall {summary['gap_recall']:.1%}, gap false positives {summary['gap_false_positive_rate']:.1%})")
    still_wrong = [r for r in results if not r.passed]
    if still_wrong:
        print("\nStill wrong (expected -> got):")
        for r in still_wrong:
            print(f"  [{'gap' if 'gap' in r.tags else 'NEW'}] {r.text!r}: {r.expected} -> {r.got}")
    critical, regressions, improvements = guards.gate(results, guards.load_baseline())
    if "--update-baseline" in sys.argv:
        guards.save_baseline(results)
        print(f"\nBaseline updated ({sum(r.passed for r in results)} passing cases).")
        return 0
    for title, rs in (("CRITICAL FAILURES", critical), ("REGRESSIONS", regressions)):
        if rs:
            print(f"\n{title}:")
            for r in rs:
                print(f"  {r.text!r}: expected {r.expected}, got {r.got}")
    if improvements:
        print(f"\n{len(improvements)} case(s) now pass that the baseline does not know about: run with --update-baseline to lock them in.")
    print("\nGATE:", "FAILED" if critical or regressions else "passed")
    return 1 if critical or regressions else 0


if __name__ == "__main__":
    raise SystemExit(main())

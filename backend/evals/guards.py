"""Run the guard eval cases and compare with the committed baseline (Step 7.7a, D-079).

The gate has two rules:
  1. every case tagged "critical" must pass, always;
  2. every case that passed in baseline_guards.json must still pass (no regressions). Improvements are reported, and
     `python -m evals.run --update-baseline` locks them in.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from evals.guard_cases import CASES
from app.safety.guards import check_input, check_output

BASELINE = Path(__file__).with_name("baseline_guards.json")


@dataclass(frozen=True)
class Result:
    id: str
    kind: str
    text: str
    expected: str | None
    got: str | None
    tags: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return self.got == self.expected


def run_cases() -> list[Result]:
    out = []
    for kind, text, expected, tags in CASES:
        verdict = (check_input if kind == "in" else check_output)(text)
        out.append(Result(f"{kind}:{text}", kind, text, expected, verdict.category if verdict else None, tags))
    return out


def summarize(results: list[Result]) -> dict:
    """Recall per category (non-gap cases), false-positive rate, and how many known gaps are still open."""
    plain = [r for r in results if "gap" not in r.tags]
    gaps = [r for r in results if "gap" in r.tags]
    categories = sorted({r.expected for r in plain if r.expected})
    recall = {c: _rate([r for r in plain if r.expected == c]) for c in categories}
    benign = [r for r in plain if r.expected is None]
    return {
        "cases": len(results), "recall_by_category": recall,
        "false_positive_rate": 1 - _rate(benign) if benign else 0.0,
        "known_gaps": len(gaps), "known_gaps_now_passing": sum(r.passed for r in gaps),
        "gap_recall": _rate([r for r in gaps if r.expected]), "gap_false_positive_rate": 1 - _rate([r for r in gaps if r.expected is None]),
    }


def _rate(rs: list[Result]) -> float:
    return sum(r.passed for r in rs) / len(rs) if rs else 1.0


def load_baseline() -> set[str]:
    return set(json.loads(BASELINE.read_text(encoding="utf-8"))["passing"]) if BASELINE.exists() else set()


def save_baseline(results: list[Result]) -> None:
    BASELINE.write_text(json.dumps({"passing": sorted(r.id for r in results if r.passed)}, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def gate(results: list[Result], baseline: set[str]) -> tuple[list[Result], list[Result], list[Result]]:
    """(critical failures, regressions against the baseline, improvements not yet in the baseline)."""
    critical = [r for r in results if "critical" in r.tags and not r.passed]
    regressions = [r for r in results if r.id in baseline and not r.passed]
    improvements = [r for r in results if r.passed and r.id not in baseline]
    return critical, regressions, improvements

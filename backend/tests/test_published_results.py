"""Step 8.7 (D-113): the published quality results can never disagree with the real gates. Offline."""

import json
from pathlib import Path

import pytest

from app.schemas.insights import RULES
from app.workflows.ai_usage import PUBLISHED, published_results

THRESHOLDS = json.loads((Path(__file__).resolve().parents[1] / "evals" / "llm_thresholds.json").read_text(encoding="utf-8"))
RAW = json.loads(PUBLISHED.read_text(encoding="utf-8"))["evals"]


@pytest.mark.parametrize("entry", RAW, ids=[e["threshold"] for e in RAW])
def test_each_pass_line_is_the_real_threshold_and_each_score_clears_it(entry):
    group, key = entry["threshold"].split(".")
    assert entry["pass_line_percent"] == round(THRESHOLDS[group][key] * 100, 1)          # the page shows the gate that is really enforced
    assert entry["percent"] >= entry["pass_line_percent"]                                  # a published score below its own gate would be a failing run
    assert entry["cases"] > 0 and 0 <= entry["percent"] <= 100 and entry["decision"].startswith("D-")


def test_the_file_parses_into_the_response_shape_with_a_date_and_a_source():
    out = published_results()
    assert out.as_of.isoformat() == "2026-11-11" and "latest recorded run" in out.source and len(out.evals) == len(RAW) >= 5


def test_the_rules_are_plain_unique_statements_and_include_the_ones_users_rely_on():
    assert len(RULES) == len(set(RULES)) >= 6 and all(r.endswith(".") and len(r) < 200 for r in RULES)
    text = " ".join(RULES).lower()
    for phrase in ("never by the ai", "press approve", "eating-disorder history", "row-level security", "15 messages"):
        assert phrase in text


def test_the_stated_chat_limit_matches_the_real_limit():
    from app.core.chat_limits import WINDOWS
    assert (600, 15) in WINDOWS and "15 messages in 10 minutes" in " ".join(RULES)

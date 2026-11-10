"""Step 7.10f (D-095): the protein shortfall note is decided by code, never shown to the wrong people."""

import copy

import pytest

from app.calc import protein_note as pn
from app.calc.meal_plan_payload import how_made, hide_numbers
from tests.test_meal_plan_payload import week  # noqa: F401  (fixture)


def test_a_clear_shortfall_gets_a_note_with_diet_specific_suggestions():
    note = pn.protein_shortfall(48.2, "vegan", "high_protein")
    assert note == {"percent": 48, "suggestions": pn.SUGGESTIONS["vegan"]}
    assert "tofu" in note["suggestions"] and "paneer" not in note["suggestions"]


def test_a_plan_near_the_target_gets_no_note():
    assert pn.protein_shortfall(pn.NOTE_BELOW_PERCENT, "vegan", None) is None
    assert pn.protein_shortfall(97, "vegetarian", None) is None
    assert pn.protein_shortfall(pn.NOTE_BELOW_PERCENT - 0.1, "vegetarian", None) is not None


def test_the_kidney_flag_never_gets_an_eat_more_protein_note():
    assert pn.protein_shortfall(40, "vegetarian", "low_protein") is None             # its target is a CAP


def test_every_diet_has_suggestions_and_an_unknown_one_falls_back():
    assert {"vegan", "vegetarian", "eggetarian", "non_vegetarian"} <= set(pn.SUGGESTIONS)
    assert pn.protein_shortfall(10, "martian", None)["suggestions"] == pn.SUGGESTIONS["vegetarian"]


def test_the_note_is_in_the_plan_only_when_the_week_falls_short(week, monkeypatch):    # noqa: F811
    avg = how_made(week, False)["average_percent_of_target"]["protein"]
    monkeypatch.setattr(pn, "NOTE_BELOW_PERCENT", avg + 1)
    made = how_made(week, False, "vegan")
    assert made["protein_shortfall"]["percent"] == round(avg) and "tofu" in made["protein_shortfall"]["suggestions"]
    monkeypatch.setattr(pn, "NOTE_BELOW_PERCENT", avg - 1)
    assert "protein_shortfall" not in how_made(week, False, "vegan")


def test_a_user_whose_numbers_are_hidden_never_gets_it(week, monkeypatch):               # noqa: F811
    monkeypatch.setattr(pn, "NOTE_BELOW_PERCENT", 1000)
    assert "protein_shortfall" not in how_made(week, True, "vegan")
    payload = {"how_made": how_made(week, False, "vegan"), "days": []}
    assert "protein_shortfall" in payload["how_made"]
    assert "protein_shortfall" not in hide_numbers(copy.deepcopy(payload))["how_made"]

import pytest

from fooddata.build import VALIDATED
from fooddata.credits import CREDITS, build_credits, current_credits, render

MANIFEST = {"sources": [
    {"key": "usda_sr_legacy", "name": "USDA", "release": "2018-04", "license": "CC0", "license_url": "u1",
     "credit": "USDA ARS", "homepage": "h1", "url": "zip"},
    {"key": "uk_cofid", "name": "CoFID", "release": "2021-03", "license": "OGL v3.0", "license_url": "u2",
     "credit": "PHE 2021", "homepage": "h2", "url": "xlsx"},
]}


def rows(*sources):
    return [{"source": s} for s in sources]


def test_each_used_source_is_credited_with_its_food_count():
    credits = build_credits(MANIFEST, rows("uk_cofid", "uk_cofid", "usda_sr_legacy", "computed"))
    assert [(s["key"], s["foods"]) for s in credits["sources"]] == [("usda_sr_legacy", 1), ("uk_cofid", 2)]
    assert credits["sources"][1]["license_url"] == "u2"     # OGL asks for a link to the licence
    assert "url" not in credits["sources"][0]                # the raw download link isn't shown
    assert credits["recipes"][0]["foods"] == 1


def test_unused_sources_are_left_out():
    assert [s["key"] for s in build_credits(MANIFEST, rows("uk_cofid"))["sources"]] == ["uk_cofid"]


def test_a_food_from_an_uncredited_source_stops_the_build():
    with pytest.raises(ValueError, match="ifct_2017"):
        build_credits(MANIFEST, rows("ifct_2017"))


def test_committed_credits_file_matches_the_current_data():
    # If this fails: run `uv run python -m fooddata.build` and commit frontend/src/sources/credits.json.
    assert CREDITS.read_text(encoding="utf-8") == render(current_credits(VALIDATED))


def test_foods_in_a_cuisine_the_app_has_not_enabled_are_not_credited_yet(monkeypatch):
    monkeypatch.setattr("app.core.vocabulary.CUISINES", ("indian",))                       # as if Mediterranean were not enabled
    from fooddata.credits import in_enabled_cuisines
    rows_ = [{"source": "usda_sr_legacy", "cuisines": "indian"}, {"source": "usda_sr_legacy", "cuisines": "mediterranean"},
             {"source": "uk_cofid", "cuisines": "indian;mediterranean"}, {"source": "uk_cofid"}]          # a missing value means Indian
    kept = in_enabled_cuisines(rows_)
    assert [r["source"] for r in kept] == ["usda_sr_legacy", "uk_cofid", "uk_cofid"]
    credits = build_credits(MANIFEST, kept)
    assert [(s["key"], s["foods"]) for s in credits["sources"]] == [("usda_sr_legacy", 1), ("uk_cofid", 2)]

import pytest

from app.calc.splits import BY_KEY, CATALOGUE, check_catalogue, fits_days, recommend_splits, split_by_key


def keys(days, level="beginner", goal="muscle_gain"):
    return [r.split.key for r in recommend_splits(days, level, goal)]


def test_the_catalogue_only_uses_known_muscles_and_patterns():
    assert check_catalogue() == []
    assert len(BY_KEY) == len(CATALOGUE)                       # keys are unique
    for split in CATALOGUE:
        assert split.key.endswith(str(split.training_days)) or split.key.startswith("full_body"), split.key


@pytest.mark.parametrize("days,expected", [
    (1, {"full_body_1"}),
    (2, {"full_body_2"}),
    (3, {"full_body_3", "ppl_3"}),
    (4, {"full_body_4", "upper_lower_4"}),
    (5, {"upper_lower_ppl_5", "bro_5"}),
    (6, {"ppl_6", "arnold_6"}),
    (7, {"ppl_6", "arnold_6"}),                                # six hard days plus one easy day
])
def test_which_splits_fit_each_number_of_days(days, expected):
    assert set(keys(days)) == expected


def test_beginners_get_full_body_first_and_are_warned_off_the_heavy_splits():
    three = recommend_splits(3, "beginner", "muscle_gain")
    assert [r.split.key for r in three] == ["full_body_3", "ppl_3"] and three[0].fit == "best"
    six = recommend_splits(6, "beginner", "muscle_gain")
    assert all(r.fit == "possible" for r in six)
    assert all("more training experience" in " ".join(r.cautions) for r in six)


def test_experienced_lifters_get_the_classic_splits_first():
    assert keys(4, "intermediate") == ["upper_lower_4", "full_body_4"]
    assert keys(5, "advanced")[0] == "upper_lower_ppl_5"
    assert keys(6, "advanced")[0] in ("ppl_6", "arnold_6")
    assert recommend_splits(4, "intermediate", "fat_loss")[0].fit == "best"


def test_twice_a_week_per_muscle_scores_higher_than_once():
    ranked = recommend_splits(5, "intermediate", "muscle_gain")
    assert [r.split.key for r in ranked] == ["upper_lower_ppl_5", "bro_5"]
    assert ranked[0].score == 3 and ranked[1].score == 1
    assert any("one session a week" in c for c in ranked[1].cautions)            # bro split for a muscle goal
    assert not any("one session a week" in c for c in recommend_splits(5, "intermediate", "general_fitness")[1].cautions)


def test_seven_days_means_six_training_days_and_one_recovery_day():
    rec = recommend_splits(7, "advanced", "muscle_gain")[0]
    assert rec.split.training_days == 6 and rec.recovery_days == 1
    assert any("recovery" in r for r in rec.reasons) and any("walking or stretching" in c for c in rec.cautions)
    assert recommend_splits(6, "advanced", "muscle_gain")[0].recovery_days == 0


def test_every_result_has_a_reason_and_a_schedule_of_the_right_length():
    for days in range(1, 8):
        for level in ("beginner", "intermediate", "advanced"):
            for rec in recommend_splits(days, level, "recomp"):
                assert rec.reasons and len(rec.split.days) == rec.split.training_days
                assert rec.fit in ("best", "good", "possible") and 0 <= rec.score <= 3


def test_only_the_top_scoring_splits_are_called_best():
    for days in range(1, 8):
        recs = recommend_splits(days, "intermediate", "muscle_gain")
        top = max(r.score for r in recs)
        assert all((r.fit == "best") == (r.score == top and top >= 2) for r in recs), days


@pytest.mark.parametrize("bad", [0, 8, -1, 3.5, 4.0, True, "3", None])
def test_days_outside_one_to_seven_or_not_whole_are_refused_with_a_clear_error(bad):
    with pytest.raises(ValueError, match="whole number"):
        recommend_splits(bad, "beginner", "fat_loss")


@pytest.mark.parametrize("key,days,expected", [
    ("upper_lower_4", 4, True), ("upper_lower_4", 5, False), ("ppl_6", 6, True), ("ppl_6", 7, True),
    ("full_body_3", 3, True), ("full_body_3", 4, False), ("bro_7", 4, False), ("", 4, False),
])
def test_a_split_fits_only_its_own_number_of_days(key, days, expected):
    assert fits_days(key, days) is expected


def test_unknown_level_and_split_key_are_refused():
    with pytest.raises(ValueError):
        recommend_splits(3, "pro", "fat_loss")
    with pytest.raises(ValueError):
        split_by_key("bro_7")
    assert split_by_key("arnold_6").training_days == 6
